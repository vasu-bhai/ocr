"""
OCR Engine - PaddleOCR wrapper
Returns token format: [{text, bbox, confidence}]
"""
import os
import numpy as np

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from paddleocr import PaddleOCR
    import logging
    # Suppress verbose paddle logging
    logging.getLogger("ppocr").setLevel(logging.ERROR)
    _paddle_reader = None
    PADDLE_AVAILABLE = True
except ImportError:
    PADDLE_AVAILABLE = False


def _get_paddle_reader():
    global _paddle_reader
    if _paddle_reader is None:
        _paddle_reader = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
    return _paddle_reader


def run_ocr(img) -> list[dict]:
    """
    Run OCR on a preprocessed image using PaddleOCR.
    img: numpy array or PIL Image
    Returns: list of {text, confidence, bbox: {x,y,w,h}}
    """
    if not PADDLE_AVAILABLE:
        return _run_basic(img)
    return _run_paddleocr(img)


def _run_paddleocr(img) -> list[dict]:
    reader = _get_paddle_reader()
    if not hasattr(img, "tolist"):  # if PIL
        img = np.array(img.convert("RGB"))
    else:
        # PaddleOCR expects 3-channel image. If grayscale (2D), convert it.
        if len(img.shape) == 2:
            img = np.stack((img,)*3, axis=-1)
        elif len(img.shape) == 3 and img.shape[2] == 4:
            # Drop alpha channel if RGBA
            img = img[:, :, :3]
    
    # result format: [[[[x,y], [x,y], [x,y], [x,y]], ('text', conf)], ...]
    results = reader.ocr(img, cls=True)
    
    tokens = []
    if not results or not results[0]:
        return tokens
        
    for res in results[0]:
        if not res: continue
        box = res[0]
        text = res[1][0]
        conf = res[1][1]
        
        if not text.strip() or conf < 0.1:
            continue
            
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        
        tokens.append({
            "text": text.strip(),
            "confidence": round(float(conf), 3),
            "bbox": {
                "x": int(min(xs)),
                "y": int(min(ys)),
                "w": int(max(xs) - min(xs)),
                "h": int(max(ys) - min(ys)),
            }
        })
    return tokens


def _run_basic(img) -> list[dict]:
    """Last-resort: return placeholder telling user to install OCR."""
    return [{
        "text": "OCR_UNAVAILABLE",
        "confidence": 0.0,
        "bbox": {"x": 0, "y": 0, "w": 100, "h": 20}
    }]


def tokens_to_text(tokens: list[dict]) -> str:
    """Reconstruct plain text from tokens, preserving rough line structure."""
    if not tokens:
        return ""

    # Group tokens into lines by y-coordinate proximity
    lines = []
    current_line = []
    last_y = -999

    sorted_tokens = sorted(tokens, key=lambda t: (t["bbox"]["y"], t["bbox"]["x"]))

    for tok in sorted_tokens:
        y = tok["bbox"]["y"]
        h = tok["bbox"].get("h", 20)
        if abs(y - last_y) > h * 0.6 and current_line:
            lines.append(" ".join(t["text"] for t in current_line))
            current_line = []
        current_line.append(tok)
        last_y = y

    if current_line:
        lines.append(" ".join(t["text"] for t in current_line))

    return "\n".join(lines)
