"""SecondSelf Streamlit Web Application (The Oracle & The Cartographer).

Local Web Interface featuring:
- Natural Language Search & RAG Q&A Engine (ask.py)
- Interactive Force-Directed Knowledge Graph (vis-network.js)
- Quick Content Ingestion & Pipeline Processing Controls
- Wiki Knowledge Base Explorer
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from lib import models, storage, embeddings, llm
import ask
import capture
import pipeline

load_dotenv()

# Page Configuration
st.set_page_config(
    page_title="SecondSelf — Knowledge Intelligence",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling (Celevare Design System Aesthetic)
CUSTOM_CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');

  /* 1. Transparent Header & Visible Sidebar Controls */
  header[data-testid="stHeader"], [data-testid="stHeader"] {
    background-color: transparent !important;
    background: transparent !important;
    box-shadow: none !important;
    border: none !important;
  }

  [data-testid="stDecoration"], [data-testid="stStatusWidget"] {
    display: none !important;
  }

  /* Style Sidebar Collapse & Expand Toggle Buttons */
  [data-testid="stSidebarCollapseButton"], [data-testid="collapsedControl"], button[data-testid="stSidebarCollapseButton"], [data-testid="stHeader"] button {
    color: #0F172A !important;
    background-color: #FFFFFF !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04) !important;
  }

  [data-testid="stSidebarCollapseButton"] svg, [data-testid="collapsedControl"] svg, [data-testid="stHeader"] svg {
    fill: #0F172A !important;
    color: #0F172A !important;
    stroke: #0F172A !important;
  }

  /* 2. Global App Colors & Fonts */
  html, body, [data-testid="stAppViewContainer"], .stApp {
    background-color: #FAFAF8 !important;
    color: #0F172A !important;
    font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    -webkit-font-smoothing: antialiased !important;
  }

  .main .block-container {
    padding-top: 1rem !important;
    padding-bottom: 3rem !important;
    max-width: 1200px !important;
  }

  /* 3. Typography */
  h1, h2, h3, h4, h5, h6, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
    font-family: 'Manrope', system-ui, sans-serif !important;
    letter-spacing: -0.025em !important;
    color: #0F172A !important;
    font-weight: 700 !important;
  }

  p, span, label, div, .stMarkdown {
    color: #334155 !important;
  }

  /* 4. Sidebar Styling */
  section[data-testid="stSidebar"] {
    background-color: #FFFFFF !important;
    border-right: 1px solid #E2E8F0 !important;
    box-shadow: 1px 0 8px rgba(0, 0, 0, 0.02) !important;
  }

  section[data-testid="stSidebar"] * {
    color: #0F172A !important;
  }

  /* 5. Metrics Styling */
  [data-testid="stMetricValue"] {
    color: #0F172A !important;
    font-family: 'Manrope', sans-serif !important;
    font-weight: 800 !important;
    font-size: 24px !important;
  }

  [data-testid="stMetricLabel"] {
    color: #64748B !important;
    font-weight: 600 !important;
    font-size: 12px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
  }

  /* 6. Inputs & Text Areas */
  input[type="text"], input[type="number"], textarea, .stTextInput input, .stTextArea textarea, select, div[data-baseweb="select"] > div {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    padding: 10px 14px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 14px !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03) !important;
    transition: all 150ms ease !important;
  }

  input[type="text"]:focus, textarea:focus, .stTextInput input:focus, .stTextArea textarea:focus {
    border-color: #10B981 !important;
    box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15) !important;
    outline: none !important;
  }

  /* Fix Number Input Step Buttons (- / +) dark patch */
  [data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"], [data-testid="stNumberInput"] div {
    background-color: #F8FAFC !important;
    border-color: #CBD5E1 !important;
    color: #0F172A !important;
  }
  [data-testid="stNumberInputStepDown"]:hover, [data-testid="stNumberInputStepUp"]:hover {
    background-color: #F1F5F9 !important;
    color: #10B981 !important;
  }
  [data-testid="stNumberInputStepDown"] svg, [data-testid="stNumberInputStepUp"] svg {
    fill: #0F172A !important;
    color: #0F172A !important;
  }

  /* Fix File Uploader */
  [data-testid="stFileUploader"], [data-testid="stFileUploader"] > div, [data-testid="stFileUploaderDropzone"] {
    background-color: #FFFFFF !important;
    border: 1.5px dashed #CBD5E1 !important;
    border-radius: 10px !important;
  }
  [data-testid="stFileUploaderDropzone"] * {
    color: #334155 !important;
    background-color: transparent !important;
  }
  [data-testid="stFileUploaderDropzone"] button {
    background-color: #F8FAFC !important;
    color: #0F172A !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
  }

  /* 7. Standard Buttons */
  .stButton > button, button[data-testid="baseButton-secondary"] {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
    padding: 8px 16px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 13.5px !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03) !important;
    transition: all 150ms ease !important;
  }

  .stButton > button:hover {
    border-color: #10B981 !important;
    color: #10B981 !important;
    background-color: #F0FDF4 !important;
  }

  /* Primary Accent Buttons */
  .stButton > button[kind="primary"], button[data-testid="baseButton-primary"] {
    background-color: #10B981 !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    box-shadow: 0 3px 10px rgba(16, 185, 129, 0.22) !important;
  }

  .stButton > button[kind="primary"]:hover, button[data-testid="baseButton-primary"]:hover {
    background-color: #059669 !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 14px rgba(16, 185, 129, 0.32) !important;
  }

  /* 8. Sleek Tabs Bar (Blends into #FAFAF8 background) */
  [data-testid="stTabs"] [data-baseweb="tab-list"] {
    background-color: #FAFAF8 !important;
    padding: 0 !important;
    border-radius: 0 !important;
    gap: 12px !important;
    border: none !important;
    border-bottom: 1.5px solid #E2E8F0 !important;
    margin-bottom: 24px !important;
  }

  [data-testid="stTabs"] [data-baseweb="tab"] {
    height: auto !important;
    background-color: transparent !important;
    border-radius: 6px 6px 0 0 !important;
    color: #64748B !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 14.5px !important;
    padding: 10px 18px !important;
    border: none !important;
    margin: 0 !important;
    box-sizing: border-box !important;
    transition: all 150ms ease !important;
  }

  [data-testid="stTabs"] [data-baseweb="tab"] p, [data-testid="stTabs"] [data-baseweb="tab"] span, [data-testid="stTabs"] [data-baseweb="tab"] div {
    color: inherit !important;
    font-size: 14.5px !important;
    font-weight: inherit !important;
  }

  [data-testid="stTabs"] [data-baseweb="tab"]:hover {
    color: #10B981 !important;
    background-color: rgba(16, 185, 129, 0.04) !important;
  }

  [data-testid="stTabs"] [aria-selected="true"] {
    background-color: transparent !important;
    color: #0F172A !important;
    font-weight: 700 !important;
    border-bottom: 2.5px solid #10B981 !important;
    box-shadow: none !important;
  }

  [data-testid="stTabs"] [data-baseweb="tab-highlight"], [data-testid="stTabs"] [data-baseweb="tab-border"] {
    display: none !important;
  }

  /* 9. Answer & Source Cards */
  .answer-card {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-left: 4px solid #10B981 !important;
    border-radius: 12px !important;
    padding: 20px 24px !important;
    margin-top: 14px !important;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.03) !important;
    color: #0F172A !important;
    font-size: 14.5px !important;
    line-height: 1.65 !important;
  }

  .source-card {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 10px !important;
    padding: 14px 18px !important;
    margin-top: 8px !important;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.02) !important;
  }

  /* 10. Celevare PARA Badges & Hero Chips */
  .badge-projects { background-color: #10B981; color: #FFFFFF; font-weight: 700; padding: 2px 10px; border-radius: 9999px; font-size: 11px; }
  .badge-areas { background-color: #6366F1; color: #FFFFFF; font-weight: 700; padding: 2px 10px; border-radius: 9999px; font-size: 11px; }
  .badge-resources { background-color: #F59E0B; color: #FFFFFF; font-weight: 700; padding: 2px 10px; border-radius: 9999px; font-size: 11px; }
  .badge-archives { background-color: #64748B; color: #FFFFFF; font-weight: 700; padding: 2px 10px; border-radius: 9999px; font-size: 11px; }
  
  .badge-hero {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background-color: #ECFDF5;
    color: #047857;
    border: 1px solid #A7F3D0;
    font-size: 12px;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 9999px;
    margin-bottom: 12px;
  }
  .badge-hero-dot {
    width: 6px;
    height: 6px;
    background-color: #10B981;
    border-radius: 50%;
  }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# Caching Heavy Resources & Data
@st.cache_resource
def get_embedding_model():
    """Cache SentenceTransformer model in memory."""
    return embeddings.load_model()


@st.cache_data
def get_graph_data(user_slug: str | None = None):
    """Load graph dataset from user's data/graph.json."""
    graph_path = storage.get_data_dir() / "graph.json"
    if not graph_path.exists():
        graph_path = storage.PROJECT_ROOT / "graph.json"
    if graph_path.exists():
        try:
            return json.loads(graph_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"nodes": [], "edges": [], "metadata": {}}


