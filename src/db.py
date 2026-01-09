from contextlib import contextmanager
from sqlalchemy import create_engine, text
from src.config import settings

_ENGINE = None


def get_engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = create_engine(f"sqlite:///{settings.sqlite_path}", future=True)
    return _ENGINE


@contextmanager
def get_conn():
    engine = get_engine()
    with engine.begin() as conn:
        yield conn


def init_schema():
    ddl_documents = """
    CREATE TABLE IF NOT EXISTS documents (
        doc_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        source TEXT NOT NULL,
        raw_path TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """

    ddl_chunks = """
    CREATE TABLE IF NOT EXISTS chunks (
        chunk_id TEXT PRIMARY KEY,
        doc_id TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        start_char INTEGER NOT NULL,
        end_char INTEGER NOT NULL,
        text TEXT NOT NULL,
        FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
    );
    """

    ddl_annotations = """
    CREATE TABLE IF NOT EXISTS annotations (
        annotation_id TEXT PRIMARY KEY,
        doc_id TEXT NOT NULL,
        label TEXT NOT NULL,
        context TEXT,
        answer_texts_json TEXT NOT NULL,
        answer_starts_json TEXT NOT NULL,
        FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
    );
    """

    ddl_idx_1 = "CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);"
    ddl_idx_2 = "CREATE INDEX IF NOT EXISTS idx_ann_doc_id ON annotations(doc_id);"
    ddl_idx_3 = "CREATE INDEX IF NOT EXISTS idx_ann_label ON annotations(label);"

    with get_conn() as conn:
        conn.execute(text(ddl_documents))
        conn.execute(text(ddl_chunks))
        conn.execute(text(ddl_annotations))
        conn.execute(text(ddl_idx_1))
        conn.execute(text(ddl_idx_2))
        conn.execute(text(ddl_idx_3))
