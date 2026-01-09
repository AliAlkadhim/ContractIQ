import json
from pathlib import Path
from typing import Dict, List, Tuple

from huggingface_hub import snapshot_download
from sqlalchemy import text

from src.config import settings
from src.db import init_schema, get_conn
from src.documents import make_doc_id
from src.chunking import chunk_text, make_chunk_id


REPO_ID = "theatticusproject/cuad"


def download_cuad_snapshot() -> Path:
    """
    Downloads HF dataset repo snapshot to data/raw/theatticusproject__cuad/
    """
    local_dir = Path(settings.raw_data_dir) / "theatticusproject__cuad"
    local_dir.mkdir(parents=True, exist_ok=True)

    snapshot_download(
        repo_id=REPO_ID,
        repo_type="dataset",
        local_dir=str(local_dir),
        local_dir_use_symlinks=False,
    )
    return local_dir


def index_txt_files(root: Path) -> Dict[str, Path]:
    """
    Map title -> txt path using CUAD_v1/full_contract_txt/**.txt
    """
    txt_root = root / "CUAD_v1" / "full_contract_txt"
    mapping = {}
    for p in txt_root.rglob("*.txt"):
        title = p.stem  # filename without .txt
        mapping[title] = p
    return mapping


def load_contract_text(txt_path: Path) -> str:
    # CUAD txts are plain; we keep it simple
    return txt_path.read_text(encoding="utf-8", errors="ignore")


def iter_cuad_annotations(root: Path):
    """
    Yields (title, paragraph_context, question, answers_list)
    answers_list: list of {"text": str, "answer_start": int}
    """
    json_path = root / "CUAD_v1" / "CUAD_v1.json"
    obj = json.loads(json_path.read_text(encoding="utf-8"))

    # SQuAD-like structure:
    # obj["data"] -> list of docs
    # doc["title"], doc["paragraphs"] -> each has "context" + "qas"
    for doc in obj.get("data", []):
        title = doc.get("title")
        for para in doc.get("paragraphs", []):
            context = para.get("context", "")
            for qa in para.get("qas", []):
                question = qa.get("question", "")
                answers = qa.get("answers", [])
                yield title, context, question, answers


def main():
    init_schema()

    root = download_cuad_snapshot()
    txt_map = index_txt_files(root)

    # 1) Insert documents + chunks (from full_contract_txt)
    inserted_docs = 0
    inserted_chunks = 0

    with get_conn() as conn:
        for title, txt_path in txt_map.items():
            doc_id = make_doc_id(title)

            # documents
            conn.execute(
                text("""
                INSERT OR IGNORE INTO documents (doc_id, title, source, raw_path)
                VALUES (:doc_id, :title, :source, :raw_path)
                """),
                {"doc_id": doc_id, "title": title, "source": "cuad-v1", "raw_path": str(txt_path)},
            )

            # chunks
            full_text = load_contract_text(txt_path)
            chunks = chunk_text(
                full_text,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )

            for ch in chunks:
                chunk_id = make_chunk_id(doc_id, ch["chunk_index"], ch["start_char"], ch["end_char"])
                conn.execute(
                    text("""
                    INSERT OR IGNORE INTO chunks
                    (chunk_id, doc_id, chunk_index, start_char, end_char, text)
                    VALUES (:chunk_id, :doc_id, :chunk_index, :start_char, :end_char, :text)
                    """),
                    {
                        "chunk_id": chunk_id,
                        "doc_id": doc_id,
                        "chunk_index": ch["chunk_index"],
                        "start_char": ch["start_char"],
                        "end_char": ch["end_char"],
                        "text": ch["text"],
                    },
                )

            inserted_docs += 1
            print(f"inserted docs: {inserted_docs}")
            inserted_chunks += len(chunks)
            print(f"inserted chunks: {inserted_chunks}")

    # 2) Insert annotations (from CUAD_v1.json)
    # Note: answer_start positions are relative to the paragraph "context" in CUAD_v1.json. :contentReference[oaicite:3]{index=3}
    inserted_anns = 0
    with get_conn() as conn:
        for title, context, question, answers in iter_cuad_annotations(root):
            if not title:
                continue
            doc_id = make_doc_id(title)

            # Normalize to lists
            answer_texts = []
            answer_starts = []
            for a in answers or []:
                t = a.get("text", "")
                s = a.get("answer_start", None)
                if t is not None and s is not None:
                    answer_texts.append(t)
                    answer_starts.append(int(s))

            annotation_id = make_doc_id(f"{doc_id}::{question}")  # reuse hash helper; good enough

            conn.execute(
                text("""
                INSERT OR IGNORE INTO annotations
                (annotation_id, doc_id, label, context, answer_texts_json, answer_starts_json)
                VALUES (:annotation_id, :doc_id, :label, :context, :answer_texts_json, :answer_starts_json)
                """),
                {
                    "annotation_id": annotation_id,
                    "doc_id": doc_id,
                    "label": question,  # CUAD question text as label
                    "context": context,
                    "answer_texts_json": json.dumps(answer_texts, ensure_ascii=False),
                    "answer_starts_json": json.dumps(answer_starts, ensure_ascii=False),
                },
            )
            inserted_anns += 1

    print(f"✅ Done. docs={inserted_docs} chunks={inserted_chunks} annotations={inserted_anns}")


if __name__ == "__main__":
    main()
