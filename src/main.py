from fastapi import FastAPI
from pydantic import BaseModel
from documents import list_documents
from rag import rag_answer

app = FastAPI(title="ContractIQ")


class ChatReq(BaseModel):
    question: str
    doc_id: str | None = None
    top_k: int = 8
    debug: bool = False


@app.get("/documents")
def docs(limit: int = 10, offset: int = 0, q: str | None = None):
    return list_documents(limit=limit, offset=offset, q=q)


@app.post("/chat")
def chat(req: ChatReq):
    return rag_answer(req.question, doc_id=req.doc_id, top_k=req.top_k, debug=req.debug)