@st.cache_data
def get_wiki_stats(user_slug: str | None = None):
    """Compute wiki note category counts and total statistics for active user."""
    notes = storage.read_wiki_notes()
    counts = {"Projects": 0, "Areas": 0, "Resources": 0, "Archives": 0}
    for note in notes:
        counts[note.para] = counts.get(note.para, 0) + 1
    return {
        "total_notes": len(notes),
        "categories": counts,
        "notes": notes,
    }


def render_graph_iframe(graph_data: dict, height: int = 680):
    """Render vis-network graph.html with inlined JSON dataset."""
    html_path = storage.PROJECT_ROOT / "static" / "graph.html"
    if not html_path.exists():
        html_path = storage.PROJECT_ROOT / "secondself" / "static" / "graph.html"
    if not html_path.exists():
        st.error("Graph viewer template static/graph.html not found.")
        return

    html_content = html_path.read_text(encoding="utf-8")
    inline_script = f"<script>window.INLINE_GRAPH_DATA = {json.dumps(graph_data)};</script>\n</head>"
    embedded_html = html_content.replace("</head>", inline_script, 1)
    components.html(embedded_html, height=height, scrolling=False)


SUPPORTED_FILE_EXTENSIONS = {".txt", ".md", ".log", ".json", ".csv"}


