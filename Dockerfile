FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CUDA_VISIBLE_DEVICES=""

WORKDIR /app

# System deps (minimal; add build-essential only if you hit a wheel build issue)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Pre-download embedding model to bake it into the image layer (faster cold starts)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY . /app

# Cloud Run sets PORT; your container must listen on it
CMD ["bash", "-lc", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
