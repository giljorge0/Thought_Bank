"""
Synthesis Agent — "You Are Not Alone" Engine
─────────────────────────────────────────────
Core Thought Bank feature. When a submitted thought lands in a dense
vector neighborhood (high cosine similarity to many existing thoughts),
this agent synthesizes the cluster into a validating response.

Adapted from:
  - Digital-Brain-Project/auto_wiki.py  (wiki generation pattern)
  - Digital-Brain-Project/relations.py  (claim extraction)
  - originality_radar/vector.js         (density scoring)
"""

import logging
from typing import Optional

from db import client as db
from services import embeddings, vector

log = logging.getLogger(__name__)

# Similarity threshold for triggering "You Are Not Alone"
YANA_THRESHOLD = 0.75  # thoughts with avgSim >= this get synthesis
YANA_MIN_NEIGHBORS = 3  # need at least this many similar thoughts


async def process_thought(thought_text: str,
                          ip_hash: str = None,
                          user_agent: str = None) -> dict:
    """
    Full pipeline for a submitted thought:
    1. Embed via Ollama
    2. k-NN query against pgvector
    3. Score originality
    4. If dense neighborhood → trigger "You Are Not Alone" synthesis
    5. Generate drift analysis
    6. Store and return result
    """

    # Step 1: Generate embedding
    vec = await embeddings.generate_embedding(thought_text)

    # Step 2: k-NN query
    neighbors = await db.knn_query(vec, k=10)
    similarities = [n["similarity"] for n in neighbors]
    neighbor_texts = [n["thought"] for n in neighbors]

    # Step 3: Score
    score = vector.score_from_similarities(similarities)
    density = vector.density_from_score(score)

    # Step 4: Check for dense neighborhood → "You Are Not Alone"
    synthesis = None
    neighbor_count = sum(1 for s in similarities if s >= YANA_THRESHOLD)

    if neighbor_count >= YANA_MIN_NEIGHBORS:
        # Get ALL similar thoughts within threshold (not just top 10)
        dense_neighbors = await db.get_high_density_neighbors(
            vec, threshold=YANA_THRESHOLD, limit=50
        )
        total_similar = len(dense_neighbors)
        similar_texts = [n["thought"] for n in dense_neighbors]

        synthesis = await embeddings.synthesize_cluster(
            similar_texts,
            count=total_similar,
            concept_hint=neighbor_texts[0] if neighbor_texts else "",
        )
        synthesis["shared_count"] = total_similar
        log.info(
            f"[YANA] Thought matched {total_similar} neighbors "
            f"(threshold={YANA_THRESHOLD})"
        )

    # Step 5: Drift analysis
    drift = await embeddings.generate_drift(
        thought_text, score, density, neighbor_texts[:5]
    )
    domain = drift.pop("domain", "General")

    # Step 6: 2D projection
    all_vecs = await db.get_all_vectors()
    coords = vector.project_coordinates(all_vecs, vec)

    # Step 7: Store
    stored = await db.insert_thought(
        thought=thought_text,
        vector=vec,
        score=score,
        density=density,
        domain=domain,
        neighbors=[
            {"thought": n["thought"], "similarity": round(n["similarity"], 3)}
            for n in neighbors[:5]
        ],
        neighbor_count=neighbor_count,
        synthesis=synthesis,
        map_x=coords["x"],
        map_y=coords["y"],
        nearest_clusters=drift.get("nearestClusters", []),
        what_common=drift.get("whatMakesItCommon", ""),
        what_novel=drift.get("whatMakesItNovel", ""),
        drift=drift.get("driftSuggestion", ""),
        ip_hash=ip_hash,
        user_agent=user_agent,
    )

    return {
        "id": stored["id"],
        "thought": thought_text,
        "score": score,
        "density": density,
        "domain": domain,
        "mapCoordinates": coords,
        "nearestNeighbors": [
            {"thought": n["thought"],
             "similarity": round(n["similarity"] * 100)}
            for n in neighbors[:5]
        ],
        "nearestClusters": drift.get("nearestClusters", []),
        "whatMakesItCommon": drift.get("whatMakesItCommon", ""),
        "whatMakesItNovel": drift.get("whatMakesItNovel", ""),
        "driftSuggestion": drift.get("driftSuggestion", ""),
        # The core feature:
        "synthesis": synthesis,
        "neighborCount": neighbor_count,
        "createdAt": stored["created_at"],
    }