def handle_capture(content_str: str):
    """Ingest new content via capture module logic."""
    raw_str = content_str.strip()
    if not raw_str:
        st.sidebar.error("Please enter text, a URL, or a file path.")
        return

    # Strip quotes for file path resolution if user typed/pasted a quoted Windows path
    clean_path = raw_str.strip('"').strip("'").strip()

    if raw_str.startswith(("http://", "https://")):
        captured_text, scrape_err = capture.scrape_url(raw_str)
        c_type = "link"
        c_src = "cli"
        orig_fn = None
        if scrape_err:
            st.sidebar.warning(f"URL fetch warning: {scrape_err}")
    elif os.path.isfile(clean_path) or (len(clean_path) < 300 and any(clean_path.lower().endswith(ext) for ext in SUPPORTED_FILE_EXTENSIONS) and os.path.exists(clean_path)):
        file_path = os.path.abspath(clean_path)
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in SUPPORTED_FILE_EXTENSIONS:
            st.sidebar.error(f"Unsupported file extension '{ext}'. Supported: {', '.join(sorted(SUPPORTED_FILE_EXTENSIONS))}")
            return
        if os.path.getsize(file_path) > 20 * 1024 * 1024:
            st.sidebar.error("File size exceeds safety limit of 20MB.")
            return
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                captured_text = f.read()
            c_type = "file"
            c_src = "path"
            orig_fn = os.path.basename(file_path)
        except Exception as e:
            st.sidebar.error(f"Error reading file from path: {e}")
            return
    else:
        # Standard plaintext note / transcript capture
        captured_text = raw_str
        c_type = "note"
        c_src = "cli"
        orig_fn = None

    if capture.check_duplicate(captured_text)[0]:
        st.sidebar.info("Item already exists in raw captures (duplicate content).")
        return

    short_id, _ = storage.generate_capture_id()
    meta = models.CaptureMeta(
        id=short_id,
        timestamp=storage.utc_now_iso(),
        type=c_type,
        source=c_src,
        original_filename=orig_fn,
        content_hash=storage.content_hash(captured_text),
    )
    saved_dir = storage.write_raw_capture(meta, captured_text)
    st.sidebar.success(f"Captured ({len(captured_text)} chars) -> raw/{saved_dir.name}")


