"""Embedding providers.

Same shape as the judge and generator: a real provider over Ollama, and a
deterministic local fallback.

The fallback is a **hashing vectoriser** — tokens hashed into buckets with
sub-linear term weighting, then L2-normalised. That is genuine lexical
similarity, not noise: "spatial sampling frames" and "geo-spatial sampling"
score close together because they share tokens. It will not catch a synonym the
way a trained model does, so it is described as lexical rather than semantic
wherever it surfaces.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import urllib.error
import urllib.request
from typing import Protocol

from app.config import settings
from app.models_content import EMBEDDING_DIM

log = logging.getLogger("sankhya.embeddings")

EMBED_MODEL = "nomic-embed-text"

STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into", "over", "under",
    "a", "an", "of", "to", "in", "on", "is", "are", "be", "by", "as", "it", "its",
    "how", "what", "why", "when", "which", "you", "your", "will", "can", "may",
}


def tokenise(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) > 2 and token not in STOPWORDS
    ]


# Below this cosine, a course from a *different* competency is not admitted as
# a substitute. The number belongs to the embedder, not to the recommender: a
# lexical embedder scores unrelated text near zero, while a trained one puts
# everything in a narrow, high band. Using one figure for both let every course
# in the catalogue clear the bar. See `scripts/check_relevance_floor.py`, which
# measures the two distributions and fails if they stop being separable.
class Embedder(Protocol):
    name: str
    is_semantic: bool
    relevance_floor: float

    def embed(self, text: str) -> list[float]: ...


class HashingEmbedder:
    """Deterministic lexical embedding. No model, no network, no download."""

    name = "hashing-lexical"
    is_semantic = False
    # Unrelated text shares almost no tokens, so it lands near zero.
    relevance_floor = 0.20

    def __init__(self, dim: int = EMBEDDING_DIM):
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        counts: dict[str, int] = {}
        for token in tokenise(text):
            counts[token] = counts.get(token, 0) + 1

        for token, count in counts.items():
            digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dim
            # Signed buckets reduce the damage a collision does: two colliding
            # tokens are as likely to cancel as to reinforce.
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign * (1.0 + math.log(count))

        norm = math.sqrt(sum(v * v for v in vector))
        return [v / norm for v in vector] if norm else vector


class OllamaEmbedder:
    name = EMBED_MODEL
    is_semantic = True
    # Measured on this catalogue: unrelated course/competency pairs run
    # 0.34-0.72 (median 0.48) and same-competency pairs 0.43-0.81 (median 0.67).
    # The bands overlap, so no cutoff separates them cleanly. 0.55 sits above
    # the unrelated median and admits roughly the top sixth of cross-competency
    # pairs — the genuinely adjacent ones — instead of all of them.
    relevance_floor = 0.55

    def __init__(self, base_url: str | None = None, model: str = EMBED_MODEL):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model

    def embed(self, text: str) -> list[float]:
        body = json.dumps({"model": self.model, "prompt": text[:8000]}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/embeddings", data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            vector = json.loads(resp.read()).get("embedding") or []

        if len(vector) != EMBEDDING_DIM:
            # The column is fixed-width. A model with a different dimension
            # needs a schema change, not silent truncation.
            raise ValueError(
                f"{self.model} returned {len(vector)} dimensions, expected {EMBEDDING_DIM}"
            )
        return vector

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                tags = json.loads(resp.read()).get("models", [])
            return any(m.get("name", "").startswith(self.model) for m in tags)
        except Exception:
            return False


def get_embedder() -> Embedder:
    embedder = OllamaEmbedder()
    if embedder.is_available():
        return embedder
    log.info("%s not pulled; using the lexical hashing embedder", EMBED_MODEL)
    return HashingEmbedder()


def cosine(a: list[float] | None, b: list[float] | None) -> float:
    """Similarity in [-1, 1]. Both inputs are already normalised in practice,
    but a zero vector must not divide by zero."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0
