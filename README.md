# Query-GSAS — GSAS-II Documentation Assistant

Semantic search + AI answers over the full GSAS-II documentation set:
**129 HTML pages** (home, help, and all 62 tutorials) plus the
**Programmer's Guide** and **Powder Crystallography** book PDFs.

Queries run entirely on your machine — no data is sent externally unless
you opt into the Anthropic API backend.

---

## Requirements

- Python 3.10+
- The packages in `requirements.txt` (all installable into the existing GSAS-II Python environment)
- For AI-generated answers: [Ollama](https://ollama.com) (free, local) **or** an Anthropic API key

---

## Installation

```bash
# From the GSAS-II Python environment:
pip install -r requirements.txt

# Copy and configure
cp .env.example .env
```

---

## First-time setup — index the documentation

Run once (or again when docs are updated). Fetches ~130 web pages and
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

### 2. Command-line — interactive mode

```bash
python cli.py          # starts a multi-turn REPL
```

```
GSAS-II Documentation Assistant
════════════════════════════════

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
  [87%] Sequential Refinement of Multiple Datasets  ›  Setting up constraints
         https://advancedphotonsource.github.io/GSAS-II-tutorials/…
```

### 3. wxPython GUI (standalone)

```bash
python gui.py
```

### 4. Embed in GSAS-II Help menu

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

The dialog is modeless — it stays open while the user works in GSAS-II.
Calling `show_assistant()` a second time raises the existing window rather
than opening a duplicate.

### 5. Web UI (optional)

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
# then open http://localhost:8000
```

---

## LLM backend configuration

Set `LLM_BACKEND` in `.env` (or environment):

| Backend | Config | Notes |
|---|---|---|
| `ollama` (default) | `OLLAMA_MODEL=llama3` | Free, fully local, no data leaves network |
| `anthropic` | `ANTHROPIC_API_KEY=sk-ant-…` | Better answers, sends queries to Anthropic |

**Ollama setup:**
```bash
# Install from https://ollama.com, then:
ollama pull llama3          # ~5 GB, good balance of speed and quality
ollama pull llama3:70b      # ~40 GB, better quality
ollama pull mistral         # ~4 GB, faster
```

**Override on the command line:**
```bash
python cli.py --backend anthropic "What is Le Bail extraction?"
python cli.py --backend ollama --model mistral "How do I index peaks?"
```

---

## Doc sources

| Category | Count |
|---|---|
| Home / installation pages | 22 |
| Help pages (all sections) | 42 |
| Tutorials | 62 |
| Programmer's Guide (PDF, readthedocs) | 1 |
| Powder Crystallography book (PDF, auto-fetches latest) | 1 |
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
