# Query-GSAS — GSAS-II Documentation Assistant

Semantic search + AI answers over the full GSAS-II documentation set:
**129 HTML pages** (home, help, and all 62 tutorials) plus the
**Programmer's Guide** and **Powder Crystallography** book PDFs.

Answers include **inline citations** — every `[N]` in the response is a
clickable link to the exact documentation section that supported that sentence.

Queries run entirely on your machine — no data is sent externally unless
you opt into the Anthropic API backend.

---

## Requirements

- Python 3.10+
- Packages in `requirements.txt` (installable into the existing GSAS-II Python environment)
- For AI-generated answers: [Ollama](https://ollama.com) (free, local) **or** an Anthropic API key

---

## Installation

```bash
# From the GSAS-II Python environment (or any Python 3.10+ env):
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
```

---

## Ollama setup (recommended — free, fully local)

```bash
brew install ollama          # macOS; see https://ollama.com for other platforms
ollama serve &               # start the local server
ollama pull llama3           # ~5 GB, good balance of speed and quality
```

Other model options:
```bash
ollama pull llama3:70b       # ~40 GB, better quality
ollama pull mistral          # ~4 GB, faster
```

---

## First-time setup — index the documentation

Run once (or again after docs are updated). Fetches ~130 web pages and
2 PDFs, embeds them locally. Takes ~10–20 minutes.

```bash
python cli.py --setup              # all sources (HTML + PDFs)
python cli.py --setup --html-only  # skip PDFs, faster (~5 min)
python cli.py --setup --reset      # drop index and rebuild from scratch
```

---

## Usage

### 1. Command-line — single question

```bash
python cli.py "How do I set up a sequential refinement?"
python cli.py "What parameters control the background in Rietveld?"
python cli.py "How do I export a CIF for publication?"
```

### 2. Command-line — interactive REPL

Multi-turn conversation with memory of previous questions in the session.

```bash
python cli.py
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
tab in the Phase panel…

Sources:
  [94%] Help: Phase General  ›  Constraints
         https://advancedphotonsource.github.io/GSAS-II-tutorials/help/phasegeneral.html
```

Commands inside the REPL:
- `clear` — reset conversation history
- `quit` / `exit` / `q` — exit

### 3. CLI flags reference

| Flag | Description |
|---|---|
| `--setup` | Index all documentation sources |
| `--setup --reset` | Drop the existing index and rebuild |
| `--setup --html-only` | Index HTML only, skip PDFs |
| `--backend ollama\|anthropic\|retrieval` | Override `LLM_BACKEND` env var |
| `--model <name>` | Override Ollama model or Anthropic model |
| `--stats` | Show chunk count, backend, and DB path, then exit |

```bash
python cli.py --stats
python cli.py --backend retrieval "What is Le Bail extraction?"
python cli.py --backend ollama --model mistral "How do I index peaks?"
```

### 4. Web UI

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
# then open http://localhost:8000
```

The web UI supports inline citations: every `[N]` in the answer is a
superscript link that opens the exact source section in a new tab.
Source chips at the bottom of each answer also link directly to the documentation.

### 5. wxPython GUI (standalone)

```bash
python gui.py
```

Requires wxPython (included with GSAS-II). Opens a modeless dialog that
stays open while you work in GSAS-II.

### 6. Embed in GSAS-II Help menu

Add to the relevant GSAS-II menu handler (e.g. `GSASIIctrl.py`):

```python
def OnDocAssistant(self, event):
    try:
        from gsas_query.gui import show_assistant
        show_assistant(self)
    except ImportError:
        wx.MessageBox(
            "GSAS-II Assistant not installed.\n"
            "See https://github.com/pawantr/Query-GSAS",
            "Not available"
        )
```

Calling `show_assistant()` a second time raises the existing window rather
than opening a duplicate.

---

## LLM backend configuration

Set `LLM_BACKEND` in `.env` or the environment:

| Backend | Config | Notes |
|---|---|---|
| `ollama` (default) | `OLLAMA_MODEL=llama3` | Free, fully local — no data leaves the network |
| `anthropic` | `ANTHROPIC_API_KEY=sk-ant-…` | Better answers; queries sent to Anthropic |
| `retrieval` | — | No LLM — returns raw matched chunks; useful offline or for testing |

---

## Inline citations

When using Ollama or Anthropic backends, every answer contains `[N]` markers
inline. In the web UI these render as clickable superscript links leading
directly to the source section. In the CLI, source URLs are listed below the
answer with relevance scores.

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

## Re-ingesting when docs update

```bash
python cli.py --setup --reset
```

Or trigger via the web API (requires `ADMIN_KEY` set in `.env`):

```bash
curl -X POST http://localhost:8000/ingest -H "X-Admin-Key: your-key"
```

---

## Security and deployment notes

- All embeddings and vector search run locally (sentence-transformers, ChromaDB).
- Ollama runs entirely on-premises — no queries leave the network.
- The `anthropic` backend sends question text and retrieved doc chunks to the
  Anthropic API. Do not use it in air-gapped or data-sensitive environments.
- The web server applies per-IP rate limiting (default 30 req/min, configurable
  via `RATE_LIMIT_RPM` in `.env`).
- The `/ingest` endpoint is protected by `X-Admin-Key`; leave `ADMIN_KEY` blank
  to disable remote re-indexing.
