from fastapi import APIRouter
router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok", "service": "DocExtract API", "version": "2.0.0"}
