"""
Celery Tasks — async document processing jobs
"""
from datetime import datetime
from worker.celery_app import celery_app
from engine.orchestrator import run_pipeline
from app.database import SessionLocal
from app.models import Document, LineItem


@celery_app.task(
    bind=True,
    max_retries=3,
    queue="high_priority",
    acks_late=True,
    name="worker.tasks.process_document",
)
def process_document(self, doc_id: str, file_path: str):
    """Full pipeline task dispatched by the upload endpoint."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter_by(id=doc_id).first()
        if not doc:
            return {"error": "Document not found"}

        doc.status = "processing"
        db.commit()

        result = run_pipeline(file_path)

        doc.raw_text = result.get("raw_text", "")
        doc.ocr_tokens = result.get("tokens", [])
        fields = result.get("fields", {})
        doc.invoice_number   = fields.get("invoice_number")
        doc.invoice_date     = fields.get("invoice_date")
        doc.due_date         = fields.get("due_date")
        
        doc.vendor_name      = fields.get("vendor_name")
        doc.vendor_address   = fields.get("vendor_address")
        doc.vendor_tax_id    = fields.get("vendor_tax_id")
        doc.vendor_phone     = fields.get("vendor_phone")
        doc.vendor_email     = fields.get("vendor_email")
        
        doc.buyer_name       = fields.get("buyer_name")
        doc.buyer_address    = fields.get("buyer_address")
        doc.buyer_tax_id     = fields.get("buyer_tax_id")
        
        doc.subtotal         = fields.get("subtotal")
        doc.tax_amount       = fields.get("tax_amount")
        doc.total_amount     = fields.get("total_amount")
        doc.discount_amount  = fields.get("discount_amount")
        doc.shipping_charges = fields.get("shipping_charges")
        
        doc.currency         = fields.get("currency", "USD")
        doc.payment_terms    = fields.get("payment_terms")
        doc.po_number        = fields.get("po_number")
        
        doc.bank_name            = fields.get("bank_name")
        doc.bank_account_number  = fields.get("bank_account_number")
        doc.bank_routing_number  = fields.get("bank_routing_number")
        doc.tax_breakdown        = fields.get("tax_breakdown")
        doc.confidence_scores = result.get("confidence_scores", {})
        doc.needs_review     = result.get("needs_review", False)
        doc.status           = "review" if doc.needs_review else "done"
        doc.processed_at     = datetime.utcnow()
        db.commit()

        for item in result.get("line_items", []):
            li = LineItem(
                document_id=doc_id,
                description=item.get("description"),
                hsn_code=item.get("hsn_code"),
                quantity=item.get("quantity"),
                unit=item.get("unit"),
                unit_price=item.get("unit_price"),
                amount=item.get("amount"),
                tax_rate=item.get("tax_rate"),
                discount=item.get("discount"),
                confidence=item.get("confidence", 1.0),
            )
            db.add(li)
        db.commit()

        return {"status": doc.status, "doc_id": doc_id}

    except Exception as exc:
        db.rollback()
        try:
            doc = db.query(Document).filter_by(id=doc_id).first()
            if doc:
                doc.status = "failed"
                doc.error_message = str(exc)
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)

    finally:
        db.close()


@celery_app.task(queue="batch", name="worker.tasks.reprocess_all")
def reprocess_all(model_version: str = None):
    """Batch reprocess all documents with a new model version."""
    db = SessionLocal()
    try:
        docs = db.query(Document).filter(
            Document.status.in_(["done", "review", "failed"])
        ).all()
        for doc in docs:
            process_document.apply_async(
                args=[doc.id, doc.file_path],
                queue="batch"
            )
        return {"queued": len(docs)}
    finally:
        db.close()
