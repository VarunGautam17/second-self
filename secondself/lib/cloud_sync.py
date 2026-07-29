import os
from pathlib import Path
from lib.supabase_client import get_supabase
from lib.storage import PROJECT_ROOT

BUCKET_NAME = "secondself"

def sync_from_cloud(user_slug: str) -> None:
    """Download all user files from Supabase to local ephemeral filesystem."""
    client = get_supabase()
    if not client:
        return
        
    user_prefix = f"users/{user_slug}/"
    _download_folder(client, user_prefix, PROJECT_ROOT / "users" / user_slug)

def _download_folder(client, prefix: str, local_dir: Path) -> None:
    try:
        files = client.storage.from_(BUCKET_NAME).list(prefix)
        for f in files:
            name = f["name"]
            if name == ".emptyFolderPlaceholder":
                continue
            
            # If it's a file (usually has an id or metadata in Supabase response)
            # Supabase storage list returns metadata for files, but just {"name": "subdir"} for folders
            is_file = "id" in f or "metadata" in f or "." in name
            if is_file:
                local_path = local_dir / name
                local_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    data = client.storage.from_(BUCKET_NAME).download(f"{prefix}{name}")
                    local_path.write_bytes(data)
                except Exception as e:
                    print(f"Error downloading {prefix}{name}: {e}")
            else:
                # It's a directory
                _download_folder(client, f"{prefix}{name}/", local_dir / name)
    except Exception as e:
        # Supabase raises if folder doesn't exist or is empty
        pass

def sync_to_cloud(user_slug: str) -> None:
    """Upload all user files from local ephemeral filesystem to Supabase."""
    client = get_supabase()
    if not client:
        return
        
    user_dir = PROJECT_ROOT / "users" / user_slug
    if not user_dir.exists():
        return
        
    _upload_folder(client, user_dir, f"users/{user_slug}/")

def _upload_folder(client, local_dir: Path, prefix: str) -> None:
    for item in local_dir.iterdir():
        if item.is_file():
            key = f"{prefix}{item.name}"
            try:
                data = item.read_bytes()
                client.storage.from_(BUCKET_NAME).upload(key, data, {"upsert": "true"})
            except Exception as e:
                print(f"Error uploading {key}: {e}")
        elif item.is_dir():
            _upload_folder(client, item, f"{prefix}{item.name}/")

def delete_from_cloud(user_slug: str) -> None:
    """Recursively delete user workspace directory from Supabase storage."""
    client = get_supabase()
    if not client:
        return
    prefix = f"users/{user_slug}/"
    _delete_folder(client, prefix)

def _delete_folder(client, prefix: str) -> None:
    try:
        files = client.storage.from_(BUCKET_NAME).list(prefix)
        file_paths = []
        for f in files:
            name = f["name"]
            if name == ".emptyFolderPlaceholder":
                continue
            is_file = "id" in f or "metadata" in f or "." in name
            if is_file:
                file_paths.append(f"{prefix}{name}")
            else:
                _delete_folder(client, f"{prefix}{name}/")
        if file_paths:
            client.storage.from_(BUCKET_NAME).remove(file_paths)
    except Exception as e:
        print(f"Error deleting folder {prefix}: {e}")

def get_username_for_api_key(api_key: str) -> str | None:
    """Check if the given API key is already associated with any registered username."""
    client = get_supabase()
    if client:
        try:
            # List all folders under users/ in Supabase
            files = client.storage.from_(BUCKET_NAME).list("users")
            for f in files:
                slug = f["name"]
                if slug == ".emptyFolderPlaceholder":
                    continue
                try:
                    data = client.storage.from_(BUCKET_NAME).download(f"users/{slug}/config.json")
                    import json
                    cfg = json.loads(data.decode("utf-8"))
                    if cfg.get("api_key") == api_key:
                        return cfg.get("user_name", slug)
                except Exception:
                    pass
        except Exception as e:
            print(f"Error checking API key ownership in cloud: {e}")
    else:
        # Check local files
        users_dir = PROJECT_ROOT / "users"
        if users_dir.is_dir():
            for user_folder in users_dir.iterdir():
                if user_folder.is_dir():
                    cfg_path = user_folder / "config.json"
                    if cfg_path.is_file():
                        try:
                            import json
                            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                            if cfg.get("api_key") == api_key:
                                return cfg.get("user_name")
                        except Exception:
                            pass
    return None


