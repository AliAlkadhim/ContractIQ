import os
from typing import List, Dict, Optional
from pinecone import Pinecone
from config import settings

if settings.force_cpu:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""


def load_local_embedder():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(settings.local_embedding_model, device="cpu")
    return model


_EMBEDDER = None


def embed_query(q: str) -> List[float]:
    global _EMBEDDER
    if _EMBEDDER is None:
        _EMBEDDER = load_local_embedder()
    v = _EMBEDDER.encode([q], normalize_embeddings=True)[0]
    v = [float(x) for x in v]
    return v


def pinecone_query(query: str, *, top_k: int = 8, doc_id: Optional[str] = None) -> Dict:
    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = pc.Index(settings.pinecone_index_name)

    vec = embed_query(query)

    flt = None
    if doc_id is not None:
        # Pinecone metadata filter (doc_id == ...)
        flt = {"doc_id": {"$eq": doc_id}}

    res = index.query(
        namespace=settings.pinecone_namespace,
        vector=vec,
        top_k=top_k,
        include_metadata=True,
        filter=flt,
    )
    return res
