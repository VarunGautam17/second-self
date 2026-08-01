"""Filesystem helpers for SecondSelf."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

from lib.models import (
    PARA_CATEGORIES,
    CaptureMeta,
    IndexState,
    RawCapture,
    WikiNote,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Legacy defaults for CLI / backward compatibility
RAW_DIR = PROJECT_ROOT / "raw"
WIKI_DIR = PROJECT_ROOT / "wiki"
DATA_DIR = PROJECT_ROOT / "data"
INDEX_PATH = DATA_DIR / "index.json"

CONTENT_FILENAMES = {
    "note": "content.md",
    "link": "content.txt",
}


_ACTIVE_USER_SLUG: str | None = None


def set_active_user_slug(slug: str | None) -> None:
    """Explicitly set active user slug for storage operations."""
    global _ACTIVE_USER_SLUG
    _ACTIVE_USER_SLUG = slug


def get_current_user_slug() -> str | None:
    """Return active user_slug from explicit state or Streamlit session_state."""
    global _ACTIVE_USER_SLUG
    if _ACTIVE_USER_SLUG:
        return _ACTIVE_USER_SLUG
    try:
        import streamlit as st
        if "user_slug" in st.session_state and st.session_state["user_slug"]:
            return st.session_state["user_slug"]
    except Exception:
        pass
    return None


def get_user_base_dir() -> Path:
    """Return base directory path for current session user or fallback to project root."""
    slug = get_current_user_slug()
    if slug:
        return PROJECT_ROOT / "users" / slug
    return PROJECT_ROOT


def get_raw_dir() -> Path:
    """Return active raw capture directory."""
    return get_user_base_dir() / "raw"


def get_wiki_dir() -> Path:
    """Return active wiki directory."""
    return get_user_base_dir() / "wiki"


def get_data_dir() -> Path:
    """Return active data directory."""
    return get_user_base_dir() / "data"


def get_index_path() -> Path:
    """Return active index.json path."""
    return get_data_dir() / "index.json"


def ensure_dirs() -> None:
    """Create required project directories for active user if missing."""
    raw_dir = get_raw_dir()
    wiki_dir = get_wiki_dir()
    data_dir = get_data_dir()

    raw_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    for category in PARA_CATEGORIES:
        (wiki_dir / category).mkdir(parents=True, exist_ok=True)


def hash_passcode(passcode: str) -> str:
    """Hash passcode using SHA-256 with salt for secure storage."""
    if not passcode:
        return ""
    salt = "SecondSelf_Salt_2026_Secure"
    return hashlib.sha256((salt + passcode).encode("utf-8")).hexdigest()


def save_user_config(user_slug: str, user_name: str, api_key: str, passcode: str = "") -> None:
    """Save user session configuration into users/<user_slug>/config.json with hashed passcode."""
    user_base = PROJECT_ROOT / "users" / user_slug
    user_base.mkdir(parents=True, exist_ok=True)
    config_path = user_base / "config.json"

    existing = load_user_config(user_slug) or {}
    passcode_hash = existing.get("passcode_hash", "")
    if passcode:
        passcode_hash = hash_passcode(passcode)

    data = {
        "user_name": user_name,
        "user_slug": user_slug,
        "api_key": api_key,
        "passcode_hash": passcode_hash,
        "last_login": utc_now_iso(),
    }
    config_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_user_config(user_slug: str) -> dict | None:
    """Load user session configuration from users/<user_slug>/config.json."""
    config_path = PROJECT_ROOT / "users" / user_slug / "config.json"
    if not config_path.is_file():
        return None
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def verify_user_passcode(user_slug: str, passcode: str = "", api_key: str = "") -> tuple[bool, str]:
    """
    Verify user authentication against stored config.
    Returns (is_valid, message).
    """
    cfg = load_user_config(user_slug)
    if not cfg:
        return False, "User workspace does not exist."

    stored_hash = cfg.get("passcode_hash", "")
    stored_key = cfg.get("api_key", "")

    # 1. Verify passcode hash if user set a passcode
    if stored_hash:
        if passcode and hash_passcode(passcode) == stored_hash:
            return True, "Authentication successful."
        else:
            return False, "Incorrect passcode for this workspace."

    # 2. Handle legacy accounts without a passcode hash
    # Check if either the passcode field or the API key field contains the correct API key
    effective_key = (passcode or api_key or "").strip()
    if stored_key and effective_key:
        if stored_key.strip() == effective_key:
            return True, "Authenticated via legacy API Key."
        else:
            return False, "Groq API Key does not match workspace owner key."

    return False, "This legacy workspace does not have a passcode set yet. Please sign in by entering your registered Groq API Key in the 'Workspace Secret Passcode' or 'Groq API Key' field to unlock it."


def init_user_workspace(user_slug: str, copy_demo_data: bool = False, user_name: str = "", api_key: str = "", passcode: str = "") -> Path:
    """Initialize user workspace in users/<user_slug>/, optionally seeding demo data."""
    user_base = PROJECT_ROOT / "users" / user_slug
    user_raw = user_base / "raw"
    user_wiki = user_base / "wiki"
    user_data = user_base / "data"

    user_raw.mkdir(parents=True, exist_ok=True)
    user_data.mkdir(parents=True, exist_ok=True)
    for category in PARA_CATEGORIES:
        (user_wiki / category).mkdir(parents=True, exist_ok=True)

    if user_name:
        save_user_config(user_slug, user_name, api_key, passcode=passcode)

    if copy_demo_data:
        demo_wiki = PROJECT_ROOT / "wiki"
        if demo_wiki.is_dir():
            for cat in PARA_CATEGORIES:
                src_cat = demo_wiki / cat
                dst_cat = user_wiki / cat
                if src_cat.is_dir():
                    for f in src_cat.glob("*.md"):
                        if not (dst_cat / f.name).exists():
                            shutil.copy2(f, dst_cat / f.name)

        demo_data = PROJECT_ROOT / "data"
        if demo_data.is_dir():
            for fname in ["graph.json", "index.json", "embeddings.pkl"]:
                src_file = demo_data / fname
                if src_file.is_file() and not (user_data / fname).is_file():
                    shutil.copy2(src_file, user_data / fname)

    return user_base


def generate_capture_id() -> tuple[str, str]:
    """
    Generate a capture ID.

    Returns:
        (short_id, folder_id) where folder_id is {YYYY-MM-DD}_{uuid8}.
    """
    short_id = uuid.uuid4().hex[:8]
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    date_part = datetime.now(ist_tz).strftime("%Y-%m-%d")
    folder_id = f"{date_part}_{short_id}"
    return short_id, folder_id


def content_hash(data: bytes | str) -> str:
    """Return SHA-256 hash prefixed with 'sha256:'."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    return f"sha256:{digest}"


