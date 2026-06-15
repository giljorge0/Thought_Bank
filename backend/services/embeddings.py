"""
Embedding & Analysis Service
─────────────────────────────
Ported from originality_radar's anthropic.js.
Uses Ollama locally (nomic-embed-text for embeddings, mistral for analysis).
Falls back to Anthropic API if configured.
"""

import json
import logging
import os
from typing import Optional

import httpx

log = logging.getLogger(__name__)

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
LLM_MODEL = os.environ.get("LLM_MODEL", "mistral")

_client = httpx.AsyncClient(timeout=120.0)


async def generate_embedding(text: str) -> list[float]:
    """Generate a vector embedding via Ollama (nomic-embed-text)."""
    try:
        resp = await _client.post(
            f"{OLLAMA_BASE}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
        )
        resp.raise_for_status()
        return resp.json()["embedding"]
    except Exception as e:
        log.error(f"Embedding error: {e}")
        raise RuntimeError(f"Failed to generate embedding: {e}")


async def generate_drift(idea: str, score: int, density: str,
                         neighbors: list[str]) -> dict:
    """
    Generate narrative analysis via local LLM.
    Ported from originality_radar's generateDrift().
    """
    neighbor_ctx = (
        "\n\nNearest neighbors:\n" + "\n".join(f"- {n}" for n in neighbors)
        if neighbors
        else "\n\n(First thought — no neighbors yet.)"
    )

    prompt = f"""You are an originality analyst. The user's thought has been scored mathematically by a vector database — do NOT change or recreate the score.

Thought: "{idea}"
Math Score: {score}/100 ({density}){neighbor_ctx}

Analyze and return ONLY a raw JSON object:
{{
  "domain": "One of: Tech, Science, Art, Social, Commerce, Nature, Philosophy, Engineering, Psychology, General",
  "nearestClusters": ["3-5 nearby concepts or fields"],
  "whatMakesItCommon": "One sentence on what makes this common.",
  "whatMakesItNovel": "One sentence on what's genuinely unusual.",
  "driftSuggestion": "One actionable suggestion to push further."
}}"""

    try:
        resp = await _client.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": LLM_MODEL, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        raw = resp.json()["response"].strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(raw)
        return {
            "domain": parsed.get("domain", "General"),
            "nearestClusters": parsed.get("nearestClusters", []),
            "whatMakesItCommon": parsed.get("whatMakesItCommon", ""),
            "whatMakesItNovel": parsed.get("whatMakesItNovel", ""),
            "driftSuggestion": parsed.get("driftSuggestion", ""),
        }
    except Exception as e:
        log.warning(f"Drift generation failed: {e}")
        return {
            "domain": "General",
            "nearestClusters": [],
            "whatMakesItCommon": "Analysis pending.",
            "whatMakesItNovel": "Analysis pending.",
            "driftSuggestion": "Try a different angle.",
        }


async def synthesize_cluster(thoughts: list[str], count: int,
                              concept_hint: str = "") -> dict:
    """
    "You Are Not Alone" synthesis.
    Takes a batch of semantically similar thoughts and produces
    a unified, validating response. Adapted from Digital-Brain-Project's
    auto_wiki.py generation pattern.
    """
    sample = thoughts[:20]  # cap context to avoid overflow
    context = "\n".join(f"- \"{t}\"" for t in sample)

    prompt = f"""You are an empathetic synthesis engine for a collective thought database.

{count} people have independently submitted thoughts very similar to each other.
Here is a sample of {len(sample)} of them:

{context}

{f"These cluster around the concept: {concept_hint}" if concept_hint else ""}

Your job: synthesize what these humans are collectively thinking and feeling.

Return ONLY a JSON object:
{{
  "core_insight": "The single universal insight these thoughts converge on (1-2 sentences).",
  "message": "A warm, validating 2-3 sentence response that begins with the count. Example opener: '{count} other people have had this exact thought.' Then briefly describe what they collectively concluded or felt.",
  "key_themes": ["3-5 recurring themes across these thoughts"],
  "best_framing": "The single most articulate way to state this shared idea (1 sentence)."
}}"""

    try:
        resp = await _client.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": LLM_MODEL, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        raw = resp.json()["response"].strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(raw)
    except Exception as e:
        log.warning(f"Synthesis failed: {e}")
        return {
            "core_insight": "Many people share this thought.",
            "message": f"{count} other people have submitted a very similar thought. You are not alone in thinking this.",
            "key_themes": [],
            "best_framing": "",
        }


async def generate_wiki_content(concept: str, thoughts: list[str],
                                 old_content: Optional[str] = None) -> str:
    """
    Generate a wiki-style synthesis for a thought cluster.
    Ported from auto_wiki.py's _generate_content().
    """
    context = "\n\n---\n".join(f"Thought: \"{t}\"" for t in thoughts[:15])

    update_note = ""
    if old_content:
        update_note = f"""
An older version exists. Update it with new material. Preserve accurate content.
Flag contradictions with [CONTRADICTION: ...]. Mark changes with [UPDATED: ...].

PREVIOUS VERSION (excerpt):
{old_content[:500]}
"""

    prompt = f"""Write a Wikipedia-style article synthesizing what many people think about: "{concept}"
{update_note}

Structure:
# {concept.title()}

[Opening: what this collective thought is about — 2-3 sentences]

[Body: key perspectives, sub-themes, tensions — 200-350 words]

## Collective Patterns
- [3-5 recurring patterns across submissions]

## Open Questions
- [3-5 questions this cluster raises]

SOURCE THOUGHTS:
{context}

Write the article only. No preamble."""

    try:
        resp = await _client.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": LLM_MODEL, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        return resp.json()["response"].strip()
    except Exception as e:
        log.error(f"Wiki generation failed: {e}")
        return f"# {concept.title()}\n\n_Synthesis pending. {len(thoughts)} thoughts in cluster._"


async def extract_claims(text: str) -> list[dict]:
    """
    Extract atomic claims from a thought.
    Ported from relations.py's ClaudeExtractor.extract_claims().
    """
    prompt = f"""Extract every distinct atomic claim from this text.
Each claim should be a single self-contained assertion.

Text: "{text}"

Respond ONLY in JSON:
{{
  "claims": [
    {{"claim": "<atomic statement>", "confidence": <0.0-1.0>}}
  ]
}}"""

    try:
        resp = await _client.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": LLM_MODEL, "prompt": prompt, "stream": False,
                  "format": "json"},
        )
        resp.raise_for_status()
        return json.loads(resp.json()["response"].strip()).get("claims", [])
    except Exception as e:
        log.warning(f"Claim extraction failed: {e}")
        return []
