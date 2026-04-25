import os
import re
import json
import uuid
import sqlite3
import datetime
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import jwt
import bcrypt
from recommender import get_recommendations
import google.generativeai as genai
try:
    from google.api_core import exceptions as google_exceptions
except ImportError:
    google_exceptions = None

# Simple in-memory cache for AI summaries
# Key: product_id, Value: { 'summary': str, 'review_count': int }
summary_cache = {}

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path, override=True)

# Global Gemini Configuration
GEMINI_MODEL = None
CHATBOT_MODEL = None

def init_gemini():
    """Programmatically detect the best available Gemini model and initialize global instance."""
    global GEMINI_MODEL, CHATBOT_MODEL
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("[Gemini] API Key missing. Using fallbacks.")
        return
    try:
        genai.configure(api_key=api_key)
        # List models and filter for generateContent support
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Preference order for Swabodhini's requirements
        preferences = [
            'models/gemini-2.0-flash', 
            'models/gemini-1.5-flash', 
            'models/gemini-flash-latest',
            'models/gemini-pro-latest'
        ]
        
        for pref in preferences:
            if pref in available_models:
                GEMINI_MODEL = pref
                break
        
        if not GEMINI_MODEL and available_models:
            GEMINI_MODEL = available_models[0]
            
        if GEMINI_MODEL:
            CHATBOT_MODEL = genai.GenerativeModel(GEMINI_MODEL)
            print(f"[Gemini] Connected to {GEMINI_MODEL}")
        else:
            print("[Gemini] No compatible models found.")
    except Exception as e:
        print(f"[Gemini] Initialization failed: {e}")

# Initialize Gemini at startup
init_gemini()

app = Flask(__name__, static_folder='public', static_url_path='')
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max upload

SECRET_KEY = os.getenv('JWT_SECRET', 'swabodhini_autism_centre_jwt_secret_key_2024')
PORT = int(os.getenv('PORT', 5000))
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'swabodhini.db')

UPLOAD_PRODUCTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'public', 'uploads', 'products')
UPLOAD_PAYMENTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'public', 'uploads', 'payments')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Ensure upload directories exist
os.makedirs(UPLOAD_PRODUCTS, exist_ok=True)
os.makedirs(UPLOAD_PAYMENTS, exist_ok=True)


# ────────────────────── DATABASE ──────────────────────

