"""
Image Preprocessing Pipeline
Handles: deskew, denoise, threshold, resize, contrast normalization
Works on PDFs and images.
"""
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np  # type: ignore # Only for type checkers; guarded at runtime below.

try:
    import numpy as np  # type: ignore[no-redef]
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from PIL import Image, ImageEnhance, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False




try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False


def pdf_to_images(pdf_path: str, dpi: int = 150) -> list:
    """Convert ALL PDF pages to PIL Images (Legacy bulk loading)."""
    images = []
    if PDFPLUMBER_AVAILABLE:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                images.append(page.to_image(resolution=dpi).original.convert("L"))
    return images


def pdf_page_to_image(pdf_path: str, page_idx: int, dpi: int = 150) -> Any:
    """Convert a SPECIFIC PDF page to a PIL Image (On-demand fast loading)."""
    if PDFPLUMBER_AVAILABLE:
        with pdfplumber.open(pdf_path) as pdf:
            if page_idx < len(pdf.pages):
                page = pdf.pages[page_idx]
                return page.to_image(resolution=dpi).original.convert("L")
    return None


def load_image(file_path: str) -> list:
    """Load any supported file (PDF or image) as list of PIL grayscale images."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return pdf_to_images(file_path)
    elif PIL_AVAILABLE:
        img = Image.open(file_path).convert("L")
        return [img]
    return []


def preprocess_image(pil_img) -> Any:
    """
    Full preprocessing pipeline for OCR.
    Returns: numpy array if cv2 available, else PIL Image
    """
    if CV2_AVAILABLE and PIL_AVAILABLE:
        return _preprocess_cv2(pil_img)
    elif PIL_AVAILABLE:
        return _preprocess_pil(pil_img)
    return pil_img


def _preprocess_cv2(pil_img):
    """OpenCV-based preprocessing (best quality)."""
    img = np.array(pil_img)

    # Ensure grayscale
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    # Step 1: Upscale if too small (OCR needs 150+ DPI equivalent)
    h, w = img.shape
    if w < 1200:
        scale = 1200 / w
        img = cv2.resize(img, (int(w * scale), int(h * scale)),
                         interpolation=cv2.INTER_CUBIC)
    elif w > 1800:  # Cap large images to keep OCR fast
        scale = 1800 / w
        img = cv2.resize(img, (int(w * scale), int(h * scale)),
                         interpolation=cv2.INTER_AREA)

    # Step 2: Fast denoise — bilateralFilter is ~100× faster than
    # fastNlMeansDenoising while still smoothing noise well.
    img = cv2.bilateralFilter(img, d=5, sigmaColor=30, sigmaSpace=30)

    # Step 3: Deskew (only when skew is likely — saves ~200ms on clean docs)
    img = _deskew_cv2(img)

    # Step 4: Adaptive threshold (handles uneven lighting)
    img = cv2.adaptiveThreshold(
        img, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 10
    )

    return img


def _deskew_cv2(img):
    """Detect and correct skew angle (fast path: skip if image looks straight)."""
    try:
        # Quick variance check — skip Hough on images that are clearly straight.
        # Sample a thin horizontal strip in the middle and check column variance.
        h, w = img.shape
        strip = img[h // 2 - 5: h // 2 + 5, :]
        if strip.std() > 60:  # High contrast strip → likely already straight
            return img

        # Find skew via Hough lines on edges (downsampled for speed)
        small = cv2.resize(img, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
        edges = cv2.Canny(small, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180,
                                 threshold=80,
                                 minLineLength=60,
                                 maxLineGap=8)
        if lines is None:
            return img

        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if x2 - x1 != 0:
                angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                if abs(angle) < 15:  # Only correct small skews
                    angles.append(angle)

        if not angles:
            return img

        median_angle = np.median(angles)
        if abs(median_angle) < 0.5:  # Skip trivial rotation
            return img

        M = cv2.getRotationMatrix2D((w / 2, h / 2), median_angle, 1)
        rotated = cv2.warpAffine(img, M, (w, h),
                                  borderMode=cv2.BORDER_REPLICATE)
        return rotated
    except Exception:
        return img


def _preprocess_pil(pil_img):
    """PIL-only fallback preprocessing."""
    img = pil_img.convert("L")

    # Resize if too small
    w, h = img.size
    if w < 1200:
        scale = 1200 / w
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    elif w > 2000:
        scale = 2000 / w
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # Enhance contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)

    # Sharpen
    img = img.filter(ImageFilter.SHARPEN)

    return img
