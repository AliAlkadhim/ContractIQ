from typing import Optional, Dict, List
from langchain_google_genai import ChatGoogleGenerativeAI

from config import settings
from retrieval import pinecone_query
from documents import fetch_chunks_by_ids


llm = ChatGoogleGenerativeAI(
    model=settings.gemini_model,
    temperature=0.0,
    google_api_key=settings.gemini_api_key,
)


def build_prompt(question: str, contexts: List[Dict]) -> str:
    ctx_block = []
    for c in contexts:
        ctx_block.append(f"[chunk_id={c['chunk_id']}]\n{c['text']}\n")
    joined = "\n---\n".join(ctx_block)

    return f"""
You are a careful contract analyst.
Answer the question using ONLY the provided chunks.
If you cannot find the answer, say you cannot find it in the provided text.

Question: {question}

Chunks:
{joined}

Return:
1) Answer (1-3 sentences)
2) Citations: list of chunk_id(s) you used
""".strip()


def rag_answer(question: str, *, doc_id: Optional[str] = None, top_k: int = 8, debug: bool = False) -> Dict:
    # 1) Retrieve
    res = pinecone_query(question, top_k=top_k, doc_id=doc_id)
    matches = res.get("matches", []) 
    # if isinstance(res, dict) else []

    retrieved_ids = [m["id"] for m in matches]
    chunks = fetch_chunks_by_ids(retrieved_ids)

    chunk_map = {c["chunk_id"]: c for c in chunks}
    ordered_chunks = [chunk_map[cid] for cid in retrieved_ids if cid in chunk_map]

    # 2) Generate (LangChain)
    prompt = build_prompt(question, ordered_chunks)
    ai_msg = llm.invoke(prompt)          # LangChain call
    answer_text = ai_msg.content         # plain string

    return {
        "answer": answer_text,
        "retrieved_chunk_ids": retrieved_ids,
        "doc_id_filter": doc_id,
        "debug": {"matches": matches} if debug else None,
    }

