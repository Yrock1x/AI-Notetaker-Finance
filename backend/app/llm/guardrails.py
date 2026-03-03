import re
from dataclasses import dataclass


@dataclass
class GroundingResult:
    score: float  # 0.0 to 1.0
    is_grounded: bool
    ungrounded_claims: list[str]
    validated_citations: list[dict]
    flagged_figures: list[dict]


# Regex patterns for financial figures
_CURRENCY_PATTERN = re.compile(
    r"[\$\u00A3\u20AC\u00A5]"          # Currency symbols: $ GBP EUR JPY
    r"\s*"
    r"\d[\d,]*"                         # Integer part with optional commas
    r"(?:\.\d+)?"                       # Optional decimal
    r"(?:\s*(?:million|billion|trillion|mn|bn|tn|m|b|k|K|M|B|T))?"  # Optional magnitude
)

_PERCENTAGE_PATTERN = re.compile(
    r"\d[\d,]*"
    r"(?:\.\d+)?"
    r"\s*%"
)

_STANDALONE_NUMBER_PATTERN = re.compile(
    r"\b\d[\d,]*"
    r"(?:\.\d+)?"
    r"\s*(?:million|billion|trillion|mn|bn|tn|bps|basis\s+points)\b"
)


def _normalize_figure(text: str) -> str:
    """Normalize a financial figure string for comparison.

    Strips whitespace, commas, and lowercases for fuzzy matching.
    """
    return re.sub(r"[,\s]+", "", text.strip()).lower()


def _extract_financial_figures(text: str) -> list[str]:
    """Extract all financial figures (currencies, percentages, large numbers) from text."""
    figures: list[str] = []

    for pattern in [_CURRENCY_PATTERN, _PERCENTAGE_PATTERN, _STANDALONE_NUMBER_PATTERN]:
        for match in pattern.finditer(text):
            fig = match.group().strip()
            if fig and fig not in figures:
                figures.append(fig)

    return figures


