import hashlib
from typing import List, Dict


def make_chunk_id(doc_id: str, chunk_index: int, start_char: int, end_char: int) -> str:
    raw = f"{doc_id}::{chunk_index}::{start_char}::{end_char}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def chunk_text(text: str, *, chunk_size: int, chunk_overlap: int) -> List[Dict]:
    """
    Simple character chunking:
    - chunk_size: max characters per chunk
    - chunk_overlap: how many chars to overlap between chunks
    Returns: list of dicts: {chunk_index, start_char, end_char, text}
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >=0 and < chunk_size")

    chunks = []
    n = len(text)
    start = 0
    i = 0

    while start < n:
        end = min(start + chunk_size, n)
        chunks.append(
            {
                "chunk_index": i,
                "start_char": start,
                "end_char": end,
                "text": text[start:end],
            }
        )
        if end == n:
            break
        start = end - chunk_overlap
        i += 1

    return chunks
