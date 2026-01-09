from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


import os

from google.cloud import storage

from src.documents import list_documents
from src.rag import rag_answer  # or rag_answer if you prefer

# --- Paths (absolute, so it works from anywhere: notebook, root, docker, cloud) ---
ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"

app = FastAPI()

# Static files (CSS)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

def _maybe_download_sqlite_db():
    sqlite_path = os.getenv("SQLITE_PATH", "") or ""
    if not sqlite_path:
        return  # fall back to config default

    p = Path(sqlite_path)
    if p.exists() and p.stat().st_size > 0:
        return

    bucket = os.getenv("GCS_DB_BUCKET")
    obj = os.getenv("GCS_DB_OBJECT")
    if not bucket or not obj:
        raise RuntimeError(
            "SQLITE_PATH set but GCS_DB_BUCKET / GCS_DB_OBJECT not set. "
            "Set them to download the populated SQLite DB from GCS."
        )

    p.parent.mkdir(parents=True, exist_ok=True)

    client = storage.Client()
    b = client.bucket(bucket)
    blob = b.blob(obj)
    blob.download_to_filename(str(p))

@app.on_event("startup")
def startup_event():

    
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/healthz")
def healthz():
    return {"ok": True}

from markupsafe import Markup, escape

def highlight_quote(quote: str, answer_span: str) -> Markup:
    """
    Safely HTML-escape the quote, then wrap answer_span with <mark> if present.
    """
    q = escape(quote)
    if answer_span:
        a = escape(answer_span)
        # highlight first occurrence
        return Markup(str(q).replace(str(a), f"<mark>{a}</mark>", 1))
    return Markup(q)



@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    docs = list_documents(limit=200)  # keep small-ish for UI
    # docs should be list[{"doc_id":..., "title":...}]
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
    # Normalize doc_id: HTML forms sometimes send "" for empty selection
    doc_id = doc_id or None

    resp = rag_answer(
        question,
        doc_id=doc_id,
        top_k=top_k,
        debug=False,
    )

    raw_citations = resp.get("citations", [])
    citations = []
    for c in raw_citations:
        quote = c.get("quote", "")
        span = c.get("answer_span", "")
        citations.append({
            "chunk_id": c.get("chunk_id", ""),
            "quote_html": highlight_quote(quote, span),
        })


    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "question": question,
            "doc_id": doc_id,
            "answer": resp.get("answer", ""),
            # "citations": resp.get("citations", []),
            "sources": resp.get("sources", []),
            "citations": citations
        },
    )
