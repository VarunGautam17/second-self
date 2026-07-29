import os
import sys
import argparse
import shutil
import re
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

# Add the current directory to sys.path so we can import from lib
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lib import models, storage, embeddings

# Load environment variables
load_dotenv()

def strip_related_notes_section(body: str) -> str:
    """Strips the auto-generated Related Notes section from the end of the body."""
    pattern = re.compile(r"\n\n\s*(?:##|###)\s*Related Notes\s*\n.*$", re.DOTALL | re.IGNORECASE)
    cleaned = pattern.sub("", body)
    return cleaned.strip()

def get_note_text_for_embedding(note: models.WikiNote) -> str:
    """Combines note tags, summary, and body to form a rich text representation for embedding."""
    tags_str = ", ".join(note.tags)
    return f"Tags: {tags_str}\nSummary: {note.summary}\n\n{note.body}"

def compute_similarity_links(
    all_notes: list[models.WikiNote],
    embeddings: np.ndarray,
    threshold: float,
    max_links: int
) -> dict[int, list[str]]:
    """Computes similarity matrix and returns a map of note index to list of top matching note IDs."""
    num_notes = len(all_notes)
    if num_notes == 0:
        return {}

    # Normalize embeddings
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1e-10  # Prevent division by zero
    norm_embeddings = embeddings / norms

    # Compute dot products (cosine similarity matrix)
    similarity_matrix = np.dot(norm_embeddings, norm_embeddings.T)

    links_by_index = {}
    for i in range(num_notes):
        matches = []
        for j in range(num_notes):
            if i == j:
                continue
            sim = float(similarity_matrix[i, j])
            if sim >= threshold:
                matches.append((sim, all_notes[j].id))

        # Sort matches by similarity score descending, then take top max_links
        matches.sort(key=lambda x: x[0], reverse=True)
        top_matches = matches[:max_links]
        links_by_index[i] = [note_id for _, note_id in top_matches]

    return links_by_index

def update_note_links(note: models.WikiNote, new_links: list[str]) -> bool:
    """Updates the links list and body of the note if changed.
    Returns True if the note was changed/updated, False otherwise.
    """
    old_links_sorted = sorted(note.links)
    new_links_sorted = sorted(new_links)

    if old_links_sorted == new_links_sorted:
        # Check if the body actually has the Related Notes section properly formatted
        clean_body = strip_related_notes_section(note.body)
        expected_body = clean_body
        if new_links:
            links_str = "\n".join(f"- [[{link_id}]]" for link_id in sorted(new_links))
            expected_body = f"{clean_body}\n\n## Related Notes\n{links_str}"
        if note.body.strip() == expected_body.strip():
            return False

    note.links = new_links
    clean_body = strip_related_notes_section(note.body)
    if new_links:
        links_str = "\n".join(f"- [[{link_id}]]" for link_id in sorted(new_links))
        note.body = f"{clean_body}\n\n## Related Notes\n{links_str}"
    else:
        note.body = clean_body

    return True

