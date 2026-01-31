import re
from typing import List, Dict, Optional

# Detect headings like:
# "1. Term", "1.1 Fees", "SECTION 2", "TERMINATION", "LIMITATION OF LIABILITY"
SECTION_RE = re.compile(r"^\s*((\d+(\.\d+)*)\s+|SECTION\s+\d+|[A-Z][A-Z\s]{4,})")

# Sentence boundary for fallback splits (avoid mid-sentence cuts)
SENTENCE_END_RE = re.compile(r"[.!?]\s+")

# Max chars per chunk
DEFAULT_MAX_CHARS = 1800


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


def _split_large_chunk(chunk: Dict[str, Optional[str]], max_chars: int) -> List[Dict[str, Optional[str]]]:
    """Break one chunk into smaller ones by paragraph then sentence, avoiding mid-sentence cuts."""
    section = chunk["section"] or "UNKNOWN"
    text = chunk["text"]
    if len(text) <= max_chars:
        return [chunk]

    out: List[Dict[str, Optional[str]]] = []
    # First split by double newline (paragraphs)
    parts = re.split(r"\n\s*\n", text)
    for i, part in enumerate(parts):
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


def chunk_text(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> List[Dict[str, Optional[str]]]:
    """
    Split text into clause/section chunks.
    - Starts a new chunk when it hits a likely section header.
    - Keeps chunks under max_chars; when flushing by size, splits at sentence boundary.
    - Fallback: chunks with no section headers are split by paragraph (double newline), then by sentence.
    """
    lines = [ln.strip() for ln in text.splitlines()]
    chunks: List[Dict[str, Optional[str]]] = []
    current_lines: List[str] = []
    current_title: Optional[str] = None

    def flush(extra_lines: Optional[List[str]] = None):
        nonlocal current_lines, current_title
        if current_lines:
            chunk = "\n".join(current_lines).strip()
            if chunk:
                chunks.append({"section": current_title or "UNKNOWN", "text": chunk})
        current_lines = list(extra_lines) if extra_lines else []
        if not extra_lines:
            current_title = None

    for ln in lines:
        if not ln:
            continue

        # New section header
        if SECTION_RE.match(ln) and len(ln) <= 80:
            flush()
            current_title = ln
            current_lines.append(ln)
        else:
            current_lines.append(ln)

        # Enforce max size: try to split at sentence boundary
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
            # keep current_title for the continuation

    flush()

    # Fallback: split any oversized chunk by paragraph/sentence
    result: List[Dict[str, Optional[str]]] = []
    for c in chunks:
        if len(c["text"] or "") > max_chars:
            result.extend(_split_large_chunk(c, max_chars))
        else:
            result.append(c)
    return result