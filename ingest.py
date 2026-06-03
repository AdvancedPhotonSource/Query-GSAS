"""
Ingestion pipeline: fetch GSAS-II tutorials (HTML) and the help PDF,
chunk by section, embed with sentence-transformers, store in ChromaDB.

Usage:
    python ingest.py                # ingest everything
    python ingest.py --html-only    # skip PDF (much faster)
    python ingest.py --reset        # drop collection and re-ingest
"""

import argparse
import hashlib
import io
import re
import sys
import time

import requests
from bs4 import BeautifulSoup, Tag
import chromadb
from sentence_transformers import SentenceTransformer

from sources import TUTORIAL_SOURCES, PDF_SOURCES, WEBPAGE_SOURCES

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "gsasii_docs"
EMBED_MODEL = "all-MiniLM-L6-v2"
MAX_CHUNK_CHARS = 1200
OVERLAP_CHARS = 150
REQUEST_DELAY = 0.5  # seconds between HTTP requests


def get_collection(reset: bool = False) -> chromadb.Collection:
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            print("Dropped existing collection.")
        except Exception:
            pass
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    """Split text into overlapping chunks at sentence boundaries."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            # Find last sentence boundary within the window
            boundary = max(
                text.rfind(". ", start, end),
                text.rfind(".\n", start, end),
                text.rfind("! ", start, end),
                text.rfind("? ", start, end),
            )
            if boundary > start + max_chars // 2:
                end = boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
    return chunks


def extract_html_sections(html: str, source_title: str) -> list[dict]:
    """Parse HTML into sections grouped by heading, with text content."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove noise
    for tag in soup(["script", "style", "nav", "footer", "img"]):
        tag.decompose()

    body = soup.find("body") or soup

    sections = []
    current_heading = source_title
    current_text_parts = []

    heading_tags = {"h1", "h2", "h3", "h4"}

    def flush():
        text = " ".join(current_text_parts).strip()
        if text and len(text) > 80:  # skip trivially short fragments
            sections.append({"heading": current_heading, "text": text})

    for elem in body.descendants:
        if not isinstance(elem, Tag):
            continue
        if elem.name in heading_tags:
            flush()
            current_heading = elem.get_text(separator=" ", strip=True)
            current_text_parts = []
        elif elem.name in {"p", "li", "td", "th", "pre", "blockquote", "dd", "dt"}:
            txt = elem.get_text(separator=" ", strip=True)
            if txt:
                current_text_parts.append(txt)

    flush()
    return sections


def ingest_html_source(source: dict, collection: chromadb.Collection, model: SentenceTransformer):
    url = source["url"]
    title = source["title"]
    category = source["category"]

    print(f"  Fetching: {title}")
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ERROR fetching {url}: {e}")
        return 0

    sections = extract_html_sections(resp.text, title)
    ids, docs, embeddings, metadatas = [], [], [], []

    for section in sections:
        chunks = chunk_text(section["text"])
        for i, chunk in enumerate(chunks):
            doc_id = hashlib.md5(f"{url}|{section['heading']}|{i}".encode()).hexdigest()
            embedding = model.encode(chunk).tolist()
            ids.append(doc_id)
            docs.append(chunk)
            embeddings.append(embedding)
            metadatas.append({
                "url": url,
                "title": title,
                "section": section["heading"],
                "category": category,
                "source_type": "html",
            })

    if ids:
        collection.upsert(ids=ids, documents=docs, embeddings=embeddings, metadatas=metadatas)
        print(f"    -> {len(ids)} chunks stored")

    time.sleep(REQUEST_DELAY)
    return len(ids)


def ingest_pdf_source(source: dict, collection: chromadb.Collection, model: SentenceTransformer):
    try:
        from pypdf import PdfReader
    except ImportError:
        print("  pypdf not installed, skipping PDF ingestion.")
        return 0

    url = source["url"]
    title = source["title"]
    category = source["category"]

    print(f"  Fetching PDF: {title}")
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ERROR fetching PDF {url}: {e}")
        return 0

    try:
        reader = PdfReader(io.BytesIO(resp.content))
    except Exception as e:
        print(f"  ERROR parsing PDF: {e}")
        return 0

    ids, docs, embeddings, metadatas = [], [], [], []
    total_pages = len(reader.pages)
    print(f"    {total_pages} pages")

    # Group pages into chunks of 3 for context continuity
    for page_start in range(0, total_pages, 3):
        page_end = min(page_start + 3, total_pages)
        combined_text = ""
        for p in range(page_start, page_end):
            page_text = reader.pages[p].extract_text() or ""
            combined_text += page_text + "\n"

        section_label = f"Pages {page_start + 1}-{page_end}"
        for i, chunk in enumerate(chunk_text(combined_text)):
            doc_id = hashlib.md5(f"{url}|{section_label}|{i}".encode()).hexdigest()
            embedding = model.encode(chunk).tolist()
            ids.append(doc_id)
            docs.append(chunk)
            embeddings.append(embedding)
            metadatas.append({
                "url": url,
                "title": title,
                "section": section_label,
                "category": category,
                "source_type": "pdf",
            })

    if ids:
        collection.upsert(ids=ids, documents=docs, embeddings=embeddings, metadatas=metadatas)
        print(f"    -> {len(ids)} chunks stored")

    return len(ids)


def main():
    parser = argparse.ArgumentParser(description="Ingest GSAS-II docs into ChromaDB")
    parser.add_argument("--html-only", action="store_true", help="Skip PDF ingestion")
    parser.add_argument("--reset", action="store_true", help="Drop and rebuild collection")
    args = parser.parse_args()

    print("Loading embedding model...")
    model = SentenceTransformer(EMBED_MODEL)

    print("Connecting to ChromaDB...")
    collection = get_collection(reset=args.reset)

    total_chunks = 0

    print("\n=== Ingesting HTML tutorials ===")
    for source in WEBPAGE_SOURCES + TUTORIAL_SOURCES:
        total_chunks += ingest_html_source(source, collection, model)

    if not args.html_only:
        print("\n=== Ingesting PDFs ===")
        for source in PDF_SOURCES:
            total_chunks += ingest_pdf_source(source, collection, model)

    print(f"\nDone. Total chunks in collection: {collection.count()}")


if __name__ == "__main__":
    main()
