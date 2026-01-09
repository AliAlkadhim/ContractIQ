from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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
            "citations": citations
        },
    )
