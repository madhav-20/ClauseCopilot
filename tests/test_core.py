"""
Unit tests for ClauseSense core modules.

Run with:  pytest tests/test_core.py -v

No LLM or Ollama calls are made; embed_texts is mocked where needed.
"""

import sys
import os
import math
import json
import types
import unittest
from unittest.mock import patch, MagicMock

# Make sure the project root is on the path so imports work from any CWD
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
# Stub out heavy optional dependencies so tests run without a full install.
# sentence_transformers is only needed at runtime; we mock embed_texts directly.
# ---------------------------------------------------------------------------
_st_stub = types.ModuleType("sentence_transformers")
_st_stub.SentenceTransformer = MagicMock()
sys.modules.setdefault("sentence_transformers", _st_stub)

from core.chunking import chunk_text, SECTION_RE, DEFAULT_MAX_CHARS
from core.agents import _extract_json_obj
from core.retrieval import retrieve_evidence_for_risk, RISK_QUERIES


# ===========================================================================
# Helpers
# ===========================================================================

def _make_unit_vector(dim: int, index: int) -> list:
    """Return a unit vector with a 1.0 at position `index` (dim total dimensions)."""
    v = [0.0] * dim
    v[index % dim] = 1.0
    return v


# ===========================================================================
# chunk_text tests
# ===========================================================================

class TestChunkText(unittest.TestCase):

    # --- Section header detection ---

    def test_numbered_section_detected(self):
        text = "1. Term\nThis contract lasts twelve months.\n\n2. Payment\nInvoices due net-30."
        chunks = chunk_text(text)
        sections = [c["section"] for c in chunks]
        self.assertIn("1. Term", sections)
        self.assertIn("2. Payment", sections)

    def test_all_caps_section_detected(self):
        text = "TERMINATION\nEither party may terminate with 30 days notice."
        chunks = chunk_text(text)
        self.assertTrue(any("TERMINATION" in c["section"] for c in chunks))

    def test_article_section_detected(self):
        text = "Article 3\nThis article covers indemnification obligations."
        chunks = chunk_text(text)
        self.assertTrue(any("Article 3" in c["section"] for c in chunks))

    def test_section_symbol_detected(self):
        text = "§ 12.3\nGoverning law shall be the State of New York."
        chunks = chunk_text(text)
        self.assertTrue(any("§ 12.3" in c["section"] for c in chunks))

    def test_schedule_exhibit_detected(self):
        for header in ("Schedule A", "Exhibit B"):
            with self.subTest(header=header):
                text = f"{header}\nThis schedule defines the service tiers."
                chunks = chunk_text(text)
                self.assertTrue(
                    any(header in c["section"] for c in chunks),
                    f"Expected '{header}' to be detected as a section header",
                )

    def test_article_roman_numeral_detected(self):
        text = "ARTICLE IV\nRepresentations and warranties of the parties."
        chunks = chunk_text(text)
        self.assertTrue(any("ARTICLE IV" in c["section"] for c in chunks))

    # --- Chunk size ---

    def test_chunks_stay_under_max_chars(self):
        # Generate a long block of text with no natural section breaks
        long_para = ("The vendor shall provide services as described herein. " * 60).strip()
        chunks = chunk_text(long_para, max_chars=DEFAULT_MAX_CHARS)
        for c in chunks:
            # Allow a small tolerance (overlap can push slightly over in the final pass)
            self.assertLessEqual(
                len(c["text"]),
                DEFAULT_MAX_CHARS + 300,
                f"Chunk too large: {len(c['text'])} chars",
            )

    def test_single_short_text_is_one_chunk(self):
        text = "1. Payment\nInvoices are due within 30 days of receipt."
        chunks = chunk_text(text)
        self.assertEqual(len(chunks), 1)

    # --- Sentence boundaries ---

    def test_split_respects_sentence_boundary(self):
        # Build text long enough to force a split but with clear sentence boundaries
        sentence = "The vendor must notify the customer of any material change. "
        long_text = sentence * 40  # well over 1800 chars
        chunks = chunk_text(long_text, max_chars=DEFAULT_MAX_CHARS)
        # Every chunk (except possibly the last) should end with sentence-ending punctuation
        for c in chunks[:-1]:
            tail = c["text"].rstrip()
            self.assertTrue(
                tail.endswith(".") or tail.endswith("?") or tail.endswith("!"),
                f"Chunk does not end at sentence boundary: ...{tail[-40:]!r}",
            )

    # --- chunk_index field ---

    def test_chunk_index_field_present_and_sequential(self):
        text = "\n\n".join(
            f"{i}. Section {i}\n" + ("Content of section. " * 5)
            for i in range(1, 8)
        )
        chunks = chunk_text(text)
        for expected_idx, c in enumerate(chunks):
            self.assertIn("chunk_index", c)
            self.assertEqual(c["chunk_index"], expected_idx)

    # --- Overlap ---

    def test_overlap_adds_context_from_previous_chunk(self):
        # Two clearly separated sections; the second should contain tail of the first
        sec1_body = "Liability is limited to the fees paid in the preceding twelve months. " * 8
        sec2_body = "Termination requires written notice of at least thirty days. " * 8
        text = f"1. Liability\n{sec1_body}\n\n2. Termination\n{sec2_body}"
        chunks = chunk_text(text)
        if len(chunks) >= 2:
            # The second chunk's text should overlap with the first chunk's content
            last_part_of_first = chunks[0]["text"][-100:]
            # At least some words from the first chunk should appear in the second
            words_from_first = last_part_of_first.split()[-5:]
            second_chunk_text = chunks[1]["text"]
            overlap_found = any(w in second_chunk_text for w in words_from_first)
            self.assertTrue(
                overlap_found,
                "Expected overlap content from first chunk to appear in second chunk",
            )


