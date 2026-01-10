# scripts/bake_embedder.py
import os
from sentence_transformers import SentenceTransformer

model_id = "sentence-transformers/all-MiniLM-L6-v2"
local_dir = "/app/models/all-MiniLM-L6-v2"
os.makedirs(local_dir, exist_ok=True)

m = SentenceTransformer(model_id, device="cpu")
m.save(local_dir)

print("Saved embedding model to:", local_dir)