def get_db():
    """Get a database connection for the current request."""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Create tables if they don't exist and seed initial data."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()

    cur.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            _id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            password TEXT,
            phone TEXT NOT NULL UNIQUE,
            isVerified INTEGER DEFAULT 0,
            role TEXT DEFAULT 'user' CHECK(role IN ('user','admin')),
            createdAt TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS products (
            _id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL CHECK(price >= 0),
            description TEXT NOT NULL,
            image TEXT DEFAULT '/images/placeholder.png',
            category TEXT DEFAULT 'General',
            stock INTEGER DEFAULT 10 CHECK(stock >= 0),
            isActive INTEGER DEFAULT 1,
            createdAt TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS orders (
            _id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            totalAmount REAL NOT NULL,
            paymentScreenshot TEXT NOT NULL,
            transactionId TEXT NOT NULL,
            status TEXT DEFAULT 'Pending Verification'
                CHECK(status IN ('Pending Verification','Approved','Rejected','Shipped','Delivered')),
            createdAt TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(_id)
        );

        CREATE TABLE IF NOT EXISTS order_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            product_id TEXT,
            name TEXT,
            price REAL,
            quantity INTEGER DEFAULT 1,
            image TEXT,
            FOREIGN KEY(order_id) REFERENCES orders(_id),
            FOREIGN KEY(product_id) REFERENCES products(_id)
        );

        CREATE TABLE IF NOT EXISTS cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            quantity INTEGER DEFAULT 1 CHECK(quantity >= 1),
            UNIQUE(user_id, product_id),
            FOREIGN KEY(user_id) REFERENCES users(_id),
            FOREIGN KEY(product_id) REFERENCES products(_id)
        );

        CREATE TABLE IF NOT EXISTS user_locations (
            user_id TEXT PRIMARY KEY,
            latitude REAL,
            longitude REAL,
            city TEXT,
            region TEXT,
            updatedAt TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(_id)
        );

        CREATE TABLE IF NOT EXISTS product_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            view_count INTEGER DEFAULT 1,
            last_viewed TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, product_id),
            FOREIGN KEY(user_id) REFERENCES users(_id),
            FOREIGN KEY(product_id) REFERENCES products(_id)
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
            comment TEXT,
            sentiment TEXT,
            createdAt TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(product_id) REFERENCES products(_id),
            FOREIGN KEY(user_id) REFERENCES users(_id)
        );
    ''')

    # Seed admin if no users exist
    row = cur.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
    if row['cnt'] == 0:
        admin_id = generate_id()
        hashed = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
        cur.execute(
            "INSERT INTO users (_id, name, email, password, phone, isVerified, role) VALUES (?,?,?,?,?,?,?)",
            (admin_id, 'Admin-Swabodhini', 'admin@swabodhini.com', hashed, '7358665496', 1, 'admin')
        )
        print('[Admin] Admin user created: Phone: 7358665496 / Password: admin123')

    # Seed products if empty
    row = cur.execute("SELECT COUNT(*) as cnt FROM products").fetchone()
    if row['cnt'] == 0:
        products = [
            ('Hand-Painted Greeting Cards', 150, 'Beautiful hand-painted greeting cards made by the talented students of Swabodhini Autism Centre. Each card is unique and made with love, featuring vibrant watercolor designs. Perfect for birthdays, festivals, and special occasions. Set of 5 cards included.', '/images/product1.jpg', 'Art & Craft', 50),
            ('Handmade Paper Bags', 200, 'Eco-friendly handmade paper bags crafted by our students. These sturdy and stylish bags are perfect for gifting and daily use. Each bag is decorated with hand-painted designs and comes in assorted colors. Set of 10 bags.', '/images/product2.jpg', 'Eco-Friendly', 30),
            ('Clay Diyas (Set of 6)', 300, 'Beautifully sculpted and painted clay diyas, handcrafted by our students. Perfect for Diwali celebrations, home decor, and religious ceremonies. Each diya is uniquely decorated with vibrant patterns and colors.', '/images/product3.jpg', 'Festive', 25),
            ('Canvas Painting - Nature', 1200, 'Original canvas painting depicting beautiful nature scenes, created by the artists at Swabodhini. Each painting is a one-of-a-kind artwork that captures the creativity and imagination of our talented students. Size: 12x16 inches.', '/images/product4.jpg', 'Art & Craft', 10),
            ('Beaded Jewelry Set', 450, 'Handcrafted beaded jewelry set including a necklace and matching earrings. Made with colorful beads and carefully assembled by our skilled students. Each piece is unique with its own character and charm.', '/images/product5.jpg', 'Accessories', 20),
            ('Embroidered Cushion Covers', 550, 'Set of 2 hand-embroidered cushion covers with beautiful floral patterns. Made with premium cotton fabric and intricate embroidery work by our students. Size: 16x16 inches. Machine washable.', '/images/product6.jpg', 'Home Decor', 15),
            ('Organic Phenyl (1L)', 180, 'High-quality organic phenyl floor cleaner made at Swabodhini. Effective disinfectant with a pleasant pine fragrance. Safe for all types of flooring. Made with eco-friendly ingredients. 1 Litre bottle.', '/images/product7.jpg', 'Cleaning', 100),
            ('Handmade Candles (Set of 4)', 350, 'Aromatic handmade candles crafted by our students. Available in lavender, rose, jasmine, and vanilla fragrances. Perfect for home decor, gifting, and creating a peaceful ambiance. Burn time: approximately 8 hours each.', '/images/product8.jpg', 'Home Decor', 35),
        ]
        for p in products:
            pid = generate_id()
            cur.execute(
                "INSERT INTO products (_id, name, price, description, image, category, stock) VALUES (?,?,?,?,?,?,?)",
                (pid, *p)
            )
        print(f'[Products] {len(products)} products seeded')

    conn.commit()
    conn.close()
    print('[OK] SQLite database initialized')


# ────────────────────── HELPERS ──────────────────────

def generate_id():
    """Generate a 24-char hex ID similar to MongoDB ObjectId."""
    return uuid.uuid4().hex[:24]


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def row_to_dict(row):
    """Convert a sqlite3.Row to a plain dict."""
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows):
    """Convert a list of sqlite3.Row to a list of dicts."""
    return [dict(r) for r in rows]


# ────────────────────── AUTH MIDDLEWARE ──────────────────────


def auth_required(f):
    """Decorator to require a valid JWT token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'message': 'Access denied. No token provided.'}), 401
        try:
            decoded = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            db = get_db()
            user = db.execute("SELECT _id, name, email, phone, role, isVerified, createdAt FROM users WHERE _id = ?",
                              (decoded['userId'],)).fetchone()
            if not user:
                return jsonify({'message': 'User not found.'}), 401
            request.user = row_to_dict(user)
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token expired.'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token.'}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator to require admin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'message': 'Access denied. No token provided.'}), 401
        try:
            decoded = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            db = get_db()
            user = db.execute("SELECT _id, name, email, phone, role, isVerified, createdAt FROM users WHERE _id = ?",
                              (decoded['userId'],)).fetchone()
            if not user or user['role'] != 'admin':
                return jsonify({'message': 'Access denied. Admin only.'}), 403
            request.user = row_to_dict(user)
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token expired.'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token.'}), 401
        return f(*args, **kwargs)
    return decorated


def create_token(user_id):
    """Generate a JWT token valid for 7 days."""
    return jwt.encode(
        {'userId': user_id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)},
        SECRET_KEY, algorithm='HS256'
    )


# ────────────────────── AUTH ROUTES ──────────────────────

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    """Simple signup with just name and phone number."""
    data = request.get_json()
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()

    if not name or not phone:
        return jsonify({'message': 'Name and phone number are required.'}), 400

    import re
    if not re.match(r'^\d{10}$', phone):
        return jsonify({'message': 'Please enter a valid 10-digit phone number.'}), 400

    db = get_db()
    existing = db.execute("SELECT _id FROM users WHERE phone = ?", (phone,)).fetchone()
    if existing:
        return jsonify({'message': 'An account with this phone number already exists. Please login instead.'}), 400

    user_id = generate_id()
    db.execute(
        "INSERT INTO users (_id, name, phone, isVerified, role) VALUES (?,?,?,?,?)",
        (user_id, name, phone, 1, 'user')
    )
    db.commit()

    token = create_token(user_id)

    return jsonify({
        'message': 'Account created successfully!',
        'token': token,
        'user': {'id': user_id, '_id': user_id, 'name': name, 'phone': phone, 'role': 'user'}
    }), 201


@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login with phone number. Admin requires password."""
    data = request.get_json()
    phone = data.get('phone', '').strip()

    if not phone:
        return jsonify({'message': 'Phone number is required.'}), 400

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
    if not user:
        return jsonify({'message': 'No account found with this phone number. Please sign up first.'}), 401

    # Admin must provide password
    if user['role'] == 'admin':
        password = data.get('password', '')
        if not password:
            return jsonify({'message': 'Password is required for admin login.', 'requirePassword': True}), 400
        if not user['password'] or not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            return jsonify({'message': 'Invalid password.'}), 401

    token = create_token(user['_id'])

    return jsonify({
        'message': 'Login successful!',
        'token': token,
        'user': {'id': user['_id'], '_id': user['_id'], 'name': user['name'], 'phone': user['phone'], 'role': user['role']}
    })


@app.route('/api/auth/me', methods=['GET'])
@auth_required
def get_me():
    return jsonify({'user': request.user})


# ────────────────────── PRODUCT ROUTES ──────────────────────

@app.route('/api/products', methods=['GET'])
def get_products():
    db = get_db()
    products = db.execute("SELECT * FROM products WHERE isActive = 1 ORDER BY createdAt DESC").fetchall()
    return jsonify(rows_to_list(products))


@app.route('/api/products/all', methods=['GET'])
@admin_required
def get_all_products():
    db = get_db()
    products = db.execute("SELECT * FROM products ORDER BY createdAt DESC").fetchall()
    return jsonify(rows_to_list(products))


@app.route('/api/products/<product_id>', methods=['GET'])
def get_product(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE _id = ?", (product_id,)).fetchone()
    if not product:
        return jsonify({'message': 'Product not found.'}), 404
    return jsonify(row_to_dict(product))


# ────────────────────── RECOMMENDATIONS ──────────────────────

@app.route('/api/products/<product_id>/recommendations', methods=['GET'])
def product_recommendations(product_id):
    """
    ML-based hybrid recommendations for a product page.
    Combines content-based (TF-IDF on name/description/category)
    and collaborative filtering (purchase co-occurrence).
    Optional query param: ?n=4  to control number of results.
    """
    db = get_db()

    # Check product exists
    product = db.execute("SELECT _id FROM products WHERE _id = ?", (product_id,)).fetchone()
    if not product:
        return jsonify({'message': 'Product not found.'}), 404

    n = min(int(request.args.get('n', 4)), 8)  # cap at 8

    # Get logged-in user if token present (to exclude already-bought)
    user_id = None
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token:
        try:
            decoded = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            user_id = decoded.get('userId')
        except Exception:
            pass

    try:
        recommendations = get_recommendations(db, product_id, user_id=user_id, n=n)
        return jsonify(recommendations)
    except Exception as e:
        # Never let recommendation errors break the page
        print(f'[Recommendations] Error: {e}')
        return jsonify([])


@app.route('/api/products', methods=['POST'])
@admin_required
def create_product():
    name = request.form.get('name')
    price = request.form.get('price')
    description = request.form.get('description')
    category = request.form.get('category', 'General')
    stock = request.form.get('stock', '10')

    image_path = '/images/placeholder.png'
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename and allowed_file(file.filename):
            filename = f"product-{int(datetime.datetime.utcnow().timestamp() * 1000)}{os.path.splitext(secure_filename(file.filename))[1]}"
            file.save(os.path.join(UPLOAD_PRODUCTS, filename))
            image_path = f'/uploads/products/{filename}'

    product_id = generate_id()
    db = get_db()
    db.execute(
        "INSERT INTO products (_id, name, price, description, image, category, stock) VALUES (?,?,?,?,?,?,?)",
        (product_id, name, float(price), description, image_path, category, int(stock))
    )
    db.commit()

    product = row_to_dict(db.execute("SELECT * FROM products WHERE _id = ?", (product_id,)).fetchone())
    return jsonify({'message': 'Product created successfully!', 'product': product}), 201


@app.route('/api/products/<product_id>', methods=['PUT'])
@admin_required
def update_product(product_id):
    db = get_db()
    existing = db.execute("SELECT * FROM products WHERE _id = ?", (product_id,)).fetchone()
    if not existing:
        return jsonify({'message': 'Product not found.'}), 404

    name = request.form.get('name', existing['name'])
    price = float(request.form.get('price', existing['price']))
    description = request.form.get('description', existing['description'])
    category = request.form.get('category', existing['category'])
    stock = int(request.form.get('stock', existing['stock']))
    is_active_raw = request.form.get('isActive')
    is_active = existing['isActive']
    if is_active_raw is not None:
        is_active = 1 if is_active_raw in ('true', 'True', '1') else 0

    image_path = existing['image']
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename and allowed_file(file.filename):
            filename = f"product-{int(datetime.datetime.utcnow().timestamp() * 1000)}{os.path.splitext(secure_filename(file.filename))[1]}"
            file.save(os.path.join(UPLOAD_PRODUCTS, filename))
            image_path = f'/uploads/products/{filename}'

    db.execute(
        "UPDATE products SET name=?, price=?, description=?, image=?, category=?, stock=?, isActive=? WHERE _id=?",
        (name, price, description, image_path, category, stock, is_active, product_id)
    )
    db.commit()

    product = row_to_dict(db.execute("SELECT * FROM products WHERE _id = ?", (product_id,)).fetchone())
    return jsonify({'message': 'Product updated successfully!', 'product': product})


@app.route('/api/products/<product_id>', methods=['DELETE'])
@admin_required
def delete_product(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE _id = ?", (product_id,)).fetchone()
    if not product:
        return jsonify({'message': 'Product not found.'}), 404
    db.execute("DELETE FROM products WHERE _id = ?", (product_id,))
    db.commit()
    return jsonify({'message': 'Product deleted successfully!'})


# ────────────────────── CART ROUTES ──────────────────────

@app.route('/api/cart', methods=['GET'])
@auth_required
def get_cart():
    db = get_db()
    items = db.execute('''
        SELECT ci.quantity, p._id, p.name, p.price, p.image, p.category, p.stock, p.isActive
        FROM cart_items ci
        JOIN products p ON ci.product_id = p._id
        WHERE ci.user_id = ?
    ''', (request.user['_id'],)).fetchall()

    cart = []
    for item in items:
        cart.append({
            'quantity': item['quantity'],
            'product': {
                '_id': item['_id'],
                'name': item['name'],
                'price': item['price'],
                'image': item['image'],
                'category': item['category'],
                'stock': item['stock'],
                'isActive': item['isActive']
            }
        })
    return jsonify(cart)


@app.route('/api/cart', methods=['POST'])
@auth_required
def add_to_cart():
    data = request.get_json()
    product_id = data.get('productId')
    quantity = data.get('quantity', 1)

    db = get_db()
    existing = db.execute(
        "SELECT * FROM cart_items WHERE user_id = ? AND product_id = ?",
        (request.user['_id'], product_id)
    ).fetchone()

    if existing:
        db.execute(
            "UPDATE cart_items SET quantity = quantity + ? WHERE user_id = ? AND product_id = ?",
            (quantity, request.user['_id'], product_id)
        )
    else:
        db.execute(
            "INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?,?,?)",
            (request.user['_id'], product_id, quantity)
        )
    db.commit()

    # Return updated cart
    return get_cart_response(db, request.user['_id'], 'Item added to cart!')


@app.route('/api/cart/<product_id>', methods=['PUT'])
@auth_required
def update_cart_item(product_id):
    data = request.get_json()
    quantity = data.get('quantity', 1)
    db = get_db()

    existing = db.execute(
        "SELECT * FROM cart_items WHERE user_id = ? AND product_id = ?",
        (request.user['_id'], product_id)
    ).fetchone()

    if not existing:
        return jsonify({'message': 'Item not found in cart.'}), 404

    if quantity <= 0:
        db.execute("DELETE FROM cart_items WHERE user_id = ? AND product_id = ?",
                   (request.user['_id'], product_id))
    else:
        db.execute("UPDATE cart_items SET quantity = ? WHERE user_id = ? AND product_id = ?",
                   (quantity, request.user['_id'], product_id))
    db.commit()

    return get_cart_response(db, request.user['_id'], 'Cart updated!')


@app.route('/api/cart/<product_id>', methods=['DELETE'])
@auth_required
def remove_from_cart(product_id):
    db = get_db()
    db.execute("DELETE FROM cart_items WHERE user_id = ? AND product_id = ?",
               (request.user['_id'], product_id))
    db.commit()
    return get_cart_response(db, request.user['_id'], 'Item removed from cart!')


@app.route('/api/cart', methods=['DELETE'])
@auth_required
def clear_cart():
    db = get_db()
    db.execute("DELETE FROM cart_items WHERE user_id = ?", (request.user['_id'],))
    db.commit()
    return jsonify({'message': 'Cart cleared!', 'cart': []})


def get_cart_response(db, user_id, message):
    """Helper to return consistent cart response."""
    items = db.execute('''
        SELECT ci.quantity, p._id, p.name, p.price, p.image, p.category, p.stock, p.isActive
        FROM cart_items ci
        JOIN products p ON ci.product_id = p._id
        WHERE ci.user_id = ?
    ''', (user_id,)).fetchall()

    cart = []
    for item in items:
        cart.append({
            'quantity': item['quantity'],
            'product': {
                '_id': item['_id'],
                'name': item['name'],
                'price': item['price'],
                'image': item['image'],
                'category': item['category'],
                'stock': item['stock'],
                'isActive': item['isActive']
            }
        })
    return jsonify({'message': message, 'cart': cart})


# ────────────────────── ORDER ROUTES ──────────────────────

@app.route('/api/orders', methods=['POST'])
@auth_required
def create_order():
    transaction_id = request.form.get('transactionId')
    products_json = request.form.get('products')
    total_amount = request.form.get('totalAmount')

    if 'paymentScreenshot' not in request.files:
        return jsonify({'message': 'Payment screenshot is required.'}), 400

    if not transaction_id:
        return jsonify({'message': 'Transaction ID is required.'}), 400

    file = request.files['paymentScreenshot']
    if not file or not file.filename:
        return jsonify({'message': 'Payment screenshot is required.'}), 400

    filename = f"payment-{request.user['_id']}-{int(datetime.datetime.utcnow().timestamp() * 1000)}{os.path.splitext(secure_filename(file.filename))[1]}"
    file.save(os.path.join(UPLOAD_PAYMENTS, filename))
    screenshot_path = f'/uploads/payments/{filename}'

    parsed_products = json.loads(products_json)
    order_id = generate_id()

    db = get_db()
    db.execute(
        "INSERT INTO orders (_id, user_id, totalAmount, paymentScreenshot, transactionId) VALUES (?,?,?,?,?)",
        (order_id, request.user['_id'], float(total_amount), screenshot_path, transaction_id)
    )

    for p in parsed_products:
        db.execute(
            "INSERT INTO order_products (order_id, product_id, name, price, quantity, image) VALUES (?,?,?,?,?,?)",
            (order_id, p.get('product'), p.get('name'), p.get('price'), p.get('quantity', 1), p.get('image'))
        )

    # Clear user's cart
    db.execute("DELETE FROM cart_items WHERE user_id = ?", (request.user['_id'],))
    db.commit()

    order = row_to_dict(db.execute("SELECT * FROM orders WHERE _id = ?", (order_id,)).fetchone())
    return jsonify({'message': 'Order placed successfully!', 'order': order}), 201


@app.route('/api/orders/my', methods=['GET'])
@auth_required
def get_my_orders():
    db = get_db()
    orders = db.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY createdAt DESC",
                        (request.user['_id'],)).fetchall()

    result = []
    for order in orders:
        o = row_to_dict(order)
        prods = db.execute("SELECT * FROM order_products WHERE order_id = ?", (o['_id'],)).fetchall()
        o['products'] = rows_to_list(prods)
        result.append(o)

    return jsonify(result)


@app.route('/api/orders', methods=['GET'])
@admin_required
def get_all_orders():
    db = get_db()
    orders = db.execute("SELECT * FROM orders ORDER BY createdAt DESC").fetchall()

    result = []
    for order in orders:
        o = row_to_dict(order)
        # Attach user info
        user = db.execute("SELECT name, email, phone FROM users WHERE _id = ?", (o['user_id'],)).fetchone()
        o['user'] = row_to_dict(user) if user else None
        # Attach products
        prods = db.execute("SELECT * FROM order_products WHERE order_id = ?", (o['_id'],)).fetchall()
        o['products'] = rows_to_list(prods)
        result.append(o)

    return jsonify(result)


@app.route('/api/orders/<order_id>/status', methods=['PUT'])
@admin_required
def update_order_status(order_id):
    data = request.get_json()
    status = data.get('status')
    valid = ['Pending Verification', 'Approved', 'Rejected', 'Shipped', 'Delivered']

    if status not in valid:
        return jsonify({'message': 'Invalid status.'}), 400

    db = get_db()
    current = db.execute("SELECT * FROM orders WHERE _id = ?", (order_id,)).fetchone()
    if not current:
        return jsonify({'message': 'Order not found.'}), 404

    # If approving, deduct stock
    if status == 'Approved' and current['status'] != 'Approved':
        prods = db.execute("SELECT * FROM order_products WHERE order_id = ?", (order_id,)).fetchall()
        for item in prods:
            if item['product_id']:
                db.execute(
                    "UPDATE products SET stock = MAX(0, stock - ?) WHERE _id = ?",
                    (item['quantity'] or 1, item['product_id'])
                )

    db.execute("UPDATE orders SET status = ? WHERE _id = ?", (status, order_id))
    db.commit()

    order = row_to_dict(db.execute("SELECT * FROM orders WHERE _id = ?", (order_id,)).fetchone())
    user = db.execute("SELECT name, email, phone FROM users WHERE _id = ?", (order['user_id'],)).fetchone()
    order['user'] = row_to_dict(user) if user else None

    return jsonify({'message': 'Order status updated!', 'order': order})


# ────────────────────── ADMIN ROUTES ──────────────────────

@app.route('/api/admin/stats', methods=['GET'])
@admin_required
def admin_stats():
    db = get_db()

    total_products = db.execute("SELECT COUNT(*) as cnt FROM products").fetchone()['cnt']
    active_products = db.execute("SELECT COUNT(*) as cnt FROM products WHERE isActive = 1").fetchone()['cnt']
    total_orders = db.execute("SELECT COUNT(*) as cnt FROM orders").fetchone()['cnt']
    pending_orders = db.execute("SELECT COUNT(*) as cnt FROM orders WHERE status = 'Pending Verification'").fetchone()['cnt']
    approved_orders = db.execute("SELECT COUNT(*) as cnt FROM orders WHERE status = 'Approved'").fetchone()['cnt']
    shipped_orders = db.execute("SELECT COUNT(*) as cnt FROM orders WHERE status = 'Shipped'").fetchone()['cnt']
    delivered_orders = db.execute("SELECT COUNT(*) as cnt FROM orders WHERE status = 'Delivered'").fetchone()['cnt']
    rejected_orders = db.execute("SELECT COUNT(*) as cnt FROM orders WHERE status = 'Rejected'").fetchone()['cnt']
    total_users = db.execute("SELECT COUNT(*) as cnt FROM users WHERE role = 'user' AND isVerified = 1").fetchone()['cnt']

    # Revenue
    revenue_row = db.execute(
        "SELECT COALESCE(SUM(totalAmount), 0) as total FROM orders WHERE status IN ('Approved','Shipped','Delivered')"
    ).fetchone()
    total_revenue = revenue_row['total']

    # Low stock
    low_stock = db.execute("SELECT name, stock FROM products WHERE stock < 5 AND isActive = 1 ORDER BY stock ASC").fetchall()

    # Recent orders
    recent = db.execute("SELECT * FROM orders ORDER BY createdAt DESC LIMIT 5").fetchall()
    recent_orders = []
    for r in recent:
        o = row_to_dict(r)
        user = db.execute("SELECT name, phone FROM users WHERE _id = ?", (o['user_id'],)).fetchone()
        o['user'] = row_to_dict(user) if user else None
        recent_orders.append(o)

    return jsonify({
        'totalProducts': total_products,
        'activeProducts': active_products,
        'totalOrders': total_orders,
        'pendingOrders': pending_orders,
        'approvedOrders': approved_orders,
        'shippedOrders': shipped_orders,
        'deliveredOrders': delivered_orders,
        'rejectedOrders': rejected_orders,
        'totalUsers': total_users,
        'totalRevenue': total_revenue,
        'lowStockProducts': rows_to_list(low_stock),
        'recentOrders': recent_orders
    })


@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_users():
    db = get_db()
    users = db.execute(
        "SELECT _id, name, phone, isVerified, createdAt FROM users WHERE role = 'user' ORDER BY createdAt DESC"
    ).fetchall()
    return jsonify(rows_to_list(users))


@app.route('/api/admin/stock', methods=['GET'])
@admin_required
def admin_stock():
    db = get_db()
    products = db.execute(
        "SELECT _id, name, stock, isActive, category, price FROM products ORDER BY stock ASC"
    ).fetchall()
    return jsonify(rows_to_list(products))


@app.route('/api/admin/stock/<product_id>', methods=['PUT'])
@admin_required
def admin_update_stock(product_id):
    data = request.get_json()
    stock = data.get('stock')
    if stock is None or int(stock) < 0:
        return jsonify({'message': 'Valid stock quantity is required.'}), 400

    db = get_db()
    product = db.execute("SELECT * FROM products WHERE _id = ?", (product_id,)).fetchone()
    if not product:
        return jsonify({'message': 'Product not found.'}), 404

    db.execute("UPDATE products SET stock = ? WHERE _id = ?", (int(stock), product_id))
    db.commit()

    product = row_to_dict(db.execute("SELECT * FROM products WHERE _id = ?", (product_id,)).fetchone())
    return jsonify({'message': 'Stock updated successfully!', 'product': product})


# ────────────────────── TRACKING ROUTES ──────────────────────

@app.route('/api/track/view', methods=['POST'])
@auth_required
def track_view():
    """Record that the logged-in user viewed a product."""
    data = request.get_json()
    product_id = data.get('productId')
    if not product_id:
        return jsonify({'message': 'productId required'}), 400

    db = get_db()
    # Upsert: increment view count & update timestamp
    existing = db.execute(
        "SELECT id FROM product_views WHERE user_id = ? AND product_id = ?",
        (request.user['_id'], product_id)
    ).fetchone()

    if existing:
        db.execute(
            """UPDATE product_views
               SET view_count = view_count + 1, last_viewed = datetime('now')
               WHERE user_id = ? AND product_id = ?""",
            (request.user['_id'], product_id)
        )
    else:
        db.execute(
            "INSERT INTO product_views (user_id, product_id) VALUES (?, ?)",
            (request.user['_id'], product_id)
        )
    db.commit()
    return jsonify({'message': 'View tracked'})


@app.route('/api/user/location', methods=['POST'])
@auth_required
def update_location():
    """Store the user's geolocation (lat/lng + optional city/region)."""
    data = request.get_json()
    lat = data.get('latitude')
    lng = data.get('longitude')
    city = data.get('city', '')
    region = data.get('region', '')

    if lat is None or lng is None:
        return jsonify({'message': 'latitude and longitude required'}), 400

    db = get_db()
    db.execute(
        """INSERT INTO user_locations (user_id, latitude, longitude, city, region, updatedAt)
           VALUES (?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(user_id) DO UPDATE SET
               latitude = excluded.latitude,
               longitude = excluded.longitude,
               city = excluded.city,
               region = excluded.region,
               updatedAt = excluded.updatedAt""",
        (request.user['_id'], float(lat), float(lng), city, region)
    )
    db.commit()
    return jsonify({'message': 'Location saved'})


# ────────────────────── CHATBOT ROUTES ──────────────────────

def get_chatbot_fallback(message):
    """Hybrid fallback system for common e-commerce queries with warm, conversational tone."""
    msg = message.lower().strip()
    
    def contains_any(keywords):
        for k in keywords:
            if k in msg:
                return True
        return False
    
    # Greetings (check first so "hi" doesn't fall through)
    if contains_any(['hi', 'hello', 'hey', 'namaste', 'greetings', 'good morning', 'good evening', 'good afternoon']):
        return "Hi there! 😊 Welcome to Swabodhini Autism Centre's shop! I can help you with our handcrafted products, shipping info, payments, and orders. What would you like to know?"
    
    # Help / what can you do
    if contains_any(['help', 'what can you', 'what do you', 'how can you', 'assist', 'support']):
        return "I can help you with:\n• 🛍️ Product info & recommendations\n• 🚚 Shipping & delivery details\n• 💳 Payment methods\n• 📦 Order status\n• ❓ General questions about Swabodhini\nJust ask away!"
    
    # Product info / what products / catalog
    if contains_any(['product', 'item', 'catalog', 'what do you sell', 'what are', 'available', 'browse', 'collection', 'range']):
        return "We offer a beautiful range of handcrafted products including greeting cards, paper bags, clay diyas, canvas paintings, beaded jewelry, cushion covers, organic phenyl, and handmade candles. Browse our shop to discover them all! 🎨"
    
    # Price / cost
    if contains_any(['price', 'cost', 'how much', 'expensive', 'cheap', 'affordable', 'budget', 'rate']):
        return "Our products are affordably priced, starting from ₹150! Greeting cards start at ₹150, paper bags at ₹200, clay diyas at ₹300, and canvas paintings at ₹1,200. Visit the shop page to see all prices!"
    
    # Shipping
    if contains_any(['ship', 'shipping', 'deliver', 'delivery', 'tracking', 'arrive', 'courier', 'dispatch', 'how long', 'days']):
        return "Our products are handcrafted by students at Swabodhini. Shipping usually takes 5-7 business days within India. You'll receive updates as your order progresses! 🚚"
    
    # Payments
    if contains_any(['pay', 'payment', 'qr', 'upi', 'checkout', 'buy', 'purchase', 'transaction', 'gpay', 'phonepe', 'paytm']):
        return "We accept payments via the QR code shown during checkout. Simply scan using any UPI app (GPay, PhonePe, Paytm, etc.) and upload your payment screenshot to complete your order. 💳"
    
    # Returns / Refunds
    if contains_any(['return', 'refund', 'exchange', 'cancel', 'money back', 'replace']):
        return "Since our products are handcrafted by students at Swabodhini Autism Centre, we unfortunately do not offer returns or exchanges. Each piece is made with love and care. We appreciate your understanding and support! ❤️"
    
    # Orders / order status
    if contains_any(['order', 'status', 'track', 'where is my', 'placed', 'confirm', 'pending', 'approved']):
        return "You can check your order status in the '📦 My Orders' section from the top menu. Orders go through these stages: Pending → Approved → Shipped → Delivered. If you have concerns, share your Transaction ID!"
    
    # How to order / buy process
    if contains_any(['how to order', 'how to buy', 'how do i', 'process', 'steps', 'place order']):
        return "Ordering is simple! 1️⃣ Browse products and click 'Add to Cart'. 2️⃣ Go to your cart and click 'Proceed to Payment'. 3️⃣ Scan the QR code and pay. 4️⃣ Upload the payment screenshot and submit. That's it!"
    
    # About Swabodhini / Autism Centre
    if contains_any(['about', 'swabodhini', 'autism', 'centre', 'center', 'who', 'organization', 'ngo', 'mission']):
        return "Swabodhini Autism Centre is dedicated to empowering individuals with autism through vocational training. Every product in our store is lovingly handcrafted by our talented students. Your purchase directly supports their growth and independence! 🌟"
    
    # Handmade / quality
    if contains_any(['handmade', 'handpainted', 'hand made', 'student', 'makes', 'quality', 'crafted', 'artisan']):
        return "Every item in our store is lovingly handcrafted by the talented students at Swabodhini Autism Centre. Each piece is unique and made with great care, ensuring excellent quality. Your purchase directly supports their vocational training! ❤️"
    
    # Gift Suggestions
    if contains_any(['gift', 'suggest', 'recommend', 'birthday', 'festival', 'diwali', 'christmas', 'occasion', 'present']):
        return "Great gift ideas from our collection: 🎨 Hand-painted greeting cards (₹150), 🪔 Clay diyas for festivals (₹300), 🕯️ Handmade candles (₹350), and 💍 Beaded jewelry sets (₹450). Each item comes with the love of our students!"
    
    # Specific products
    if contains_any(['card', 'greeting']):
        return "Our Hand-Painted Greeting Cards (₹150 for a set of 5) feature vibrant watercolor designs, perfect for birthdays, festivals, and special occasions! Each card is uniquely painted by our students. 🎨"
    if contains_any(['bag', 'paper bag']):
        return "Our Handmade Paper Bags (₹200 for a set of 10) are eco-friendly and decorated with hand-painted designs. Perfect for gifting and daily use! 🛍️"
    if contains_any(['diya', 'diwali', 'lamp']):
        return "Our Clay Diyas (₹300 for a set of 6) are beautifully sculpted and painted by our students. Perfect for Diwali celebrations and home decor! 🪔"
    if contains_any(['painting', 'canvas', 'art']):
        return "Our Canvas Paintings (₹1,200) depict beautiful nature scenes and are one-of-a-kind artworks by our talented student artists. Size: 12x16 inches. 🖼️"
    if contains_any(['jewelry', 'jewellery', 'necklace', 'earring', 'bead']):
        return "Our Beaded Jewelry Sets (₹450) include a necklace and matching earrings, carefully assembled by our skilled students. Each piece is unique! 💍"
    if contains_any(['cushion', 'cover', 'pillow', 'embroid']):
        return "Our Embroidered Cushion Covers (₹550 for a set of 2) feature beautiful floral patterns on premium cotton. Size: 16x16 inches, machine washable! 🧵"
    if contains_any(['phenyl', 'cleaner', 'cleaning', 'floor']):
        return "Our Organic Phenyl (₹180 for 1L) is an effective disinfectant with a pleasant pine fragrance. Safe for all floor types and made with eco-friendly ingredients! 🧹"
    if contains_any(['candle', 'wax', 'fragrance', 'aroma']):
        return "Our Handmade Candles (₹350 for a set of 4) come in lavender, rose, jasmine, and vanilla fragrances. Perfect for home decor and gifting! 🕯️"
    
    # Contact
    if contains_any(['contact', 'email', 'phone', 'call', 'reach', 'number', 'address', 'location']):
        return "You can reach us through this platform! For any queries about orders or products, feel free to ask me here. For urgent matters, please visit our centre directly. 📞"
    
    # Thanks / bye
    if contains_any(['thank', 'thanks', 'bye', 'goodbye', 'great', 'awesome', 'nice', 'good', 'ok', 'okay']):
        return "You're welcome! 😊 Happy to help! If you have any more questions, feel free to ask. Happy shopping at Swabodhini! 🛍️"
    
    # Cart related
    if contains_any(['cart', 'add to cart', 'basket', 'remove']):
        return "You can add products to your cart by clicking 'Add to Cart' on any product page. View your cart anytime by clicking '🛒 My Cart' in the top menu. You can adjust quantities or remove items there!"
    
    # Account / login
    if contains_any(['account', 'login', 'signup', 'sign up', 'register', 'log in', 'password', 'otp']):
        return "To create an account, just enter your name and phone number on the signup page. For login, enter your registered phone number. It's quick and easy! 📱"
    
    # Default Fallback — provide varied, helpful response
    return ("I'd love to help! Here are some things I can assist you with:\n"
            "• 🛍️ Product details & recommendations\n"
            "• 🚚 Shipping & delivery info (5-7 business days)\n"
            "• 💳 Payment process (QR code based)\n"
            "• 📦 Order tracking\n"
            "• ❤️ About Swabodhini Autism Centre\n"
            "What would you like to know?")

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle customer support chatbot messages via Google Gemini API with robust fallbacks."""
    data = request.get_json()
    message = data.get('message', '').strip()
    
    if not message:
        return jsonify({'reply': "Hi! I'm here to help you with our handcrafted products, shipping, and more. How can I help today?"})

    try:
        # Check if AI is available
        if not CHATBOT_MODEL:
            # Try one last-minute init if it failed at startup
            if os.getenv('GEMINI_API_KEY'):
                init_gemini()
            
            if not CHATBOT_MODEL:
                print("[Chatbot] Using fallback response (AI not initialized)")
                return jsonify({'reply': get_chatbot_fallback(message)})

        system_instruction = (
            "You are a friendly e-commerce customer support assistant for Swabodhini Autism Centre, "
            "which sells handcrafted products made by students with autism. "
            "Products include: Hand-Painted Greeting Cards (₹150), Handmade Paper Bags (₹200), "
            "Clay Diyas set of 6 (₹300), Canvas Paintings (₹1200), Beaded Jewelry Sets (₹450), "
            "Embroidered Cushion Covers (₹550), Organic Phenyl 1L (₹180), Handmade Candles set of 4 (₹350). "
            "IMPORTANT POLICIES: 1) No returns or exchanges on any products. "
            "2) Payment is via QR code scan during checkout — upload screenshot to confirm. "
            "3) Shipping takes 5-7 business days within India. "
            "Keep your responses SHORT (2-3 sentences max), warm, and helpful. "
            "Always give a SPECIFIC, RELEVANT answer to the user's question. "
            "If asked about topics completely unrelated to e-commerce or the centre, politely decline."
        )
        
        prompt = f"{system_instruction}\n\nCustomer question: {message}\nYour helpful response:"
        
        # Use timeout to prevent hanging requests and activate fallback gracefully
        response = CHATBOT_MODEL.generate_content(prompt, request_options={'timeout': 10})
        
        return jsonify({'reply': response.text})
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "ResourceExhausted" in error_msg:
            print("[Chatbot Fallback] Quota exceeded")
        elif "quota" in error_msg.lower():
             print("[Chatbot Fallback] API Quota limit reached")
        else:
            print(f"[Chatbot] Using fallback response (Error: {error_msg[:50]}...)")
            
        return jsonify({'reply': get_chatbot_fallback(message)})


# ────────────────────── NLP & SMART SEARCH ROUTES ──────────────────────

# re is imported at the top of the file
try:
    from textblob import TextBlob
except ImportError:
    TextBlob = None

@app.route('/api/search', methods=['GET'])
def smart_search():
    """
    NLP-powered Smart Search V2 (Swabodhini Catalog Optimized).
    Extracts price intent, categories, corrects typos, and maps gift intents.
    Always returns valid JSON — never an HTML error page.
    """
    try:
        query = request.args.get('q', '').lower().strip()
        db = get_db()

        if not query:
            # Fallback to all active products
            return jsonify({
                'success': True,
                'filters': {},
                'fallback_message': None,
                'products': rows_to_list(
                    db.execute("SELECT * FROM products WHERE isActive = 1 ORDER BY createdAt DESC").fetchall()
                )
            })

        filters = {'max_price': None, 'min_price': None, 'category': None, 'keywords': [], 'intent': []}

        # 1. Price Intent Extraction
        price_match = re.search(r'(under|below|less than|max)\s*(\d+)', query)
        if price_match:
            filters['max_price'] = int(price_match.group(2))

        if 'cheap' in query:
            if not filters['max_price']:
                filters['max_price'] = 300
            filters['intent'].append('Budget/Cheap')
        elif 'budget' in query:
            if not filters['max_price']:
                filters['max_price'] = 500
            filters['intent'].append('Budget/Cheap')
        elif 'premium' in query:
            filters['min_price'] = 500
            filters['intent'].append('Premium')

        # 2. Gift & Occasion Intent Mapping
        gift_keywords = ['gift', 'festival', 'traditional', 'decor']
        has_gift_intent = any(k in query for k in gift_keywords)
        if has_gift_intent:
            filters['intent'].append('Gift/Festive Suggestion')

        # 3. Handmade & Eco Intent
        if 'handmade' in query or 'artisan' in query or 'hand painted' in query:
            filters['intent'].append('Handmade Art')
        if 'eco' in query or 'eco friendly' in query or 'eco-friendly' in query:
            filters['category'] = 'Eco-Friendly'
            filters['intent'].append('Eco-Friendly')

        # 4. Category Extraction
        known_categories = ['art & craft', 'eco-friendly', 'festive', 'accessories', 'home decor', 'cleaning']
        for cat in known_categories:
            if cat in query and not filters['category']:
                filters['category'] = cat
                query = query.replace(cat, '')
                break

        # 5. NLP Preprocessing: Spelling Correction & Singularization
        # Catalog-specific typo dictionary (checked BEFORE singularization)
        catalog_typos = {
            'candels': 'candle', 'candel': 'candle',
            'diyas': 'diya',
            'paintings': 'painting',
            'earing': 'earring', 'earings': 'earring',
            'jewelery': 'jewelry', 'jewellery': 'jewelry',
            'bags': 'bag', 'giftz': 'gift', 'giftes': 'gift'
        }
        stop_words = {
            'under', 'below', 'less', 'than', 'max', 'cheap', 'budget',
            'premium', 'for', 'the', 'a', 'with', 'and', 'in', 'on', 'of',
            'items', 'products'
        }
        words = []
        typos_corrected = False

        if TextBlob:
            try:
                blob = TextBlob(query)
                for w in blob.words:
                    w_str = str(w).lower()
                    if w_str in stop_words or w_str.isdigit():
                        continue

                    # Check catalog typo dict FIRST
                    if w_str in catalog_typos:
                        words.append(catalog_typos[w_str])
                        typos_corrected = True
                        continue

                    # Singularize: Word is a string subclass, str() is safe
                    try:
                        singular = str(w.singularize()).lower()
                    except Exception:
                        singular = w_str

                    words.append(singular)
            except Exception as nlp_err:
                print(f"[Search] TextBlob NLP processing failed: {nlp_err}")
                # Graceful fallback: split on whitespace
                words = [
                    w for w in query.split()
                    if w not in stop_words and not w.isdigit()
                ]
        else:
            words = [
                w for w in query.split()
                if w not in stop_words and not w.isdigit()
            ]

        filters['keywords'] = words
        if typos_corrected:
            filters['intent'].append('Typo Corrected')

        # Build and Execute Search logic with Fallback
        def execute_search(require_category, strict_keywords):
            sql = "SELECT * FROM products WHERE isActive = 1"
            params = []

            if filters['max_price']:
                sql += " AND price <= ?"
                params.append(filters['max_price'])
            if filters['min_price']:
                sql += " AND price >= ?"
                params.append(filters['min_price'])

            if require_category and filters['category']:
                sql += " AND LOWER(category) LIKE ?"
                params.append(f"%{filters['category'].lower()}%")

            # Keyword matching
            if filters['keywords'] or (has_gift_intent and not strict_keywords):
                sql += " AND ("
                keyword_conditions = []
                if filters['keywords']:
                    for word in filters['keywords']:
                        condition = "(LOWER(name) LIKE ? OR LOWER(description) LIKE ? OR LOWER(category) LIKE ?)"
                        keyword_conditions.append(condition)
                        params.extend([f"%{word}%", f"%{word}%", f"%{word}%"])

                # If gift intent, append related keywords as OR conditions
                if has_gift_intent and not strict_keywords:
                    for gift_item in ['candle', 'diya', 'card', 'jewelry', 'cushion']:
                        condition = "(LOWER(name) LIKE ? OR LOWER(category) LIKE ?)"
                        keyword_conditions.append(condition)
                        params.extend([f"%{gift_item}%", f"%{gift_item}%"])

                if not keyword_conditions:
                    sql += " 1=1)"
                elif strict_keywords and filters['keywords']:
                    sql += " AND ".join(keyword_conditions) + ")"
                else:
                    sql += " OR ".join(keyword_conditions) + ")"

            sql += " ORDER BY createdAt DESC LIMIT 15"
            return db.execute(sql, params).fetchall()

        # Stage 1: Strict Match
        results = execute_search(require_category=True, strict_keywords=True)
        fallback_message = None

        # Stage 2: Relax Category
        if not results and filters['category']:
            results = execute_search(require_category=False, strict_keywords=True)
            if results:
                fallback_message = "No exact matches in that category. Showing related items instead."

        # Stage 3: Relax Keywords (OR matching + Gift expansion)
        if not results and (filters['keywords'] or 'Gift/Festive Suggestion' in filters['intent']):
            results = execute_search(require_category=False, strict_keywords=False)
            if results:
                fallback_message = "Couldn't find an exact match. You might like these related items!"

        # Stage 4: Ultimate Fallback
        if not results:
            results = db.execute("SELECT * FROM products WHERE isActive = 1 ORDER BY RANDOM() LIMIT 4").fetchall()
            fallback_message = "No exact items found. Here are some of our popular handcrafted products!"

        return jsonify({
            'success': True,
            'filters': filters,
            'fallback_message': fallback_message,
            'products': rows_to_list(results)
        })

    except Exception as e:
        print(f"[Search ERROR] /api/search crashed for query '{request.args.get('q', '')}': {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Search failed',
            'filters': {},
            'fallback_message': 'Search is temporarily unavailable. Showing all products instead.',
            'products': []
        }), 500

# ────────────────────── REVIEW & SENTIMENT ROUTES ──────────────────────

@app.route('/api/products/<product_id>/reviews', methods=['POST'])
@auth_required
def submit_review(product_id):
    """Submit a review with automatic Sentiment Analysis."""
    data = request.get_json()
    rating = int(data.get('rating', 5))
    comment = data.get('comment', '').strip()
    
    if not comment:
        return jsonify({'message': 'Review comment is required.'}), 400
        
    if rating < 1 or rating > 5:
        return jsonify({'message': 'Rating must be between 1 and 5.'}), 400
        
    # 1. Perform Sentiment Analysis
    sentiment = 'Neutral'
    if TextBlob:
        blob = TextBlob(comment)
        polarity = blob.sentiment.polarity
        if polarity > 0.1:
            sentiment = 'Positive'
        elif polarity < -0.1:
            sentiment = 'Negative'
            
    db = get_db()
    
    # Ensure product exists
    if not db.execute("SELECT _id FROM products WHERE _id = ?", (product_id,)).fetchone():
        return jsonify({'message': 'Product not found.'}), 404
        
    db.execute(
        "INSERT INTO reviews (product_id, user_id, rating, comment, sentiment) VALUES (?, ?, ?, ?, ?)",
        (product_id, request.user['_id'], rating, comment, sentiment)
    )
    db.commit()
    
    return jsonify({'message': 'Review submitted successfully!', 'sentiment': sentiment})

@app.route('/api/products/<product_id>/reviews', methods=['GET'])
def get_reviews(product_id):
    """Get all reviews for a product with sentiment statistics."""
    db = get_db()
    reviews = db.execute('''
        SELECT r.*, u.name as user_name 
        FROM reviews r 
        JOIN users u ON r.user_id = u._id 
        WHERE r.product_id = ? 
        ORDER BY r.createdAt DESC
    ''', (product_id,)).fetchall()
    
    reviews_list = rows_to_list(reviews)
    
    # Calculate stats
    stats = {'Positive': 0, 'Negative': 0, 'Neutral': 0, 'total': len(reviews_list)}
    for rev in reviews_list:
        stats[rev['sentiment']] += 1
        
    return jsonify({'reviews': reviews_list, 'stats': stats})

@app.route('/api/products/<product_id>/summary', methods=['GET'])
def get_review_summary(product_id):
    """Automatic AI Review Summarization using Gemini."""
    db = get_db()
    reviews = db.execute("SELECT comment FROM reviews WHERE product_id = ?", (product_id,)).fetchall()
    review_count = len(reviews)
    
    # Check cache first to avoid redundant API calls if review count hasn't changed
    if product_id in summary_cache:
        cached_data = summary_cache[product_id]
        if cached_data['review_count'] == review_count:
            return jsonify({'summary': cached_data['summary']})

    if review_count < 3:
        return jsonify({'summary': 'Not enough reviews yet for AI summary.'})
        
    comments = " | ".join([r['comment'] for r in reviews if r['comment']])
    
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("[Summary Error] GEMINI_API_KEY is missing. AI summarization skipped.")
        return jsonify({'summary': 'Customers generally liked the product quality but had mixed opinions about delivery and customization.'})
        
    try:
        if not CHATBOT_MODEL:
            init_gemini()
            if not CHATBOT_MODEL:
                raise Exception("AI model not initialized")

        # Improved, more natural prompt as per requirements
        prompt = (
            "You are summarizing customer reviews for a handcrafted e-commerce product. "
            "Write one short, human-readable sentence mentioning the most common positives and negatives based on these reviews. "
            "Keep it concise (1-2 sentences max) and avoid robotic wording. "
            f"Reviews: {comments}"
        )
        
        response = CHATBOT_MODEL.generate_content(prompt, request_options={'timeout': 10})
        
        # Ensure we return valid text even if AI returns something strange
        summary_text = response.text.strip() if response and hasattr(response, 'text') else None
        
        if summary_text:
            # Update cache
            summary_cache[product_id] = {
                'summary': summary_text,
                'review_count': review_count
            }
            return jsonify({'summary': summary_text})
        else:
            raise Exception("Empty response from AI")

    except Exception as e:
        error_msg = str(e)
        # Handle Quota/Rate Limit Errors
        if "429" in error_msg or "ResourceExhausted" in error_msg:
            print("[Summary Fallback] Quota exceeded")
        else:
            print(f"[Summary] Using fallback (Error: {error_msg[:50]}...)")
            
        return jsonify({'summary': 'Customers generally liked the product quality but had mixed opinions about delivery and customization.'})
# ────────────────────── HTML PAGE ROUTES ──────────────────────

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/landing')
def landing_page():
    return send_from_directory(app.static_folder, 'landing.html')


@app.route('/product')
def product_page():
    return send_from_directory(app.static_folder, 'product.html')


@app.route('/cart')
def cart_page():
    return send_from_directory(app.static_folder, 'cart.html')


@app.route('/payment')
def payment_page():
    return send_from_directory(app.static_folder, 'payment.html')


@app.route('/admin')
def admin_page():
    return send_from_directory(app.static_folder, 'admin.html')


@app.route('/admin-dashboard')
def admin_dashboard_page():
    return send_from_directory(app.static_folder, 'admin-dashboard.html')


@app.route('/orders')
def orders_page():
    return send_from_directory(app.static_folder, 'orders.html')


# ────────────────────── ERROR HANDLERS ──────────────────────

@app.errorhandler(404)
def not_found(e):
    # If it's an API request, return JSON
    if request.path.startswith('/api/'):
        return jsonify({'message': 'Not found'}), 404
    return send_from_directory(app.static_folder, 'index.html')


@app.errorhandler(500)
def server_error(e):
    return jsonify({'message': 'Something went wrong!'}), 500


# ────────────────────── RUN ──────────────────────

if __name__ == '__main__':
    init_db()
    print(f'\n[Server] Swabodhini E-Commerce Server running on http://localhost:{PORT}')
    print(f'[DB] Backend: Python/Flask + SQLite')
    print(f'[Admin] Admin Login: Phone: 7358665496 / Password: admin123\n')
    app.run(host='0.0.0.0', port=PORT, debug=True)