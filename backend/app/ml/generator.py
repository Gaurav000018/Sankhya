"""Question generation providers.

Mirrors `judge.py`: a real provider over Ollama, and a deterministic stub so the
pipeline is demonstrable on any machine.

The stub is worth a note. It builds each question around a sentence copied
verbatim from the passage, so the citations it produces genuinely verify. That
means the whole integrity path — generate, verify, queue, review, approve — can
be exercised end to end with no model pulled, and the citation check is being
tested rather than bypassed.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Protocol

from app.config import settings
from app.services.quizgen import (
    Candidate,
    GENERATION_SYSTEM,
    build_generation_prompt,
    parse_candidates,
    verify_citation,
)

log = logging.getLogger("sankhya.generator")

# Small models drop `citation_quote` or paraphrase it, and a question whose quote
# is not in the passage is thrown away. One targeted retry recovers most of them.
QUOTE_RETRY_SUFFIX = (
    "\n\nYour previous questions were rejected because their citation_quote did "
    "not appear in the passage word for word. Copy and paste a whole sentence "
    "from between the ---BEGIN--- and ---END--- markers into citation_quote, "
    "character for character. Do not shorten it, correct its spelling, or "
    "rewrite it. A question you cannot quote for is one you must not write."
)


class Generator(Protocol):
    model_name: str

    def generate(self, chunk_text: str, *, competency: str | None,
                 count: int, bloom: str) -> list[Candidate]: ...


class OllamaGenerator:
    def __init__(self, base_url: str | None = None, model: str | None = None,
                 timeout: int = 180):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model_name = model or settings.judge_model
        self.timeout = timeout

    def _generate(self, prompt: str) -> str:
        body = json.dumps({
            "model": self.model_name,
            "system": GENERATION_SYSTEM,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            # Deterministic, so regenerating the same passage does not quietly
            # produce a different question bank each run.
            "options": {"temperature": 0, "seed": 26101, "num_predict": 1600},
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/generate", data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read()).get("response", "")

    def generate(self, chunk_text: str, *, competency: str | None,
                 count: int, bloom: str) -> list[Candidate]:
        prompt = build_generation_prompt(
            chunk_text, competency=competency, count=count, bloom=bloom
        )

        best: list[Candidate] = []
        for attempt, text in enumerate((prompt, prompt + QUOTE_RETRY_SUFFIX)):
            try:
                candidates = parse_candidates(self._generate(text))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                log.warning("Generation call failed (attempt %d): %s", attempt + 1, exc)
                return best

            # A candidate whose quote is not in the passage will be discarded
            # downstream, so a batch where none verify is a wasted passage. The
            # quote is the one field a small model drops, and asking again costs
            # one call against a passage that would otherwise yield nothing.
            #
            # Retrying is the only honest repair here: filling the quote in
            # ourselves would make verification check our own work.
            usable = [
                c for c in candidates
                if verify_citation(chunk_text, c.citation_quote or "")
            ]
            if usable:
                return candidates
            best = candidates
            if candidates:
                log.info(
                    "No verifiable citation in %d candidate(s) from this passage; "
                    "asking again (attempt %d)", len(candidates), attempt + 1,
                )

        return best

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                tags = json.loads(resp.read()).get("models", [])
            stem = self.model_name.split(":")[0]
            return any(m.get("name", "").startswith(stem) for m in tags)
        except Exception:
            return False


class StubGenerator:
    """Deterministic generator for machines with no model pulled."""

    model_name = "stub-generator"

    def generate(self, chunk_text: str, *, competency: str | None,
                 count: int, bloom: str) -> list[Candidate]:
        sentences = [
            s.strip() for s in re.split(r"(?<=[.!?])\s+", chunk_text or "")
            if len(s.strip()) >= 40
        ]
        if not sentences:
            return []

        candidates: list[Candidate] = []
        for sentence in sentences[:count]:
            words = [w.strip(".,;:()") for w in sentence.split() if len(w.strip(".,;:()")) > 5]
            if len(words) < 3:
                continue
            key = words[0]
            candidates.append(Candidate(
                stem=(
                    f"According to the source material, which term correctly "
                    f"completes this statement about {competency or 'the topic'}? "
                    f"\"{sentence.replace(key, '______', 1)}\""
                ),
                options=[key, f"not {key}", f"{key} ratio", f"inverse {key}"],
                correct_index=0,
                explanation=(
                    f"The passage states this directly. Generated by the stub "
                    f"provider for pipeline testing, not a real assessment item."
                ),
                distractor_rationale=[
                    "Negation of the correct term",
                    "A related but different quantity",
                    "The reciprocal, which the passage does not describe",
                ],
                # Copied verbatim, so the citation check has something real to
                # verify rather than being trivially satisfied.
                citation_quote=sentence,
                bloom_level=bloom,
            ))
        return candidates


def get_generator() -> Generator:
    generator = OllamaGenerator()
    if generator.is_available():
        return generator
    log.warning("Generation model %s unavailable; using the stub generator",
                generator.model_name)
    return StubGenerator()
