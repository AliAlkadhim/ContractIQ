from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from google.cloud import storage

from src.config import settings
from src.documents import list_documents
from src.rag import rag_answer


# --- Paths (project-root based) ---
ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"

app = FastAPI()


# --- Static + templates ---
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _parse_gs_uri(gs_uri: str) -> tuple[str, str]:
    """
    Parse gs://bucket/path/to/object into (bucket, object).
    (Optional alternative to using GCS_DB_BUCKET + GCS_DB_OBJECT.)
    """
    u = urlparse(gs_uri)
    if u.scheme != "gs":
        raise ValueError(f"Expected gs://... URI, got: {gs_uri}")
    bucket = u.netloc
    obj = u.path.lstrip("/")
    if not bucket or not obj:
        raise ValueError(f"Invalid gs uri: {gs_uri}")
    return bucket, obj


def _maybe_download_sqlite_db():
    """
    Cloud Run mode:
      - deploy.sh sets SQLITE_PATH=/tmp/contractrag.db
      - deploy.sh sets GCS_DB_BUCKET and GCS_DB_OBJECT
      - this downloads gs://bucket/object -> SQLITE_PATH if file missing/empty

    Local mode:
      - no GCS_* env vars => no-op; app uses local settings.sqlite_path
    """
    dest = Path(settings.sqlite_path)

    # If DB is already present and non-empty, don't download.
    if dest.exists() and dest.stat().st_size > 0:
        return

    # Source of DB in GCS (matches your deploy.sh)
    bucket = os.getenv("GCS_DB_BUCKET")
    obj = os.getenv("GCS_DB_OBJECT")

    # Optional alternative: allow a single URI env var
    gs_uri = os.getenv("CONTRACTIQ_DB_GCS_URI")
    if (not bucket or not obj) and gs_uri:
        bucket, obj = _parse_gs_uri(gs_uri)

    # If nothing configured, do nothing (local dev).
    if not bucket or not obj:
        return

    dest.parent.mkdir(parents=True, exist_ok=True)

    client = storage.Client()
    b = client.bucket(bucket)
    blob = b.blob(obj)
    blob.download_to_filename(str(dest))

    if not dest.exists() or dest.stat().st_size == 0:
        raise RuntimeError("SQLite DB download failed or produced an empty file.")


@app.on_event("startup")
def startup_event():
    _maybe_download_sqlite_db()


def highlight_quote(quote: str, answer_span: str) -> Markup:
    """
    Safely HTML-escape the quote, then wrap answer_span with <mark> if present.
    You can keep this even if you don't show citations right now.
    """
    q = escape(quote)
    if answer_span:
        a = escape(answer_span)
        return Markup(str(q).replace(str(a), f"<mark>{a}</mark>", 1))
    return Markup(q)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    docs = list_documents(limit=200)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "docs": docs,
        },
    )


@app.post("/ask", response_class=HTMLResponse)
def ask(
    request: Request,
    question: str = Form(...),
    doc_id: Optional[str] = Form(None),
    top_k: int = Form(12),
):
    doc_id = doc_id or None

    resp = rag_answer(
        question,
        doc_id=doc_id,
        top_k=top_k,
        debug=False,
    )

    # If citations come back in the future, keep safe HTML highlighting.
    raw_citations = resp.get("citations", []) or []
    citations = []
    for c in raw_citations:
        quote = c.get("quote", "")
        span = c.get("answer_span", "")
        citations.append(
            {
                "chunk_id": c.get("chunk_id", ""),
                "quote_html": highlight_quote(quote, span),
            }
        )

    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "question": question,
            "doc_id": doc_id,
            "answer": resp.get("answer", ""),
            "sources": resp.get("sources", []),
            "citations": citations,  # ok if template ignores
        },
    )
