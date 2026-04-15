"""
recommender.py  –  Hybrid ML recommendations for Swabodhini E-Commerce
=======================================================================

Architecture
------------
  Signal 1 (40%) – SVD Collaborative Filtering   (scikit-surprise, trained model)
  Signal 2 (30%) – Content-Based Filtering        (TF-IDF cosine similarity)
  Signal 3 (15%) – Location Signal                (Haversine, 50 km radius)
  Signal 4 (15%) – View History                   (time-decayed view score)

The SVD model is loaded once from  svd_model.pkl  (produced by train_model.py).
If the model file is absent the system falls back to pure content-based scoring
so the app never breaks.

Run order
---------
  1. python seed_ml_data.py       # populate DB with synthetic interactions
  2. python train_model.py --eval # train SVD + print metrics
  3. python app.py                # serve – recommender auto-loads the model
"""

import math
import os
import pickle
import sqlite3
from collections import defaultdict

# ── Model path ───────────────────────────────────────────────────────────────
_BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
_MODEL_PATH = os.path.join(_BASE_DIR, 'svd_model.pkl')

# ── Lazy-load SVD model once per process ─────────────────────────────────────
_svd_model = None
_svd_loaded = False   # distinguish "not tried" from "tried + failed"


def _load_svd():
    global _svd_model, _svd_loaded
    if _svd_loaded:
        return _svd_model
    _svd_loaded = True
    if not os.path.exists(_MODEL_PATH):
        print("[recommender] svd_model.pkl not found – falling back to content-based only.")
        return None
    try:
        with open(_MODEL_PATH, "rb") as f:
            _svd_model = pickle.load(f)
        print("[recommender] SVD model loaded ✓")
    except Exception as e:
        print(f"[recommender] Could not load SVD model: {e}")
        _svd_model = None
    return _svd_model


# ─────────────────────────────────────────────────────────────────────────────
# Signal 1 – SVD Collaborative Filtering
# ─────────────────────────────────────────────────────────────────────────────

def _svd_scores(product_id, user_id, all_pids):
    """
    Use the trained SVD model to estimate ratings for all products
    from this user's perspective.  Returns dict {product_id: score [0,1]}.
    """
    algo = _load_svd()
    if algo is None or user_id is None:
        return {}

    raw = {}
    for pid in all_pids:
        if pid == product_id:
            continue
        try:
            pred = algo.predict(user_id, pid)
            raw[pid] = pred.est          # estimated rating in [1, 5]
        except Exception:
            pass

    if not raw:
        return {}

    min_r = min(raw.values())
    max_r = max(raw.values())
    span  = (max_r - min_r) or 1.0
    return {pid: (r - min_r) / span for pid, r in raw.items()}


# ─────────────────────────────────────────────────────────────────────────────
# Signal 2 – Content-Based Filtering (TF-IDF)
# ─────────────────────────────────────────────────────────────────────────────

def _tokenise(text):
    import re
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if len(t) > 2]


def _tfidf_vectors(documents):
    tokenised = [_tokenise(d) for d in documents]
    N  = len(tokenised)
    df = defaultdict(int)
    for tokens in tokenised:
        for t in set(tokens):
            df[t] += 1
    vectors = []
    for tokens in tokenised:
        tf = defaultdict(float)
        for t in tokens:
            tf[t] += 1
        total = len(tokens) or 1
        vec = {
            t: (cnt / total) * math.log(N / (df[t] + 1) + 1)
            for t, cnt in tf.items()
        }
        vectors.append(vec)
    return vectors


def _cosine(a, b):
    dot    = sum(a.get(t, 0.0) * v for t, v in b.items())
    norm_a = math.sqrt(sum(v * v for v in a.values())) or 1.0
    norm_b = math.sqrt(sum(v * v for v in b.values())) or 1.0
    return dot / (norm_a * norm_b)


def _content_scores(products, src_idx, src_category):
    corpus = [
        f"{p['name']} {p['description']} {p['category']} {p['category']}"
        for p in products
    ]
    tfidf   = _tfidf_vectors(corpus)
    src_vec = tfidf[src_idx]
    scores  = {}
    for i, p in enumerate(products):
        if i == src_idx:
            continue
        sim = _cosine(src_vec, tfidf[i])
        if p['category'] == src_category:
            sim = min(1.0, sim + 0.15)
        scores[p['_id']] = sim
    return scores


# ─────────────────────────────────────────────────────────────────────────────
# Signal 3 – Location (Haversine, 50 km)
# ─────────────────────────────────────────────────────────────────────────────

