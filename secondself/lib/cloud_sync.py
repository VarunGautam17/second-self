import os
import json
from pathlib import Path
from lib.supabase_client import get_supabase
from lib.storage import PROJECT_ROOT

BUCKET_NAME = "secondself"

def ensure_bucket_exists(client) -> bool:
    """Ensure the storage bucket exists in Supabase, creating it if missing."""
    try:
        buckets = client.storage.list_buckets()
        exists = any(
            (getattr(b, "name", None) == BUCKET_NAME or getattr(b, "id", None) == BUCKET_NAME or (isinstance(b, dict) and b.get("name") == BUCKET_NAME))
            for b in buckets
        )
        if not exists:
            try:
                client.storage.create_bucket(BUCKET_NAME, options={"public": True})
            except Exception as e:
                print(f"Could not auto-create bucket '{BUCKET_NAME}': {e}")
        return True
    except Exception as e:
        print(f"Error checking Supabase bucket: {e}")
        return False

def sync_from_cloud(user_slug: str) -> bool:
    """Download all user files from Supabase to local ephemeral filesystem."""
    client = get_supabase()
    if not client:
        return False
    ensure_bucket_exists(client)
    _download_folder(client, f"users/{user_slug}", PROJECT_ROOT / "users" / user_slug)
    return True

def _download_folder(client, prefix: str, local_dir: Path) -> None:
    clean_prefix = prefix.strip("/")
    try:
        files = client.storage.from_(BUCKET_NAME).list(clean_prefix)
        if not files:
            return
        for f in files:
            name = f.get("name")
            if not name or name == ".emptyFolderPlaceholder":
                continue
            
            item_path = f"{clean_prefix}/{name}" if clean_prefix else name
            
            # A file has a non-None id or metadata with size in Supabase storage
            is_file = f.get("id") is not None or (isinstance(f.get("metadata"), dict) and "size" in f["metadata"])
            
            if is_file:
                local_path = local_dir / name
                local_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    data = client.storage.from_(BUCKET_NAME).download(item_path)
                    local_path.write_bytes(data)
                except Exception as e:
                    print(f"Error downloading {item_path}: {e}")
            else:
                # Recurse into subdirectory
                _download_folder(client, item_path, local_dir / name)
    except Exception as e:
        print(f"Error listing folder '{clean_prefix}': {e}")

def sync_to_cloud(user_slug: str) -> bool:
    """Upload all user files from local ephemeral filesystem to Supabase."""
    client = get_supabase()
    if not client:
        return False
    ensure_bucket_exists(client)
    user_dir = PROJECT_ROOT / "users" / user_slug
    if not user_dir.exists():
        return False
        
    _upload_folder(client, user_dir, f"users/{user_slug}")
    return True

def _upload_folder(client, local_dir: Path, prefix: str) -> None:
    clean_prefix = prefix.strip("/")
    for item in local_dir.iterdir():
        item_key = f"{clean_prefix}/{item.name}" if clean_prefix else item.name
        if item.is_file():
            try:
                data = item.read_bytes()
                try:
                    client.storage.from_(BUCKET_NAME).upload(item_key, data, {"upsert": "true"})
                except Exception:
                    # Fallback to update if upload raises conflict
                    client.storage.from_(BUCKET_NAME).update(item_key, data)
            except Exception as e:
                print(f"Error uploading {item_key}: {e}")
        elif item.is_dir():
            _upload_folder(client, item, item_key)

def delete_from_cloud(user_slug: str) -> None:
    """Recursively delete user workspace directory from Supabase storage."""
    client = get_supabase()
    if not client:
        return
    prefix = f"users/{user_slug}"
    _delete_folder(client, prefix)

def _delete_folder(client, prefix: str) -> None:
    clean_prefix = prefix.strip("/")
    try:
        files = client.storage.from_(BUCKET_NAME).list(clean_prefix)
        file_paths = []
        for f in files:
            name = f.get("name")
            if not name or name == ".emptyFolderPlaceholder":
                continue
            item_path = f"{clean_prefix}/{name}"
            is_file = f.get("id") is not None or (isinstance(f.get("metadata"), dict) and "size" in f["metadata"])
            if is_file:
                file_paths.append(item_path)
            else:
                _delete_folder(client, item_path)
        if file_paths:
            client.storage.from_(BUCKET_NAME).remove(file_paths)
    except Exception as e:
        print(f"Error deleting folder {clean_prefix}: {e}")

def get_username_for_api_key(api_key: str) -> str | None:
    """Check if the given API key is already associated with any registered username."""
    client = get_supabase()
    if client:
        try:
            files = client.storage.from_(BUCKET_NAME).list("users")
            for f in files:
                slug = f.get("name")
                if not slug or slug == ".emptyFolderPlaceholder":
                    continue
                try:
                    data = client.storage.from_(BUCKET_NAME).download(f"users/{slug}/config.json")
                    cfg = json.loads(data.decode("utf-8"))
                    if cfg.get("api_key") == api_key:
                        return cfg.get("user_name", slug)
                except Exception:
                    pass
        except Exception as e:
            print(f"Error checking API key ownership in cloud: {e}")
    else:
        users_dir = PROJECT_ROOT / "users"
        if users_dir.is_dir():
            for user_folder in users_dir.iterdir():
                if user_folder.is_dir():
                    cfg_path = user_folder / "config.json"
                    if cfg_path.is_file():
                        try:
                            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                            if cfg.get("api_key") == api_key:
                                return cfg.get("user_name")
                        except Exception:
                            pass
    return None
