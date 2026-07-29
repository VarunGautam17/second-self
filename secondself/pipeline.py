"""Unified pipeline orchestrator for SecondSelf."""

from __future__ import annotations

import os
import sys
import argparse

# Add current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from lib import storage
import classify
import link
import build_graph

def run_classify(force: bool = False, model: str = "llama-3.1-8b-instant", limit: int | None = None) -> None:
    """Run auto-classification pipeline step."""
    print("=" * 60)
    print("STEP 1: AUTO-CLASSIFYING RAW CAPTURES")
    print("=" * 60)
    sys.argv = ["classify.py"]
    if force:
        sys.argv.append("--force")
    if model:
        sys.argv.extend(["--model", model])
    if limit:
        sys.argv.extend(["--limit", str(limit)])
    classify.main()

def run_link(threshold: float = 0.4, max_links: int = 5, model: str = "all-MiniLM-L6-v2", dry_run: bool = False) -> None:
    """Run auto-linking and migration pipeline step."""
    print("\n" + "=" * 60)
    print("STEP 2: AUTO-LINKING & MIGRATING NOTES")
    print("=" * 60)
    sys.argv = ["link.py", "--threshold", str(threshold), "--max-links", str(max_links), "--model", model]
    if dry_run:
        sys.argv.append("--dry-run")
    link.main()

def run_build_graph(output: str | None = None, verbose: bool = False) -> None:
    """Run graph dataset generation pipeline step."""
    print("\n" + "=" * 60)
    print("STEP 3: GENERATING GRAPH DATASET (graph.json)")
    print("=" * 60)
    sys.argv = ["build_graph.py"]
    if output:
        sys.argv.extend(["--output", output])
    if verbose:
        sys.argv.append("--verbose")
    build_graph.main()

def run_process(
    force: bool = False,
    classify_model: str = "llama-3.1-8b-instant",
    threshold: float = 0.4,
    max_links: int = 5,
    embedding_model: str = "all-MiniLM-L6-v2",
    verbose: bool = False,
) -> None:
    """Run full pipeline process sequentially: Classify -> Link -> Build Graph."""
    print("\nSTARTING SECONDSELF PIPELINE (Classify -> Link -> Build Graph)...")
    run_classify(force=force, model=classify_model)
    run_link(threshold=threshold, max_links=max_links, model=embedding_model)
    run_build_graph(verbose=verbose)
    print("\nSECONDSELF PIPELINE PROCESSING COMPLETE.")

def main():
    parser = argparse.ArgumentParser(
        description="SecondSelf Unified Pipeline: Orchestrate classification, linking, and graph generation."
    )
    subparsers = parser.add_subparsers(dest="command", help="Pipeline step to execute")

    # Classify command
    classify_parser = subparsers.add_parser("classify", help="Run auto-classification on raw captures")
    classify_parser.add_argument("--force", action="store_true", help="Force re-classification")
    classify_parser.add_argument("--model", default="llama-3.1-8b-instant", help="Groq model")

    # Link command
    link_parser = subparsers.add_parser("link", help="Run auto-linking and note migration")
    link_parser.add_argument("--threshold", type=float, default=0.4, help="Similarity threshold")
    link_parser.add_argument("--max-links", type=int, default=5, help="Max links per note")

    # Build Graph command
    graph_parser = subparsers.add_parser("build_graph", help="Generate graph.json dataset")
    graph_parser.add_argument("--verbose", action="store_true", help="Verbose output")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a note by ID and rebuild graph")
    delete_parser.add_argument("note_id", help="The note ID to delete")

    # Process command (Full end-to-end)
    process_parser = subparsers.add_parser("process", help="Run full pipeline: classify -> link -> build_graph")
    process_parser.add_argument("--force", action="store_true", help="Force re-classification")
    process_parser.add_argument("--threshold", type=float, default=0.4, help="Similarity threshold")
    process_parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.command == "classify":
        run_classify(force=args.force, model=args.model)
    elif args.command == "link":
        run_link(threshold=args.threshold, max_links=args.max_links)
    elif args.command == "build_graph":
        run_build_graph(verbose=args.verbose)
    elif args.command == "delete":
        if storage.delete_wiki_note(args.note_id):
            print(f"Deleted note file for ID: {args.note_id}")
            run_process(threshold=0.4)
        else:
            print(f"Note ID '{args.note_id}' not found in wiki/.")
    elif args.command == "process":
        run_process(force=args.force, threshold=args.threshold, verbose=args.verbose)
    else:
        # Default behavior if no subcommand is passed: run full process
        run_process()

if __name__ == "__main__":
    main()
