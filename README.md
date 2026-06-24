# gsas-query — GSAS-II Documentation Assistant

Semantic search + AI answers over the full GSAS-II documentation set:
**129 HTML pages** (home, help, and all 62 tutorials) plus the
**Programmer's Guide** and **Powder Crystallography** book PDFs.

Answers include **inline citations** — every `[N]` in the response is a
clickable link to the exact documentation section that supported that sentence.

All embedding and retrieval runs on your machine — no data is sent externally
unless you explicitly choose the Anthropic API backend.

---

## Installation

### pip

```bash
pip install gsas-query
```

Or install directly from source:

```bash
pip install git+https://github.com/pawantr/Query-GSAS.git
```

### conda

```bash
conda install -c conda-forge gsas-query
```

### Into an existing GSAS-II environment

```bash
# Activate the GSAS-II conda environment first, then:
pip install gsas-query
```

### Development / editable install

```bash
git clone https://github.com/pawantr/Query-GSAS.git
cd Query-GSAS
pip install -e ".[dev]"
```

---

## Ollama — free local LLM (recommended)

```bash
brew install ollama          # macOS; see https://ollama.com for other platforms
ollama serve &               # start the local server
ollama pull llama3           # ~5 GB one-time download
```

Other model options: `llama3:70b` (better quality, ~40 GB), `mistral` (faster, ~4 GB).

---

## First-time setup — index the documentation

Run once, or again when the docs are updated. Fetches ~130 web pages and 2 PDFs,
embeds everything locally. Takes ~10–20 minutes.

The index is stored in `~/.gsas_query/chroma_db` (override with `GSAS_QUERY_DATA_DIR`).

```bash
gsas-query --setup              # all sources (HTML + PDFs)
gsas-query --setup --html-only  # skip PDFs, faster (~5 min)
gsas-query --setup --reset      # drop index and rebuild from scratch
```

---

## Usage

### Command-line — single question

```bash
gsas-query "How do I set up a sequential refinement?"
gsas-query "What parameters control the background in Rietveld?"
gsas-query "How do I export a CIF for publication?"
```

### Command-line — interactive REPL

Multi-turn conversation that remembers previous questions in the session.

```bash
gsas-query
```

```
GSAS-II Documentation Assistant
════════════════════════════════════════════════════════════════════════════════

Knowledge base: 3,847 indexed chunks.
LLM backend: ollama
Type your question and press Enter. 'clear' resets history, 'quit' exits.

────────────────────────────────────────────────────────────────────────────────
You: How do I constrain lattice parameters?
Thinking…
Assistant: To constrain lattice parameters in GSAS-II, open the Constraints
tab in the Phase panel [1]…

Sources:
  [94%] Help: Phase General  ›  Constraints
         https://advancedphotonsource.github.io/GSAS-II-tutorials/help/phasegeneral.html
```

Commands inside the REPL: `clear` (reset history), `quit` / `exit` (exit).

### Desktop GUI

Opens a standalone floating dialog — stays open while you work in GSAS-II.

```bash
gsas-query --gui
```

### Embed in GSAS-II Help menu

Add one call to the GSAS-II menu handler (e.g. in `GSASIIctrl.py`):

```python
def OnDocAssistant(self, event):
    try:
        from gsas_query.gui import show_assistant
        show_assistant(self)          # self = GSAS-II main frame
    except ImportError:
        wx.MessageBox(
            "GSAS-II Assistant not installed.\n"
            "Run: pip install gsas-query",
            "Not available"
        )
```

`show_assistant()` is idempotent — calling it a second time raises the existing
window rather than opening a duplicate.

### Web UI

```bash
gsas-query-web                          # serves on 0.0.0.0:8000
HOST=127.0.0.1 PORT=8765 gsas-query-web
```

Then open `http://localhost:8000` in a browser. The web UI shows inline citations
as clickable superscript links and source chips below each answer.

---

## CLI flags reference

| Flag | Description |
|---|---|
| `--setup` | Index all documentation sources |
| `--setup --reset` | Drop the existing index and rebuild |
| `--setup --html-only` | Index HTML only, skip PDFs |
| `--gui` | Open the wxPython desktop assistant |
| `--backend ollama\|anthropic\|retrieval` | Override `LLM_BACKEND` env var |
| `--model <name>` | Override Ollama or Anthropic model |
| `--stats` | Show chunk count, backend, and DB path |

---

## LLM backend configuration

Set `LLM_BACKEND` in a `.env` file or the environment:

| Backend | Config | Notes |
|---|---|---|
| `ollama` (default) | `OLLAMA_MODEL=llama3` | Free, fully local — no data leaves the network |
| `anthropic` | `ANTHROPIC_API_KEY=sk-ant-…` | Better answers; queries sent to Anthropic |
| `retrieval` | — | No LLM — returns raw matched chunks; useful offline or for testing |

```bash
gsas-query --backend retrieval "What is Le Bail extraction?"
gsas-query --backend ollama --model mistral "How do I index peaks?"
```

---

## Inline citations

When using Ollama or Anthropic backends, answers contain `[N]` markers inline.
In the **web UI** these render as clickable superscript links opening the exact
source section. In the **CLI**, source URLs are listed below the answer with
relevance scores.

---

## Doc sources

| Category | Count |
|---|---|
| Home / installation pages | 22 |
| Help pages (all sections) | 42 |
| Tutorials | 62 |
| Programmer's Guide (PDF, readthedocs) | 1 |
| Powder Crystallography book (PDF, auto-fetches latest release) | 1 |
| **Total** | **128 sources** |

All HTML sources are fetched from
`https://advancedphotonsource.github.io/GSAS-II-tutorials/`.
The book PDF is fetched from the latest GitHub release of
[briantoby/PowderCrystallography](https://github.com/briantoby/PowderCrystallography/releases).

---

## Re-indexing when docs update

```bash
gsas-query --setup --reset
```

Or trigger via the web API (requires `ADMIN_KEY` set in `.env`):

```bash
curl -X POST http://localhost:8000/ingest -H "X-Admin-Key: your-key"
```

---

## Security and deployment notes

- All embeddings and vector search run locally (sentence-transformers, ChromaDB).
- Ollama runs entirely on-premises — no queries leave the network.
- The `anthropic` backend sends question text and retrieved doc chunks to Anthropic.
  Do not use it in air-gapped or data-sensitive environments.
- The web server applies per-IP rate limiting (default 30 req/min, configurable
  via `RATE_LIMIT_RPM` in `.env`).
- The `/ingest` endpoint is protected by `X-Admin-Key`; leave `ADMIN_KEY` blank
  to disable remote re-indexing.

---

## User data directory

The ChromaDB index is stored at `~/.gsas_query/chroma_db` by default.
Override with the `GSAS_QUERY_DATA_DIR` environment variable:

```bash
GSAS_QUERY_DATA_DIR=/data/gsas_query gsas-query --setup
```
