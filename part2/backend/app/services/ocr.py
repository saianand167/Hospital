"""
OCR Abstraction Layer.
Supports Tesseract (real) and Mock (dev/test) providers.

The main API method is:
    ocr_provider.extract(image, language) -> OCRResult(text, confidence)
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import pytesseract
from PIL import Image


@dataclass
class OCRResult:
    """Returned by every OCR provider's extract() method."""
    text: str
    confidence: float   # 0.0 - 1.0


class OCRProvider(ABC):
    @abstractmethod
    def extract(self, image: Image.Image, language: str = "eng",
                handwritten: bool = False) -> OCRResult:
        """Extract text and confidence from a PIL Image."""
        pass


class TesseractOCRProvider(OCRProvider):
    """
    Real Tesseract OCR.
    Falls back to 'eng' if the requested language pack is missing.
    """

    def extract(self, image: Image.Image, language: str = "eng",
                handwritten: bool = False) -> OCRResult:
        lang = language.lower()
        try:
            data = pytesseract.image_to_data(
                image, lang=lang,
                output_type=pytesseract.Output.DICT
            )
        except Exception:
            try:
                data = pytesseract.image_to_data(
                    image, lang="eng",
                    output_type=pytesseract.Output.DICT
                )
            except Exception as e:
                return OCRResult(text="", confidence=0.0)

        # Confidence: Tesseract gives per-word confidence (0-100), -1 = no word
        confidences = [
            float(c) for c in data.get("conf", [])
            if str(c).strip() not in ("-1", "")
        ]
        avg_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0

        # Assemble full text preserving line structure
        words   = data.get("text",    [])
        levels  = data.get("level",   [])
        confs   = data.get("conf",    [])
        lines: list[str] = []
        current_line: list[str] = []
        for word, level, conf in zip(words, levels, confs):
            if level == 5 and word.strip():          # level 5 = word
                current_line.append(word)
            elif level == 4 and current_line:        # level 4 = line boundary
                lines.append(" ".join(current_line))
                current_line = []
        if current_line:
            lines.append(" ".join(current_line))
        full_text = "\n".join(lines).strip()

        # If line-assembly produced nothing, fall back to simple join
        if not full_text:
            full_text = " ".join(w for w in words if w.strip())

        # Handwritten: cap confidence so low-conf flag is always set
        if handwritten:
            avg_conf = min(avg_conf, 0.60)

        return OCRResult(text=full_text, confidence=avg_conf)

    # ── Legacy aliases kept for backwards compatibility ───────────────────────
    def extract_text(self, image: Image.Image, language: str = "eng") -> str:
        return self.extract(image, language).text

    def extract_text_with_confidence(self, image: Image.Image,
                                     language: str = "eng",
                                     handwritten: bool = False):
        r = self.extract(image, language, handwritten)
        return r.text, r.confidence


class MockOCRProvider(OCRProvider):
    """Zero-setup mock — for unit tests only."""
    MOCK_TEXT = (
        "CLINICAL LABORATORY REPORT\n"
        "Renal Panel  Specimen: Serum/Plasma\n"
        "Glucose - Random  78  mg/dL  70-140\n"
        "BUN  9.81  mg/dL  6-20\n"
        "Serum Creatinine  0.86  mg/dL  0.90-1.30\n"
        "eGFR  115.5  mL/min/1.73m2  >60\n"
        "Complete Blood Count\n"
        "WBC  8800  cells/uL  4500-11000\n"
        "Hemoglobin  15.1  g/dL  13.0-17.0\n"
        "Platelets  216  K/uL  150-400\n"
    )

    def extract(self, image: Image.Image, language: str = "eng",
                handwritten: bool = False) -> OCRResult:
        conf = 0.60 if handwritten else 0.85
        return OCRResult(text=self.MOCK_TEXT, confidence=conf)

    def extract_text(self, image, language="eng"):
        return self.MOCK_TEXT

    def extract_text_with_confidence(self, image, language="eng", handwritten=False):
        return self.MOCK_TEXT, 0.60 if handwritten else 0.85


def get_ocr_provider(provider_name: str) -> OCRProvider:
    if provider_name.lower() == "tesseract":
        return TesseractOCRProvider()
    return MockOCRProvider()
