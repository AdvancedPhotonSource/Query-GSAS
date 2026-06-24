"""
RAG engine: query ChromaDB, retrieve relevant chunks, generate answer.

LLM_BACKEND env var controls which LLM is used:
  "ollama"     (default) — local Ollama server, fully on-premises
  "anthropic"            — Anthropic Claude API (requires ANTHROPIC_API_KEY)
  "retrieval"            — no LLM; returns raw matched chunks (offline / testing)
"""

import os
from functools import lru_cache

import chromadb
from sentence_transformers import SentenceTransformer

from ._paths import get_chroma_path

COLLECTION_NAME = "gsasii_docs"
EMBED_MODEL = "all-MiniLM-L6-v2"
TOP_K = 6

SYSTEM_PROMPT = """\
You are an expert assistant for GSAS-II (General Structure Analysis System-II), \
crystallographic analysis software developed at Argonne National Laboratory.

You answer questions using the GSAS-II tutorials, help manual, and documentation \
provided as context. Your users are crystallographers, materials scientists, and \
physicists who need precise, actionable answers.

Guidelines:
- Be specific and technical. Use proper crystallographic terminology.
- When a question involves a step-by-step procedure, preserve the numbered steps.
- Each context section is numbered [1], [2], etc. Cite sources inline as you write \
  by inserting the number in brackets (e.g. "Open the Phase tab [1] and select..."). \
  Place the citation immediately after the sentence or clause it supports. Do NOT add \
  a separate references section at the end. Do NOT reproduce the raw "[Source: ...]" \
  labels from the context — use only the numeric [N] markers.
- If the provided context does not contain enough information to answer, say so clearly \
  and suggest which tutorial might cover the topic.
- Do not fabricate parameter names, menu paths, or file formats.
"""


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(EMBED_MODEL)


@lru_cache(maxsize=1)
def _get_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=get_chroma_path())
    return client.get_or_create_collection(COLLECTION_NAME)


def _retrieve(question: str) -> tuple[str, list[dict], dict[str, dict]]:
    model = _get_model()
    collection = _get_collection()

    if collection.count() == 0:
        return "", [], {}

    embedding = model.encode(question).tolist()
    results = collection.query(
        query_embeddings=[embedding],
        n_results=TOP_K,
        include=["documents", "metadatas", "distances"],
    )

    context_parts = []
    citations: dict[str, dict] = {}
    sources = []
    seen_sources: set = set()

    for i, (doc, meta, dist) in enumerate(zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ), start=1):
        context_parts.append(
            f"[{i}] [Source: {meta['title']} | Section: {meta['section']}]\n{doc}"
        )
        citations[str(i)] = {
            "title": meta["title"],
            "section": meta["section"],
            "url": meta["url"],
        }
        source_key = (meta["url"], meta["section"])
        if source_key not in seen_sources:
            seen_sources.add(source_key)
            sources.append({
                "title": meta["title"],
                "section": meta["section"],
                "url": meta["url"],
                "category": meta.get("category", ""),
                "relevance": round(1 - dist, 3),
            })

    context = "\n\n---\n\n".join(context_parts)
    return context, sources, citations


def _build_messages(question: str, context: str, history: list[dict]) -> list[dict]:
    messages = []
    for turn in history[-6:]:
        if turn.get("role") in {"user", "assistant"}:
            messages.append({"role": turn["role"], "content": turn["content"]})

    user_content = (
        f"Context from GSAS-II documentation:\n\n{context}\n\n"
        f"---\n\nQuestion: {question}"
        if context
        else question
    )
    messages.append({"role": "user", "content": user_content})
    return messages


def _answer_anthropic(messages: list[dict]) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return response.content[0].text


def _answer_ollama(messages: list[dict]) -> str:
    import httpx
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL", "llama3")

    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
    resp = httpx.post(
        f"{ollama_url}/api/chat",
        json={"model": ollama_model, "messages": full_messages, "stream": False},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def answer_question(question: str, history: list[dict]) -> dict:
    """Main entry point: returns {answer, sources, citations}."""
    if not question.strip():
        return {"answer": "Please enter a question.", "sources": [], "citations": {}}

    context, sources, citations = _retrieve(question)

    if not context:
        return {
            "answer": (
                "The knowledge base is empty. Run `gsas-query --setup` "
                "to index the GSAS-II documentation."
            ),
            "sources": [],
            "citations": {},
        }

    backend = os.environ.get("LLM_BACKEND", "ollama").lower()

    if backend == "retrieval":
        answer = (
            "Most relevant sections (no LLM synthesis — install Ollama or set "
            "LLM_BACKEND=anthropic for generated answers):\n\n" + context
        )
        return {"answer": answer, "sources": sources, "citations": citations}

    messages = _build_messages(question, context, history)

    if backend == "ollama":
        answer = _answer_ollama(messages)
    else:
        answer = _answer_anthropic(messages)

    return {"answer": answer, "sources": sources, "citations": citations}
