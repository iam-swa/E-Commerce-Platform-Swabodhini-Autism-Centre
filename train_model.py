"""
train_model.py  –  Train the SVD collaborative-filtering model for
                   Swabodhini E-Commerce recommendations.

Usage:
    python train_model.py          # trains and saves model
    python train_model.py --eval   # also prints RMSE + Precision@K report

Output:
    svd_model.pkl   – trained Surprise SVD model (loaded by recommender.py)
    model_meta.json – product-id list + training timestamp (for cache busting)
"""

import argparse
import json
import math
import os
import pickle
import sqlite3
import datetime
from collections import defaultdict

# ── scikit-surprise ──────────────────────────────────────────────────────────
try:
    from surprise import SVD, Dataset, Reader, accuracy
    from surprise.model_selection import train_test_split, cross_validate
except ImportError:
    raise SystemExit(
        "\n[ERROR] scikit-surprise not installed.\n"
        "Run:  pip install scikit-surprise numpy\n"
    )

import numpy as np

DB_PATH    = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'swabodhini.db')
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'svd_model.pkl')
META_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'model_meta.json')


# ────────────────────────────────────────────────────────────────────────────
# Step 1 – Build implicit ratings from order + view data
# ────────────────────────────────────────────────────────────────────────────

def build_ratings(db_path=DB_PATH):
    """
    Construct implicit ratings (1–5 scale) from behavioural signals:

      purchase  → 5.0   (strongest signal)
      view ×N   → 1.0 + min(log2(N), 2.0)   (1.0 to 3.0)

    The two signals are combined per (user, product) pair and capped at 5.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Purchase signal
    rows = conn.execute("""
        SELECT o.user_id, op.product_id, COUNT(*) as times
        FROM   order_products op
        JOIN   orders o ON o._id = op.order_id
        WHERE  o.status IN ('Approved','Shipped','Delivered')
          AND  op.product_id IS NOT NULL
          AND  o.user_id IS NOT NULL
        GROUP  BY o.user_id, op.product_id
    """).fetchall()

    ratings = defaultdict(float)
    for r in rows:
        key = (r["user_id"], r["product_id"])
        ratings[key] = max(ratings[key], 5.0)

    # View signal
    views = conn.execute("""
        SELECT user_id, product_id, view_count
        FROM   product_views
        WHERE  user_id IS NOT NULL AND product_id IS NOT NULL
    """).fetchall()

    for v in views:
        key = (v["user_id"], v["product_id"])
        view_score = 1.0 + min(math.log2(v["view_count"] + 1), 2.0)
        ratings[key] = min(5.0, ratings[key] + view_score)

    # Fetch active product ids (for meta)
    product_ids = [
        r[0] for r in conn.execute(
            "SELECT _id FROM products WHERE isActive=1"
        ).fetchall()
    ]

    conn.close()

    data = [
        {"user_id": uid, "product_id": pid, "rating": round(rat, 2)}
        for (uid, pid), rat in ratings.items()
    ]
    print(f"[train] Interaction matrix: {len(data)} (user, product) pairs "
          f"across {len(set(d['user_id'] for d in data))} users "
          f"and {len(set(d['product_id'] for d in data))} products.")
    return data, product_ids


# ────────────────────────────────────────────────────────────────────────────
# Step 2 – Train SVD
# ────────────────────────────────────────────────────────────────────────────

def train(data):
    """Train Surprise SVD on the implicit-rating dataset."""
    if len(data) < 10:
        raise ValueError(
            "[train] Not enough interaction data. "
            "Run  python seed_ml_data.py  first."
        )

    reader  = Reader(rating_scale=(1.0, 5.0))
    dataset = Dataset.load_from_df(
        __import__('pandas').DataFrame(data)[["user_id", "product_id", "rating"]],
        reader,
    )

    trainset, testset = train_test_split(dataset, test_size=0.20, random_state=42)

    # SVD hyper-parameters (tuned for small datasets)
    algo = SVD(
        n_factors=50,
        n_epochs=30,
        lr_all=0.005,
        reg_all=0.02,
        random_state=42,
        verbose=False,
    )
    algo.fit(trainset)
    print("[train] SVD model trained ✓")
    return algo, trainset, testset, dataset


# ────────────────────────────────────────────────────────────────────────────
# Step 3 – Evaluate
# ────────────────────────────────────────────────────────────────────────────

def evaluate(algo, testset, dataset, k=4):
    """Print RMSE, MAE, and Precision / Recall @ K."""
    predictions = algo.test(testset)
    rmse = accuracy.rmse(predictions, verbose=False)
    mae  = accuracy.mae(predictions,  verbose=False)

    # Precision@K and Recall@K
    # A prediction is "relevant" if estimated rating >= 3.5
    THRESHOLD = 3.5
    user_est_true = defaultdict(list)
    for pred in predictions:
        user_est_true[pred.uid].append((pred.est, pred.r_ui))

    precisions, recalls = [], []
    for uid, preds in user_est_true.items():
        preds.sort(key=lambda x: x[0], reverse=True)
        top_k     = preds[:k]
        n_rel     = sum(1 for _, true_r in preds        if true_r >= THRESHOLD)
        n_rec_k   = sum(1 for est, _    in top_k        if est    >= THRESHOLD)
        n_rel_rec = sum(1 for est, true_r in top_k if est >= THRESHOLD and true_r >= THRESHOLD)

        precisions.append(n_rec_k   / k      if k      > 0 else 0)
        recalls.append   (n_rel_rec / n_rel  if n_rel  > 0 else 0)

    print("\n" + "="*50)
    print("  SVD Model Evaluation Report")
    print("="*50)
    print(f"  RMSE             : {rmse:.4f}")
    print(f"  MAE              : {mae:.4f}")
    print(f"  Precision@{k}      : {np.mean(precisions):.4f}")
    print(f"  Recall@{k}         : {np.mean(recalls):.4f}")
    print(f"  Test samples     : {len(predictions)}")
    print("="*50 + "\n")

    # 5-fold cross-validation RMSE
    cv = cross_validate(algo, dataset, measures=["RMSE","MAE"], cv=5, verbose=False)
    print(f"  5-fold CV RMSE   : {np.mean(cv['test_rmse']):.4f} "
          f"(±{np.std(cv['test_rmse']):.4f})")
    print(f"  5-fold CV MAE    : {np.mean(cv['test_mae']):.4f} "
          f"(±{np.std(cv['test_mae']):.4f})\n")

    return {
        "rmse": round(rmse, 4),
        "mae":  round(mae,  4),
        f"precision_at_{k}": round(float(np.mean(precisions)), 4),
        f"recall_at_{k}":    round(float(np.mean(recalls)),    4),
    }


# ────────────────────────────────────────────────────────────────────────────
# Step 4 – Save
# ────────────────────────────────────────────────────────────────────────────

def save_model(algo, product_ids, metrics=None):
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(algo, f)

    meta = {
        "trained_at":  datetime.datetime.now().isoformat(),
        "product_ids": product_ids,
        "metrics":     metrics or {},
        "model":       "SVD (scikit-surprise)",
        "n_factors":   50,
        "n_epochs":    30,
    }
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"[train] Model saved → {MODEL_PATH}")
    print(f"[train] Meta  saved → {META_PATH}")


# ────────────────────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", action="store_true",
                        help="Print RMSE / Precision@K evaluation report")
    args = parser.parse_args()

    data, product_ids = build_ratings()
    algo, trainset, testset, dataset = train(data)

    metrics = None
    if args.eval:
        metrics = evaluate(algo, testset, dataset, k=4)

    save_model(algo, product_ids, metrics)
    print("[train] All done ✓")
