import os
import sys
from pathlib import Path
from sentence_transformers import SentenceTransformer

# Add current directory to path to import lib
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lib import storage

def main():
    # 1. Load notes from wiki/
    print("Reading wiki notes...")
    notes = storage.read_wiki_notes()
    if not notes:
        print("No notes found in wiki. Please run classify.py and link.py first.")
        return

    # 2. Load model
    model_name = "all-MiniLM-L6-v2"
    print(f"Loading SentenceTransformer model '{model_name}'...")
    model = SentenceTransformer(model_name)

    # 3. Generate embeddings
    print("Generating embeddings...")
    texts = [f"Tags: {', '.join(n.tags)}\nSummary: {n.summary}\n\n{n.body}" for n in notes]
    embeddings = model.encode(texts, convert_to_numpy=True)

    print("\n--- Note Embeddings ---")
    for note, embedding in zip(notes, embeddings):
        print(f"Note ID: {note.id}")
        print(f"  Summary: {note.summary}")
        print(f"  Embedding Shape: {embedding.shape}")
        # Print the first 5 elements of the embedding vector
        vector_preview = ", ".join(f"{val:.4f}" for val in embedding[:5])
        print(f"  Vector Preview (first 5 elements): [{vector_preview}, ...]")
        print("-" * 50)

if __name__ == "__main__":
    main()
