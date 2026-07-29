import os
import sys
import argparse
import json
import re
import time
import yaml
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

# Add the current directory to sys.path so we can import from lib
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lib import models, storage

# Load environment variables
load_dotenv()

# System prompt for the Groq LLM
SYSTEM_PROMPT = """You are an expert librarian and personal organizer. Your task is to analyze the content of a raw captured note, link description, or file, and classify it according to the PARA method.

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

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)

def is_classified(content: str) -> bool:
    """Return True if content already has a YAML frontmatter block."""
    return content.lstrip().startswith("---")

def strip_existing_frontmatter(content: str) -> str:
    """Strip existing frontmatter from the content if present."""
    match = _FRONTMATTER_RE.match(content)
    if match:
        return match.group(2).lstrip("\n")
    return content

def classify_content_with_retry(client: Groq, content: str, model: str, max_retries: int = 3) -> dict:
    """Calls Groq API to classify the content, with retry/exponential backoff logic."""
    sample_content = content
    if len(content) > 4000:
        sample_content = content[:3000] + "\n\n... [middle text omitted for classification] ...\n\n" + content[-1000:]

    for attempt in range(1, max_retries + 1):
        try:
            # We enforce JSON output format
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Content to classify:\n\n{sample_content}"}
                ],
                model=model,
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            raw_response = response.choices[0].message.content
            # Parse the response as JSON
            data = json.loads(raw_response)
            
            # Basic validation of the returned structure
            if "para" not in data or "tags" not in data or "summary" not in data:
                raise ValueError("LLM response is missing required fields (para, tags, or summary)")
            
            para = data["para"]
            if para not in models.PARA_CATEGORIES:
                # Force standard category matching/fallback
                for category in models.PARA_CATEGORIES:
                    if category.lower() == str(para).lower():
                        data["para"] = category
                        break
                else:
                    data["para"] = "Resources" # Safe fallback
            
            return data
            
        except Exception as e:
            print(f"  [Attempt {attempt}/{max_retries}] Error during LLM classification: {e}")
            if attempt == max_retries:
                raise
            time.sleep(2 ** attempt)

def main():
    parser = argparse.ArgumentParser(
        description="Second Self Auto-Classify: Send raw captures to Groq API for PARA framework classification."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-classify notes even if they already have YAML frontmatter."
    )
    parser.add_argument(
        "--model",
        default="llama-3.1-8b-instant",
        help="Groq API model to use (default: llama-3.1-8b-instant)."
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of raw captures to process."
    )
    args = parser.parse_args()

    # Verify Groq API key and get client
    try:
        from lib import llm
        client = llm.get_client()
    except Exception as e:
        print(f"Error initializing Groq client: {e}")
        return

    # Read all raw captures
    print("Reading raw captures...")
    raw_captures = storage.read_raw_captures()
    if not raw_captures:
        print("No raw captures found.")
        return

    processed_count = 0
    skipped_count = 0
    errors_count = 0

    for capture in raw_captures:
        if args.limit and processed_count >= args.limit:
            print(f"Reached limit of {args.limit} files. Stopping.")
            break

        if not capture.content_path:
            print(f"Skipping {capture.folder_id}: No content file found.")
            skipped_count += 1
            continue

        file_path = Path(capture.content_path)
        if not file_path.is_file():
            print(f"Skipping {capture.folder_id}: Content path {file_path} is not a file.")
            skipped_count += 1
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            errors_count += 1
            continue

        has_fm = is_classified(content)
        if has_fm and not args.force:
            print(f"Skipping {capture.folder_id}: Already classified (has frontmatter).")
            skipped_count += 1
            continue

        print(f"Classifying {capture.folder_id} ({capture.meta.type})...")
        
        # Strip frontmatter if we are forcing re-classification
        raw_body = strip_existing_frontmatter(content)

        try:
            metadata = classify_content_with_retry(client, raw_body, args.model)
            
            # Format and write new frontmatter
            frontmatter_data = {
                "id": capture.meta.id,
                "raw_id": capture.meta.id,
                "para": metadata["para"],
                "tags": metadata["tags"],
                "summary": metadata["summary"],
                "created": capture.meta.timestamp,
                "links": [] # Implicit links will be populated in Phase 2.2
            }
            
            yaml_block = yaml.safe_dump(
                frontmatter_data,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            ).strip()
            
            new_content = f"---\n{yaml_block}\n---\n\n{raw_body.rstrip()}\n"
            file_path.write_text(new_content, encoding="utf-8")
            
            print(f"  Category: {metadata['para']}")
            print(f"  Tags: {', '.join(metadata['tags'])}")
            print(f"  Summary: {metadata['summary']}")
            print(f"  Saved frontmatter to: {file_path}")
            processed_count += 1
            
        except Exception as e:
            print(f"Failed to process {capture.folder_id} due to errors: {e}")
            errors_count += 1
            continue

    print(f"\nProcessing complete.")
    print(f"  Successfully processed: {processed_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Errors encountered: {errors_count}")

if __name__ == "__main__":
    main()
