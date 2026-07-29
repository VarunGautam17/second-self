# Second Self: Phase-wise Implementation Plan

This document outlines the detailed step-by-step, 5-phase (0-4) implementation plan for building the **Second Self** AI brain, based on the requirements from `PROBLEM_STATEMENT.md` and `architecture.md`.

---

## Phase 0: Project Foundation & Setup
**Objective:** Establish the development environment, repository structure, and core shared data/storage models.

### Tasks
1. **Initialize Project:**
   * Create the root project directory `secondself/`.
   * Initialize a Git repository.
2. **Directory Structure:**
   * Create `raw/` (for raw captures).
   * Create `wiki/` (`Projects/`, `Areas/`, `Resources/`, `Archives/`).
   * Create `data/` (for index state, embeddings, and graph datasets).
   * Create `lib/` (for modular core libraries).
   * Create `static/` (for web visualizers).
3. **Dependencies & Models:**
   * Configure `requirements.txt` (`groq`, `sentence-transformers`, `streamlit`, `pyyaml`, `numpy`, `python-dotenv`).
   * Implement shared dataclasses in `lib/models.py` (`CaptureMeta`, `WikiNote`, `GraphNode`, `GraphEdge`, `AskResult`, `IndexState`).
   * Implement helper functions in `lib/storage.py` (`generate_capture_id`, `write_raw_capture`, `write_wiki_note`, `load_index`, `save_index`).

### Exit Criteria
* [x] Repo structure exists (`raw/`, `wiki/`, `data/`, `lib/`, `static/`).
* [x] Shared data models and storage utility scripts function properly.

---

## Phase 1: Ingestion Pipeline (The Archivist)
**Objective:** Build the foundational capture mechanism that ingests any information (notes, links, files) into the `raw/` directory.

### Tasks
1. **Build `capture.py`:**
   * CLI interface supporting `note`, `link`, `file`, and interactive stdin input.
   * Auto-generates unique timestamped IDs (`{YYYY-MM-DD}_{uuid8}`).
2. **Storage Logic:**
   * Save content into `raw/{folder_id}/` with `meta.json` and `content.*`.
3. **Testing:**
   * Populate `raw/` with 10+ real personal items.

### Exit Criteria
* [x] `capture.py` successfully writes to `raw/` with unique IDs and timestamps.
* [x] `raw/` contains at least 10 real captured items.

---

## Phase 2: Classification & Linking (The Librarian)
**Objective:** Automate note categorization using LLMs and cross-linking via vector embeddings.

### Sub-Phase 2.1 — Auto-Classify
1. **Groq Integration & LLM Helper (`lib/llm.py` & `classify.py`):**
   * Implement `lib/llm.py` (`call_llm`, `classify_content`) using `llama-3.1-8b-instant`.
   * Enforce JSON output format for `para` category, `tags`, and `summary`.
   * Parse unprocessed items in `raw/` and write standard YAML frontmatter to Markdown notes.

### Sub-Phase 2.2 — Auto-Link & Embedding Cache
1. **Embeddings Helper (`lib/embeddings.py` & `link.py`):**
   * Implement `lib/embeddings.py` (`load_model`, `embed_texts`, `save_embeddings`, `load_embeddings`, `cosine_similarity`).
   * Generate 384-dimensional embeddings using `all-MiniLM-L6-v2`.
   * Save precomputed note embeddings dictionary into `data/embeddings.pkl`.
   * Auto-link high similarity pairs ($\ge 0.5$ cosine score) using `[[note_id]]` links under `## Related Notes` and frontmatter `links`.
2. **Migration & Pipeline Orchestration (`pipeline.py`):**
   * Move processed notes into `wiki/<PARA>/<id>.md`.
   * Implement `pipeline.py` (`classify`, `link`, `build_graph`, `process`).

### Exit Criteria
* [x] Raw captures automatically get PARA categories, tags, and summaries.
* [x] High-similarity notes are cross-linked without manual intervention.
* [x] Precomputed note embeddings are cached to `data/embeddings.pkl`.
* [x] `wiki/` is populated with 15+ organized items.

---

## Phase 3: Graph Generation (The Cartographer)
**Objective:** Transform flat wiki Markdown files into a structured graph dataset (`graph.json`) and render an interactive force-directed graph.

### Sub-Phase 3.1 — Graph Data Model (`build_graph.py`)
1. **Node Extraction:** Parse `wiki/**/*.md` frontmatter (`id`, `summary`, `para`, `tags`, `content_preview`, `group`).
2. **Edge Extraction:** Extract relationships from `links` frontmatter and `[[note_id]]` body regex, suppressing self-loops and duplicate edges.
3. **Data Export:** Export graph dataset to `graph.json` and `data/graph.json`, updating `last_graph_build` in `data/index.json`.

### Sub-Phase 3.2 — Interactive Graph Viewer (`static/graph.html`)
1. **`vis-network` Visualizer:** Create `static/graph.html` using `vis-network.js` force-directed layout (Barnes-Hut physics).
2. **Styling & Interactivity:** Node colors mapped to PARA categories, hover tooltips displaying note summary + content preview, drag/zoom enabled.
3. **Standalone & Streamlit Preview:** Supports standalone browser previewing and clean iframe embedding in Streamlit.

### Exit Criteria
* [x] Script `build_graph.py` builds node and edge lists from wiki notes cleanly.
* [x] `graph.json` is exported with valid node/edge schemas.
* [x] `static/graph.html` renders interactive force-directed graph with tooltips and drag/zoom.

---

## Phase 4: RAG Q&A & Deployment (The Oracle)
**Objective:** Enable natural language querying over personal notes using Retrieval-Augmented Generation (RAG) and deploy a public Streamlit web app.

### Sub-Phase 4.1 — Natural Language Search (`ask.py`)
1. **RAG Search Engine (`ask.py` & `lib/llm.py`):**
   * Embed question using `lib/embeddings.py`.
   * Retrieve top-$K$ ($K=5$) relevant notes from `data/embeddings.pkl` via cosine similarity.
   * Construct RAG prompt context and call `synthesize_answer()` via `lib/llm.py` with temperature 0.3.
   * Return structured `AskResult` with answer text and source citations (`[{id, summary, relevance_score, para}]`).
   * Provide fallback handling (*"I don't have notes about that"*) when no relevant notes match.

### Sub-Phase 4.2 — Streamlit Dashboard & Deployment (`app.py`)
1. **Streamlit UI (`app.py`):**
   * Build multi-panel layout: Ask Bar + Answer & Source Cards + Embedded `vis-network` Graph + Sidebar (Quick Capture, Process Pipeline button, Knowledge Stats).
   * Optimize performance with `@st.cache_resource` (SentenceTransformer model) and `@st.cache_data` (`graph.json`).
2. **Public Deployment:**
   * Push repository to GitHub.
   * Deploy to Streamlit Community Cloud (`share.streamlit.io`) with `GROQ_API_KEY` environment variable configured.

### Exit Criteria
* [x] `ask.py` returns accurate answers strictly grounded in personal notes with source citations.
* [x] `app.py` displays interactive knowledge graph and conversational Q&A search bar.
* [ ] Application is deployed live on a public URL.
