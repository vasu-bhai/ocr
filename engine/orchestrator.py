"""
Pipeline Orchestrator
Ties together: load → preprocess → OCR → clean → extract
Returns a standardized result dict.
"""
import time
import traceback
import os
from engine.preprocess import load_image, preprocess_image, pdf_page_to_image
from engine.ocr import run_ocr, tokens_to_text
from engine.clean import clean_ocr_text
from engine.extract import extract_fields

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

from app.logger import get_logger
logger = get_logger("orchestrator")


def run_pipeline(file_path: str) -> dict:
    """
    Full end-to-end pipeline for a single document.

    Args:
        file_path: Path to PDF or image file

    Returns:
        {
          raw_text, tokens, fields, confidence_scores,
          line_items, needs_review, processing_time_ms
        }
    """
    t0 = time.time()
    result = {
        "raw_text": "",
        "tokens": [],
        "fields": {},
        "confidence_scores": {},
        "line_items": [],
        "needs_review": True,
        "processing_time_ms": 0,
        "pages_processed": 0,
        "error": None,
    }

    try:
        logger.info(f"Starting pipeline for {file_path}")
        ext = os.path.splitext(file_path)[1].lower()
        all_tokens = []
        all_text_lines = []

        if ext == ".pdf" and PDFPLUMBER_AVAILABLE:
            logger.info("Processing as PDF via pdfplumber")
            with pdfplumber.open(file_path) as pdf:
                result["pages_processed"] = len(pdf.pages)
                for page_idx, page in enumerate(pdf.pages):
                    words = page.extract_words()
                    has_images = len(page.images) > 0
                    
                    if len(words) < 10 and has_images:
                        # Fallback to OCR for scanned image page
                        logger.warning(f"Page {page_idx} appears to be a scanned image (few words). Using OCR fallback.")
                        pil_img = pdf_page_to_image(file_path, page_idx)
                        if pil_img:
                            preprocessed = preprocess_image(pil_img)
                            tokens = run_ocr(preprocessed)
                        else:
                            tokens = []
                    else:
                        # Fast path: Native PDF text
                        tokens = []
                        for w in words:
                            tokens.append({
                                "text": w["text"],
                                "confidence": 1.0,
                                "bbox": {
                                    "x": int(w["x0"]),
                                    "y": int(w["top"]),
                                    "w": int(w["x1"] - w["x0"]),
                                    "h": int(w["bottom"] - w["top"])
                                }
                            })
                    
                    if page_idx > 0:
                        page_h = page.height if page.height else 1100
                        y_offset = page_idx * page_h
                        for tok in tokens:
                            tok["bbox"]["y"] += int(y_offset)
                            tok["page"] = page_idx
                    
                    all_tokens.extend(tokens)
                    all_text_lines.append(tokens_to_text(tokens))
                    
        else:
            # Traditional Image path
            pages = load_image(file_path)
            if not pages:
                result["error"] = "Could not load file. Ensure PDF/image is valid."
                return result

            result["pages_processed"] = len(pages)

            for page_idx, page in enumerate(pages):
                preprocessed = preprocess_image(page)
                tokens = run_ocr(preprocessed)

                if page_idx > 0:
                    page_h = page.height if hasattr(page, 'height') else 1100
                    y_offset = page_idx * page_h
                    for tok in tokens:
                        tok["bbox"]["y"] += int(y_offset)
                        tok["page"] = page_idx

                all_tokens.extend(tokens)
                all_text_lines.append(tokens_to_text(tokens))

        logger.info("Concatenating and cleaning extracted text")
        full_text = "\n\n--- PAGE BREAK ---\n\n".join(all_text_lines)
        clean_text = clean_ocr_text(full_text)

        result["raw_text"] = clean_text
        result["tokens"] = all_tokens

        # Step 4: Extract fields
        logger.info("Sending text to LLM for structured extraction")
        extraction = extract_fields(all_tokens, clean_text)
        logger.info(f"Extraction successful. Found {len(extraction.get('line_items', []))} line items.")
        result["fields"] = extraction["fields"]
        result["confidence_scores"] = extraction["confidence_scores"]
        result["line_items"] = extraction["line_items"]
        result["needs_review"] = extraction["needs_review"]

    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()
        result["needs_review"] = True

    result["processing_time_ms"] = int((time.time() - t0) * 1000)
    logger.info(f"Pipeline finished in {result['processing_time_ms']}ms")
    return result
