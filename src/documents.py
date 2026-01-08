import hashlib
import json
from pathlib import Path
from typing import Optional, List, Dict
from sqlalchemy import text

from config import settings
from db import get_conn


def make_doc_id(title: str) -> str:
    return hashlib.sha256(title.encode("utf-8")).hexdigest()[:16]


def list_documents(limit: int = 10, offset: int = 0, q: Optional[str] = None) -> List[Dict]:
    sql = """
    SELECT doc_id, title, source, raw_path
    FROM documents
    {where}
    ORDER BY title
    LIMIT :limit OFFSET :offset
    """
    where = ""
    params = {"limit": limit, "offset": offset}
    if q:
        where = "WHERE title LIKE :q"
        params["q"] = f"%{q}%"

    with get_conn() as conn:
        rows = conn.execute(text(sql.format(where=where)), params).fetchall()

    return [dict(r._mapping) for r in rows]


def fetch_chunks_for_doc(doc_id: str, limit: int = 20) -> List[Dict]:
    sql = """
    SELECT chunk_id, doc_id, chunk_index, start_char, end_char, text
    FROM chunks
    WHERE doc_id = :doc_id
    ORDER BY chunk_index
    LIMIT :limit
    """
    with get_conn() as conn:
        rows = conn.execute(text(sql), {"doc_id": doc_id, "limit": limit}).fetchall()
    return [dict(r._mapping) for r in rows]


def fetch_chunks_by_ids(chunk_ids: List[str]) -> List[Dict]:
    """
    Safe IN-clause with named parameters.
    """
    if not chunk_ids:
        return []

    params = {}
    placeholders = []
    for i, cid in enumerate(chunk_ids):
        key = f"id{i}"
        params[key] = cid
        placeholders.append(f":{key}")

    sql = f"""
    SELECT chunk_id, doc_id, chunk_index, start_char, end_char, text
    FROM chunks
    WHERE chunk_id IN ({", ".join(placeholders)})
    """

    with get_conn() as conn:
        rows = conn.execute(text(sql), params).fetchall()
    # return [dict(r._mapping) for r in rows]
        by_id = {r[0]: r for r in rows}
    ordered = []
    for cid in chunk_ids:
        if cid in by_id:
            r = by_id[cid]
            ordered.append({
                "chunk_id": r[0],
                "doc_id": r[1],
                "chunk_index": int(r[2]),
                "start_char": int(r[3]),
                "end_char": int(r[4]),
                "text": r[5],
            })
    return ordered



def fetch_annotations_for_doc(doc_id: str, label_contains: Optional[str] = None, limit: int = 20) -> List[Dict]:
    sql = """
    SELECT annotation_id, doc_id, label, context, answer_texts_json, answer_starts_json
    FROM annotations
    WHERE doc_id = :doc_id
    {label_filter}
    ORDER BY label
    LIMIT :limit
    """
    label_filter = ""
    params = {"doc_id": doc_id, "limit": limit}
    if label_contains:
        label_filter = "AND label LIKE :label"
        params["label"] = f"%{label_contains}%"

    with get_conn() as conn:
        rows = conn.execute(text(sql.format(label_filter=label_filter)), params).fetchall()

    out = []
    for r in rows:
        d = dict(r._mapping)
        d["answer_texts"] = json.loads(d["answer_texts_json"])
        d["answer_starts"] = json.loads(d["answer_starts_json"])
        out.append(d)
    return out
