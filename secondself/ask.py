"""Natural Language Search & RAG Q&A Engine for SecondSelf (The Oracle)."""

from __future__ import annotations

import os
import sys
import argparse
import re
import numpy as np

# Add current directory to sys.path to enable imports from lib
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lib import models, storage, embeddings, llm


def ask(
    question: str,
    top_k: int = 5,
    score_threshold: float = 0.05,
    model=None,
) -> models.AskResult:
    """
    Perform Retrieval-Augmented Generation (RAG) Q&A over the SecondSelf knowledge brain.

    Args:
        question: User query string.
        top_k: Maximum number of context notes to retrieve.
        score_threshold: Minimum cosine similarity required to include a note in context.
        model: Optional pre-loaded SentenceTransformer model instance.

    Returns:
        AskResult object containing the synthesized answer and list of cited sources.
    """
    question = question.strip()
    if not question:
        return models.AskResult(
            answer="Please enter a valid question.",
            sources=[],
        )

    # 1. Load all wiki notes
    wiki_notes = storage.read_wiki_notes()
    if not wiki_notes:
        return models.AskResult(
            answer="I don't have any notes in your brain to answer that question.",
            sources=[],
        )

    notes_by_id = {note.id: note for note in wiki_notes}

    # 2. Load cached embeddings or compute missing ones
    cached_embeddings = embeddings.load_embeddings()
    missing_notes = [note for note in wiki_notes if note.id not in cached_embeddings]

    if missing_notes:
        print(f"Computing embeddings for {len(missing_notes)} uncached notes...")
        missing_texts = [
            f"Tags: {', '.join(n.tags)}\nSummary: {n.summary}\n\n{n.body}"
            for n in missing_notes
        ]
        new_vecs = embeddings.embed_texts(missing_texts, model=model)
        for note, vec in zip(missing_notes, new_vecs):
            cached_embeddings[note.id] = vec
        embeddings.save_embeddings(cached_embeddings)

    # 3. Embed the user's question
    question_vec = embeddings.embed_text(question, model=model)

    # 4. Calculate similarity scores across all wiki notes
    scored_notes = []
    query_words = set(re.findall(r'\b\w{3,}\b', question.lower()))

    for note in wiki_notes:
        note_vec = cached_embeddings.get(note.id)
        if note_vec is None:
            continue
        sim = embeddings.cosine_similarity(question_vec, note_vec)
        
        # Keyword Match Boost: boost score if note body or tags contain query words
        note_text_lower = (f"{note.summary} " + " ".join(note.tags) + f" {note.body}").lower()
        match_count = sum(1 for word in query_words if word in note_text_lower)
        if match_count > 0:
            boost = min(0.20, match_count * 0.05)
            sim += boost
            
        scored_notes.append((sim, note))

    # Sort descending by similarity score
    scored_notes.sort(key=lambda x: x[0], reverse=True)

    # 5. Filter top-k notes meeting the similarity threshold
    relevant_matches = [
        (score, note) for score, note in scored_notes[:top_k] if score >= score_threshold
    ]

    if not relevant_matches:
        return models.AskResult(
            answer="I don't have enough relevant information in your notes to answer that question.",
            sources=[],
        )

    # Prepare context structures for LLM synthesis and source citations
    context_notes = []
    sources = []

    for score, note in relevant_matches:
        context_notes.append({
            "id": note.id,
            "summary": note.summary,
            "para": note.para,
            "tags": note.tags,
            "body": note.body,
        })
        sources.append(
            models.AskSource(
                id=note.id,
                summary=note.summary,
                relevance_score=round(float(score), 4),
                para=note.para,
            )
        )

    # 6. Call Groq LLM to synthesize answer
    answer = llm.synthesize_answer(context_notes, question, temperature=0.3)

    return models.AskResult(answer=answer, sources=sources)


def main():
    parser = argparse.ArgumentParser(
        description="SecondSelf Ask (The Oracle): RAG natural language Q&A engine."
    )
    parser.add_argument(
        "query",
        nargs="?",
        type=str,
        help="The question to ask your personal knowledge brain."
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Maximum number of context notes to retrieve (default: 5)."
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.2,
        help="Minimum similarity threshold for retrieval (default: 0.2)."
    )
    args = parser.parse_args()

    query = args.query
    if not query:
        print("🧠 SecondSelf Oracle — Interactive Q&A Mode")
        print("Type your question below (or 'exit' to quit):\n")
        while True:
            try:
                user_input = input("Question: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break
            if user_input.lower() in ("exit", "quit"):
                break
            if not user_input:
                continue

            result = ask(user_input, top_k=args.top_k, score_threshold=args.threshold)
            print("\nAnswer:")
            print(result.answer)
            print("\nSources:")
            if result.sources:
                for src in result.sources:
                    print(f"  - [{src.id}] ({src.para}) {src.summary} (Score: {src.relevance_score})")
            else:
                print("  No matching sources.")
            print("-" * 60 + "\n")
        return

    result = ask(query, top_k=args.top_k, score_threshold=args.threshold)
    print("\nAnswer:")
    print(result.answer)
    print("\nSources Cited:")
    if result.sources:
        for src in result.sources:
            print(f"  - [{src.id}] ({src.para}) {src.summary} (Relevance: {src.relevance_score})")
    else:
        print("  None.")


if __name__ == "__main__":
    main()
