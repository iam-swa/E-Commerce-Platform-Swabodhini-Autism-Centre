import os
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

# Load environment variables
load_dotenv()

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
