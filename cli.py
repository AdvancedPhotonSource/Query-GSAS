"""
GSAS-II Documentation Assistant — command-line interface.

First-time setup (downloads and indexes all docs, ~10 min):
    python cli.py --setup
    python cli.py --setup --reset    # re-index from scratch
    python cli.py --setup --html-only  # skip large PDFs, faster

Ask a single question:
    python cli.py "How do I set up a sequential refinement?"

Interactive mode (multi-turn, remembers context):
    python cli.py
"""

import os
import sys
import textwrap

# Must be before sentence_transformers import to prevent loky worker
# processes from re-importing this module as __main__ (Python 3.13+/macOS)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "chroma_db")
WIDTH = 80  # console wrap width


# ── Formatting helpers ─────────────────────────────────────────────────────────

def _hr(char="─", width=WIDTH):
    print(char * width)


def _wrap(text: str, indent: int = 0) -> str:
    prefix = " " * indent
    return textwrap.fill(text, width=WIDTH, initial_indent=prefix, subsequent_indent=prefix)


def _print_answer(result: dict):
    answer = result.get("answer", "")
    sources = result.get("sources", [])

    print()
    # Print answer — preserve paragraph breaks
    for para in answer.split("\n"):
        if para.strip():
            print(_wrap(para))
        else:
            print()

    if sources:
        print()
        _hr("·")
        print("Sources:")
        seen = set()
        for s in sources:
            key = s["url"]
            if key in seen:
                continue
            seen.add(key)
            rel = int(s.get("relevance", 0) * 100)
            label = f"  [{rel}%] {s['title']}"
            if s.get("section") and s["section"] != s["title"]:
                label += f"  ›  {s['section']}"
            print(label)
            print(f"         {s['url']}")
    print()


def _collection_count() -> int:
    try:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        return client.get_or_create_collection("gsasii_docs").count()
    except Exception:
        return 0


# ── Setup / ingestion ──────────────────────────────────────────────────────────

def run_setup(reset: bool = False, html_only: bool = False):
    """Run ingestion pipeline; called from --setup flag."""
    # Ensure ingest.py is on the path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    try:
        import ingest
    except ImportError as e:
        print(f"Error: could not import ingest.py — {e}")
        sys.exit(1)

    print("Starting ingestion. This may take 10-20 minutes.")
    print("(Fetching ~130 web pages and 2 PDFs, embedding all text)\n")

    import argparse
    # Patch sys.argv so ingest.main() sees the right flags
    argv_backup = sys.argv
    sys.argv = ["ingest.py"]
    if reset:
        sys.argv.append("--reset")
    if html_only:
        sys.argv.append("--html-only")
    try:
        ingest.main()
    finally:
        sys.argv = argv_backup


# ── RAG query ─────────────────────────────────────────────────────────────────

def ask(question: str, history: list | None = None) -> dict:
    """Query the RAG engine. Returns {answer, sources}."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    import rag
    return rag.answer_question(question, history or [])


# ── Interactive REPL ───────────────────────────────────────────────────────────

def interactive():
    count = _collection_count()
    if count == 0:
        print("\nWarning: the knowledge base is empty.")
        print("Run:  python cli.py --setup\n")
    else:
        print(f"\nKnowledge base: {count:,} indexed chunks.")

    backend = os.environ.get("LLM_BACKEND", "ollama")
    print(f"LLM backend: {backend}")
    print("Type your question and press Enter. 'clear' resets history, 'quit' exits.\n")
    _hr()

    history: list[dict] = []

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not question:
            continue

        if question.lower() in {"quit", "exit", "q"}:
            print("Goodbye.")
            break

        if question.lower() in {"clear", "reset"}:
            history.clear()
            print("(History cleared)\n")
            continue

        print("Thinking…", end="", flush=True)
        try:
            result = ask(question, history)
        except Exception as e:
            print(f"\rError: {e}\n")
            continue

        print("\r" + " " * 12 + "\r", end="")  # clear "Thinking…"
        print("Assistant:", end="")
        _print_answer(result)

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": result.get("answer", "")})


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="GSAS-II Documentation Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("question", nargs="?", help="Question to ask (omit for interactive mode)")
    parser.add_argument("--setup", action="store_true", help="Index documentation (first-time setup)")
    parser.add_argument("--reset", action="store_true", help="Drop and rebuild the index")
    parser.add_argument("--html-only", action="store_true", help="Skip PDFs during setup")
    parser.add_argument("--backend", choices=["ollama", "anthropic", "retrieval"],
                        help="Override LLM_BACKEND env var")
    parser.add_argument("--model", help="Override OLLAMA_MODEL or ANTHROPIC_MODEL")
    parser.add_argument("--stats", action="store_true", help="Show index statistics and exit")
    args = parser.parse_args()

    # Apply overrides before any import of rag.py
    if args.backend:
        os.environ["LLM_BACKEND"] = args.backend
    if args.model:
        backend = os.environ.get("LLM_BACKEND", "ollama")
        if backend == "ollama":
            os.environ["OLLAMA_MODEL"] = args.model
        else:
            os.environ["ANTHROPIC_MODEL"] = args.model

    print("GSAS-II Documentation Assistant")
    _hr("═")

    if args.stats:
        count = _collection_count()
        print(f"Indexed chunks : {count:,}")
        print(f"LLM backend    : {os.environ.get('LLM_BACKEND', 'ollama')}")
        print(f"Chroma DB      : {CHROMA_PATH}")
        return

    if args.setup:
        run_setup(reset=args.reset, html_only=args.html_only)
        return

    if args.question:
        count = _collection_count()
        if count == 0:
            print("Knowledge base is empty. Run:  python cli.py --setup")
            sys.exit(1)
        print(f"({count:,} chunks indexed)\n")
        result = ask(args.question)
        _print_answer(result)
    else:
        interactive()


if __name__ == "__main__":
    main()
