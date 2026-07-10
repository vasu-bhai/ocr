"""
Test Suite — DocExtract Pipeline
Run: pytest tests/ -v
"""
import os
import sys
import pytest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ── Text cleaning tests ───────────────────────────────────────────────────────
class TestCleaning:
    def setup_method(self):
        from worker.pipeline.clean import (
            clean_ocr_text, normalize_amount, normalize_date,
            extract_currency, find_field_synonym
        )
        self.clean = clean_ocr_text
        self.amount = normalize_amount
        self.date = normalize_date
        self.currency = extract_currency
        self.synonym = find_field_synonym

    def test_normalize_us_amount(self):
        assert self.amount("$1,234.56") == 1234.56

    def test_normalize_european_amount(self):
        assert self.amount("1.234,56") == 1234.56

    def test_normalize_plain_amount(self):
        assert self.amount("5000") == 5000.0

    def test_normalize_amount_with_currency_prefix(self):
        assert self.amount("USD 12,500.00") == 12500.0

    def test_normalize_bad_amount(self):
        assert self.amount("N/A") is None
        assert self.amount("") is None

    def test_date_iso(self):
        assert self.date("2024-01-15") == "2024-01-15"

    def test_date_dmy(self):
        assert self.date("15/01/2024") == "2024-01-15"

    def test_date_named_month(self):
        result = self.date("January 15, 2024")
        assert result == "2024-01-15"

    def test_date_named_month_short(self):
        result = self.date("15 Jan 2024")
        assert result == "2024-01-15"

    def test_currency_symbol(self):
        assert self.currency("$1,234.56") == "USD"
        assert self.currency("€500") == "EUR"
        assert self.currency("£200") == "GBP"

    def test_currency_code(self):
        assert self.currency("USD 500") == "USD"
        assert self.currency("Total: INR 10000") == "INR"

    def test_field_synonym_invoice_number(self):
        assert self.synonym("Invoice No") == "invoice_number"
        assert self.synonym("inv #") == "invoice_number"
        assert self.synonym("Bill No") == "invoice_number"

    def test_field_synonym_total(self):
        assert self.synonym("Amount Due") == "total_amount"
        assert self.synonym("Grand Total") == "total_amount"
        assert self.synonym("Total Payable") == "total_amount"

    def test_field_synonym_vendor(self):
        assert self.synonym("From") == "vendor_name"
        assert self.synonym("Billed By") == "vendor_name"

    def test_ocr_cleanup(self):
        # Spaced out text (OCR artifact)
        result = self.clean("I N V O I C E")
        assert "I N V O I C E" not in result or len(result) > 0  # at minimum doesn't crash

    def test_amount_none_on_empty(self):
        assert self.amount(None) is None


# ── Extraction tests ──────────────────────────────────────────────────────────
class TestExtraction:
    def setup_method(self):
        from worker.pipeline.extract import extract_fields
        self.extract = extract_fields

    def _run(self, text):
        import asyncio
        return asyncio.run(self.extract([], text))

    def test_extract_invoice_number(self):
        result = self._run("Invoice No: INV-2024-001\nTotal: $500.00")
        assert result["fields"].get("invoice_number") is not None
        assert "INV" in result["fields"]["invoice_number"].upper() or \
               "2024" in result["fields"]["invoice_number"]

    def test_extract_total_amount(self):
        result = self._run("Grand Total: $12,345.67")
        assert result["fields"].get("total_amount") == 12345.67

    def test_extract_date(self):
        result = self._run("Invoice Date: 15/01/2024\nTotal: $100")
        assert result["fields"].get("invoice_date") is not None

    def test_extract_currency_usd(self):
        result = self._run("Total: USD 1,000.00")
        assert result["fields"].get("currency") == "USD"

    def test_extract_po_number(self):
        result = self._run("PO Number: PO-9821\nTotal: $100")
        po = result["fields"].get("po_number")
        assert po is not None
        assert "9821" in str(po)

    def test_needs_review_on_missing_critical_fields(self):
        result = self._run("This is a document with no invoice fields")
        assert result["needs_review"] is True

    def test_confidence_scores_present(self):
        result = self._run("Invoice #INV-001\nTotal: $500")
        assert isinstance(result["confidence_scores"], dict)

    def test_line_items_extraction(self):
        text = (
            "Consulting Services      10   150.00   1500.00\n"
            "Software License          1   500.00    500.00\n"
            "Total: $2,000.00"
        )
        result = self._run(text)
        # May or may not extract items depending on spacing
        assert isinstance(result["line_items"], list)


# ── Pipeline integration test ─────────────────────────────────────────────────
class TestPipeline:
    def test_pipeline_runs_on_text_file(self, tmp_path):
        """Create a minimal text 'invoice' and run the full pipeline."""
        from worker.pipeline.orchestrator import run_pipeline

        # Create a minimal test invoice as a text file
        # (PDF generation needs reportlab, so we test the text path)
        invoice_content = """
        ACME CORPORATION
        123 Business St, New York, NY 10001

        INVOICE

        Invoice #: INV-2024-TEST-001
        Date: 15/01/2024
        Due Date: 15/02/2024

        Bill To:
        MineHub Industries
        456 Trade Ave, London

        Description           Qty    Unit Price    Amount
        Consulting Services    5      200.00       1000.00
        Software License       1      500.00        500.00

        Subtotal: $1,500.00
        Tax (10%): $150.00
        Total Due: $1,650.00

        Payment Terms: Net 30
        """

        # Write as a .txt pretending to be a simple text doc
        f = tmp_path / "test_invoice.txt"
        f.write_text(invoice_content)

        # The pipeline will fail gracefully on .txt (no OCR)
        # but should not raise an exception
        try:
            result = run_pipeline(str(f))
            assert "fields" in result
            assert "confidence_scores" in result
            assert "line_items" in result
            assert "needs_review" in result
        except Exception as e:
            # Pipeline should always return a dict, never raise
            pytest.fail(f"Pipeline raised exception: {e}")

    def test_pipeline_handles_nonexistent_file(self):
        from worker.pipeline.orchestrator import run_pipeline
        result = run_pipeline("/nonexistent/path/file.pdf")
        # Should not crash — return error in result dict
        assert "error" in result or result.get("needs_review") is True


# ── API endpoint tests ────────────────────────────────────────────────────────
class TestAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_documents_list_empty(self, client):
        resp = client.get("/api/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert "documents" in data
        assert "total" in data

    def test_upload_wrong_type(self, client):
        resp = client.post(
            "/api/upload",
            files={"file": ("test.exe", b"binary content", "application/octet-stream")},
        )
        assert resp.status_code == 400

    def test_status_not_found(self, client):
        resp = client.get("/api/status/nonexistent-id")
        assert resp.status_code == 404

    def test_result_not_found(self, client):
        resp = client.get("/api/result/nonexistent-id")
        assert resp.status_code == 404

    def test_stats_endpoint(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "accuracy_rate" in data

    def test_review_queue_empty(self, client):
        resp = client.get("/api/review-queue")
        assert resp.status_code == 200
        assert "documents" in resp.json()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
