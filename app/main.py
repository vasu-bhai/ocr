"""
DocExtract - AI Document Extraction System
Main FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os

from app.database import engine, Base
from app.routers import documents, corrections, health
from app.logger import get_logger

logger = get_logger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    logger.info("Starting DocExtract API...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified.")
    yield
    # Shutdown cleanup
    logger.info("Shutting down DocExtract API.")


app = FastAPI(
    title="DocExtract API",
    description="AI-powered invoice and document extraction system",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (frontend)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Register routers
app.include_router(health.router, tags=["health"])
app.include_router(documents.router, prefix="/api", tags=["documents"])
app.include_router(corrections.router, prefix="/api", tags=["corrections"])


@app.get("/", include_in_schema=False)
async def serve_frontend():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "DocExtract API running. See /docs for API reference."}
