"""
seed_ml_data.py  –  Populate the Swabodhini DB with realistic synthetic
                    users, orders, and product-views so the SVD model has
                    enough interaction data to train on.

Run once (safe to re-run – skips if data already exists):
    python seed_ml_data.py
"""

import sqlite3
import uuid
import random
import math
import os
import datetime
import bcrypt

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'swabodhini.db')

# Chennai coordinates (centre) – synthetic users placed around it
CENTRE_LAT, CENTRE_LON = 13.0827, 80.2707

SAMPLE_NAMES = [
    "Priya Rajan", "Arun Kumar", "Divya Menon", "Karthik Subramanian",
    "Meena Iyer", "Suresh Nair", "Anitha Krishnan", "Vijay Balasubramaniam",
    "Lakshmi Venkat", "Ramesh Pillai", "Deepa Natarajan", "Ganesh Murthy",
    "Saranya Selvam", "Manoj Chandrasekaran", "Pooja Srinivasan", "Dinesh Arumugam",
    "Kavitha Sundaram", "Balamurugan Raja", "Nithya Ramaswamy", "Senthil Kumar",
    "Revathi Gopal", "Harish Babu", "Vidya Shankar", "Muthukumar Pandian",
    "Asha Devi", "Rajesh Nadar", "Sujatha Varghese", "Aravind Loganathan",
    "Bharathi Ramamurthy", "Prakash Mohan",
]

# Category-based purchase affinity – users tend to buy within certain clusters
CATEGORY_CLUSTERS = {
    "art_lover":     ["Art & Craft", "Art & Craft", "Home Decor"],
    "eco_conscious": ["Eco-Friendly", "Cleaning", "Eco-Friendly"],
    "home_decor":    ["Home Decor", "Festive", "Art & Craft"],
    "gifting":       ["Art & Craft", "Festive", "Accessories", "Home Decor"],
    "general":       ["Art & Craft", "Eco-Friendly", "Festive", "Accessories",
                      "Home Decor", "Cleaning"],
}


def random_offset(radius_km=80):
    """Random lat/lon offset within radius_km of centre."""
    angle = random.uniform(0, 2 * math.pi)
    dist  = random.uniform(0, radius_km)
    dlat  = dist / 111.0
    dlon  = dist / (111.0 * math.cos(math.radians(CENTRE_LAT)))
    return (
        CENTRE_LAT + dlat * math.cos(angle),
        CENTRE_LON + dlon * math.sin(angle),
    )