def utc_now_iso() -> str:
    """Return current IST time as ISO 8601 string with +05:30 timezone offset."""
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist_tz).strftime("%Y-%m-%dT%H:%M:%S+05:30")


def _content_filename(capture_type: str, original_filename: str | None) -> str:
    if capture_type == "note":
        return "content.md"
    if capture_type == "link":
        return "content.txt"
    if original_filename:
        suffix = Path(original_filename).suffix or ".bin"
        return f"content{suffix}"
    return "content.bin"


def write_raw_capture(meta: CaptureMeta, content: bytes | str) -> Path:
    """
    Create raw/{folder_id}/ with meta.json and content file.

    Returns:
        Path to the capture directory.
    """
    ensure_dirs()

    if isinstance(content, str):
        content_bytes = content.encode("utf-8")
    else:
        content_bytes = content

    if meta.content_hash is None:
        meta.content_hash = content_hash(content_bytes)

    folder_id = meta.folder_id
    capture_dir = get_raw_dir() / folder_id
    capture_dir.mkdir(parents=True, exist_ok=True)

    content_name = _content_filename(meta.type, meta.original_filename)
    content_path = capture_dir / content_name
    if isinstance(content, str):
        content_path.write_text(content, encoding="utf-8")
    else:
        content_path.write_bytes(content_bytes)

    meta_path = capture_dir / "meta.json"
    meta_dict = {
        "id": meta.id,
        "timestamp": meta.timestamp,
        "type": meta.type,
        "source": meta.source,
        "original_filename": meta.original_filename,
        "content_hash": meta.content_hash,
    }
    meta_path.write_text(json.dumps(meta_dict, indent=2) + "\n", encoding="utf-8")

    return capture_dir


def _load_capture_meta(meta_path: Path) -> CaptureMeta:
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    return CaptureMeta(
        id=data["id"],
        timestamp=data["timestamp"],
        type=data["type"],
        source=data["source"],
        original_filename=data.get("original_filename"),
        content_hash=data.get("content_hash"),
    )


def _find_content_file(capture_dir: Path) -> Path | None:
    for path in sorted(capture_dir.iterdir()):
        if path.name == "meta.json":
            continue
        if path.name.startswith("content."):
            return path
    return None


