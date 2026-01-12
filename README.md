# ContractIQ — Contract QA with RAG over CUAD (FastAPI • Pinecone • Gemini)

ContractIQ is an end-to-end **contract question-answering web app** that implements a **Retrieval-Augmented Generation (RAG)** workflow over the **Contract Understanding Atticus Dataset (CUAD)**. It retrieves relevant contract text chunks via **vector search (Pinecone)**, then uses **Gemini** to produce an answer grounded in the retrieved sources. The UI displays both the answer and the raw retrieved chunks so users can verify what the model saw.

- **CUAD dataset:** https://www.atticusprojectai.org/cuad  
- **CUAD paper (arXiv):** https://arxiv.org/abs/2103.06268  

---

## What it does

- Ask questions about contract terms (e.g., “What is the governing law?”, “What is the effective date?”, “What are the termination conditions?”).
- Optionally filter to a specific contract (doc_id) or search across all contracts.
- Uses a RAG pipeline: retrieve top-k relevant chunks, then generate an answer constrained to those chunks.
- Shows retrieved chunk text (“sources”) in the UI for transparency and easy auditing.

---

## Open the live web application here 👉 https://contractiq-313669223614.us-central1.run.app/

---

## How it works (technical overview)

### 1) UI → Backend request
The home page renders a contract selector and a question form. Submitting the form sends a POST request to `/ask` with:
- `question` (required)
- `doc_id` (optional; empty means search across all contracts)
- `top_k` (how many chunks to retrieve)

### 2) Embedding + retrieval (Pinecone)
ContractIQ embeds the user’s query using a local transformer embedding model (SentenceTransformers), producing a 384-dimensional vector. It then queries a Pinecone index to retrieve the nearest contract chunks.

Retrieval supports an optional metadata filter (`doc_id`) to reduce cross-document noise. Pinecone returns ranked matches with chunk IDs (and scores if included).

### 3) Chunk hydration (SQLite)
Pinecone returns chunk IDs, but the full chunk text is stored in a local SQLite database (`contractrag.db`). ContractIQ fetches chunk rows by ID and preserves retrieval order so the UI shows sources in the same rank order returned by Pinecone.

### 4) Generation (Gemini)
The backend builds a prompt containing the question and the retrieved chunk texts (each annotated with `chunk_id`). Gemini generates an answer and is instructed to answer using only the provided chunks, otherwise reply that the answer cannot be found in the provided text.

### 5) Explainability
The result page shows the question, the LLM answer, and the retrieved chunks (“sources”), including `chunk_id` and `chunk_index`.

---

## Architecture

```
Browser (Jinja templates)
   |
   v
FastAPI backend (Python)
   |
   +--> SQLite: contractrag.db (documents + chunks + annotations)
   |
   +--> Pinecone: vector index (dense embeddings + metadata filters)
   |
   +--> Gemini via LangChain (langchain-google-genai), model: gemini-2.5-flash
   |
   v
HTML response: Answer + Retrieved chunks (sources)
```


## Tech stack
### Backend / Web

- FastAPI

- Jinja2

- Uvicorn

### Retrieval + storage

- Pinecone (vector database)

- SQLite (contractrag.db)

- SQLAlchemy

### Embedding Model

- SentenceTransformers (`sentence-transformers/all-MiniLM-L6-v2`)

### LLM

- Gemini via LangChain (`langchain-google-genai`), model: `gemini-2.5-flash`

---

## Dataset: CUAD (Contract Understanding Atticus Dataset)

CUAD is a benchmark dataset for contract clause understanding, described as:

- ~510 commercial contracts

- 13,000+ expert annotations

- 41 clause categories (e.g., governing law, termination, effective date, etc.)

ContractIQ uses CUAD by ingesting contract texts, chunking documents, storing chunks in SQLite, embedding chunks, and indexing them in Pinecone for vector retrieval.

- CUAD overview: https://www.atticusprojectai.org/cuad

- Paper: https://arxiv.org/abs/2103.06268

---

## Repo Structure

```
ContractIQ/
├── main.py                     # FastAPI app entry (root)
├── src/
│   ├── config.py               # Settings (env vars)
│   ├── db.py                   # DB connection helpers (SQLite)
│   ├── documents.py            # list docs, fetch chunks
│   ├── retrieval.py            # embed query + Pinecone query
│   ├── rag.py                  # RAG orchestration + prompt + Gemini call
│   ├── chunking.py             # chunking + stable chunk_id hashing
│   ├── ingest_cuad_to_sqlite.py # CUAD -> SQLite ingestion
│   ├── upsert_chunks_to_pinecone.py # SQLite chunks -> Pinecone upsert
│   └── setup_pinecone_index.py # index dimension validation / creation
├── templates/
│   ├── index.html              # Home + form
│   └── result.html             # Answer + sources
├── static/
│   └── style.css               # UI styling
├── data/                       # gitignored (contains contractrag.db locally)
├── requirements.txt
└── README.md
```
