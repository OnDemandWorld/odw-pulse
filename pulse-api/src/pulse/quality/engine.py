"""Quality scoring engine for generated content.

Evaluates generated content against vault sources, glossary terms, and
quality heuristics to produce a numeric quality score and flags.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class QualityScore:
    """Quality assessment result for generated content.

    Attributes:
        score: Overall quality score from 0 to 100
        flags: List of quality flags / issues detected
        details: Detailed breakdown of scoring components
    """

    score: int
    flags: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


class QualityScoringEngine:
    """Engine for scoring the quality of generated content.

    Evaluates content based on multiple heuristics:
    - Length appropriateness
    - Glossary term compliance
    - Vault source reference accuracy
    - Basic readability checks
    """

    def __init__(
        self,
        min_length: int = 50,
        max_length: int = 10000,
    ) -> None:
        """Initialize the quality scoring engine.

        Args:
            min_length: Minimum expected content length in characters
            max_length: Maximum expected content length in characters
        """
        self._min_length = min_length
        self._max_length = max_length

    def score(
        self,
        content: str,
        vault_sources: list[str] | None = None,
        glossary: list[dict[str, Any]] | None = None,
    ) -> QualityScore:
        """Score generated content for quality.

        Args:
            content: The generated text content to evaluate
            vault_sources: Optional list of source texts that should be referenced
            glossary: Optional list of glossary term dicts with 'term' key

        Returns:
            QualityScore with numeric score (0-100) and issue flags
        """
        score = 100
        flags: list[str] = []
        details: dict[str, Any] = {}

        # 1. Length check
        length_score, length_flags = self._check_length(content)
        score -= length_score
        flags.extend(length_flags)
        details["length"] = {
            "chars": len(content),
            "deduction": length_score,
        }

        # 2. Glossary compliance
        if glossary:
            glossary_score, glossary_flags = self._check_glossary(content, glossary)
            score -= glossary_score
            flags.extend(glossary_flags)
            details["glossary"] = {
                "deduction": glossary_score,
                "missing_terms": [f for f in glossary_flags if f.startswith("Missing")],
            }

        # 3. Vault source reference
        if vault_sources:
            vault_score, vault_flags = self._check_vault_sources(content, vault_sources)
            score -= vault_score
            flags.extend(vault_flags)
            details["vault"] = {
                "deduction": vault_score,
            }

        # 4. Basic quality heuristics
        quality_score, quality_flags = self._check_quality_heuristics(content)
        score -= quality_score
        flags.extend(quality_flags)
        details["heuristics"] = {
            "deduction": quality_score,
        }

        # Clamp score to [0, 100]
        final_score = max(0, min(100, score))

        return QualityScore(
            score=final_score,
            flags=flags,
            details=details,
        )

    def _check_length(self, content: str) -> tuple[int, list[str]]:
        """Check if content length is within acceptable range.

        Returns:
            Tuple of (deduction, flags)
        """
        flags: list[str] = []
        deduction = 0
        length = len(content)

        if length < self._min_length:
            deduction += 20
            flags.append(f"Content too short ({length} chars, minimum {self._min_length})")
        elif length > self._max_length:
            deduction += 10
            flags.append(f"Content too long ({length} chars, maximum {self._max_length})")

        return deduction, flags

    def _check_glossary(
        self,
        content: str,
        glossary: list[dict[str, Any]],
    ) -> tuple[int, list[str]]:
        """Check if content uses glossary terms correctly.

        Returns:
            Tuple of (deduction, flags)
        """
        flags: list[str] = []
        deduction = 0
        content_lower = content.lower()

        for term_entry in glossary:
            term = term_entry.get("term", "")
            if not term:
                continue

            # Check if the term appears in the content
            if term.lower() not in content_lower:
                deduction += 2
                flags.append(f"Missing glossary term: '{term}'")

        return deduction, flags

    def _check_vault_sources(
        self,
        content: str,
        vault_sources: list[str],
    ) -> tuple[int, list[str]]:
        """Check if content references vault sources.

        Returns:
            Tuple of (deduction, flags)
        """
        flags: list[str] = []
        deduction = 0

        if not vault_sources:
            return deduction, flags

        # Check if any meaningful phrases from sources appear in content
        content_lower = content.lower()
        references_found = 0

        for source in vault_sources:
            # Extract key phrases (words > 4 chars) from source
            words = re.findall(r"\b\w{5,}\b", source.lower())
            if not words:
                continue
            # Check if at least one key word appears
            if any(word in content_lower for word in words[:5]):
                references_found += 1

        if references_found == 0:
            deduction += 15
            flags.append("No vault source references detected in content")

        return deduction, flags

    def _check_quality_heuristics(self, content: str) -> tuple[int, list[str]]:
        """Apply basic quality heuristics.

        Returns:
            Tuple of (deduction, flags)
        """
        flags: list[str] = []
        deduction = 0

        # Check for placeholder text
        placeholder_patterns = [
            r"\[INSERT\b",
            r"\[TODO\b",
            r"\[PLACEHOLDER\b",
            r"lorem ipsum",
            r"xxx+",
        ]
        for pattern in placeholder_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                deduction += 15
                flags.append(f"Content contains placeholder text matching '{pattern}'")
                break

        # Check for excessive repetition (same sentence repeated)
        sentences = re.split(r"[.!?]+", content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        if len(sentences) > 3:
            unique_ratio = len(set(sentences)) / len(sentences)
            if unique_ratio < 0.5:
                deduction += 10
                flags.append("Content contains excessive repetition")

        # Check for all-caps sections (excluding short acronyms)
        all_caps_words = re.findall(r"\b[A-Z]{4,}\b", content)
        if len(all_caps_words) > 3:
            deduction += 5
            flags.append("Content contains excessive ALL CAPS text")

        return deduction, flags
