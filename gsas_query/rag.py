"""
RAG engine: query ChromaDB, retrieve relevant chunks, generate answer.

Backend selection (in priority order):
  1. If ``LLM_BACKEND`` env var is set explicitly, it is always honoured.
  2. If ``LLM_BACKEND`` is not set and ``llama_cpp`` (llama-cpp-python) is
     importable, the llama_cpp backend is selected automatically.
  3. Otherwise the default is ``ollama``.

Supported LLM_BACKEND values:
  "ollama"     — local Ollama server, fully on-premises
  "anthropic"  — Anthropic Claude API (requires ANTHROPIC_API_KEY)
  "llama_cpp"  — in-process llama-cpp-python (requires LLAMA_CPP_MODEL path)
  "retrieval"  — no LLM; returns raw matched chunks (offline / testing)
"""

import os
from functools import lru_cache

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from ._paths import get_chroma_path

COLLECTION_NAME = "gsasii_docs"
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
def _get_ef() -> DefaultEmbeddingFunction:
    return DefaultEmbeddingFunction()


@lru_cache(maxsize=1)
def _get_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=get_chroma_path())
    return client.get_or_create_collection(COLLECTION_NAME)


def _retrieve(question: str) -> tuple[str, list[dict], dict[str, dict]]:
    collection = _get_collection()

    if collection.count() == 0:
        return "", [], {}

    embedding = _get_ef()([question])[0]
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


def _effective_backend() -> str:
    """Return the backend to use.

    Priority:
      1. ``LLM_BACKEND`` env var when explicitly set.
      2. ``llama_cpp`` when llama-cpp-python is importable and LLM_BACKEND unset.
      3. ``ollama`` as the final default.
    """
    env_backend = os.environ.get("LLM_BACKEND", "").strip().lower()
    if env_backend:
        return env_backend
    try:
        import llama_cpp  # noqa: F401
        return "llama_cpp"
    except ImportError:
        pass
    return "ollama"


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


@lru_cache(maxsize=1)
def _get_llama(model_path: str, n_ctx: int):
    from llama_cpp import Llama
    return Llama(model_path=model_path, n_ctx=n_ctx, verbose=False)


def _answer_llama_cpp(messages: list[dict]) -> str:
    model_path = os.environ.get("LLAMA_CPP_MODEL", "").strip()
    if not model_path:
        raise RuntimeError(
            "LLAMA_CPP_MODEL is not set. "
            "Set it to the path of a GGUF model file, e.g. "
            "LLAMA_CPP_MODEL=/path/to/model.gguf"
        )
    n_ctx = int(os.environ.get("LLAMA_CPP_N_CTX", "4096"))
    max_tokens = int(os.environ.get("LLAMA_CPP_MAX_TOKENS", "1500"))
    llm = _get_llama(model_path, n_ctx)
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
    response = llm.create_chat_completion(messages=full_messages, max_tokens=max_tokens)
    return response["choices"][0]["message"]["content"]


def _ollama_url() -> str:
    return os.environ.get("OLLAMA_URL", "http://localhost:11434")


def _installed_ollama_models() -> list[str]:
    import httpx
    resp = httpx.get(f"{_ollama_url()}/api/tags", timeout=5)
    resp.raise_for_status()
    data = resp.json() or {}
    return [m.get("name", "") for m in data.get("models", []) if m.get("name")]


def _choose_ollama_model() -> str:
    preferred = os.environ.get("OLLAMA_MODEL", "").strip()
    models = _installed_ollama_models()

    if not models:
        raise RuntimeError(
            "No Ollama models are installed. Run e.g. "
            "`ollama pull llama3.1:8b` or `ollama pull qwen2.5:3b`."
        )

    if preferred:
        if preferred in models:
            return preferred
        raise RuntimeError(
            f"OLLAMA_MODEL='{preferred}' is not installed. "
            f"Available models: {', '.join(models)}"
        )

    for candidate in ("llama3.1:8b", "llama3", "qwen2.5:3b"):
        if candidate in models:
            return candidate

    return models[0]


def _answer_ollama(messages: list[dict]) -> str:
    import httpx
    ollama_url = _ollama_url()
    ollama_model = _choose_ollama_model()

    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
    try:
        resp = httpx.post(
            f"{ollama_url}/api/chat",
            json={"model": ollama_model, "messages": full_messages, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        detail = ""
        try:
            detail = f" | Response: {e.response.text}"
        except Exception:
            pass
        raise RuntimeError(f"Ollama API error: {e}{detail}") from e
    return resp.json()["message"]["content"]


def answer_question(question: str, history: list[dict]) -> dict:
    """Main entry point: returns {answer, sources, citations, backend}."""
    if not question.strip():
        return {"answer": "Please enter a question.", "sources": [], "citations": {}, "backend": ""}

    context, sources, citations = _retrieve(question)

    if not context:
        return {
            "answer": (
                "The knowledge base is empty. Run `gsas-query --setup` "
                "to index the GSAS-II documentation."
            ),
            "sources": [],
            "citations": {},
            "backend": "",
        }

    backend = _effective_backend()

    if backend == "retrieval":
        answer = (
            "Most relevant sections (no LLM synthesis — install llama-cpp-python, "
            "Ollama, or set LLM_BACKEND=anthropic for generated answers):\n\n" + context
        )
        return {"answer": answer, "sources": sources, "citations": citations, "backend": backend}

    messages = _build_messages(question, context, history)

    if backend == "llama_cpp":
        answer = _answer_llama_cpp(messages)
    elif backend == "ollama":
        answer = _answer_ollama(messages)
    else:
        answer = _answer_anthropic(messages)

    return {"answer": answer, "sources": sources, "citations": citations, "backend": backend}
