"""
ORM Models — Document, LineItem, Correction
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Boolean, Text, DateTime, Numeric, Integer, JSON

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    status = Column(String, default="pending")       # pending/processing/done/review/failed
    file_size = Column(Integer)
    file_type = Column(String)

    # Extracted fields
    invoice_number = Column(String)
    invoice_date = Column(String)
    due_date = Column(String)
    vendor_name = Column(String, index=True)
    vendor_address = Column(String)
    vendor_tax_id = Column(String)
    vendor_phone = Column(String)
    vendor_email = Column(String)
    buyer_name = Column(String)
    buyer_address = Column(String)
    buyer_tax_id = Column(String)
    subtotal = Column(Float)
    tax_amount = Column(Float)
    total_amount = Column(Float)
    discount_amount = Column(Float)
    shipping_charges = Column(Float)
    currency = Column(String, default="USD")
    payment_terms = Column(String)
    po_number = Column(String)
    
    bank_name = Column(String)
    bank_account_number = Column(String)
    bank_routing_number = Column(String)
    
    tax_breakdown = Column(JSON)

    # Raw OCR output
    raw_text = Column(Text)
    ocr_tokens = Column(JSON)                        # [{text, bbox, confidence}]

    # Quality
    confidence_scores = Column(JSON)                 # {field: score}
    needs_review = Column(Boolean, default=False)
    error_message = Column(Text)
    extraction_version = Column(String, default="1.0.0")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    corrected_at = Column(DateTime)

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "status": self.status,
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "due_date": self.due_date,
            "vendor_name": self.vendor_name,
            "vendor_address": self.vendor_address,
            "vendor_tax_id": self.vendor_tax_id,
            "vendor_phone": self.vendor_phone,
            "vendor_email": self.vendor_email,
            "buyer_name": self.buyer_name,
            "buyer_address": self.buyer_address,
            "buyer_tax_id": self.buyer_tax_id,
            "subtotal": float(self.subtotal) if self.subtotal else None,
            "tax_amount": float(self.tax_amount) if self.tax_amount else None,
            "total_amount": float(self.total_amount) if self.total_amount else None,
            "discount_amount": float(self.discount_amount) if self.discount_amount else None,
            "shipping_charges": float(self.shipping_charges) if self.shipping_charges else None,
            "currency": self.currency,
            "payment_terms": self.payment_terms,
            "po_number": self.po_number,
            "bank_name": self.bank_name,
            "bank_account_number": self.bank_account_number,
            "bank_routing_number": self.bank_routing_number,
            "tax_breakdown": self.tax_breakdown,
            "confidence_scores": self.confidence_scores,
            "needs_review": self.needs_review,
            "extraction_version": self.extraction_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }


class LineItem(Base):
    __tablename__ = "line_items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, nullable=False)
    description = Column(String)
    hsn_code = Column(String)
    quantity = Column(Float)
    unit = Column(String)
    unit_price = Column(Float)
    amount = Column(Float)
    tax_rate = Column(Float)
    discount = Column(Float)
    confidence = Column(Float)

    def to_dict(self):
        return {
            "id": self.id,
            "description": self.description,
            "hsn_code": self.hsn_code,
            "quantity": self.quantity,
            "unit": self.unit,
            "unit_price": float(self.unit_price) if self.unit_price else None,
            "amount": float(self.amount) if self.amount else None,
            "tax_rate": float(self.tax_rate) if self.tax_rate else None,
            "discount": float(self.discount) if self.discount else None,
            "confidence": self.confidence,
        }


class Correction(Base):
    __tablename__ = "corrections"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, nullable=False)
    field_name = Column(String, nullable=False)
    original_value = Column(Text)
    corrected_value = Column(Text)
    corrected_by = Column(String, default="human")
    created_at = Column(DateTime, default=datetime.utcnow)
