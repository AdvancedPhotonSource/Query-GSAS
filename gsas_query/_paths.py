"""Central path management for user data (chroma index) and package assets."""

import os
from pathlib import Path

# Suppress HuggingFace tokenizer fork warning — must happen before any import
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def get_data_dir() -> Path:
    """Return (and create) the user data directory for gsas_query."""
    d = Path(os.environ.get("GSAS_QUERY_DATA_DIR", Path.home() / ".gsas_query"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_chroma_path() -> str:
    return str(get_data_dir() / "chroma_db")


def get_static_dir() -> Path:
    return Path(__file__).parent / "static"
