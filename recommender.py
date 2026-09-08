"""
recommender.py  –  Hybrid ML recommendations for Swabodhini E-Commerce
=======================================================================

Architecture
------------
  Signal 1 (40%) – SVD Collaborative Filtering   (trained model if present)
  Signal 2 (30%) – Content-Based Filtering        (TF-IDF cosine similarity)
  Signal 3 (15%) – Location Signal                (Haversine, 50 km radius)
  Signal 4 (15%) – View History                   (time-decayed view score)

The SVD model is loaded once from svd_model.pkl (if present).
If the model file is absent or unsupported, the system falls back to pure content-based scoring
so the app never breaks.
"""

import math
import os
import pickle
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
    algo = _load_svd()
    if algo is None or user_id is None:
        return {}

    raw = {}
    for pid in all_pids:
        if pid == product_id:
            continue
        try:
            pred = algo.predict(user_id, pid)
            raw[pid] = pred.est
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
        f"{p.get('name', '')} {p.get('description', '')} {p.get('category', '')} {p.get('category', '')}"
        for p in products
    ]
    tfidf   = _tfidf_vectors(corpus)
    src_vec = tfidf[src_idx]
    scores  = {}
    for i, p in enumerate(products):
        if i == src_idx:
            continue
        sim = _cosine(src_vec, tfidf[i])
        if p.get('category') == src_category:
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
    try:
        cur = db.cursor()
        cur.execute("SELECT latitude, longitude FROM user_locations WHERE user_id = %s", (user_id,))
        loc = cur.fetchone()
        if not loc:
            return {}

        user_lat = loc['latitude'] if isinstance(loc, dict) else loc[0]
        user_lon = loc['longitude'] if isinstance(loc, dict) else loc[1]
        if user_lat is None or user_lon is None:
            return {}

        cur.execute("SELECT user_id, latitude, longitude FROM user_locations WHERE user_id != %s", (user_id,))
        neighbours = cur.fetchall()
        nearby_ids = []
        for n in neighbours:
            n_id  = n['user_id'] if isinstance(n, dict) else n[0]
            n_lat = n['latitude'] if isinstance(n, dict) else n[1]
            n_lon = n['longitude'] if isinstance(n, dict) else n[2]
            if n_lat is not None and n_lon is not None:
                if _haversine_km(user_lat, user_lon, n_lat, n_lon) <= radius_km:
                    nearby_ids.append(n_id)

        if not nearby_ids:
            return {}

        cur.execute("""
            SELECT op.product_id, COUNT(*) as cnt
            FROM   order_products op
            JOIN   orders o ON o._id = op.order_id
            WHERE  o.user_id = ANY(%s)
              AND  o.status IN ('Approved','Shipped','Delivered')
              AND  op.product_id IS NOT NULL
            GROUP  BY op.product_id
        """, (nearby_ids,))
        rows = cur.fetchall()
        if not rows:
            return {}

        scores = {}
        for r in rows:
            pid = r['product_id'] if isinstance(r, dict) else r[0]
            cnt = r['cnt'] if isinstance(r, dict) else r[1]
            scores[pid] = cnt

        max_cnt = max(scores.values()) or 1
        return {pid: cnt / max_cnt for pid, cnt in scores.items()}
    except Exception as e:
        print(f"[recommender location] Error: {e}")
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Signal 4 – View History (time-decayed)
# ─────────────────────────────────────────────────────────────────────────────

def _view_scores(db, user_id, bought_ids):
    try:
        cur = db.cursor()
        cur.execute("""
            SELECT product_id, view_count,
                   EXTRACT(EPOCH FROM (NOW() - last_viewed)) / 86400.0 AS days_ago
            FROM   product_views
            WHERE  user_id = %s
        """, (user_id,))
        rows = cur.fetchall()

        scores = {}
        for r in rows:
            pid = r['product_id'] if isinstance(r, dict) else r[0]
            if pid in bought_ids:
                continue
            view_count = (r['view_count'] if isinstance(r, dict) else r[1]) or 1
            days_ago   = max((r['days_ago'] if isinstance(r, dict) else r[2]) or 0, 0)
            recency    = math.exp(-0.1 * days_ago)
            freq_boost = math.log(view_count + 1)
            scores[pid] = min(1.0, recency * freq_boost)

        if scores:
            max_v  = max(scores.values()) or 1.0
            scores = {pid: s / max_v for pid, s in scores.items()}
        return scores
    except Exception as e:
        print(f"[recommender view] Error: {e}")
        return {}


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
    try:
        cur = db.cursor()
        cur.execute('SELECT * FROM products WHERE "isActive" = 1')
        all_products = cur.fetchall()
        if not all_products or len(all_products) < 2:
            return []

        products   = [dict(p) for p in all_products]
        pid_to_idx = {p['_id']: i for i, p in enumerate(products)}
        all_pids   = [p['_id'] for p in products]

        if product_id not in pid_to_idx:
            return []

        src_idx = pid_to_idx[product_id]
        src     = products[src_idx]

        bought_ids = set()
        if user_id:
            try:
                cur.execute("""
                    SELECT DISTINCT op.product_id
                    FROM   order_products op
                    JOIN   orders o ON o._id = op.order_id
                    WHERE  o.user_id = %s
                      AND  o.status IN ('Approved','Shipped','Delivered')
                """, (user_id,))
                rows = cur.fetchall()
                bought_ids = {r['product_id'] if isinstance(r, dict) else r[0] for r in rows}
            except Exception:
                pass

        svd_sc   = _svd_scores(product_id, user_id, all_pids)
        cont_sc  = _content_scores(products, src_idx, src.get('category', ''))
        loc_sc   = _location_scores(db, user_id) if user_id else {}
        view_sc  = _view_scores(db, user_id, bought_ids) if user_id else {}

        candidate_pids = {p['_id'] for p in products if p['_id'] != product_id}
        hybrid = {}

        for pid in candidate_pids:
            base = cont_sc.get(pid, 0.0)
            score = content_weight * base

            if svd_sc:
                score += svd_weight * svd_sc.get(pid, 0.0)
            else:
                score += svd_weight * base

            if loc_sc:
                score += location_weight * loc_sc.get(pid, 0.0)
            else:
                score += location_weight * base

            if view_sc:
                score += view_weight * view_sc.get(pid, 0.0)
            else:
                score += view_weight * base

            hybrid[pid] = score

        if bought_ids:
            hybrid = {pid: s for pid, s in hybrid.items() if pid not in bought_ids}

        ranked  = sorted(hybrid.items(), key=lambda x: x[1], reverse=True)[:n]
        pid_map = {p['_id']: p for p in products}
        return [pid_map[pid] for pid, _ in ranked if pid in pid_map]
    except Exception as e:
        print(f"[recommender] Error: {e}")
        return []