def main():
    parser = argparse.ArgumentParser(
        description="Second Self Auto-Linking & Migration: Link related notes using local embeddings and migrate raw files."
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.4,
        help="Cosine similarity threshold for linking notes (default: 0.4)."
    )
    parser.add_argument(
        "--max-links",
        type=int,
        default=5,
        help="Maximum number of auto-links per note (default: 5)."
    )
    parser.add_argument(
        "--model",
        default="all-MiniLM-L6-v2",
        help="Sentence-transformers model to use (default: all-MiniLM-L6-v2)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform calculations and show updates/migration steps without writing to disk."
    )
    args = parser.parse_args()

    print(f"Loading SentenceTransformer model '{args.model}'...")
    try:
        model = SentenceTransformer(args.model)
    except Exception as e:
        print(f"Error loading model: {e}")
        sys.exit(1)

    # 1. Load existing wiki notes
    print("Reading existing wiki notes...")
    wiki_notes = storage.read_wiki_notes()
    print(f"Found {len(wiki_notes)} existing wiki notes.")

    # 2. Load unprocessed raw captures that are classified
    print("Reading unprocessed raw captures...")
    raw_captures = storage.read_raw_captures(unprocessed_only=True)
    
    new_notes_data = []  # List of tuples: (WikiNote, RawCapture)
    skipped_unclassified = 0

    for capture in raw_captures:
        if not capture.content_path:
            continue
        content_path = Path(capture.content_path)
        if not content_path.is_file():
            continue

        # Parse the note to check if it's classified
        note = storage._parse_wiki_note(content_path)
        if note is None:
            skipped_unclassified += 1
            continue

        new_notes_data.append((note, capture))

    print(f"Found {len(new_notes_data)} new classified notes to process.")
    if skipped_unclassified > 0:
        print(f"Skipped {skipped_unclassified} unclassified raw captures.")

    if not new_notes_data and not wiki_notes:
        print("No wiki notes or new raw captures to process. Exiting.")
        return

    # Combine all notes to build a global similarity map
    new_notes = [note for note, _ in new_notes_data]
    all_notes = wiki_notes + new_notes
    print(f"Computing embeddings for all {len(all_notes)} notes...")

    texts = [get_note_text_for_embedding(note) for note in all_notes]
    try:
        note_embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    except Exception as e:
        print(f"Error generating embeddings: {e}")
        sys.exit(1)

    # Calculate similarity links
    print(f"Calculating similarity links (threshold: {args.threshold}, max-links: {args.max_links})...")
    links_by_index = compute_similarity_links(all_notes, note_embeddings, args.threshold, args.max_links)

    # Track which notes need updating
    wiki_updates = []  # List of (WikiNote, path) that already exist in wiki but need updates
    new_wiki_notes = []  # List of (WikiNote, RawCapture) to be migrated to wiki

    # Apply links to existing wiki notes
    for i, note in enumerate(wiki_notes):
        new_links = links_by_index.get(i, [])
        if update_note_links(note, new_links):
            wiki_updates.append(note)

    # Apply links to new notes
    for i, (note, capture) in enumerate(new_notes_data):
        # Index in all_notes is len(wiki_notes) + i
        global_idx = len(wiki_notes) + i
        new_links = links_by_index.get(global_idx, [])
        update_note_links(note, new_links)
        new_wiki_notes.append((note, capture))

    # Output details of proposed actions
    print("\n--- Proposed Operations ---")
    if wiki_updates:
        print(f"Existing Wiki Notes to Update ({len(wiki_updates)}):")
        for note in wiki_updates:
            print(f"  - [{note.para}] {note.id} ({note.summary}) -> Links: {note.links}")
    else:
        print("No existing wiki notes need updating.")

    print(f"\nNew Notes to Migrate and Save ({len(new_wiki_notes)}):")
    for note, capture in new_wiki_notes:
        print(f"  - Ingesting: {capture.folder_id} -> wiki/{note.para}/{note.id}.md")
        print(f"    Summary: {note.summary}")
        print(f"    Links: {note.links}")

    if args.dry_run:
        print("\n[Dry Run] No files written, moved, or deleted.")
        return

    # 3. Perform Migration and Writes
    print("\nExecuting filesystem updates...")

    # Write updated existing wiki notes
    for note in wiki_updates:
        print(f"Updating existing wiki note: wiki/{note.para}/{note.id}.md")
        storage.write_wiki_note(note)

    # Load current index
    index = storage.load_index()

    # Save and migrate new notes
    for note, capture in new_wiki_notes:
        dest_path = storage.write_wiki_note(note)
        print(f"Migrated and saved: {dest_path}")

        # Delete raw folder
        raw_folder_path = Path(capture.path)
        if raw_folder_path.exists() and raw_folder_path.is_dir():
            shutil.rmtree(raw_folder_path)
            print(f"Deleted raw capture folder: {capture.folder_id}")

        # Record in index.json
        index.raw_processed[capture.folder_id] = {
            "processed_at": storage.utc_now_iso(),
            "wiki_path": str(dest_path),
            "note_id": note.id
        }

    # Save index updates
    storage.save_index(index)
    print("Index updated successfully.")

    # Save precomputed note embeddings to data/embeddings.pkl
    embeddings_dict = {note.id: emb for note, emb in zip(all_notes, note_embeddings)}
    saved_pkl = embeddings.save_embeddings(embeddings_dict)
    print(f"Saved note embeddings cache ({len(embeddings_dict)} vectors) to: {saved_pkl}")

    print("Auto-linking and migration complete.")

if __name__ == "__main__":
    main()
