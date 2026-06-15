"""
Database Client
───────────────
Async PostgreSQL + pgvector client for Thought Bank.
Ported from originality_radar's client.js (pg-promise) to asyncpg.
"""

import asyncpg
import json
import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=os.environ["DATABASE_URL"],
            min_size=2,
            max_size=10,
        )
        # Register pgvector type codec
        async with _pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            log.info("✓ Database connected")
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def run_migrations():
    """Run SQL migration files in order."""
    pool = await get_pool()
    migrations_dir = Path(__file__).parent / "migrations"

    for sql_file in sorted(migrations_dir.glob("*.sql")):
        log.info(f"  Running migration: {sql_file.name}")
        sql = sql_file.read_text()
        async with pool.acquire() as conn:
            await conn.execute(sql)
    log.info("✓ Migrations complete")


# ── Thought CRUD ─────────────────────────────────────────────────────────────

async def insert_thought(thought: str, vector: list, score: int,
                         density: str, domain: str, neighbors: list,
                         neighbor_count: int, synthesis: dict | None,
                         map_x: float, map_y: float,
                         nearest_clusters: list, what_common: str,
                         what_novel: str, drift: str,
                         ip_hash: str = None, user_agent: str = None,
                         cluster_id: str = None) -> dict:
    pool = await get_pool()
    vec_str = f"[{','.join(str(v) for v in vector)}]"

    row = await pool.fetchrow("""
        INSERT INTO thoughts (
            thought, vector, score, density, domain, cluster_id,
            nearest_neighbors, neighbor_count, synthesis,
            map_x, map_y,
            nearest_clusters, what_makes_it_common, what_makes_it_novel,
            drift_suggestion, ip_hash, user_agent
        ) VALUES (
            $1, $2::vector, $3, $4, $5, $6,
            $7::jsonb, $8, $9::jsonb,
            $10, $11,
            $12, $13, $14, $15, $16, $17
        )
        RETURNING id, created_at
    """,
        thought, vec_str, score, density, domain, cluster_id,
        json.dumps(neighbors), neighbor_count,
        json.dumps(synthesis) if synthesis else None,
        map_x, map_y,
        nearest_clusters, what_common, what_novel, drift,
        ip_hash, user_agent,
    )
    return {"id": str(row["id"]), "created_at": row["created_at"].isoformat()}


async def knn_query(vector: list, k: int = 10, exclude_id: str = None) -> list:
    """Find k nearest neighbors by cosine distance."""
    pool = await get_pool()
    vec_str = f"[{','.join(str(v) for v in vector)}]"

    if exclude_id:
        rows = await pool.fetch("""
            SELECT id, thought, score, density, domain,
                   1 - (vector <=> $1::vector) AS similarity,
                   map_x, map_y, created_at
            FROM thoughts
            WHERE id != $3
            ORDER BY vector <=> $1::vector
            LIMIT $2
        """, vec_str, k, exclude_id)
    else:
        rows = await pool.fetch("""
            SELECT id, thought, score, density, domain,
                   1 - (vector <=> $1::vector) AS similarity,
                   map_x, map_y, created_at
            FROM thoughts
            ORDER BY vector <=> $1::vector
            LIMIT $2
        """, vec_str, k)

    return [dict(r) for r in rows]


async def get_all_vectors() -> list:
    """Fetch all vectors for PCA projection."""
    pool = await get_pool()
    rows = await pool.fetch("SELECT vector::text FROM thoughts ORDER BY created_at")
    vectors = []
    for r in rows:
        vec_text = r["vector"]
        if vec_text:
            nums = [float(x) for x in vec_text.strip("[]").split(",")]
            vectors.append(nums)
    return vectors


async def get_thoughts_for_map(domain: str = None) -> list:
    """Fetch all thoughts with coordinates for visualization."""
    pool = await get_pool()
    if domain:
        rows = await pool.fetch("""
            SELECT id, thought, score, density, domain, map_x, map_y,
                   cluster_id, created_at
            FROM thoughts WHERE domain = $1
            ORDER BY created_at DESC
        """, domain)
    else:
        rows = await pool.fetch("""
            SELECT id, thought, score, density, domain, map_x, map_y,
                   cluster_id, created_at
            FROM thoughts ORDER BY created_at DESC
        """)
    return [dict(r) for r in rows]


async def get_analytics() -> dict:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM thought_analytics LIMIT 1")
    if not row:
        return {"total_thoughts": 0, "avg_score": 0}
    return dict(row)


async def get_cluster_thoughts(cluster_id: str) -> list:
    """Get all thoughts belonging to a cluster."""
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT id, thought, score, density, created_at
        FROM thoughts WHERE cluster_id = $1
        ORDER BY score ASC
    """, cluster_id)
    return [dict(r) for r in rows]


async def get_high_density_neighbors(vector: list, threshold: float = 0.75,
                                      limit: int = 50) -> list:
    """Find all thoughts within a similarity threshold (for "You Are Not Alone")."""
    pool = await get_pool()
    vec_str = f"[{','.join(str(v) for v in vector)}]"
    rows = await pool.fetch("""
        SELECT id, thought, score, density, domain,
               1 - (vector <=> $1::vector) AS similarity,
               created_at
        FROM thoughts
        WHERE 1 - (vector <=> $1::vector) >= $2
        ORDER BY similarity DESC
        LIMIT $3
    """, vec_str, threshold, limit)
    return [dict(r) for r in rows]


# ── Cluster operations ───────────────────────────────────────────────────────

async def upsert_cluster(cluster_id: str = None, **kwargs) -> str:
    pool = await get_pool()
    if cluster_id:
        sets = []
        vals = [cluster_id]
        i = 2
        for k, v in kwargs.items():
            if k == "centroid":
                sets.append(f"{k} = ${i}::vector")
                vals.append(f"[{','.join(str(x) for x in v)}]")
            elif k in ("claims", "contradictions"):
                sets.append(f"{k} = ${i}::jsonb")
                vals.append(json.dumps(v))
            else:
                sets.append(f"{k} = ${i}")
                vals.append(v)
            i += 1
        sets.append("updated_at = NOW()")
        await pool.execute(
            f"UPDATE thought_clusters SET {', '.join(sets)} WHERE id = $1",
            *vals
        )
        return cluster_id
    else:
        centroid = kwargs.pop("centroid", None)
        cen_str = f"[{','.join(str(x) for x in centroid)}]" if centroid else None
        row = await pool.fetchrow("""
            INSERT INTO thought_clusters (label, centroid, member_count, density)
            VALUES ($1, $2::vector, $3, $4)
            RETURNING id
        """, kwargs.get("label"), cen_str,
             kwargs.get("member_count", 0), kwargs.get("density", 0))
        return str(row["id"])


async def get_trending_clusters(limit: int = 10) -> list:
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT id, label, member_count, density, velocity_7d, velocity_30d,
               wiki_content, trending, created_at, updated_at
        FROM thought_clusters
        WHERE trending = TRUE
        ORDER BY velocity_7d DESC
        LIMIT $1
    """, limit)
    return [dict(r) for r in rows]


async def get_all_clusters() -> list:
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT id, label, member_count, density, velocity_7d, velocity_30d,
               wiki_content, wiki_version, trending, created_at, updated_at
        FROM thought_clusters
        ORDER BY member_count DESC
    """)
    return [dict(r) for r in rows]
