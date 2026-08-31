"""
Image preprocessing pipeline for OCR quality improvement.
Does NOT modify the original uploaded file.
"""
import io
import numpy as np
import cv2
from PIL import Image


def pil_from_bytes(data: bytes) -> Image.Image:
    """Load a PIL image from raw bytes."""
    return Image.open(io.BytesIO(data)).convert("RGB")


def _to_numpy(pil_image: Image.Image) -> np.ndarray:
    img = np.array(pil_image)
    if len(img.shape) == 3:
        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    return img


def _to_grayscale(img: np.ndarray) -> np.ndarray:
    if len(img.shape) == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def _resize_for_ocr(img: np.ndarray, min_width: int = 1000) -> np.ndarray:
    h, w = img.shape[:2]
    if w < min_width:
        scale = min_width / w
        return cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return img


def _denoise(img: np.ndarray) -> np.ndarray:
    return cv2.fastNlMeansDenoising(img, h=10)


def _enhance_contrast(img: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(img)


def _deskew(img: np.ndarray) -> np.ndarray:
    """Detect and correct minor skew."""
    coords = np.column_stack(np.where(img < 128))
    if len(coords) < 5:
        return img
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.5:
        return img
    (h, w) = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def _threshold(img: np.ndarray) -> np.ndarray:
    _, result = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return result


def assess_image_quality(pil_image: Image.Image) -> dict:
    """
    Assess document quality before OCR.
    Detects: low resolution, blur, contrast issues, extreme skew, blank/empty images.
    Returns quality metrics dictionary.
    """
    img = _to_numpy(pil_image)
    gray = _to_grayscale(img)
    h, w = gray.shape[:2]

    reasons = []
    
    # 1. Resolution check
    if w < 400 or h < 400:
        reasons.append("Very low resolution")
    
    # 2. Blank / Empty image (low variance in pixel intensity)
    std_dev = float(np.std(gray))
    mean_val = float(np.mean(gray))
    if std_dev < 8.0:
        reasons.append("Blank or empty image")

    # 3. Blur detection using Laplacian variance
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if laplacian_var < 50.0 and "Blank or empty image" not in reasons:
        reasons.append("Image is blurry")

    # 4. Contrast score (normalized standard deviation)
    contrast_score = round(min(std_dev / 64.0, 1.0), 2)
    if contrast_score < 0.25 and "Blank or empty image" not in reasons:
        reasons.append("Very low contrast")

    # 5. Blur score (normalized Laplacian variance)
    blur_score = round(min(laplacian_var / 500.0, 1.0), 2)

    # 6. Skew detection
    coords = np.column_stack(np.where(gray < 128))
    rotation_deg = 0.0
    if len(coords) >= 5:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        rotation_deg = round(float(angle), 1)

    requires_reupload = any(r in reasons for r in ["Blank or empty image", "Very low resolution"])
    overall = "poor" if reasons else ("fair" if blur_score < 0.5 or contrast_score < 0.5 else "good")

    return {
        "overall": overall,
        "blur_score": blur_score,
        "contrast_score": contrast_score,
        "resolution": {"width": w, "height": h},
        "rotation_degrees": rotation_deg,
        "requires_reupload": requires_reupload,
        "reasons": reasons
    }


def preprocess_for_ocr(pil_image: Image.Image, handwritten: bool = False) -> Image.Image:
    """
    Apply a configurable preprocessing pipeline.

    Printed text: full pipeline (resize, denoise, contrast, deskew, threshold)
    Handwritten:  lighter pipeline (resize, contrast, deskew) — preserve stroke detail
    """
    img = _to_numpy(pil_image)
    gray = _to_grayscale(img)
    gray = _resize_for_ocr(gray)

    if not handwritten:
        gray = _denoise(gray)
        gray = _enhance_contrast(gray)
        gray = _deskew(gray)
        gray = _threshold(gray)
    else:
        gray = _enhance_contrast(gray)
        gray = _deskew(gray)

    return Image.fromarray(gray)