def _haversine_km(lat1, lon1, lat2, lon2):
    R    = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a    = (math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _location_scores(db, user_id, radius_km=50.0):
    loc = db.execute(
        "SELECT latitude, longitude FROM user_locations WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    if not loc or loc[0] is None:
        return {}

    user_lat, user_lon = loc[0], loc[1]
    neighbours = db.execute(
        "SELECT user_id, latitude, longitude FROM user_locations WHERE user_id != ?",
        (user_id,)
    ).fetchall()
    nearby_ids = [
        n[0] for n in neighbours
        if n[1] is not None and n[2] is not None
        and _haversine_km(user_lat, user_lon, n[1], n[2]) <= radius_km
    ]
    if not nearby_ids:
        return {}

    ph   = ','.join('?' * len(nearby_ids))
    rows = db.execute(f"""
        SELECT op.product_id, COUNT(*) as cnt
        FROM   order_products op
        JOIN   orders o ON o._id = op.order_id
        WHERE  o.user_id IN ({ph})
          AND  o.status IN ('Approved','Shipped','Delivered')
          AND  op.product_id IS NOT NULL
        GROUP  BY op.product_id
    """, nearby_ids).fetchall()
    if not rows:
        return {}

    max_cnt = max(r[1] for r in rows) or 1
    return {r[0]: r[1] / max_cnt for r in rows}


# ─────────────────────────────────────────────────────────────────────────────
# Signal 4 – View History (time-decayed)
# ─────────────────────────────────────────────────────────────────────────────

def _view_scores(db, user_id, bought_ids):
    rows = db.execute("""
        SELECT product_id, view_count,
               CAST((julianday('now') - julianday(last_viewed)) AS REAL) AS days_ago
        FROM   product_views
        WHERE  user_id = ?
    """, (user_id,)).fetchall()

    scores = {}
    for r in rows:
        pid = r[0]
        if pid in bought_ids:
            continue
        view_count = r[1] or 1
        days_ago   = max(r[2] or 0, 0)
        recency    = math.exp(-0.1 * days_ago)
        freq_boost = math.log(view_count + 1)
        scores[pid] = min(1.0, recency * freq_boost)

    if scores:
        max_v  = max(scores.values()) or 1.0
        scores = {pid: s / max_v for pid, s in scores.items()}
    return scores


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_recommendations(
    db,
    product_id,
    user_id=None,
    n=4,
    svd_weight=0.40,
    content_weight=0.30,
    location_weight=0.15,
    view_weight=0.15,
):
    """
    Return up to n recommended products (list of dicts).

    Signals
    -------
    svd       : SVD collaborative filtering (trained scikit-surprise model)
    content   : TF-IDF cosine similarity + category bonus
    location  : popularity among users within 50 km (Haversine)
    view      : time-decayed view history (not yet purchased)

    Any missing/empty signal has its weight redistributed to content-based,
    so the function always returns results if products exist.
    """
    all_products = db.execute(
        "SELECT * FROM products WHERE isActive = 1"
    ).fetchall()
    if len(all_products) < 2:
        return []

    products    = [dict(p) for p in all_products]
    pid_to_idx  = {p['_id']: i for i, p in enumerate(products)}
    all_pids    = [p['_id'] for p in products]

    if product_id not in pid_to_idx:
        return []

    src_idx = pid_to_idx[product_id]
    src     = products[src_idx]

    # Purchased products for this user (to exclude from results)
    bought_ids = set()
    if user_id:
        rows = db.execute("""
            SELECT DISTINCT op.product_id
            FROM   order_products op
            JOIN   orders o ON o._id = op.order_id
            WHERE  o.user_id = ?
              AND  o.status IN ('Approved','Shipped','Delivered')
        """, (user_id,)).fetchall()
        bought_ids = {r[0] for r in rows}

    # ── Compute all four signals ─────────────────────────────────────────────
    svd_sc   = _svd_scores(product_id, user_id, all_pids)
    cont_sc  = _content_scores(products, src_idx, src['category'])
    loc_sc   = _location_scores(db, user_id) if user_id else {}
    view_sc  = _view_scores(db, user_id, bought_ids) if user_id else {}

    # ── Blend with graceful fallback ─────────────────────────────────────────
    candidate_pids = {p['_id'] for p in products if p['_id'] != product_id}
    hybrid = {}

    for pid in candidate_pids:
        base = cont_sc.get(pid, 0.0)
        score = content_weight * base

        # SVD – fallback to content if model unavailable
        if svd_sc:
            score += svd_weight * svd_sc.get(pid, 0.0)
        else:
            score += svd_weight * base

        # Location – fallback to content if no geo data
        if loc_sc:
            score += location_weight * loc_sc.get(pid, 0.0)
        else:
            score += location_weight * base

        # View history – fallback to content if no view data
        if view_sc:
            score += view_weight * view_sc.get(pid, 0.0)
        else:
            score += view_weight * base

        hybrid[pid] = score

    # Exclude already-purchased products
    if bought_ids:
        hybrid = {pid: s for pid, s in hybrid.items() if pid not in bought_ids}

    ranked  = sorted(hybrid.items(), key=lambda x: x[1], reverse=True)[:n]
    pid_map = {p['_id']: p for p in products}
    return [pid_map[pid] for pid, _ in ranked if pid in pid_map]
