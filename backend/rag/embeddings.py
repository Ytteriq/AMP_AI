"""
rag/embeddings.py
Local HuggingFace embeddings using sentence-transformers/all-MiniLM-L6-v2.
Runs locally on CPU, with normalize_embeddings=True.
"""

import os
from dotenv import find_dotenv, load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings

# Load environment configuration
env_path = find_dotenv(usecwd=True)
if env_path:
    load_dotenv(env_path)
else:
    load_dotenv()

try:
    from backend.config import settings
    MODEL_NAME = settings.EMBEDDING_MODEL or os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
except ImportError:
    MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


def get_embeddings() -> HuggingFaceEmbeddings:
    """Returns the local HuggingFaceEmbeddings instance."""
    return HuggingFaceEmbeddings(
        model_name=MODEL_NAME,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


# Module-level instance
embeddings = get_embeddings()
