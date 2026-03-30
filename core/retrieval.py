"""
Retrieval over contract chunks for risk review.
Uses semantic similarity so the LLM sees the most relevant clauses per risk category.
"""
from core.embeddings import embed_texts

# Risk-category queries — retrieved chunks surface the most relevant contract clauses.
RISK_QUERIES = [
    # Original 8
    "limitation of liability and liability cap",
    "indemnity and indemnification",
    "termination for convenience and auto-renewal",
    "data privacy security and GDPR",
    "payment terms fees and pricing",
    "warranties service level agreement SLA",
    "confidentiality and non-disclosure",
    "insurance and compliance",
    # Added 7
    "intellectual property ownership and work for hire and deliverables",
    "force majeure and business continuity and acts of god",
    "dispute resolution arbitration and governing law and jurisdiction",
    "assignment change of control and acquisition and merger",
    "audit rights and inspection and record keeping",
    "non-solicitation of employees and no-hire clauses",
    "subcontracting and third party processors and data sharing",
]


def _dot(a: list, b: list) -> float:
    """Dot product of two vectors (embeddings are L2-normalised, so equals cosine similarity)."""
    return sum(x * y for x, y in zip(a, b))


# Max chars sent to the LLM to avoid context/overflow errors.
EVIDENCE_MAX_CHARS = 14_000


def retrieve_evidence_for_risk(
    chunks: list,
    top_k_per_query: int = 5,
    max_chars: int = EVIDENCE_MAX_CHARS,
) -> str:
    """
    From the current document's chunks, retrieve the most relevant clauses for risk review
    by running semantic search with risk-themed queries.

    Improvements over the original:
    - All query embeddings are computed in a single embed_texts() call (faster, one model pass).
    - Each evidence chunk is prefixed with its section title so the LLM knows the source.
    - Results are deduplicated by chunk index.
    - Concatenated evidence is capped at max_chars.
    """
    if not chunks:
        return ""

    texts = [c["text"] for c in chunks]

    # Embed all document chunks in one pass
    chunk_embs = embed_texts(texts)

    # Embed ALL risk queries in a single batch call (instead of one call per query)
    query_embs = embed_texts(RISK_QUERIES)

    evidence_indices: set[int] = set()
    for q_emb in query_embs:
        scores = [_dot(q_emb, ce) for ce in chunk_embs]
        top_indices = sorted(range(len(scores)), key=lambda i: -scores[i])[:top_k_per_query]
        evidence_indices.update(top_indices)

    evidence_chunks = [chunks[i] for i in sorted(evidence_indices)]

    # Prefix each chunk with its section title so the LLM knows where it came from
    parts = []
    for c in evidence_chunks:
        section = c.get("section") or "UNKNOWN"
        parts.append(f"[SECTION: {section}]\n{c['text']}")

    out = "\n\n".join(parts)
    if len(out) > max_chars:
        out = out[:max_chars] + "\n\n[... text truncated to fit model context ...]"
    return out
