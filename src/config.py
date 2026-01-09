from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

ROOT = Path(__file__).resolve().parent.parent   # project root
ENV_PATH = ROOT / ".env"
print(ENV_PATH)
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # REQUIRED
    pinecone_api_key: str
    gemini_api_key: str

    # Paths (ABSOLUTE by default)
    # sqlite_path: str = str(ROOT / "data" / "contractrag.db")
    sqlite_path: str = os.getenv("SQLITE_PATH", str(ROOT / "data" / "contractrag.db"))
    raw_data_dir: str = str(ROOT / "data" / "raw")

    # Pinecone
    # pinecone_index_name: str = "contractiq-v1"
    pinecone_index_name: str = "contractiq-384"
    pinecone_namespace: str = "cuad-chunks-v2"
    pinecone_metric: str = "cosine"

    # Needed only if you want the script to auto-create an index:
    pinecone_cloud: str | None = "aws"   # e.g. "gcp" or "aws"
    pinecone_region: str | None =  "us-east-1" # e.g. "us-central1" (must match Pinecone options)

    # Embeddings (local default)
    local_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    force_cpu: bool = True
    embed_batch_size: int = 64

    # Chunking
    chunk_size: int = 1200
    chunk_overlap: int = 200

    # Gemini generation
    gemini_model: str = "gemini-2.5-flash"

settings = Settings()
