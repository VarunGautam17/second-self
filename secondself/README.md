# Second Self

An AI-powered "second brain" that ingests raw information, automatically organizes it using the PARA framework, discovers implicit relationships using vector embeddings, visualizes the knowledge graph, and provides a conversational Q&A interface using Retrieval-Augmented Generation (RAG).

## Project Structure

```text
secondself/
├── raw/               # Staging area for raw captured text/links/files
├── wiki/              # Organized, classified, and auto-linked Markdown notes
├── capture.py         # Ingestion script to capture notes/links/files
├── classify.py        # LLM-based PARA categorization
├── link.py            # Local embeddings and similarity auto-linking
├── build_graph.py     # Parses wiki/ and generates graph.json
├── graph.json         # Graph topology (Nodes and Edges)
├── ask.py             # Q&A / RAG query engine
├── app.py             # Streamlit application (Graph + Chat UI)
└── requirements.txt   # Python dependencies
```

## Setup Instructions

### 1. Prerequisites
- Python 3.10 or higher
- A Groq API key (for fast LLM inference)

### 2. Environment Setup
Create a virtual environment and install the required dependencies:

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Windows (CMD):
.\venv\Scripts\activate.bat
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the `secondself/` directory and add your Groq API key:

```env
GROQ_API_KEY=your_groq_api_key_here
```

### 4. Running the Pipeline
Detailed instructions for each module will be added as they are implemented.
- **Ingestion:** `python capture.py`
- **Classification:** `python classify.py`
- **Linking:** `python link.py`
- **Graph Generation:** `python build_graph.py`
- **UI & Chat:** `streamlit run app.py`
