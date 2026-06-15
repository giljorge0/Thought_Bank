"""
Cluster Analytics
─────────────────
Phase 2 & 3 features:
  - DBSCAN spatial clustering on pgvector embeddings
  - Temporal velocity tracking (cluster growth rate)
  - Wiki synthesis for mature clusters (adapted from auto_wiki.py)

Designed to run as a scheduled background job (APScheduler or cron).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np

from db import client as db
from services import embeddings

log = logging.getLogger(__name__)


async def run_clustering(eps: float = 0.3, min_samples: int = 5):
    """
    Run DBSCAN on all thought vectors to identify dense clusters.
    Updates the thought_clusters table and assigns cluster_id to thoughts.
    """
    from sklearn.cluster import DBSCAN

    pool = await db.get_pool()

    # Fetch all thoughts with vectors
    rows = await pool.fetch("""
        SELECT id, thought, vector::text, score, created_at
        FROM thoughts ORDER BY created_at
    """)

    if len(rows) < min_samples:
        log.info(f"[clustering] Only {len(rows)} thoughts — skipping (need {min_samples})")
        return

    # Parse vectors
    ids = []
    texts = []
    vectors = []
    timestamps = []
    for r in rows:
        vec_text = r["vector"]
        if not vec_text:
            continue
        nums = [float(x) for x in vec_text.strip("[]").split(",")]
        ids.append(str(r["id"]))
        texts.append(r["thought"])
        vectors.append(nums)
        timestamps.append(r["created_at"])

    X = np.array(vectors, dtype=np.float32)

    # Normalize for cosine-based DBSCAN (use angular distance)
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms[norms == 0] = 1
    X_normed = X / norms

    # DBSCAN with cosine metric
    clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine")
    labels = clustering.fit_predict(X_normed)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    log.info(f"[clustering] Found {n_clusters} clusters from {len(ids)} thoughts")

    # Process each cluster
    for cluster_label in set(labels):
        if cluster_label == -1:
            continue  # noise

        mask = labels == cluster_label
        cluster_ids = [ids[i] for i in range(len(ids)) if mask[i]]
        cluster_texts = [texts[i] for i in range(len(ids)) if mask[i]]
        cluster_vecs = X[mask]
        cluster_times = [timestamps[i] for i in range(len(ids)) if mask[i]]

        # Compute centroid
        centroid = cluster_vecs.mean(axis=0).tolist()

        # Compute intra-cluster density (avg pairwise similarity)
        if len(cluster_vecs) > 1:
            from sklearn.metrics.pairwise import cosine_similarity as cs
            sim_matrix = cs(cluster_vecs)
            np.fill_diagonal(sim_matrix, 0)
            avg_density = sim_matrix.sum() / (len(cluster_vecs) * (len(cluster_vecs) - 1))
        else:
            avg_density = 1.0

        # Compute velocity
        now = datetime.now(timezone.utc)
        v7 = sum(1 for t in cluster_times
                 if t.replace(tzinfo=timezone.utc) > now - timedelta(days=7))
        v30 = sum(1 for t in cluster_times
                  if t.replace(tzinfo=timezone.utc) > now - timedelta(days=30))

        vel_7d = v7 / 7.0
        vel_30d = v30 / 30.0

        # Trending if 7-day velocity is 2x the 30-day average
        trending = vel_7d > (vel_30d * 2) and v7 >= 3

        # Upsert cluster
        cid = await db.upsert_cluster(
            label=f"Cluster {cluster_label}",
            centroid=centroid,
            member_count=len(cluster_ids),
            density=float(avg_density),
            velocity_7d=vel_7d,
            velocity_30d=vel_30d,
            trending=trending,
        )

        # Assign thoughts to cluster
        for tid in cluster_ids:
            await pool.execute(
                "UPDATE thoughts SET cluster_id = $1 WHERE id = $2",
                cid, tid,
            )

        # Generate wiki for clusters with enough members
        if len(cluster_ids) >= 10:
            await _generate_cluster_wiki(cid, cluster_texts)

    log.info(f"[clustering] Done. {n_clusters} clusters processed.")


async def _generate_cluster_wiki(cluster_id: str, thoughts: list[str]):
    """Generate/update wiki content for a cluster. Adapted from auto_wiki.py."""
    pool = await db.get_pool()

    # Get current wiki content for diff-patch
    row = await pool.fetchrow(
        "SELECT wiki_content, wiki_version, label FROM thought_clusters WHERE id = $1",
        cluster_id,
    )
    old_content = row["wiki_content"] if row else None
    old_version = row["wiki_version"] if row else 0
    label = row["label"] if row else "Unknown"

    # Generate new wiki
    content = await embeddings.generate_wiki_content(
        concept=label,
        thoughts=thoughts,
        old_content=old_content,
    )

    # Extract claims (from relations.py pattern)
    claims = []
    for t in thoughts[:10]:
        c = await embeddings.extract_claims(t)
        claims.extend(c)

    await db.upsert_cluster(
        cluster_id=cluster_id,
        wiki_content=content,
        wiki_version=old_version + 1,
        claims=claims,
    )
    log.info(f"[wiki] Updated cluster {cluster_id} wiki (v{old_version + 1})")


async def compute_trend_velocity():
    """
    Phase 3: Compute velocity for all clusters.
    Designed to run periodically (e.g., hourly).
    """
    pool = await db.get_pool()
    clusters = await db.get_all_clusters()
    now = datetime.now(timezone.utc)

    for c in clusters:
        cid = str(c["id"])
        thoughts = await db.get_cluster_thoughts(cid)

        v7 = sum(1 for t in thoughts
                 if t["created_at"].replace(tzinfo=timezone.utc) > now - timedelta(days=7))
        v30 = sum(1 for t in thoughts
                  if t["created_at"].replace(tzinfo=timezone.utc) > now - timedelta(days=30))

        vel_7d = v7 / 7.0
        vel_30d = v30 / 30.0
        trending = vel_7d > (vel_30d * 2) and v7 >= 3

        await db.upsert_cluster(
            cluster_id=cid,
            velocity_7d=vel_7d,
            velocity_30d=vel_30d,
            trending=trending,
            member_count=len(thoughts),
        )

    log.info(f"[velocity] Updated {len(clusters)} clusters")