def handle_uploaded_file(uploaded_file):
    """Ingest uploaded file directly from Streamlit browser widget."""
    if uploaded_file is None:
        st.sidebar.error("Please select a file to upload.")
        return

    try:
        bytes_data = uploaded_file.getvalue()
        captured_text = bytes_data.decode("utf-8", errors="replace")
    except Exception as e:
        st.sidebar.error(f"Failed to read uploaded file: {e}")
        return

    if not captured_text.strip():
        st.sidebar.error("Uploaded file is empty.")
        return

    if capture.check_duplicate(captured_text)[0]:
        st.sidebar.info("Uploaded item already exists in raw captures (duplicate content).")
        return

    short_id, _ = storage.generate_capture_id()
    meta = models.CaptureMeta(
        id=short_id,
        timestamp=storage.utc_now_iso(),
        type="file",
        source="upload",
        original_filename=uploaded_file.name,
        content_hash=storage.content_hash(captured_text),
    )
    saved_dir = storage.write_raw_capture(meta, captured_text)
    st.sidebar.success(f"Uploaded '{uploaded_file.name}' ({len(captured_text)} chars) -> raw/{saved_dir.name}")


def render_auth_screen():
    """Render landing screen prompting user for Name and Groq API Key."""
    st.markdown("""
    <div style='text-align: center; padding-top: 30px; padding-bottom: 20px;'>
        <h1 style='font-size: 3.5rem; font-weight: 800; font-family: "Manrope", "Inter", sans-serif; color: #0F172A; letter-spacing: -0.04em; margin-bottom: 8px;'>
            Second<span style='color: #10B981;'>Self</span>
        </h1>
        <p style='font-size: 1.15rem; color: #64748B; max-width: 600px; margin: 0 auto 24px auto; font-family: "Inter", sans-serif;'>
            Your private, AI-powered Personal Knowledge Brain. Sign in with your name and Groq API key to access your personalized workspace.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2.2, 1])
    with col2:
        with st.form("auth_form", clear_on_submit=False):
            st.markdown("### 🔑 Access Your 2nd Brain")
            user_name_input = st.text_input("Your Name / Username", placeholder="e.g. Varun Gautam")
            groq_key_input = st.text_input(
                "Groq API Key",
                type="password",
                placeholder="gsk_...",
                help="Enter your personal Groq API key from console.groq.com"
            )
            seed_demo = st.checkbox(
                "Load Demo Knowledge Base (Pre-populates sample PARA notes & graph)",
                value=True
            )

            submitted = st.form_submit_button("Enter My 2nd Brain 🚀", use_container_width=True)

            if submitted:
                clean_name = user_name_input.strip()
                clean_key = groq_key_input.strip()

                if not clean_name:
                    st.error("Please enter your name or username to identify your 2nd brain.")
                    return

                # If user left API key empty, fallback to server secrets / env if available
                if not clean_key:
                    if "GROQ_API_KEY" in st.secrets:
                        clean_key = st.secrets["GROQ_API_KEY"]
                    else:
                        clean_key = os.environ.get("GROQ_API_KEY", "")

                if not clean_key:
                    st.error("Please enter your Groq API Key. Get a free key at https://console.groq.com/")
                    return

                with st.spinner("Validating Groq API key..."):
                    if hasattr(llm, "validate_groq_api_key"):
                        valid, msg = llm.validate_groq_api_key(clean_key)
                    else:
                        try:
                            from groq import Groq
                            test_client = Groq(api_key=clean_key)
                            test_client.models.list()
                            valid, msg = True, "API Key successfully validated!"
                        except Exception as ex:
                            valid, msg = False, f"Invalid Groq API key: {ex}"

                if not valid:
                    st.error(msg)
                    return

                # Create clean slug for user folder (e.g. "varun_gautam")
                user_slug = re.sub(r'[^a-zA-Z0-9_-]', '_', clean_name.lower())
                storage.init_user_workspace(user_slug, copy_demo_data=seed_demo)

                st.session_state["user_name"] = clean_name
                st.session_state["user_slug"] = user_slug
                st.session_state["groq_api_key"] = clean_key
                st.session_state["user_authenticated"] = True

                st.cache_data.clear()
                st.success(f"Welcome back, {clean_name}!")
                st.rerun()


def main():
    # 1. User Authentication Check
    if "user_authenticated" not in st.session_state:
        st.session_state["user_authenticated"] = False

    if not st.session_state["user_authenticated"]:
        render_auth_screen()
        return

    user_name = st.session_state.get("user_name", "User")
    user_slug = st.session_state.get("user_slug", "default")

    # Load model and stats for active user session
    emb_model = get_embedding_model()
    wiki_stats = get_wiki_stats(user_slug)
    graph_data = get_graph_data(user_slug)

    # Initialize RAG input session state
    if "rag_query_input" not in st.session_state:
        st.session_state["rag_query_input"] = ""

    # SIDEBAR CONTROL PANEL
    with st.sidebar:
        st.markdown("<h2 style='margin-bottom:0px; font-weight:800; font-family:\"Inter\", sans-serif; color:#0F172A; letter-spacing:-0.035em; display:inline-block;'>Second<span style='color:#10B981;'>Self</span></h2>", unsafe_allow_html=True)
        st.caption("Personal Knowledge Intelligence")

        # Active User Identity Badge & Logout
        st.info(f"👤 Logged in as **{user_name}**")
        st.success("Groq API Connected", icon="✅")

        if st.button("Switch User / Log Out 🚪", key="btn_logout", use_container_width=True):
            st.session_state["user_authenticated"] = False
            st.session_state["user_name"] = ""
            st.session_state["user_slug"] = ""
            st.session_state["groq_api_key"] = ""
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")

        # Knowledge Base Statistics
        st.subheader("Knowledge Stats")
        col1, col2 = st.columns(2)
        col1.metric("Wiki Notes", wiki_stats["total_notes"])
        col2.metric("Graph Nodes", len(graph_data.get("nodes", [])))

        cats = wiki_stats["categories"]
        st.caption(
            f"**Projects:** {cats['Projects']} | **Areas:** {cats['Areas']} | **Resources:** {cats['Resources']} | **Archives:** {cats['Archives']}"
        )
        st.caption(f"**Graph Edges:** {len(graph_data.get('edges', []))}")

        st.markdown("---")

        # Ingestion UI with Tabs for Upload & Text/URL
        st.subheader("Ingest Content")
        ingest_tab_file, ingest_tab_text = st.tabs(["Upload File", "Text / Path"])

        with ingest_tab_file:
            uploaded_file = st.file_uploader(
                "Browse or Drag & Drop File:",
                type=["txt", "md", "log", "json", "csv"],
                key="sidebar_file_uploader",
                help="Drag & drop any text file or transcript here."
            )
            if st.button("Ingest Uploaded File", use_container_width=True, key="btn_upload_file"):
                if uploaded_file:
                    handle_uploaded_file(uploaded_file)
                    st.cache_data.clear()
                else:
                    st.error("Please choose a file first.")

        with ingest_tab_text:
            capture_input = st.text_area(
                "Paste Text, Transcript, URL, or Path:",
                placeholder="Paste text note, transcript, URL (https://...), or file path (e.g. C:\\Users\\...)",
                height=110,
                key="sidebar_text_area",
            )
            if st.button("Ingest Content", use_container_width=True, key="btn_ingest_text"):
                if capture_input:
                    handle_capture(capture_input)
                    st.cache_data.clear()
                else:
                    st.error("Please enter content or path.")

        st.markdown("---")

        # Pipeline Processing Control
        st.subheader("Pipeline Controls")
        if st.button("Run Pipeline (Process & Link)", use_container_width=True, type="primary"):
            with st.spinner("Processing raw captures, computing embeddings & rebuilding graph..."):
                pipeline.run_process(threshold=0.4)
                st.cache_data.clear()
                st.success("Pipeline executed successfully!")
                st.rerun()

        if st.button("Refresh Cache", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # MAIN CONTENT PANEL
    st.markdown('<div class="badge-hero"><span class="badge-hero-dot"></span> An AI project to imitate your personal brain</div>', unsafe_allow_html=True)
    st.markdown('<h1 style="font-size:36px; font-weight:800; margin-bottom:6px; font-family:\'Inter\', sans-serif; color:#0F172A; letter-spacing:-0.035em; display:inline-block;">Second<span style="color:#10B981;">Self</span></h1>', unsafe_allow_html=True)
    st.markdown('<p style="color:#64748B; font-size:15px; margin-bottom:24px;">Your Personal Knowledge Intelligence Platform — PARA Framework, Knowledge Graph & RAG Search</p>', unsafe_allow_html=True)

    tab_ask, tab_graph, tab_wiki = st.tabs([
        "Ask Knowledge Base",
        "Knowledge Graph",
        "Wiki Explorer",
    ])

    # TAB 1: RAG Q&A SEARCH
    with tab_ask:
        st.subheader("Natural Language Query & RAG Synthesis")
        st.write("Ask questions in plain English to search and synthesize answers grounded in your personal notes.")

        # Quick Example Queries with working Session State Click Handlers
        st.markdown("**Quick Examples:**")
        ex_col1, ex_col2, ex_col3 = st.columns(3)
        if ex_col1.button("Notes about embeddings", use_container_width=True, key="btn_ex1"):
            st.session_state["rag_query_input"] = "What notes do I have about embeddings?"
            st.rerun()
        if ex_col2.button("Tokyo packing list", use_container_width=True, key="btn_ex2"):
            st.session_state["rag_query_input"] = "What items do I have in my Tokyo trip packing list?"
            st.rerun()
        if ex_col3.button("Summarize active projects", use_container_width=True, key="btn_ex3"):
            st.session_state["rag_query_input"] = "Summarize my active projects and current work"
            st.rerun()

        user_query = st.text_input(
            "Enter your question:",
            key="rag_query_input",
            placeholder="e.g. What is the formula for similarity search in vector embeddings?",
        )

        col_ask_btn, col_top_k = st.columns([4, 1])
        top_k_val = col_top_k.number_input("Top K Sources", min_value=1, max_value=10, value=5)
        run_search = col_ask_btn.button("Search Knowledge Base", type="primary", use_container_width=True)

        if run_search and user_query:
            with st.spinner("Searching knowledge base & synthesizing answer with Groq LLM..."):
                result = ask.ask(user_query, top_k=top_k_val, score_threshold=0.05, model=emb_model)

            # Render Answer Panel
            st.markdown("### Answer")
            st.markdown(f'<div class="answer-card">{result.answer}</div>', unsafe_allow_html=True)

            # Render Sources Panel
            st.markdown("### Cited Sources")
            if result.sources:
                for src in result.sources:
                    badge_class = f"badge-{src.para.lower()}"
                    st.markdown(
                        f"""
                        <div class="source-card">
                          <span class="{badge_class}">{src.para}</span>
                          <strong>Note ID:</strong> <code>{src.id}</code> — <em>Relevance: {src.relevance_score:.4f}</em><br/>
                          <div style="margin-top: 4px; font-size: 13px; color: #475569;">{src.summary}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.info("No relevant note sources passed the similarity threshold.")


    # TAB 2: INTERACTIVE KNOWLEDGE GRAPH
    with tab_graph:
        st.subheader("Interactive Knowledge Brain Topology")
        st.caption("Powered by vis-network.js Barnes-Hut force-directed layout. Hover nodes for tooltips, click nodes to view details, and use category filters.")

        g_data = get_graph_data()
        if not g_data.get("nodes"):
            st.warning("No graph dataset found. Please run the pipeline to generate graph.json.")
        else:
            render_graph_iframe(g_data, height=720)

    # TAB 3: WIKI EXPLORER
    with tab_wiki:
        st.subheader("Wiki Notes Directory")
        notes = wiki_stats["notes"]

        cat_filter = st.selectbox("Filter by PARA Category:", ["All", "Projects", "Areas", "Resources", "Archives"])
        search_filter = st.text_input("Search notes by title, tag, or content:", placeholder="Type to filter...")

        filtered_notes = notes
        if cat_filter != "All":
            filtered_notes = [n for n in filtered_notes if n.para == cat_filter]
        if search_filter:
            sf_lower = search_filter.lower()
            filtered_notes = [
                n for n in filtered_notes
                if sf_lower in n.summary.lower()
                or sf_lower in n.body.lower()
                or any(sf_lower in t.lower() for t in n.tags)
                or sf_lower in n.id.lower()
            ]

        st.caption(f"Showing {len(filtered_notes)} of {len(notes)} notes")

        for note in filtered_notes:
            with st.expander(f"[{note.para}] {note.id} — {note.summary}"):
                c1, c2, c3 = st.columns(3)
                c1.write(f"**ID:** `{note.id}`")
                c2.write(f"**Category:** `{note.para}`")
                c3.write(f"**Created:** `{note.created}`")

                st.write(f"**Tags:** {', '.join(['#' + t for t in note.tags])}")
                st.markdown("**Body:**")
                st.code(note.body, language="markdown")

                if st.button(f"Delete Note {note.id}", key=f"btn_del_{note.id}"):
                    if storage.delete_wiki_note(note.id):
                        pipeline.run_process(threshold=0.4)
                        st.cache_data.clear()
                        st.success(f"Deleted note {note.id} and updated knowledge brain!")
                        st.rerun()
                    else:
                        st.error(f"Could not find or delete note file for ID {note.id}")


if __name__ == "__main__":
    main()

