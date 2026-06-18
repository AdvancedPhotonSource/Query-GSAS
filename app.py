"""
FastAPI web server for the GSAS-II documentation chatbot.

Routes:
  GET  /           -> chat UI (static/index.html)
  POST /chat       -> RAG query, returns {answer, sources}
  POST /ingest     -> trigger background re-ingestion (admin key required)
  GET  /health     -> liveness check
  GET  /stats      -> collection stats

Run:
  uvicorn app:app --host 0.0.0.0 --port 8000
"""

import os
import subprocess
import time
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(
    title="GSAS-II Assistant",
    description="RAG chatbot over GSAS-II tutorials and help documentation",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
)

# CORS — restrict in production by setting ALLOWED_ORIGINS env var
_allowed_origins = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# --------------------------------------------------------------------------- #
# Request / Response models                                                    #
# --------------------------------------------------------------------------- #

class HistoryTurn(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[HistoryTurn] = Field(default_factory=list, max_length=20)


class Source(BaseModel):
    title: str
    section: str
    url: str
    category: str
    relevance: float


class Citation(BaseModel):
    title: str
    section: str
    url: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    citations: dict[str, Citation]
    elapsed_ms: int


# --------------------------------------------------------------------------- #
# Simple rate limiting (in-memory, per IP)                                     #
# --------------------------------------------------------------------------- #

_rate_store: dict[str, list[float]] = {}
RATE_LIMIT = int(os.environ.get("RATE_LIMIT_RPM", "30"))  # requests per minute


def check_rate_limit(request: Request):
    if RATE_LIMIT <= 0:
        return  # disabled
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    timestamps = [t for t in _rate_store.get(ip, []) if now - t < 60]
    if len(timestamps) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please slow down.")
    timestamps.append(now)
    _rate_store[ip] = timestamps


# --------------------------------------------------------------------------- #
# Routes                                                                       #
# --------------------------------------------------------------------------- #

@app.get("/", include_in_schema=False)
async def serve_ui():
    return FileResponse("static/index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/stats")
async def stats():
    from rag import _get_collection
    try:
        col = _get_collection()
        count = col.count()
    except Exception:
        count = -1
    backend = os.environ.get("LLM_BACKEND", "anthropic")
    return {"chunks_indexed": count, "llm_backend": backend}


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    http_request: Request,
    _: None = Depends(check_rate_limit),
):
    from rag import answer_question

    t0 = time.monotonic()
    history = [h.model_dump() for h in request.history]
    result = answer_question(request.message, history)
    elapsed = int((time.monotonic() - t0) * 1000)

    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        citations=result.get("citations", {}),
        elapsed_ms=elapsed,
    )


@app.post("/ingest")
async def trigger_ingest(request: Request):
    admin_key = os.environ.get("ADMIN_KEY", "")
    provided = request.headers.get("X-Admin-Key", "")
    if admin_key and provided != admin_key:
        raise HTTPException(status_code=403, detail="Invalid admin key.")

    subprocess.Popen(
        ["python", "ingest.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return {"status": "ingestion started in background"}


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again."},
    )
