from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Accept upper-case env vars (Cloud Run / deploy.sh)
    pinecone_api_key: str = Field(validation_alias="PINECONE_API_KEY")
    gemini_api_key: str = Field(validation_alias="GEMINI_API_KEY")

    # Let Cloud Run override DB path
    sqlite_path: str = Field(default=str(ROOT / "data" / "contractrag.db"), validation_alias="SQLITE_PATH")

    raw_data_dir: str = str(ROOT / "data" / "raw")
    
    pinecone_index_name: str = "contractiq-384"
    pinecone_namespace: str = "cuad-chunks-v2"
    pinecone_metric: str = "cosine"

    local_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    force_cpu: bool = True
    embed_batch_size: int = 64

    chunk_size: int = 1200
    chunk_overlap: int = 200

    gemini_model: str = "gemini-2.5-flash"

settings = Settings()

    