def _parse_raw_capture(capture_dir: Path) -> RawCapture | None:
    meta_path = capture_dir / "meta.json"
    if not meta_path.is_file():
        return None

    meta = _load_capture_meta(meta_path)
    content_path = _find_content_file(capture_dir)
    return RawCapture(
        folder_id=capture_dir.name,
        meta=meta,
        path=str(capture_dir),
        content_path=str(content_path) if content_path else None,
    )


def read_raw_captures(*, unprocessed_only: bool = False) -> list[RawCapture]:
    """
    List raw captures from raw/.

    Args:
        unprocessed_only: If True, exclude items already in index.json.
    """
    ensure_dirs()
    index = load_index() if unprocessed_only else None
    captures: list[RawCapture] = []
    raw_dir = get_raw_dir()

    if not raw_dir.is_dir():
        return captures

    for capture_dir in sorted(raw_dir.iterdir()):
        if not capture_dir.is_dir():
            continue
        raw = _parse_raw_capture(capture_dir)
        if raw is None:
            continue
        if unprocessed_only and index is not None:
            if raw.folder_id in index.raw_processed:
                continue
        captures.append(raw)

    return captures


def load_index() -> IndexState:
    """Load data/index.json, initializing defaults if missing or corrupt."""
    ensure_dirs()
    index_path = get_index_path()
    if not index_path.is_file():
        state = IndexState()
        save_index(state)
        return state

    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("index.json root must be an object")
        return IndexState.from_dict(data)
    except (json.JSONDecodeError, ValueError, OSError):
        return IndexState()


def save_index(state: IndexState) -> None:
    """Atomically write data/index.json."""
    ensure_dirs()
    index_path = get_index_path()
    tmp_path = index_path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(state.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(index_path)


def write_wiki_note(note: WikiNote) -> Path:
    """Write wiki/{para}/{id}.md with YAML frontmatter and body."""
    ensure_dirs()
    wiki_dir = get_wiki_dir()

    if note.para not in PARA_CATEGORIES:
        raise ValueError(f"Invalid PARA category: {note.para}")

    note_path = wiki_dir / note.para / f"{note.id}.md"
    frontmatter = {
        "id": note.id,
        "raw_id": note.raw_id,
        "para": note.para,
        "tags": note.tags,
        "summary": note.summary,
        "created": note.created,
        "links": note.links,
    }
    yaml_block = yaml.safe_dump(
        frontmatter,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).strip()
    content = f"---\n{yaml_block}\n---\n\n{note.body.rstrip()}\n"
    note_path.write_text(content, encoding="utf-8")
    return note_path


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_wiki_note(note_path: Path) -> WikiNote | None:
    text = note_path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None

    frontmatter = yaml.safe_load(match.group(1)) or {}
    body = match.group(2).lstrip("\n")

    para = frontmatter.get("para", "Resources")
    if para not in PARA_CATEGORIES:
        para = "Resources"

    return WikiNote(
        id=str(frontmatter.get("id", note_path.stem)),
        raw_id=str(frontmatter.get("raw_id", "")),
        para=para,
        tags=list(frontmatter.get("tags") or []),
        summary=str(frontmatter.get("summary", "")),
        created=str(frontmatter.get("created", "")),
        links=[str(link_id) for link_id in (frontmatter.get("links") or [])],
        body=body,
        path=str(note_path),
    )


def read_wiki_notes() -> list[WikiNote]:
    """Parse all wiki/**/*.md notes."""
    ensure_dirs()
    wiki_dir = get_wiki_dir()
    notes: list[WikiNote] = []

    for category in PARA_CATEGORIES:
        category_dir = wiki_dir / category
        if not category_dir.is_dir():
            continue
        for note_path in sorted(category_dir.glob("*.md")):
            note = _parse_wiki_note(note_path)
            if note is not None:
                notes.append(note)

    return notes


def delete_wiki_note(note_id: str) -> bool:
    """Delete a wiki note Markdown file by ID across all PARA categories."""
    ensure_dirs()
    wiki_dir = get_wiki_dir()
    deleted = False
    for category in PARA_CATEGORIES:
        note_path = wiki_dir / category / f"{note_id}.md"
        if note_path.is_file():
            try:
                note_path.unlink()
                deleted = True
            except Exception as e:
                print(f"Error deleting note file {note_path}: {e}")
    return deleted


def write_graph_json(nodes: list[dict], edges: list[dict], output_path: Path | None = None) -> Path:
    """Write serialized nodes and edges to graph.json atomically."""
    ensure_dirs()
    if output_path is None:
        output_path = get_data_dir() / "graph.json"

    graph_data = {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "generated_at": utc_now_iso(),
        },
    }

    tmp_path = output_path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(graph_data, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(output_path)
    return output_path