# ===========================================================================
# _extract_json_obj tests
# ===========================================================================

class TestExtractJsonObj(unittest.TestCase):

    def test_clean_json(self):
        raw = '{"risk_score": 7, "red_flags": []}'
        result = _extract_json_obj(raw)
        self.assertEqual(result["risk_score"], 7)
        self.assertEqual(result["red_flags"], [])

    def test_json_in_markdown_fence(self):
        raw = '```json\n{"risk_score": 5, "red_flags": [{"category": "Liability"}]}\n```'
        result = _extract_json_obj(raw)
        self.assertEqual(result["risk_score"], 5)
        self.assertEqual(result["red_flags"][0]["category"], "Liability")

    def test_json_with_surrounding_text(self):
        raw = 'Here is my analysis:\n{"risk_score": 3, "red_flags": []}\nEnd of output.'
        result = _extract_json_obj(raw)
        self.assertEqual(result["risk_score"], 3)

    def test_json_missing_leading_brace(self):
        # Model outputs starting directly with a key
        raw = '"risk_score": 8, "red_flags": []}'
        result = _extract_json_obj(raw)
        self.assertEqual(result["risk_score"], 8)

    def test_json_trailing_comma(self):
        raw = '{"risk_score": 4, "red_flags": [{"category": "Payment",},],}'
        result = _extract_json_obj(raw)
        self.assertEqual(result["risk_score"], 4)

    def test_empty_string_raises(self):
        with self.assertRaises(ValueError):
            _extract_json_obj("")

    def test_whitespace_only_raises(self):
        with self.assertRaises(ValueError):
            _extract_json_obj("   \n  ")

    def test_unparseable_raises(self):
        with self.assertRaises(ValueError):
            _extract_json_obj("This is just plain text with no JSON anywhere.")

    def test_nested_json_parsed(self):
        raw = json.dumps({
            "risk_score": 9,
            "red_flags": [
                {
                    "category": "Termination",
                    "severity": "CRITICAL",
                    "evidence_quote": "Vendor may terminate at any time.",
                    "why_risky": "No protection for buyer.",
                    "suggested_fallback": "Either party may terminate with 30 days notice.",
                }
            ],
        })
        result = _extract_json_obj(raw)
        self.assertEqual(result["risk_score"], 9)
        self.assertEqual(result["red_flags"][0]["severity"], "CRITICAL")


