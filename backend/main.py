"""
LLM Agent Call Centre - FastAPI Backend
========================================
Phases:
  1. Audio Ingestion   → transcribe & normalise incoming calls
  2. LLM Triage        → classify severity, intent, entities
  3. Case Queue        → prioritised queue with real-time updates
  4. Recommendation    → action plan + helper-service dispatch
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import audio, triage, cases, recommendations, helpers
from core.config import settings
from core.queue import case_queue          # in-memory priority queue (swap for Redis)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    print("🚀  Call Centre backend starting …")
    await case_queue.initialise()
    yield
    print("🛑  Call Centre backend shutting down …")
    await case_queue.teardown()


app = FastAPI(
    title="LLM Agent Call Centre API",
    description="Audio ingestion → LLM triage → case queue → recommendations",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# all the routes will be here



@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "version": app.version}