def seed(db_path=DB_PATH, n_users=30, orders_per_user=(2, 6), views_per_user=(3, 10)):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()

    # ── Fetch existing products ──────────────────────────────────────────────
    products = cur.execute(
        "SELECT _id, category FROM products WHERE isActive = 1"
    ).fetchall()
    if not products:
        print("[seed] No products found – run the Flask app once first to init DB.")
        conn.close()
        return

    prod_ids = [p["_id"] for p in products]
    cat_map  = {p["_id"]: p["category"] for p in products}

    # ── Check existing synthetic users ───────────────────────────────────────
    existing = cur.execute(
        "SELECT COUNT(*) as cnt FROM users WHERE role='user'"
    ).fetchone()["cnt"]
    if existing >= n_users:
        print(f"[seed] {existing} synthetic users already present – skipping user creation.")
    else:
        needed = n_users - existing
        print(f"[seed] Creating {needed} synthetic users …")
        hashed_pw = bcrypt.hashpw(b"test1234", bcrypt.gensalt(10)).decode()

        for i in range(needed):
            uid   = str(uuid.uuid4())
            name  = random.choice(SAMPLE_NAMES)
            phone = f"9{random.randint(100000000, 999999999)}"
            email = f"user{existing+i+1}@swabodhini.test"
            lat, lon = random_offset()

            cur.execute(
                "INSERT OR IGNORE INTO users "
                "(_id, name, email, password, phone, isVerified, role) "
                "VALUES (?,?,?,?,?,1,'user')",
                (uid, name, email, hashed_pw, phone),
            )
            cur.execute(
                "INSERT OR REPLACE INTO user_locations "
                "(user_id, latitude, longitude, city, region) "
                "VALUES (?,?,?,'Chennai','Tamil Nadu')",
                (uid, lat, lon),
            )

    conn.commit()

    # ── Synthetic orders ─────────────────────────────────────────────────────
    users = cur.execute(
        "SELECT _id FROM users WHERE role='user'"
    ).fetchall()
    user_ids = [u["_id"] for u in users]

    existing_orders = cur.execute("SELECT COUNT(*) as cnt FROM orders").fetchone()["cnt"]
    if existing_orders >= len(user_ids) * 2:
        print(f"[seed] {existing_orders} orders already present – skipping order creation.")
    else:
        print(f"[seed] Creating synthetic orders …")
        cluster_names = list(CATEGORY_CLUSTERS.keys())
        statuses = ["Approved", "Shipped", "Delivered", "Delivered", "Delivered"]

        for uid in user_ids:
            cluster   = random.choice(cluster_names)
            fav_cats  = CATEGORY_CLUSTERS[cluster]
            n_orders  = random.randint(*orders_per_user)

            for _ in range(n_orders):
                oid    = str(uuid.uuid4())
                status = random.choice(statuses)
                total  = 0.0

                # 1–3 products per order, biased toward user's favourite categories
                basket_size = random.randint(1, 3)
                chosen = []
                for _ in range(basket_size):
                    fav_cat = random.choice(fav_cats)
                    cat_prods = [p for p in prod_ids if cat_map.get(p) == fav_cat]
                    pool = cat_prods if cat_prods else prod_ids
                    pid  = random.choice(pool)
                    if pid not in chosen:
                        chosen.append(pid)

                price_rows = cur.execute(
                    f"SELECT _id, name, price, image FROM products "
                    f"WHERE _id IN ({','.join('?'*len(chosen))})",
                    chosen,
                ).fetchall()

                days_ago = random.randint(1, 180)
                ts = (datetime.datetime.now() -
                      datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")

                for pr in price_rows:
                    total += pr["price"]

                cur.execute(
                    "INSERT OR IGNORE INTO orders "
                    "(_id, user_id, totalAmount, paymentScreenshot, transactionId, status, createdAt) "
                    "VALUES (?,?,?,'synthetic','synthetic_txn',?,?)",
                    (oid, uid, total, status, ts),
                )
                for pr in price_rows:
                    cur.execute(
                        "INSERT INTO order_products "
                        "(order_id, product_id, name, price, quantity, image) "
                        "VALUES (?,?,?,?,1,?)",
                        (oid, pr["_id"], pr["name"], pr["price"], pr["image"]),
                    )

    conn.commit()

    # ── Synthetic product views ──────────────────────────────────────────────
    existing_views = cur.execute("SELECT COUNT(*) as cnt FROM product_views").fetchone()["cnt"]
    if existing_views >= len(user_ids) * 3:
        print(f"[seed] {existing_views} views already present – skipping view creation.")
    else:
        print(f"[seed] Creating synthetic product views …")
        for uid in user_ids:
            n_views = random.randint(*views_per_user)
            viewed  = random.sample(prod_ids, min(n_views, len(prod_ids)))
            for pid in viewed:
                days_ago  = random.randint(0, 30)
                view_cnt  = random.randint(1, 8)
                last_view = (datetime.datetime.now() -
                             datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
                cur.execute(
                    "INSERT OR REPLACE INTO product_views "
                    "(user_id, product_id, view_count, last_viewed) VALUES (?,?,?,?)",
                    (uid, pid, view_cnt, last_view),
                )

    conn.commit()
    conn.close()

    total_orders = cur.execute if False else None   # just for print
    conn2 = sqlite3.connect(db_path)
    counts = {
        "users":  conn2.execute("SELECT COUNT(*) FROM users WHERE role='user'").fetchone()[0],
        "orders": conn2.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "views":  conn2.execute("SELECT COUNT(*) FROM product_views").fetchone()[0],
    }
    conn2.close()
    print(f"[seed] Done. DB now has: {counts['users']} users, "
          f"{counts['orders']} orders, {counts['views']} product views.")


if __name__ == "__main__":
    seed()