# ===========================================================================
# retrieve_evidence_for_risk tests
# ===========================================================================

class TestRetrieveEvidenceForRisk(unittest.TestCase):
    """
    Tests use a small set of mock chunks with deterministic mock embeddings.
    embed_texts is patched to return pre-computed vectors — no model is loaded.
    """

    DIM = 16  # Embedding dimensionality for mocks

    def _mock_embed(self, texts):
        """
        Return a unit vector per text, cycling through dimensions.
        Chunk texts are mapped by their index in self._all_texts.
        Query texts each get their own fixed vector.
        """
        results = []
        for text in texts:
            if text in self._text_to_vec:
                results.append(self._text_to_vec[text])
            else:
                # Unknown text — return zero vector
                results.append([0.0] * self.DIM)
        return results

    def setUp(self):
        n_chunks = self.DIM  # One chunk per dimension so each is uniquely retrievable
        self._chunks = [
            {
                "section": f"Section {i + 1}",
                "text": f"Chunk text number {i}: " + ("x " * 20),
                "chunk_index": i,
            }
            for i in range(n_chunks)
        ]

        # Map chunk text → unit vector at dimension i
        self._text_to_vec = {}
        for i, c in enumerate(self._chunks):
            self._text_to_vec[c["text"]] = _make_unit_vector(self.DIM, i)

        # Map each risk query to a unit vector that points at chunk 0, 1, 2, ...
        # cycling through available chunks so multiple queries can hit the same chunk
        for j, q in enumerate(RISK_QUERIES):
            self._text_to_vec[q] = _make_unit_vector(self.DIM, j % n_chunks)

    def test_returns_nonempty_string(self):
        with patch("core.retrieval.embed_texts", side_effect=self._mock_embed):
            result = retrieve_evidence_for_risk(self._chunks, top_k_per_query=2)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_results_are_deduplicated(self):
        """
        Multiple queries that point at the same chunk should not produce duplicate
        text in the output.
        """
        with patch("core.retrieval.embed_texts", side_effect=self._mock_embed):
            result = retrieve_evidence_for_risk(self._chunks, top_k_per_query=3)
        # Count occurrences of each unique chunk text in the output
        for c in self._chunks:
            # A chunk should appear at most once
            count = result.count(c["text"])
            self.assertLessEqual(
                count, 1,
                f"Chunk text appeared {count} times — deduplication failed",
            )

    def test_respects_max_chars_cap(self):
        max_chars = 500
        with patch("core.retrieval.embed_texts", side_effect=self._mock_embed):
            result = retrieve_evidence_for_risk(
                self._chunks, top_k_per_query=5, max_chars=max_chars
            )
        self.assertLessEqual(
            len(result), max_chars + len("\n\n[... text truncated to fit model context ...]"),
            "Output exceeded max_chars cap",
        )

    def test_section_prefix_in_output(self):
        """Each chunk should be prefixed with [SECTION: ...]."""
        with patch("core.retrieval.embed_texts", side_effect=self._mock_embed):
            result = retrieve_evidence_for_risk(self._chunks, top_k_per_query=1)
        self.assertIn("[SECTION:", result)

    def test_empty_chunks_returns_empty_string(self):
        result = retrieve_evidence_for_risk([], top_k_per_query=5)
        self.assertEqual(result, "")

    def test_embed_texts_called_exactly_twice(self):
        """After batching, embed_texts should be called exactly twice:
        once for chunk texts, once for all query texts together."""
        call_count = {"n": 0}

        def counting_embed(texts):
            call_count["n"] += 1
            return self._mock_embed(texts)

        with patch("core.retrieval.embed_texts", side_effect=counting_embed):
            retrieve_evidence_for_risk(self._chunks, top_k_per_query=2)

        self.assertEqual(
            call_count["n"], 2,
            f"Expected embed_texts to be called 2 times (batched), got {call_count['n']}",
        )


if __name__ == "__main__":
    unittest.main()
