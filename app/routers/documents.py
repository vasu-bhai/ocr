"""
Documents Router - Upload, status polling, result retrieval
"""
import os
import uuid
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Document, LineItem, Correction
from app.config import settings
from engine.orchestrator import run_pipeline
from app.logger import get_logger
import os
import shutil

logger = get_logger("documents_router")

router = APIRouter()

os.makedirs(settings.upload_dir, exist_ok=True)

ALLOWED_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/webp",
}
MAX_FILE_SIZE = settings.max_file_size_mb * 1024 * 1024


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # Validate file type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            400,
            f"Unsupported file type: {file.content_type}. "
            f"Allowed: PDF, JPEG, PNG, TIFF, WebP"
        )

    doc_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] or ".pdf"
    save_path = os.path.join(settings.upload_dir, f"{doc_id}{ext}")

    # Save file
    logger.info(f"Uploading file: {file.filename} ({file.content_type})")
    with open(save_path, "wb") as f:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            logger.warning(f"File {file.filename} rejected: too large ({len(content)} bytes)")
            raise HTTPException(413, f"File too large. Max {settings.max_file_size_mb}MB.")
        f.write(content)

    # Create DB record
    logger.info(f"Creating database record for {doc_id}")
    doc = Document(
        id=doc_id,
        filename=file.filename,
        file_path=save_path,
        file_size=len(content),
        file_type=file.content_type,
        status="queued",
    )
    db.add(doc)
    db.commit()

    # Process in background
    logger.info(f"Queued background processing task for {doc_id}")
    background_tasks.add_task(process_document_task, doc_id, save_path)

    return {
        "doc_id": doc_id,
        "status": "queued",
        "message": "Document queued for processing. Poll /api/status/{doc_id} for updates.",
    }


async def process_document_task(doc_id: str, file_path: str):
    """Background task that runs the full extraction pipeline."""
    from app.database import SessionLocal
    db = SessionLocal()
    logger.info(f"Starting background processing for doc_id: {doc_id}")
    try:
        doc = db.query(Document).filter_by(id=doc_id).first()
        if not doc:
            logger.error(f"Document {doc_id} not found in database!")
            return

        doc.status = "processing"
        db.commit()

        # Run full pipeline
        logger.info(f"Running OCR/LLM pipeline for {doc_id}")
        result = run_pipeline(file_path)
        logger.info(f"Pipeline completed for {doc_id} in {result.get('processing_time_ms', 0)}ms")

        # Store extracted fields
        doc.raw_text = result.get("raw_text", "")
        doc.ocr_tokens = result.get("tokens", [])
        doc.invoice_number = result["fields"].get("invoice_number")
        doc.invoice_date = result["fields"].get("invoice_date")
        doc.due_date = result["fields"].get("due_date")
        doc.vendor_name = result["fields"].get("vendor_name")
        doc.vendor_address = result["fields"].get("vendor_address")
        doc.buyer_name = result["fields"].get("buyer_name")
        doc.buyer_address = result["fields"].get("buyer_address")
        doc.subtotal = result["fields"].get("subtotal")
        doc.tax_amount = result["fields"].get("tax_amount")
        doc.total_amount = result["fields"].get("total_amount")
        doc.currency = result["fields"].get("currency", "USD")
        doc.payment_terms = result["fields"].get("payment_terms")
        doc.po_number = result["fields"].get("po_number")
        doc.confidence_scores = result.get("confidence_scores", {})
        doc.needs_review = result.get("needs_review", False)
        doc.status = "review" if doc.needs_review else "done"
        doc.processed_at = datetime.utcnow()

        db.commit()

        # Store line items
        for item in result.get("line_items", []):
            li = LineItem(
                document_id=doc_id,
                description=item.get("description"),
                quantity=item.get("quantity"),
                unit=item.get("unit"),
                unit_price=item.get("unit_price"),
                amount=item.get("amount"),
                confidence=item.get("confidence", 1.0),
            )
            db.add(li)
        db.commit()

    except Exception as e:
        logger.exception(f"Pipeline failed for {doc_id}: {e}")
        doc = db.query(Document).filter_by(id=doc_id).first()
        if doc:
            doc.status = "failed"
            doc.error_message = str(e)
            db.commit()
    finally:
        db.close()


@router.get("/status/{doc_id}")
def get_status(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter_by(id=doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    return {"doc_id": doc_id, "status": doc.status}


@router.get("/result/{doc_id}")
def get_result(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter_by(id=doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    if doc.status in ("pending", "queued", "processing"):
        return {"status": doc.status, "message": "Still processing..."}

    line_items = db.query(LineItem).filter_by(document_id=doc_id).all()
    result = doc.to_dict()
    result["line_items"] = [li.to_dict() for li in line_items]
    return result


@router.get("/documents")
def list_documents(
    skip: int = 0,
    limit: int = 50,
    status: str = None,
    db: Session = Depends(get_db),
):
    query = db.query(Document)
    if status:
        query = query.filter(Document.status == status)
    docs = query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
    total = query.count()
    return {
        "total": total,
        "documents": [d.to_dict() for d in docs],
    }


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter_by(id=doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    # Remove file
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    # Remove line items
    db.query(LineItem).filter_by(document_id=doc_id).delete()
    db.delete(doc)
    db.commit()
    return {"message": "Document deleted"}
