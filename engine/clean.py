"""
Text Cleaning & Normalization
Cleans raw OCR artifacts before sending text to the LLM.
"""
import re

# ── OCR character-level fixes ────────────────────────────────────────────────
OCR_CHAR_FIXES = [
    # Only replace O with 0 when it is strictly between two digit characters.
    (r'(?<=\d)O(?=\d)', '0'),        # O between digits → 0
    (r'(?<!\w)l(?=\d)', '1'),        # l before digit → 1
    (r'(?<=\d)l(?!\w)', '1'),        # digit followed by l → 1
    (r'(?<!\w)I(?=\d)', '1'),        # I before digit → 1
    (r'\bS(?=\d)', '$'),             # S before digit ($ OCR error)
    (r'\|', 'I'),                    # pipe → I (common OCR error)
    (r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', ''),  # control chars
    (r'[ \t]{2,}', ' '),             # collapse horizontal whitespace
]

def clean_ocr_text(raw: str) -> str:
    text = raw
    for pattern, repl in OCR_CHAR_FIXES:
        text = re.sub(pattern, repl, text)
    return text.strip()
