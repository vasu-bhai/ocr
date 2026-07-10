"""
FastAPI Dependencies
Reusable Depends() for DB sessions, auth, etc.
"""
from app.database import SessionLocal


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
