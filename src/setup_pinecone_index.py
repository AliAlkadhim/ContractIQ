import os
from src.config import settings

if settings.force_cpu:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""

def get_embed_dim() -> int:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(settings.local_embedding_model, device="cpu")
    return model.get_sentence_embedding_dimension()

def main():
    dim = get_embed_dim()
    print("Local embedding dimension:", dim)

    # Pinecone SDK imports vary by install; try the recommended GRPC path first.
    try:
        from pinecone.grpc import PineconeGRPC as Pinecone
        from pinecone import ServerlessSpec
    except Exception:
        from pinecone import Pinecone, ServerlessSpec

    pc = Pinecone(api_key=settings.pinecone_api_key)
    name = settings.pinecone_index_name

    # If index exists, validate dimension
    if pc.has_index(name):
        desc = pc.describe_index(name)
        existing_dim = getattr(desc, "dimension", None) or desc.get("dimension")
        print("Index exists:", name, "| dimension:", existing_dim)
        if existing_dim != dim:
            raise RuntimeError(
                f"Index dimension mismatch: index={existing_dim} vs embedder={dim}. "
                f"Create a new index or switch embedding model."
            )
        print("✅ Index OK.")
        return

    # If it doesn't exist, create it (requires cloud+region)
    if not settings.pinecone_cloud or not settings.pinecone_region:
        raise RuntimeError(
            "Index does not exist and PINECONE_CLOUD / PINECONE_REGION are not set in .env. "
            "Set them or create the index in the Pinecone console."
        )

    pc.create_index(
        name=name,
        vector_type="dense",
        dimension=dim,
        metric=settings.pinecone_metric,
        spec=ServerlessSpec(cloud=settings.pinecone_cloud, region=settings.pinecone_region),
        deletion_protection="disabled",
    )
    print("✅ Created index:", name)

if __name__ == "__main__":
    main()
