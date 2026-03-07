"""
LLM Agent Call Centre - FastAPI Backend
========================================
Phases:
  1. Audio Ingestion   → transcribe & normalise incoming calls
  2. LLM Triage        → classify severity, intent, entities
  3. Case Queue        → prioritised queue with real-time updates
  4. Recommendation    → action plan + helper-service dispatch
"""

# main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.settings import settings
from routers.cases import router as cases_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Call Centre backend starting …")
    yield
    print("🛑 Call Centre backend shutting down …")


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

app.include_router(cases_router, prefix="/cases", tags=["Cases"])


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "version": app.version}
