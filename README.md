# DocExtract — AI Document Extraction System

> Production-grade invoice and trade document extraction. Upload a PDF or image → get structured JSON. Built for fintech and supply-chain workflows.

![Python](https://img.shields.io/badge/Python-3.11-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green) ![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Architecture

```
User Upload (PDF/Image)
        │
        ▼
  FastAPI Upload API
        │
        ▼
  Background Task / Celery
        │
        ├─► Image Preprocessing (deskew, denoise, threshold)
        │
        ├─► OCR Engine (EasyOCR → Tesseract fallback)
        │
        ├─► Text Cleaning & Normalization
        │
        ├─► Hybrid Extraction (Regex → Spatial → NER)
        │
        └─► PostgreSQL / SQLite
                │
                ├─► REST API (structured JSON)
                └─► Review Queue (low-confidence flags)
```

## Quick Start (5 minutes)

### 1. Clone and install

```bash
git clone https://github.com/yourname/docextract
cd docextract
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

> **Minimal install** (if EasyOCR is too heavy):
> ```bash
> pip install fastapi uvicorn sqlalchemy pillow pymupdf python-multipart python-dateutil
> ```
> The system will use the lightest available OCR backend automatically.

### 2. Configure

```bash
cp .env.example .env
# Edit .env — defaults work out of the box with SQLite
```

### 3. Run

```bash
uvicorn api.main:app --reload --port 8000
```

Open **http://localhost:8000** — the full UI loads automatically.

API docs: **http://localhost:8000/docs**

---

## Docker (recommended for production)

```bash
cd infra
docker compose up -d
```

Includes: FastAPI, PostgreSQL, Redis, Flower (Celery monitor).

---

## Features

| Feature | Status |
|---|---|
| PDF upload & processing | ✅ |
| Image upload (JPG/PNG/TIFF) | ✅ |
| Multi-page PDF support | ✅ |
| EasyOCR backend | ✅ |
| Tesseract fallback | ✅ |
| Image preprocessing (deskew, denoise) | ✅ |
| Invoice field extraction | ✅ |
| Line item extraction | ✅ |
| Confidence scoring per field | ✅ |
| Human review queue | ✅ |
| Correction API (feedback loop) | ✅ |
| REST API with OpenAPI docs | ✅ |
| Dark-mode web UI | ✅ |
| SQLite (dev) / PostgreSQL (prod) | ✅ |
| Celery async queue | ✅ (optional) |
| Synthetic data generator | ✅ |
| Noise augmentation pipeline | ✅ |
| spaCy NER training scripts | ✅ |
| LayoutLMv3 fine-tuning scripts | ✅ |
| Benchmark/evaluation suite | ✅ |
| Docker Compose | ✅ |

---

## API Reference

### Upload a document
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@invoice.pdf"

# Response:
# {"doc_id": "abc-123", "status": "queued"}
```

### Poll status
```bash
curl http://localhost:8000/api/status/abc-123
# {"doc_id": "abc-123", "status": "done"}
```

### Get extracted result
```bash
curl http://localhost:8000/api/result/abc-123
```
```json
{
  "status": "done",
  "invoice_number": "INV-2024-001",
  "invoice_date": "2024-01-15",
  "vendor_name": "Acme Corporation",
  "total_amount": 1650.00,
  "currency": "USD",
  "confidence_scores": {
    "invoice_number": 0.88,
    "total_amount": 0.92,
    "vendor_name": 0.61
  },
  "needs_review": false,
  "line_items": [
    {"description": "Consulting", "quantity": 5, "unit_price": 200.0, "amount": 1000.0}
  ]
}
```

### Submit human corrections
```bash
curl -X POST http://localhost:8000/api/correct/abc-123 \
  -H "Content-Type: application/json" \
  -d '{"corrections": {"vendor_name": "Acme Corp Ltd", "total_amount": 1650.00}}'
```

---

## Generate Synthetic Training Data

```bash
# Generate 500 synthetic invoices (PDF format)
python -m data.synthetic.generate --count 500 --output ./data/raw/synthetic

# Add noise to simulate real-world scans
python -m data.synthetic.noise \
  --input ./data/raw/synthetic \
  --output ./data/noisy \
  --copies 3 \
  --severity medium
```

## Run Evaluation Benchmark

```bash
python -m evaluation.benchmark \
  --gt data/raw/synthetic/ground_truth.json \
  --max 100
```

## Train Custom NER Model

```bash
# 1. Prepare data (or use bootstrap examples)
python -m models.ner.train --prepare --output models/ner/artifacts

# 2. Train with spaCy
python -m spacy train models/ner/artifacts/config.cfg \
  --output models/ner/artifacts/model \
  --gpu-id -1

# 3. Evaluate
python -m models.ner.train --evaluate --model models/ner/artifacts/model/model-best
```

## Fine-tune LayoutLMv3

```bash
python -m models.layoutlm.finetune \
  --data data/labelled/layoutlm_dataset \
  --output models/layoutlm/artifacts \
  --epochs 10
```

---

## Project Structure

```
docextract/
├── api/                        # FastAPI application
│   ├── main.py                 # App entry point
│   ├── database.py             # SQLAlchemy models
│   └── routers/
│       ├── documents.py        # Upload, result, status
│       └── corrections.py     # Human review, stats
├── worker/
│   ├── pipeline/
│   │   ├── preprocess.py       # Image cleaning
│   │   ├── ocr.py              # OCR engine wrapper
│   │   ├── clean.py            # Text normalization
│   │   ├── extract.py          # Field extraction
│   │   └── orchestrator.py     # Pipeline runner
│   ├── celery_app.py           # Celery configuration
│   └── tasks.py                # Async task definitions
├── models/
│   ├── ner/train.py            # spaCy NER training
│   └── layoutlm/finetune.py   # LayoutLMv3 fine-tuning
├── data/
│   └── synthetic/
│       ├── generate.py         # Invoice generator
│       └── noise.py            # Noise augmentation
├── evaluation/benchmark.py     # Accuracy measurement
├── static/index.html           # Full web UI
├── tests/test_pipeline.py      # Test suite
├── infra/
│   ├── docker-compose.yml
│   └── Dockerfile.api
├── requirements.txt
└── .env.example
```

---

## Supported Extraction Fields

| Field | Example |
|---|---|
| `invoice_number` | INV-2024-001 |
| `invoice_date` | 2024-01-15 |
| `due_date` | 2024-02-15 |
| `vendor_name` | Acme Corporation |
| `vendor_address` | 123 Main St, New York |
| `buyer_name` | MineHub Industries |
| `buyer_address` | 456 Trade Ave |
| `subtotal` | 1500.00 |
| `tax_amount` | 150.00 |
| `total_amount` | 1650.00 |
| `currency` | USD |
| `payment_terms` | Net 30 |
| `po_number` | PO-8821 |
| `line_items[]` | description, qty, price, amount |

---

## Production Notes

- **OCR accuracy** depends heavily on image quality. The preprocessing pipeline (deskew + denoise + adaptive threshold) handles most real-world scan degradation.
- **Confidence scores** are per-field (0.0–1.0). Fields below 0.55 are flagged for human review.
- **Corrections** submitted via `/api/correct` are stored in the `corrections` table — use them to build a retraining dataset.
- **Scale**: For >1000 docs/day, enable Celery (`CELERY_ENABLED=true`) and add GPU workers.

---

## License

MIT — build freely, deploy commercially.
