"""
Retrieval over contract chunks for risk review.
Uses semantic similarity so the LLM sees the most relevant clauses per risk category.
"""
from core.embeddings import embed_texts

# Queries that target common risk categories; we retrieve top chunks per query.
RISK_QUERIES = [
    "limitation of liability and liability cap",
    "indemnity and indemnification",
    "termination for convenience and auto-renewal",
    "data privacy security and GDPR",
    "payment terms fees and pricing",
    "warranties service level agreement SLA",
    "confidentiality and non-disclosure",
    "insurance and compliance",
]


def _dot(a: list, b: list) -> float:
    """Dot product of two vectors (embeddings are L2-normalized, so this is cosine similarity)."""
    return sum(x * y for x, y in zip(a, b))


# Max chars sent to the LLM to avoid context/overflow errors (Ollama typical limit ~4k–8k tokens).
EVIDENCE_MAX_CHARS = 14_000


def retrieve_evidence_for_risk(chunks: list, top_k_per_query: int = 5, max_chars: int = EVIDENCE_MAX_CHARS) -> str:
    """
    From the current document's chunks, retrieve the most relevant clauses for risk review
    by running semantic search with risk-themed queries. Dedupes and returns concatenated text.
    Capped at max_chars so the prompt fits within Ollama's context.
    """
    if not chunks:
        return ""

    texts = [c["text"] for c in chunks]
    chunk_embs = embed_texts(texts)

    evidence_indices = set()
    for query in RISK_QUERIES:
        q_emb = embed_texts([query])[0]
        scores = [_dot(q_emb, ce) for ce in chunk_embs]
        top_indices = sorted(range(len(scores)), key=lambda i: -scores[i])[:top_k_per_query]
        evidence_indices.update(top_indices)

    evidence_chunks = [chunks[i] for i in sorted(evidence_indices)]
    out = "\n\n".join(c["text"] for c in evidence_chunks)
    if len(out) > max_chars:
        out = out[:max_chars] + "\n\n[... text truncated to fit model context ...]"
    return out
