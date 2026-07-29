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
        if not url and "SUPABASE_URL" in st.secrets:
            url = st.secrets["SUPABASE_URL"]
        if not key and "SUPABASE_KEY" in st.secrets:
            key = st.secrets["SUPABASE_KEY"]
    except Exception:
        pass
        
    if url and key and create_client:
        try:
            _supabase_client = create_client(url, key)
            return _supabase_client
        except Exception as e:
            print(f"Failed to initialize Supabase client: {e}")
            
    return None