class FinancialGuardrails:
    GROUNDING_THRESHOLD = 0.7

    def validate_citations(
        self,
        answer: str,
        citations: list[dict],
        source_chunks: list[dict],
    ) -> list[dict]:
        """Verify that every citation in the answer maps to a real source chunk.

        Each citation dict has: text, source_id.
        Each source_chunk dict has: text, source_id, source_type.

        Returns a list of validated citation dicts, each augmented with a 'valid' bool
        and a 'reason' string explaining the validation result.
        """
        # Index source chunks by source_id for fast lookup
        source_index: dict[str, list[dict]] = {}
        for chunk in source_chunks:
            sid = chunk.get("source_id", "")
            source_index.setdefault(sid, []).append(chunk)

        validated: list[dict] = []

        for citation in citations:
            cite_text = citation.get("text", "").strip()
            cite_source_id = citation.get("source_id", "")

            result = {
                "text": cite_text,
                "source_id": cite_source_id,
                "valid": False,
                "reason": "",
            }

            if not cite_text:
                result["reason"] = "Empty citation text"
                validated.append(result)
                continue

            # Check if the source_id matches any known source chunk
            matching_chunks = source_index.get(cite_source_id, [])
            if not matching_chunks:
                result["reason"] = f"No source chunk found with source_id '{cite_source_id}'"
                validated.append(result)
                continue

            # Check if the cited text is substantively present in any of the matching chunks
            cite_normalized = cite_text.lower().strip()
            found = False
            for chunk in matching_chunks:
                chunk_text_lower = chunk.get("text", "").lower()
                if cite_normalized in chunk_text_lower:
                    found = True
                    break

            if found:
                result["valid"] = True
                result["reason"] = "Citation text found in source chunk"
            else:
                # Partial match: check if significant words from citation appear in chunk
                cite_words = set(re.findall(r"\b\w{4,}\b", cite_normalized))
                if cite_words:
                    best_overlap = 0.0
                    for chunk in matching_chunks:
                        chunk_words = set(re.findall(r"\b\w{4,}\b", chunk.get("text", "").lower()))
                        if cite_words:
                            overlap = len(cite_words & chunk_words) / len(cite_words)
                            best_overlap = max(best_overlap, overlap)

                    if best_overlap >= 0.7:
                        result["valid"] = True
                        result["reason"] = (
                            f"Partial match ({best_overlap:.0%} "
                            f"word overlap) with source chunk"
                        )
                    else:
                        result["reason"] = (
                            f"Citation text not found in source chunks "
                            f"(best word overlap: {best_overlap:.0%})"
                        )
                else:
                    result["reason"] = "Citation text too short to validate"

            validated.append(result)

        return validated

    def validate_financial_figures(
        self,
        answer: str,
        source_chunks: list[dict],
    ) -> list[dict]:
        """Cross-check any financial figures in the answer against source material.

        Extracts figures from both the answer and sources, then compares
        figure-to-figure (normalized) instead of checking substrings against
        the full source text, which avoids false positives.

        Returns a list of dicts with 'figure', 'found_in_source', and 'source_id' (if found).
        """
        answer_figures = _extract_financial_figures(answer)

        if not answer_figures:
            return []

        # Extract figures from each source chunk and map normalized forms to source_ids
        normalized_source_map: dict[str, str] = {}
        for chunk in source_chunks:
            source_text = chunk.get("text", "")
            source_id = chunk.get("source_id", "")
            for fig in _extract_financial_figures(source_text):
                norm = _normalize_figure(fig)
                if norm not in normalized_source_map:
                    normalized_source_map[norm] = source_id

        results: list[dict] = []

        for figure in answer_figures:
            normalized = _normalize_figure(figure)
            source_id = normalized_source_map.get(normalized)

            results.append({
                "figure": figure,
                "found_in_source": source_id is not None,
                "source_id": source_id,
            })

        return results

    def calculate_grounding_score(
        self,
        answer: str,
        citations: list[dict],
        source_chunks: list[dict],
    ) -> float:
        """Calculate overall grounding score (0-1) based on citation coverage and figure validation.

        The score is a weighted combination of:
        - Citation validity ratio (60% weight)
        - Financial figure grounding ratio (40% weight)
        If no citations or figures are present, their respective components default to 1.0
        (i.e., absence of citations/figures is not penalized).
        """
        # Citation score
        validated_citations = self.validate_citations(answer, citations, source_chunks)
        if validated_citations:
            valid_count = sum(1 for c in validated_citations if c.get("valid"))
            citation_score = valid_count / len(validated_citations)
        else:
            citation_score = 1.0 if not citations else 0.0

        # Figure score
        figure_results = self.validate_financial_figures(answer, source_chunks)
        if figure_results:
            grounded_count = sum(1 for f in figure_results if f.get("found_in_source"))
            figure_score = grounded_count / len(figure_results)
        else:
            figure_score = 1.0  # No figures to validate

        # Weighted combination
        score = 0.6 * citation_score + 0.4 * figure_score
        return round(score, 4)

    def check_and_flag(
        self,
        answer: str,
        citations: list[dict],
        source_chunks: list[dict],
    ) -> GroundingResult:
        """Run all guardrail checks and return a combined GroundingResult.

        Performs citation validation, financial figure validation, and computes
        the overall grounding score. Flags ungrounded claims and figures.
        """
        validated_citations = self.validate_citations(answer, citations, source_chunks)
        figure_results = self.validate_financial_figures(answer, source_chunks)
        score = self.calculate_grounding_score(answer, citations, source_chunks)

        # Collect ungrounded claims (invalid citations)
        ungrounded_claims: list[str] = []
        for vc in validated_citations:
            if not vc.get("valid"):
                ungrounded_claims.append(
                    f"Unverified citation: \"{vc.get('text', '')}\" - {vc.get('reason', '')}"
                )

        # Collect flagged figures (not found in sources)
        flagged_figures: list[dict] = []
        for fr in figure_results:
            if not fr.get("found_in_source"):
                flagged_figures.append({
                    "figure": fr["figure"],
                    "issue": f"Financial figure '{fr['figure']}' not found in any source material",
                })

        is_grounded = score >= self.GROUNDING_THRESHOLD

        return GroundingResult(
            score=score,
            is_grounded=is_grounded,
            ungrounded_claims=ungrounded_claims,
            validated_citations=validated_citations,
            flagged_figures=flagged_figures,
        )
