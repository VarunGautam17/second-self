# Second Self: Edge Cases & Corner Scenarios

This document outlines potential edge cases, failure modes, and corner scenarios for the Second Self project. Addressing these will ensure system stability, data integrity, and a reliable user experience across the 5 implementation phases.

---

## 1. Ingestion Pipeline (`capture.py`)

| Scenario | Potential Impact | Mitigation Strategy |
| :--- | :--- | :--- |
| **Empty Inputs** | Creating blank files in `raw/` that break downstream processing. | Validate input length before writing. Throw an error if input is empty or just whitespace. |
| **Unsupported File Types** | Binary files, images, or PDFs getting dumped as gibberish into Markdown files. | Explicitly check file extensions/MIME types. For Phase 1, only accept `.txt` or `.md`. (Later: add PDF/HTML parsing). |
| **Paywalled or Broken URLs** | Fetching a URL returns a 403 Forbidden, 404, or Cloudflare captcha HTML instead of content. | Implement HTTP status code checks. Save the URL itself as the note if the content cannot be scraped. |
| **Massive Files** | A 500-page book is ingested, which will later crash the LLM context window during classification. | Set a maximum file size or character limit for ingestion. Chunk large files into smaller related notes. |
| **Duplicate Captures** | The exact same URL or note is captured multiple times, leading to duplicate nodes in the graph. | Compute a hash of the content/URL and check against existing files before saving, or deduplicate during the `wiki/` migration. |

---

## 2. Classification & Linking (`classify.py` & `link.py`)

| Scenario | Potential Impact | Mitigation Strategy |
| :--- | :--- | :--- |
| **LLM Rate Limits & Timeouts** | `classify.py` fails halfway through processing `raw/` due to Groq API limits. | Implement exponential backoff and retry logic. Ensure the script tracks which files have been successfully processed so it can resume. |
| **Malformed LLM Output** | The LLM returns conversational text (e.g., "Here is your JSON:") instead of raw, parseable JSON. | Use strict system prompts demanding *only* JSON. Wrap the parsing in a `try/except` block and use regex to extract the JSON payload if wrapped in markdown blockticks. |
| **The "Super Node" Problem** | A highly generic note (e.g., "Technology") is similar to *everything*, generating hundreds of edges and cluttering the graph. | Implement a maximum edge limit per node (e.g., top 5 most similar). Raise the cosine similarity threshold. |
| **Orphaned Nodes** | A highly specific note has 0 links, making it hard to discover. | Accept this as normal behavior (not everything is related), or enforce linking it to a broad PARA category hub node. |
| **Self-Referential Links** | `link.py` calculates similarity of a note against itself and inserts a link. | Filter out the current note's UUID from the vector search space before generating edges. |

---

## 3. Graph Generation (`build_graph.py`)

| Scenario | Potential Impact | Mitigation Strategy |
| :--- | :--- | :--- |
| **Malformed YAML Frontmatter** | Manual user edits or LLM hallucinations break the YAML, crashing the parser. | Use safe YAML parsing. Skip or move malformed files to an `error/` directory instead of crashing the whole script. |
| **Dead/Broken Links** | A user manually deletes a note from `wiki/`, but other notes still link to its UUID. | The graph builder must verify that the target node ID exists before creating an edge. Ignore dead links. |
| **Special Characters in Content** | Quotes, emojis, or unescaped characters in the note title break the exported `graph.json`. | Ensure strict UTF-8 JSON serialization. Sanitize titles before export. |
| **Scale limits (Browser Crash)** | The user accumulates 5,000+ notes. Rendering 5,000 nodes simultaneously freezes the Streamlit browser tab. | Implement graph pruning in `build_graph.py` (e.g., only export the last 6 months, or only nodes with >1 connection), or use WebGL-based rendering. |

---

## 4. RAG Q&A & Deployment (`ask.py` & `app.py`)

| Scenario | Potential Impact | Mitigation Strategy |
| :--- | :--- | :--- |
| **Context Window Overflow** | Retrieving the top 10 relevant notes exceeds Llama 3's maximum token limit. | Calculate token lengths before appending context. Only inject the top-K notes that fit within the safe window limit. |
| **Out-of-Domain Questions** | User asks "What is the capital of France?" and the LLM hallucinates an answer instead of using the brain. | Strictly prompt the LLM: "Answer ONLY using the provided context. If the answer is not in the context, say 'I don't know based on your notes'." |
| **Empty Knowledge Base** | User asks a question before running `capture.py`. | Detect if `wiki/` is empty and display a friendly UI message asking the user to capture data first. |
| **Privacy & Security Risks** | The app is deployed to a public URL. Personal secrets, API keys, or private journal entries become publicly accessible. | Implement Streamlit authentication (e.g., a simple password prompt) before showing the graph or search bar. **Critical if capturing real personal data.** |
| **Mobile UI Breakage** | The force-directed graph overlaps the chat input or becomes un-draggable on smartphones. | Configure the `vis-network` canvas to be responsive (100% width/height). Restrict zoom/pan touch events on mobile if necessary. |
