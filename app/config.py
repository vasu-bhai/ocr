"""
Centralized Application Settings
Single source of truth — reads from .env once, used everywhere.
"""
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────
    app_env: str = "production"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # ── Database ─────────────────────────────────────────
    database_url: str = "sqlite:///./docextract.db"

    # ── File Storage ─────────────────────────────────────
    storage_backend: str = "local"
    upload_dir: str = "uploads"
    max_file_size_mb: int = 50

    # ── OCR Engine ───────────────────────────────────────
    ocr_gpu: bool = False

    # ── LLM Extraction (Groq) ────────────────────────────
    groq_api_key: str = ""
    groq_model = GROQ_MODEL

    # ── Extraction ───────────────────────────────────────
    confidence_review_threshold: float = 0.85

    # ── Logging ──────────────────────────────────────────
    log_level: str = "INFO"
    log_file: str = "logs/docextract.log"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
