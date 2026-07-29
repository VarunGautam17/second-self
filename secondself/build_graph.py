import os
import sys
import argparse
import re
from pathlib import Path
from dotenv import load_dotenv

# Add the current directory to sys.path so we can import from lib
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lib import models, storage

# Load environment variables
load_dotenv()

# Regex to match Markdown wiki-links like [[note_id]]
WIKI_LINK_RE = re.compile(r"\[\[([a-zA-Z0-9_-]+)\]\]")

def clean_body_preview(body: str, max_chars: int = 200) -> str:
    """Strips headers, frontmatter leftovers, and returns a clean preview snippet of the note body."""
    # Remove ## Related Notes section if present
    body_clean = re.sub(r"\n\n\s*(?:##|###)\s*Related Notes\s*\n.*$", "", body, flags=re.DOTALL | re.IGNORECASE)
    # Remove markdown titles / headers
    body_clean = re.sub(r"^#+\s+.*$", "", body_clean, flags=re.MULTILINE)
    # Collapse extra whitespace
    body_clean = " ".join(body_clean.split()).strip()
    if len(body_clean) > max_chars:
        return body_clean[:max_chars].rstrip() + "..."
    return body_clean

def build_graph(verbose: bool = False) -> tuple[list[dict], list[dict]]:
    """Reads all notes from wiki/, extracts nodes and edges, and returns (nodes, edges)."""
    notes = storage.read_wiki_notes()
    if not notes:
        print("No wiki notes found.")
        return [], []

    valid_note_ids = {note.id for note in notes}
    nodes = []
    edges = []
    seen_edges = set()

    print(f"Parsing {len(notes)} notes from wiki/...")

    for note in notes:
        # Build Node Object
        label = note.summary if note.summary else note.id
        preview = clean_body_preview(note.body)
        
        node_obj = {
            "id": note.id,
            "label": label,
            "para": note.para,
            "tags": note.tags,
            "summary": note.summary,
            "content_preview": preview,
            "group": note.para,
        }
        nodes.append(node_obj)

        # Collect targets from frontmatter links & body [[note_id]] references
        target_ids = set(note.links)
        body_links = WIKI_LINK_RE.findall(note.body)
        for target_id in body_links:
            target_ids.add(target_id)

        for target_id in target_ids:
            if target_id == note.id:
                continue # Skip self-loops
            if target_id not in valid_note_ids:
                if verbose:
                    print(f"  [Warning] Note {note.id} references unknown target ID: '{target_id}'")
                continue

            # Unique key for undirected / directed edge deduplication
            edge_key = (note.id, target_id)
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                edge_obj = {
                    "source": note.id,
                    "target": target_id,
                    "weight": 1.0,
                    "type": "semantic",
                }
                edges.append(edge_obj)

    return nodes, edges

def main():
    parser = argparse.ArgumentParser(
        description="Second Self Graph Generator: Extract nodes & edges from wiki notes into graph.json."
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Custom path to output graph.json file (default: secondself/graph.json)."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed node and edge extraction info."
    )
    args = parser.parse_args()

    nodes, edges = build_graph(verbose=args.verbose)

    if not nodes:
        print("No nodes to export.")
        return

    output_path = Path(args.output) if args.output else storage.PROJECT_ROOT / "graph.json"
    written_path = storage.write_graph_json(nodes, edges, output_path)
    
    # Also write a copy to data/graph.json for convenience
    data_graph_path = storage.DATA_DIR / "graph.json"
    storage.write_graph_json(nodes, edges, data_graph_path)

    # Update index.json with last_graph_build timestamp
    index = storage.load_index()
    index.last_graph_build = storage.utc_now_iso()
    storage.save_index(index)

    print("\n--- Graph Generation Summary ---")
    print(f"Total Nodes: {len(nodes)}")
    print(f"Total Edges: {len(edges)}")
    print(f"Saved graph to: {written_path}")
    print(f"Saved copy to: {data_graph_path}")
    print(f"Updated data/index.json (last_graph_build: {index.last_graph_build})")

    if args.verbose:
        print("\nNodes Overview:")
        for n in nodes:
            print(f"  - [{n['para']}] {n['id']}: {n['label']} ({len(n['tags'])} tags)")
        if edges:
            print("\nEdges Overview:")
            for e in edges:
                print(f"  - {e['source']} -> {e['target']} (weight={e['weight']}, type={e['type']})")

if __name__ == "__main__":
    main()
