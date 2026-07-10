"""Corrections Router - Human-in-the-loop feedback"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel

from app.dependencies import get_db
from app.models import Document, Correction, LineItem

router = APIRouter()


class CorrectionRequest(BaseModel):
    corrections: dict
    corrected_by: str = "human"


@router.post("/correct/{doc_id}")
def submit_correction(
    doc_id: str,
    req: CorrectionRequest,
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter_by(id=doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    field_map = {
        "invoice_number": "invoice_number",
        "invoice_date": "invoice_date",
        "due_date": "due_date",
        "vendor_name": "vendor_name",
        "vendor_address": "vendor_address",
        "buyer_name": "buyer_name",
        "total_amount": "total_amount",
        "subtotal": "subtotal",
        "tax_amount": "tax_amount",
        "currency": "currency",
        "payment_terms": "payment_terms",
        "po_number": "po_number",
    }

    for field, new_value in req.corrections.items():
        if field not in field_map:
            continue
        original = getattr(doc, field_map[field], None)

        # Save correction record for retraining
        corr = Correction(
            document_id=doc_id,
            field_name=field,
            original_value=str(original) if original is not None else None,
            corrected_value=str(new_value),
            corrected_by=req.corrected_by,
        )
        db.add(corr)

        # Update document
        setattr(doc, field_map[field], new_value)

    doc.corrected_at = datetime.utcnow()
    doc.needs_review = False
    doc.status = "done"
    db.commit()

    return {"message": "Corrections saved", "doc_id": doc_id}


@router.get("/review-queue")
def get_review_queue(db: Session = Depends(get_db)):
    docs = (
        db.query(Document)
        .filter(Document.needs_review == True)
        .order_by(Document.created_at.desc())
        .limit(50)
        .all()
    )
    return {"count": len(docs), "documents": [d.to_dict() for d in docs]}


@router.get("/corrections/{doc_id}")
def get_corrections(doc_id: str, db: Session = Depends(get_db)):
    corrections = (
        db.query(Correction).filter_by(document_id=doc_id).all()
    )
    return [
        {
            "field": c.field_name,
            "original": c.original_value,
            "corrected": c.corrected_value,
            "by": c.corrected_by,
            "at": c.created_at.isoformat(),
        }
        for c in corrections
    ]


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(Document).count()
    done = db.query(Document).filter(Document.status == "done").count()
    review = db.query(Document).filter(Document.status == "review").count()
    failed = db.query(Document).filter(Document.status == "failed").count()
    processing = db.query(Document).filter(Document.status.in_(["processing", "queued"])).count()
    return {
        "total": total,
        "done": done,
        "needs_review": review,
        "failed": failed,
        "processing": processing,
        "accuracy_rate": round(done / total * 100, 1) if total > 0 else 0,
    }
