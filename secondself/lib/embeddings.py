"""Embedding utilities and caching layer for SecondSelf."""

from __future__ import annotations

import os
import sys
import pickle
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer

# Add parent directory to sys.path if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib import storage

EMBEDDINGS_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDINGS_PKL_PATH = storage.DATA_DIR / "embeddings.pkl"

_model_cache: SentenceTransformer | None = None

def load_model(model_name: str = EMBEDDINGS_MODEL_NAME) -> SentenceTransformer:
    """Load and cache the SentenceTransformer model."""
    global _model_cache
    if _model_cache is None:
        _model_cache = SentenceTransformer(model_name)
    return _model_cache

def embed_text(text: str, model: SentenceTransformer | None = None) -> np.ndarray:
    """Generate a single 384-dimensional vector embedding for text."""
    if model is None:
        model = load_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding

def embed_texts(texts: list[str], model: SentenceTransformer | None = None, show_progress: bool = False) -> np.ndarray:
    """Generate batch embeddings for a list of texts."""
    if model is None:
        model = load_model()
    embeddings = model.encode(texts, show_progress_bar=show_progress, convert_to_numpy=True)
    return embeddings

def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Compute cosine similarity score between two 1D vectors."""
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))

def save_embeddings(embeddings_dict: dict[str, np.ndarray], output_path: Path | None = None) -> Path:
    """Save note embeddings dictionary {note_id: np.ndarray} to data/embeddings.pkl."""
    storage.ensure_dirs()
    if output_path is None:
        output_path = EMBEDDINGS_PKL_PATH

    tmp_path = output_path.with_suffix(".pkl.tmp")
    with open(tmp_path, "wb") as f:
        pickle.dump(embeddings_dict, f, protocol=pickle.HIGHEST_PROTOCOL)
    tmp_path.replace(output_path)
    return output_path

def load_embeddings(input_path: Path | None = None) -> dict[str, np.ndarray]:
    """Load note embeddings dictionary {note_id: np.ndarray} from data/embeddings.pkl."""
    if input_path is None:
        input_path = EMBEDDINGS_PKL_PATH

    if not input_path.is_file():
        return {}

    try:
        with open(input_path, "rb") as f:
            data = pickle.load(f)
        if isinstance(data, dict):
            return data
        return {}
    except Exception as e:
        print(f"[Warning] Failed to load embeddings cache from {input_path}: {e}")
        return {}
