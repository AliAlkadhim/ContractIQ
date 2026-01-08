import os
from typing import List, Dict
from sqlalchemy import text
from config import settings
from db import get_conn

from pinecone import Pinecone

# Force CPU if needed (prevents accidental CUDA usage)
if settings.force_cpu:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""


def doc_titles_map():
    with get_conn() as conn:
        rows = conn.execute(text("SELECT doc_id, title FROM documents")).fetchall()
    return {r[0]: r[1] for r in rows}


def load_local_embedder():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(settings.local_embedding_model, device="cpu")
    dim = model.get_sentence_embedding_dimension()
    return model, dim


def fetch_chunk_batch(after_rowid: int, limit: int) -> List[Dict]:
    # We use sqlite rowid for paging: fast + simple.
    sql = """
    SELECT rowid, chunk_id, doc_id, chunk_index, start_char, end_char, text
    FROM chunks
    WHERE rowid > :after
    ORDER BY rowid
    LIMIT :limit
    """
    with get_conn() as conn:
        rows = conn.execute(text(sql), {"after": after_rowid, "limit": limit}).fetchall()
    return [dict(r._mapping) for r in rows]


def main():
    embedder, dim = load_local_embedder()
    print("Local embedding dim:", dim)

    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = pc.Index(settings.pinecone_index_name)

    # Iterate chunks and upsert in batches
    last_rowid = 0
    total = 0
    BATCH = settings.embed_batch_size

    titles = doc_titles_map()

    while True:
        batch = fetch_chunk_batch(last_rowid, BATCH)
        if not batch:
            break

        texts = [r["text"] for r in batch]
        vecs = embedder.encode(texts, batch_size=min(64, BATCH), normalize_embeddings=True)

        vectors = []
        for r, v in zip(batch, vecs):
            vectors.append(
                {
                    "id": r["chunk_id"],
                    "values": v.tolist(),
                    "metadata": {
                        "title": titles.get(r["doc_id"], ""),
                        "doc_id": r["doc_id"],
                        "chunk_index": r["chunk_index"],
                        "start_char": r["start_char"],
                        "end_char": r["end_char"],
                        "source": "cuad-v1",
                    },
                }
            )

        # Upsert = insert if new, replace if existing
        index.upsert(vectors=vectors, namespace=settings.pinecone_namespace)

        last_rowid = batch[-1]["rowid"]
        total += len(batch)
        print(f"upserted {total} chunks... last_rowid={last_rowid}")

    print(f"✅ Upsert complete. total_chunks={total}")


if __name__ == "__main__":
    main()
