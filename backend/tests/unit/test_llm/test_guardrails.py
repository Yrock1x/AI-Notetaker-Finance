"""Unit tests for financial guardrails."""

from app.llm.guardrails import FinancialGuardrails, GroundingResult


class TestValidateCitations:
    def setup_method(self):
        self.guardrails = FinancialGuardrails()

    def test_valid_citation_exact_match(self):
        """Citation text that is a substring of source chunk should be valid."""
        citations = [{"text": "revenue grew by 25%", "source_id": "chunk_1"}]
        sources = [{"text": "The company's revenue grew by 25% year over year", "source_id": "chunk_1"}]
        result = self.guardrails.validate_citations("answer", citations, sources)
        assert len(result) == 1
        assert result[0]["valid"] is True

    def test_invalid_citation_no_matching_source_id(self):
        """Citation referencing a non-existent source_id should be invalid."""
        citations = [{"text": "some claim", "source_id": "nonexistent"}]
        sources = [{"text": "some claim here", "source_id": "chunk_1"}]
        result = self.guardrails.validate_citations("answer", citations, sources)
        assert len(result) == 1
        assert result[0]["valid"] is False
        assert "nonexistent" in result[0]["reason"]

    def test_valid_citation_word_overlap(self):
        """Citation with >= 70% word overlap should be valid via partial match."""
        citations = [{"text": "management increased operational efficiency across departments", "source_id": "chunk_1"}]
        sources = [{"text": "management team increased operational efficiency across multiple departments last quarter", "source_id": "chunk_1"}]
        result = self.guardrails.validate_citations("answer", citations, sources)
        assert result[0]["valid"] is True

    def test_invalid_citation_low_word_overlap(self):
        """Citation with low word overlap should be invalid."""
        citations = [{"text": "company plans to expand internationally into new markets", "source_id": "chunk_1"}]
        sources = [{"text": "revenue figures showed positive growth trends", "source_id": "chunk_1"}]
        result = self.guardrails.validate_citations("answer", citations, sources)
        assert result[0]["valid"] is False

    def test_empty_citation_text(self):
        """Empty citation text should be marked invalid."""
        citations = [{"text": "", "source_id": "chunk_1"}]
        sources = [{"text": "some text", "source_id": "chunk_1"}]
        result = self.guardrails.validate_citations("answer", citations, sources)
        assert result[0]["valid"] is False
        assert "Empty" in result[0]["reason"]

    def test_multiple_citations_mixed(self):
        """Mix of valid and invalid citations should be handled correctly."""
        citations = [
            {"text": "revenue grew", "source_id": "chunk_1"},
            {"text": "fake claim", "source_id": "nonexistent"},
        ]
        sources = [{"text": "revenue grew significantly", "source_id": "chunk_1"}]
        result = self.guardrails.validate_citations("answer", citations, sources)
        assert result[0]["valid"] is True
        assert result[1]["valid"] is False


class TestValidateFinancialFigures:
    def setup_method(self):
        self.guardrails = FinancialGuardrails()

    def test_currency_figure_found(self):
        """Currency figures present in source should be marked as found."""
        answer = "The deal was valued at $50 million."
        sources = [{"text": "Deal valuation: $50 million enterprise value", "source_id": "s1"}]
        result = self.guardrails.validate_financial_figures(answer, sources)
        assert any(r["found_in_source"] for r in result)

    def test_percentage_figure_found(self):
        """Percentage figures present in source should be marked as found."""
        answer = "EBITDA margin was 15%."
        sources = [{"text": "The EBITDA margin was 15% for the quarter", "source_id": "s1"}]
        result = self.guardrails.validate_financial_figures(answer, sources)
        found = [r for r in result if r["found_in_source"]]
        assert len(found) >= 1

    def test_figure_not_found_flagged(self):
        """Figures not present in any source should be flagged."""
        answer = "Revenue reached $999 billion last year."
        sources = [{"text": "Revenue was approximately $100 million", "source_id": "s1"}]
        result = self.guardrails.validate_financial_figures(answer, sources)
        assert any(not r["found_in_source"] for r in result)

    def test_no_figures_returns_empty(self):
        """Answer with no financial figures should return empty list."""
        answer = "The management team discussed strategic priorities."
        sources = [{"text": "some text", "source_id": "s1"}]
        result = self.guardrails.validate_financial_figures(answer, sources)
        assert result == []


class TestGroundingScore:
    def setup_method(self):
        self.guardrails = FinancialGuardrails()

    def test_fully_grounded_score(self):
        """All valid citations and figures should give score close to 1.0."""
        answer = "Revenue was $50 million."
        citations = [{"text": "Revenue was $50 million", "source_id": "s1"}]
        sources = [{"text": "Revenue was $50 million for FY2024", "source_id": "s1"}]
        score = self.guardrails.calculate_grounding_score(answer, citations, sources)
        assert score >= 0.9

    def test_no_citations_no_figures_defaults_to_one(self):
        """No citations and no figures should default to 1.0."""
        answer = "The team discussed next steps."
        score = self.guardrails.calculate_grounding_score(answer, [], [])
        assert score == 1.0

    def test_all_invalid_citations_low_score(self):
        """All invalid citations should give a low score."""
        citations = [
            {"text": "fabricated claim one", "source_id": "nonexistent"},
            {"text": "fabricated claim two", "source_id": "nonexistent"},
        ]
        sources = [{"text": "actual source text", "source_id": "s1"}]
        score = self.guardrails.calculate_grounding_score("answer", citations, sources)
        assert score < 0.7

    def test_threshold_check(self):
        """Score >= 0.7 should mean is_grounded = True."""
        assert FinancialGuardrails.GROUNDING_THRESHOLD == 0.7


class TestCheckAndFlag:
    def setup_method(self):
        self.guardrails = FinancialGuardrails()

    def test_grounded_result(self):
        """Well-grounded answer should have is_grounded=True."""
        answer = "Revenue was $50 million."
        citations = [{"text": "Revenue was $50 million", "source_id": "s1"}]
        sources = [{"text": "Revenue was $50 million for the fiscal year", "source_id": "s1"}]
        result = self.guardrails.check_and_flag(answer, citations, sources)
        assert isinstance(result, GroundingResult)
        assert result.is_grounded is True
        assert result.score >= 0.7
        assert len(result.ungrounded_claims) == 0

    def test_ungrounded_result(self):
        """Poorly grounded answer should have is_grounded=False and list ungrounded claims."""
        citations = [
            {"text": "completely made up fact", "source_id": "fake"},
            {"text": "another fabrication", "source_id": "fake"},
        ]
        sources = [{"text": "real source text about financials", "source_id": "s1"}]
        result = self.guardrails.check_and_flag("answer with $999 trillion", citations, sources)
        assert result.is_grounded is False
        assert len(result.ungrounded_claims) == 2
        assert len(result.flagged_figures) >= 1
