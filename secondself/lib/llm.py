"""Groq LLM helper utilities for SecondSelf."""

from __future__ import annotations

import os
import sys
import json
import time
from dotenv import load_dotenv
from groq import Groq

# Add parent directory to sys.path if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib import models

load_dotenv()

SYSTEM_CLASSIFY_PROMPT = """You are an expert librarian and personal organizer. Your task is to analyze the content of a raw captured note, link description, or file, and classify it according to the PARA method.

Provide:
1. "para": The PARA category. Must be EXACTLY one of: "Projects", "Areas", "Resources", "Archives".
   Definitions:
   - "Projects": Active goals with a clear deadline (e.g., planning a trip, code development projects, writing articles, event planning).
   - "Areas": Spheres of activity with a standard to be maintained over time, no end date (e.g., health, fitness, finances, career, personal development, home maintenance).
   - "Resources": Topics or themes of ongoing interest or reference material (e.g., programming languages, cooking recipes, articles to read, coding snippets, lists).
   - "Archives": Inactive items from the other three categories (e.g., completed projects, old interests, inactive responsibilities).
2. "tags": A list of 2-5 lowercase semantic tags (words or simple phrases) that capture the key topics of the note.
3. "summary": A concise one-line summary of the content (maximum 15 words).

You MUST return a JSON object with this exact structure:
{
  "para": "Projects" | "Areas" | "Resources" | "Archives",
  "tags": ["tag1", "tag2"],
  "summary": "Concise one-line summary"
}
Output only the JSON object. Do not include any introductory or concluding text.
"""

SYSTEM_RAG_PROMPT = """You are SecondSelf, an intelligent personal knowledge assistant.
Your goal is to answer the user's question accurately based strictly on their personal knowledge base notes provided below.

Rules:
1. Answer the question using ONLY the provided Note Contexts.
2. If the provided notes do not contain enough relevant information to answer the question, state clearly: "I don't have enough information in your notes to answer that question."
3. Always cite the note ID in brackets (e.g., [1d7b5581]) whenever referencing information from a note.
4. Keep your response helpful, concise, and direct.
"""

def get_client() -> Groq:
    """Return an initialized Groq client prioritizing active user session key."""
    api_key = None
    try:
        import streamlit as st
        if "groq_api_key" in st.session_state and st.session_state["groq_api_key"]:
            api_key = st.session_state["groq_api_key"]
        elif "GROQ_API_KEY" in st.secrets:
            api_key = st.secrets["GROQ_API_KEY"]
    except Exception:
        pass

    if not api_key:
        api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        raise ValueError("GROQ_API_KEY is not configured. Please enter your Groq API key on the login screen.")

    return Groq(api_key=api_key)


def validate_groq_api_key(api_key: str) -> tuple[bool, str]:
    """Test Groq API key validity with a lightweight API call."""
    clean_key = api_key.strip()
    if not clean_key:
        return False, "Groq API key cannot be empty."
    try:
        client = Groq(api_key=clean_key)
        client.models.list()
        return True, "API Key successfully validated!"
    except Exception as e:
        return False, f"Invalid Groq API key: {e}"

def call_llm(
    prompt: str,
    system: str = "",
    model: str = "llama-3.1-8b-instant",
    json_mode: bool = False,
    temperature: float = 0.0,
    max_retries: int = 3,
) -> str:
    """Call Groq API with automatic retry logic and backoff."""
    client = get_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs = {
        "messages": messages,
        "model": model,
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            if attempt == max_retries:
                raise RuntimeError(f"Groq API call failed after {max_retries} attempts: {e}")
            time.sleep(2 ** attempt)

def classify_content(content: str, model: str = "llama-3.1-8b-instant") -> dict:
    """Classify raw content into PARA framework using Groq LLM."""
    sample_content = content
    if len(content) > 4000:
        sample_content = content[:3000] + "\n\n... [middle text omitted for classification] ...\n\n" + content[-1000:]

    prompt = f"Content to classify:\n\n{sample_content}"
    raw_response = call_llm(
        prompt=prompt,
        system=SYSTEM_CLASSIFY_PROMPT,
        model=model,
        json_mode=True,
        temperature=0.0,
    )
    data = json.loads(raw_response)
    if "para" not in data or "tags" not in data or "summary" not in data:
        raise ValueError("LLM response missing required fields (para, tags, summary)")

    para = data["para"]
    if para not in models.PARA_CATEGORIES:
        for cat in models.PARA_CATEGORIES:
            if cat.lower() == str(para).lower():
                data["para"] = cat
                break
        else:
            data["para"] = "Resources"
    return data

def synthesize_answer(
    context_notes: list[dict],
    question: str,
    model: str = "llama-3.1-8b-instant",
    temperature: float = 0.3,
) -> str:
    """Synthesize a RAG response based on retrieved note context."""
    if not context_notes:
        return "I don't have any relevant notes in your brain to answer that question."

    formatted_contexts = []
    for idx, note in enumerate(context_notes, 1):
        formatted_contexts.append(
            f"--- Note [{note['id']}] (Category: {note['para']}) ---\n"
            f"Summary: {note['summary']}\n"
            f"Tags: {', '.join(note.get('tags', []))}\n"
            f"Content:\n{note['body']}\n"
        )
    combined_context = "\n".join(formatted_contexts)

    prompt = f"Context Notes:\n{combined_context}\n\nUser Question: {question}"
    return call_llm(
        prompt=prompt,
        system=SYSTEM_RAG_PROMPT,
        model=model,
        temperature=temperature,
    )
