import os
import threading
from typing import List, Dict, Optional

from pinecone import Pinecone
from src.config import settings

if settings.force_cpu:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""

# Where the Dockerfile bakes the model
LOCAL_MODEL_DIR = "/app/models/all-MiniLM-L6-v2"

_EMBEDDER = None
_EMBEDDER_LOCK = threading.Lock()


def load_local_embedder():
    """
    Load the sentence-transformers embedder without any network calls.

    We prefer the baked local directory (LOCAL_MODEL_DIR). If it's not present,
    we fall back to settings.local_embedding_model (which might be a HF repo id),
    but in Cloud Run you *want* the baked dir to exist so this never hits HF.
    """
    from sentence_transformers import SentenceTransformer

    model_path = LOCAL_MODEL_DIR if os.path.isdir(LOCAL_MODEL_DIR) else settings.local_embedding_model

    # Try to force local-only loading when possible.
    # (Different versions of sentence-transformers may accept different kwargs.)
    try:
        return SentenceTransformer(model_path, device="cpu", local_files_only=True, token=False)
    except TypeError:
        # Older versions may not accept token/local_files_only here;
        # loading from a local folder path should still be offline-safe.
        return SentenceTransformer(model_path, device="cpu", local_files_only=True)


def embed_query(q: str) -> List[float]:
    global _EMBEDDER
    if _EMBEDDER is None:
        with _EMBEDDER_LOCK:
            if _EMBEDDER is None:
                _EMBEDDER = load_local_embedder()

    v = _EMBEDDER.encode([q], normalize_embeddings=True)[0]
    return [float(x) for x in v]


def pinecone_query(query: str, *, top_k: int = 8, doc_id: Optional[str] = None) -> Dict:
    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = pc.Index(settings.pinecone_index_name)

    vec = embed_query(query)

    flt = None
    if doc_id is not None:
        flt = {"doc_id": {"$eq": doc_id}}

    res = index.query(
        namespace=settings.pinecone_namespace,
        vector=vec,
        top_k=top_k,
        include_metadata=True,
        filter=flt,
    )
    return res
