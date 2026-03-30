import re
from typing import List, Dict, Optional

# Detect contract section headings in multiple common formats:
#   "1. Term", "1.1 Fees", "12.3.4 Clause"   — numbered
#   "SECTION 2"                                — explicit SECTION keyword
#   "Article 5", "ARTICLE IV"                  — Article + number or Roman numeral
#   "§ 12.3"                                   — section symbol
#   "Schedule A", "Exhibit B"                  — schedules and exhibits (mixed or upper case)
#   "TERMINATION", "LIMITATION OF LIABILITY"   — ALL CAPS headings (≥5 chars)
SECTION_RE = re.compile(
    r"^\s*("
    r"(\d+(\.\d+)*\.?\s+)"                                 # "1. ", "1 ", "1.1 ", "12.3.4 "
    r"|SECTION\s+\d+"                                     # "SECTION 2"
    r"|Article\s+\d+"                                     # "Article 5"  (title-case)
    r"|ARTICLE\s+([IVXivx]+|\d+)"                         # "ARTICLE IV", "ARTICLE 4"
    r"|§\s*\d+(\.\d+)*"                                   # "§ 12.3"
    r"|(Schedule|Exhibit|SCHEDULE|EXHIBIT)\s+[A-Za-z0-9]" # "Schedule A", "Exhibit B"
    r"|[A-Z][A-Z\s]{4,}"                                  # "TERMINATION", "LIMITATION OF LIABILITY"
    r")"
)

# Sentence boundary for fallback splits (avoid mid-sentence cuts)
SENTENCE_END_RE = re.compile(r"[.!?]\s+")

# Max chars per chunk (before overlap is applied)
DEFAULT_MAX_CHARS = 1800

# Characters from the end of the previous chunk to prepend to the next chunk
OVERLAP_CHARS = 200


def _split_at_sentence(t: str, max_len: int) -> tuple[str, str]:
    """Split text at last sentence boundary before max_len. Returns (before, after)."""
    if len(t) <= max_len:
        return t, ""
    window = t[: max_len + 1]
    match = None
    for m in SENTENCE_END_RE.finditer(window):
        match = m
    if match:
        end = match.end()
        return t[:end].strip(), t[end:].strip()
    return t[:max_len].strip(), t[max_len:].strip()


def _split_large_chunk(
    chunk: Dict[str, Optional[str]], max_chars: int
) -> List[Dict[str, Optional[str]]]:
    """Break one chunk into smaller ones by paragraph then sentence, avoiding mid-sentence cuts."""
    section = chunk["section"] or "UNKNOWN"
    text = chunk["text"]
    if len(text) <= max_chars:
        return [chunk]

    out: List[Dict[str, Optional[str]]] = []
    parts = re.split(r"\n\s*\n", text)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        while len(part) > max_chars:
            before, after = _split_at_sentence(part, max_chars)
            title = section if not out else f"{section} (cont.)"
            out.append({"section": title, "text": before})
            part = after
        if part:
            title = section if not out else f"{section} (cont.)"
            out.append({"section": title, "text": part})
    return out if out else [chunk]


def chunk_text(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> List[Dict]:
    """
    Split contract text into clause/section chunks.

    - Starts a new chunk at recognised section headings.
    - Keeps chunks under max_chars; splits at sentence boundaries when forced.
    - Adds ~200-char overlap from the previous chunk to preserve cross-boundary context.
    - Adds a 'chunk_index' field (0-based position in the document) to each chunk.

    Returns list of dicts: {"section": str, "text": str, "chunk_index": int}
    """
    lines = [ln.strip() for ln in text.splitlines()]
    chunks: List[Dict[str, Optional[str]]] = []
    current_lines: List[str] = []
    current_title: Optional[str] = None

    def flush(extra_lines: Optional[List[str]] = None):
        nonlocal current_lines, current_title
        if current_lines:
            chunk_body = "\n".join(current_lines).strip()
            if chunk_body:
                chunks.append({"section": current_title or "UNKNOWN", "text": chunk_body})
        current_lines = list(extra_lines) if extra_lines else []
        if not extra_lines:
            current_title = None

    for ln in lines:
        if not ln:
            continue

        # New section header detected
        if SECTION_RE.match(ln) and len(ln) <= 80:
            flush()
            current_title = ln
            current_lines.append(ln)
        else:
            current_lines.append(ln)

        # Enforce max size: split at sentence boundary
        while sum(len(x) for x in current_lines) > max_chars:
            text_so_far = "\n".join(current_lines)
            before, after = _split_at_sentence(text_so_far, max_chars)
            if before:
                chunks.append({"section": current_title or "UNKNOWN", "text": before})
            if not after:
                current_lines = []
                current_title = None
                break
            current_lines = [after] if after else []

    flush()

    # Fallback: split any oversized chunk by paragraph/sentence
    raw: List[Dict[str, Optional[str]]] = []
    for c in chunks:
        if len(c["text"] or "") > max_chars:
            raw.extend(_split_large_chunk(c, max_chars))
        else:
            raw.append(c)

    # Apply chunk overlap and assign chunk_index
    # Each chunk i > 0 gets the last OVERLAP_CHARS of chunk i-1 prepended,
    # starting at a sentence boundary where possible.  This prevents context
    # loss at chunk boundaries and improves retrieval quality.
    final: List[Dict] = []
    for idx, c in enumerate(raw):
        body = c["text"]
        if idx > 0 and final:
            prev_text = final[-1]["text"]
            # Take the last OVERLAP_CHARS of the previous chunk
            tail = prev_text[-OVERLAP_CHARS:] if len(prev_text) > OVERLAP_CHARS else prev_text
            # Advance to the next sentence boundary inside the tail so we don't
            # start in the middle of a sentence
            m = SENTENCE_END_RE.search(tail)
            if m:
                tail = tail[m.end():]
            if tail.strip():
                body = tail.strip() + "\n" + body
        final.append({"section": c["section"], "text": body, "chunk_index": idx})

    return final
