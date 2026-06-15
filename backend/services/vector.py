"""
Vector Math Service
───────────────────
Ported from originality_radar's vector.js.
Cosine similarity, originality scoring, density labels, 2D projection.
"""

import math
import numpy as np
from typing import Optional


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    if len(a) != len(b) or len(a) == 0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def score_from_similarities(similarities: list[float]) -> int:
    """
    Originality score from k-NN similarities.
    Score = (1 - avgSimilarity) × 100
    """
    if not similarities:
        return 95  # first thought is void by definition
    top = similarities[:min(10, len(similarities))]
    avg = sum(top) / len(top)
    return max(0, min(100, round((1 - avg) * 100)))


def density_from_score(score: int) -> str:
    """Map score to density label."""
    if score <= 15:
        return "SATURATED"
    elif score <= 35:
        return "DENSE"
    elif score <= 55:
        return "POPULATED"
    elif score <= 75:
        return "SPARSE"
    elif score <= 90:
        return "FRONTIER"
    return "VOID"


def project_coordinates(all_vectors: list[list[float]],
                        new_vector: list[float]) -> dict:
    """
    Project a high-dim vector to 2D via incremental PCA.
    Ported from originality_radar's projectCoordinates().
    """
    if not all_vectors or len(all_vectors) < 2:
        return {
            "x": float(math.tanh(new_vector[0] * 3)) if new_vector else 0,
            "y": float(math.tanh(new_vector[1] * 3)) if len(new_vector) > 1 else 0,
        }

    combined = all_vectors + [new_vector]
    mat = np.array(combined, dtype=np.float32)
    means = mat.mean(axis=0)
    centered_new = np.array(new_vector, dtype=np.float32) - means

    # Power iteration for top 2 principal axes
    centered = mat - means

    def power_iterate(data, deflate_axis=None):
        v = data[0].copy()
        if deflate_axis is not None:
            proj = np.dot(v, deflate_axis)
            v = v - proj * deflate_axis
        norm = np.linalg.norm(v)
        if norm < 1e-10:
            return v
        v = v / norm
        # One power iteration: Cv = X^T X v
        Cv = data.T @ (data @ v)
        if deflate_axis is not None:
            proj = np.dot(Cv, deflate_axis)
            Cv = Cv - proj * deflate_axis
        norm = np.linalg.norm(Cv)
        return Cv / norm if norm > 1e-10 else Cv

    axis1 = power_iterate(centered)
    axis2 = power_iterate(centered, axis1)

    x = float(np.dot(centered_new, axis1))
    y = float(np.dot(centered_new, axis2))

    scale = math.sqrt(len(new_vector)) * 0.15
    return {
        "x": float(math.tanh(x / scale)),
        "y": float(math.tanh(y / scale)),
    }
