from typing import Optional, Dict, List
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config import settings
from src.retrieval import pinecone_query
from src.documents import fetch_chunks_by_ids


llm = ChatGoogleGenerativeAI(
    model=settings.gemini_model,
    temperature=0.0,
    google_api_key=settings.gemini_api_key,
)

import json
from typing import Optional, Dict, Any

def build_prompt_json(question: str, chunks: list[dict]) -> str:
    ctx = "\n---\n".join([f"[chunk_id={c['chunk_id']}]\n{c['text']}" for c in chunks])

    return f"""
You are a careful contract analyst.

Use ONLY the provided chunks.
Do NOT repeat or paraphrase the chunks.

Your response MUST be valid JSON.
Your response MUST start with '{{' and end with '}}'.
No markdown, no extra text.

Return JSON exactly with this schema:
{{
  "answer": "string",
  "citations": [
    {{
      "chunk_id": "string",
      "quote": "string",
      "answer_span": "string"
    }}
  ]
}}

If the answer is not present in the chunks, return:
{{"answer":"NOT FOUND","citations":[]}}

Rules for citations:
- chunk_id must be one of the provided chunk_ids.
- quote must be copied verbatim from the chunk.
- answer_span must be an exact substring of quote.

Question: {question}

Chunks:
{ctx}
""".strip()



def extract_first_json_object(s: str) -> dict:
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model output.")
    return json.loads(s[start:end+1])


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



def build_prompt_2(question: str, chunks: list[dict]) -> str:
    ctx = "\n---\n".join([f"[chunk_id={c['chunk_id']}]\n{c['text']}" for c in chunks])
    return f"""
Answer the question using ONLY the chunks below.
If you cannot find the answer in the chunks, say: I cannot find the answer in the provided text.

When you answer, include the chunk_id(s) you relied on at the end like:
CITATIONS: chunk_id1, chunk_id2

Question: {question}

Chunks:
{ctx}
""".strip()


# def rag_answer(question: str, *, doc_id: Optional[str] = None, top_k: int = 8, debug: bool = False) -> Dict:
#     # 1) Retrieve
#     res = pinecone_query(question, top_k=top_k, doc_id=doc_id)
#     matches = res.get("matches", []) 
#     # if isinstance(res, dict) else []

#     retrieved_ids = [m["id"] for m in matches]
#     chunks = fetch_chunks_by_ids(retrieved_ids)

#     chunk_map = {c["chunk_id"]: c for c in chunks}
#     ordered_chunks = [chunk_map[cid] for cid in retrieved_ids if cid in chunk_map]

#     # 2) Generate (LangChain)
#     prompt = build_prompt(question, ordered_chunks)
#     ai_msg = llm.invoke(prompt)          # LangChain call
#     answer_text = ai_msg.content         # plain string

#     return {
#         "answer": answer_text,
#         "retrieved_chunk_ids": retrieved_ids,
#         "doc_id_filter": doc_id,
#         "debug": {"matches": matches} if debug else None,
#     }

def build_prompt_plain(question: str, chunks: list[dict]) -> str:
    ctx = "\n---\n".join([f"[chunk_id={c['chunk_id']}]\n{c['text']}" for c in chunks])
    return (
        "Answer using ONLY the chunks. If not found, say you cannot find it.\n\n"
        f"Question: {question}\n\nChunks:\n{ctx}"
    )

def build_prompt_json_relaxed(question: str, chunks: list[dict]) -> str:
    ctx = "\n---\n".join([f"[chunk_id={c['chunk_id']}]\n{c['text']}" for c in chunks])

    return f"""
You are a careful contract analyst.

Use ONLY the provided chunks.

Your response MUST be valid JSON and MUST start with {{ and end with }}.

Schema:
{{
  "answer": "string",
  "citations": [
    {{"chunk_id":"string","quote":"string","answer_span":"string"}}
  ]
}}

VERY IMPORTANT:
- Try hard to answer. Only return NOT FOUND if there is truly no relevant text.
- If the question asks for a value (like governing law), return the exact value as answer_span.

Question: {question}

Chunks:
{ctx}
""".strip()


def rag_answer(question: str, *, doc_id: Optional[str] = None, top_k: int = 8, debug: bool = False) -> Dict[str, Any]:
    # 1) Retrieve
    res = pinecone_query(question, top_k=top_k, doc_id=doc_id)
    matches = res.get("matches", [])# if isinstance(res, dict) else []
    print("MATCHES:", matches)
    retrieved_ids = [m["id"] for m in matches]

    # 2) Fetch chunk text (your ordered fetch_chunks_by_ids is perfect)
    chunks = fetch_chunks_by_ids(retrieved_ids)

    # 3) Generate
    prompt = build_prompt_2(question, chunks)
    ai_msg = llm.invoke(prompt)
    answer_text = ai_msg.content if hasattr(ai_msg, "content") else str(ai_msg)

    return {
        "answer": answer_text,
        "citations": [],  # keep empty for now (UI will show "No citations")
        "retrieved_chunk_ids": retrieved_ids,
        "doc_id_filter": doc_id,
        "debug": {"matches": matches} if debug else None,
    }


if __name__=="__main__":
    rag_answer("what is the date")