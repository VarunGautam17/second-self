import os
try:
    from supabase import create_client, Client
except ImportError:
    Client = None
    create_client = None

_supabase_client = None

def get_supabase() -> Client | None:
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    
    try:
        import streamlit as st
        if not url:
            try:
                url = st.secrets.get("SUPABASE_URL", None)
            except Exception:
                pass
        if not key:
            try:
                key = st.secrets.get("SUPABASE_KEY", None)
            except Exception:
                pass
    except Exception:
        pass
        
    if url:
        url = str(url).strip()
    if key:
        key = str(key).strip()
        
    if url and key and create_client:
        try:
            _supabase_client = create_client(url, key)
            return _supabase_client
        except Exception as e:
            print(f"Failed to initialize Supabase client: {e}")
            
    return None
