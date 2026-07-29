import os
import sys
import argparse
from bs4 import BeautifulSoup
import requests

# Append lib directory if needed or import directly since we run in secondself/
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lib import models, storage

# Constants
MAX_CHAR_LIMIT = 2000000
SUPPORTED_EXTENSIONS = {".txt", ".md", ".log", ".json", ".csv"}

def check_duplicate(content: str) -> tuple[bool, str | None]:
    """Computes content hash and checks if it exists in raw captures.
    Returns (is_duplicate, duplicate_folder_name).
    """
    new_hash = storage.content_hash(content)
    existing_captures = storage.read_raw_captures()
    for capture in existing_captures:
        if capture.meta.content_hash == new_hash:
            return True, capture.folder_id
    return False, None

def clean_html(html_content: str) -> str:
    """Strips HTML tags and extracts readable text."""
    soup = BeautifulSoup(html_content, "html.parser")
    # Remove script, style, nav, footer, header elements
    for element in soup(["script", "style", "nav", "footer", "header"]):
        element.decompose()
    # Get text and clean whitespace
    text = soup.get_text(separator="\n")
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    cleaned_text = "\n".join(chunk for chunk in chunks if chunk)
    
    title = soup.title.string.strip() if soup.title and soup.title.string else "Scraped Webpage"
    return f"# {title}\n\n{cleaned_text}"

def scrape_url(url: str) -> tuple[str, str]:
    """Fetches a URL and returns (content, error_message).
    If scraping fails, content will be a fallback representation, and error_message will be filled.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            cleaned_text = clean_html(response.text)
            content = f"URL: {url}\n\n{cleaned_text}"
            return content, ""
        else:
            err = f"HTTP status code {response.status_code}"
            fallback = f"URL: {url}\nError: {err}\n\nCould not scrape URL. Ingested URL as plaintext fallback."
            return fallback, err
    except Exception as e:
        err = str(e)
        fallback = f"URL: {url}\nError: {err}\n\nCould not scrape URL due to exception. Ingested URL as plaintext fallback."
        return fallback, err

def main():
    parser = argparse.ArgumentParser(
        description="Second Self Ingestion Command: Capture notes, URLs, and local files into the raw/ staging folder."
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="The content to capture (plain text, a URL starting with http/https, or path to a local text file)."
    )
    args = parser.parse_args()
    
    # Resolve input content
    input_str = ""
    if args.input is not None:
        if args.input == "-":
            print("Reading from stdin...")
            input_str = sys.stdin.read().strip()
        else:
            input_str = args.input.strip()
            
    if not input_str:
        print("Error: No input provided. Provide a string, URL, file path, or '-' to read from stdin.")
        parser.print_help()
        sys.exit(1)
        
    # Variables to track capture metadata
    capture_type = None
    capture_source = None
    original_filename = None
    content = ""
    
    # Strip quotes for file path resolution
    clean_path = input_str.strip().strip('"').strip("'").strip()
    
    # Auto-detect source type
    if input_str.startswith(("http://", "https://")):
        print(f"Ingesting URL: {input_str}...")
        content, scrape_err = scrape_url(input_str)
        capture_type = "link"
        capture_source = "cli"
        if scrape_err:
            print(f"Warning: Failed to scrape URL content ({scrape_err}). Ingesting URL as fallback.")
            
    elif os.path.isfile(clean_path) or (len(clean_path) < 300 and any(clean_path.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS) and os.path.exists(clean_path)):
        try:
            print(f"Ingesting file: {clean_path}...")
            file_path = os.path.abspath(clean_path)
            ext = os.path.splitext(file_path)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                print(f"Error reading file: Unsupported file type '{ext}'. Supported types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
                sys.exit(1)
                
            size_bytes = os.path.getsize(file_path)
            if size_bytes > 20 * 1024 * 1024:
                print("Error reading file: File size exceeds safety limit of 20MB.")
                sys.exit(1)
                
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
                
            capture_type = "file"
            capture_source = "path"
            original_filename = os.path.basename(file_path)
        except Exception as e:
            print(f"Error reading file: {e}")
            sys.exit(1)
    else:
        # Standard plaintext note capture
        print("Ingesting text note...")
        content = input_str
        capture_type = "note"
        capture_source = "stdin" if args.input == "-" else "cli"
        
    # Final validation on content length
    if not content.strip():
        print("Error: Ingested content is empty.")
        sys.exit(1)
        
    if len(content) > MAX_CHAR_LIMIT:
        print(f"Error: Ingested content length ({len(content)} chars) exceeds maximum limit of {MAX_CHAR_LIMIT} chars.")
        sys.exit(1)
        
    # Check deduplication
    is_dup, dup_folder = check_duplicate(content)
    if is_dup:
        print(f"Skipped capture: Duplicate content detected (already exists in raw/{dup_folder}).")
        sys.exit(0)
        
    # Write the capture using storage library
    try:
        short_id, _ = storage.generate_capture_id()
        meta = models.CaptureMeta(
            id=short_id,
            timestamp=storage.utc_now_iso(),
            type=capture_type,
            source=capture_source,
            original_filename=original_filename,
            content_hash=storage.content_hash(content)
        )
        saved_dir = storage.write_raw_capture(meta, content)
        print("Successfully captured!")
        print(f"  ID: {short_id}")
        print(f"  Saved to: {saved_dir}")
    except Exception as e:
        print(f"Error saving capture: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
