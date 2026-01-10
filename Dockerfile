FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HF_HOME=/app/.cache/huggingface \
    TRANSFORMERS_CACHE=/app/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence_transformers

WORKDIR /app

# System deps
# - bash is used by your CMD
# - curl is optional but often useful for debugging/healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy your app code
COPY . /app

# Bake the embedding model into the image (into a *real* local folder)
# so runtime never calls Hugging Face.
RUN python - <<'PY'
import os
from sentence_transformers import SentenceTransformer

model_id = "sentence-transformers/all-MiniLM-L6-v2"
local_dir = "/app/models/all-MiniLM-L6-v2"
os.makedirs(local_dir, exist_ok=True)

m = SentenceTransformer(model_id, device="cpu")
m.save(local_dir)

print("Saved embedding model to:", local_dir)
PY

# After the model is baked, force offline mode at runtime to guarantee
# no accidental Hugging Face calls.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

# Cloud Run sets PORT; default is 8080
CMD ["bash", "-lc", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
