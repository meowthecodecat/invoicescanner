"""Local OCR-based extraction service (no OpenAI)."""

from __future__ import annotations

import base64
import re
import os
import shutil
import io
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None

try:
    import pytesseract
    from PIL import Image
    from PIL import ImageOps
    from PIL import ImageEnhance
except Exception:  # pragma: no cover
    pytesseract = None
    Image = None
    ImageOps = None
    ImageEnhance = None

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

try:
    from paddleocr import PaddleOCR
except Exception:  # pragma: no cover
    PaddleOCR = None

from dateutil import parser as date_parser


# Validation rules: lists of invalid values that should be rejected
INVALID_SHOP_NAMES = {
    "fourni par", "provided by", "fournisseur", "supplier",
    "facturé à", "facture à", "billed to", "client", "customer",
    "adresse", "address", "tél", "tel", "email", "siret", "siren",
    "tva", "vat", "iban", "bic", "date", "facture", "invoice"
}

INVALID_CUSTOMER_NAMES = {
    "facturé à", "facture à", "billed to", "client", "customer",
    "fourni par", "provided by", "adresse", "address", "tél", "tel",
    "email", "siret", "siren", "tva", "vat", "iban", "bic", "date",
    "facture", "invoice", "shop name", "nom", "name"
}

INVALID_VAT_NUMBERS = {
    "vatquantit", "vat", "tva", "quantité", "quantite", "quantity"
}


@dataclass
class OCRUsageInfo:
    """Mimic the AI usage_info shape used elsewhere."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class OCRService:
    """
    Extract invoice fields using:
    - PDF embedded text when available (fast, best quality)
    - otherwise OCR (Tesseract) on rendered pages / images
    """

    def extract_invoice_data(
        self,
        file_content: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        file_type = self._get_file_type(filename, content_type)

        if file_type == "pdf":
            text = self._extract_text_from_pdf(file_content)
            if not text.strip():
                # Only require Tesseract if we actually need OCR.
                self._configure_tesseract()
                text = self._ocr_pdf(file_content)
        elif file_type == "image":
            # Images always require OCR.
            self._configure_tesseract()
            text = self._ocr_image_bytes(file_content)
        else:
            raise Exception(
                f"Unsupported invoice type ({file_type}). Please upload an image (PNG/JPG) or a PDF."
            )

        extracted = self._parse_invoice_text(text)
        usage = OCRUsageInfo().__dict__
        return extracted, usage

    @staticmethod
    def _configure_tesseract() -> None:
        """
        Configure pytesseract to find the `tesseract` binary.
        Priority:
        1) TESSERACT_CMD env var (absolute path to tesseract.exe)
        2) PATH lookup (shutil.which)
        3) Common Windows install locations
        """
        if pytesseract is None:
            raise Exception("OCR not available (pytesseract not installed).")

        # 1) Explicit env var
        tesseract_cmd = (os.getenv("TESSERACT_CMD") or "").strip().strip('"')
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        else:
            # 2) PATH lookup
            found = shutil.which("tesseract")
            if found:
                pytesseract.pytesseract.tesseract_cmd = found
            else:
                # 3) Common Windows locations
                candidates = [
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                    r"C:\Program Files\Tesseract-OCR\tesseract",
                ]
                for c in candidates:
                    if os.path.exists(c):
                        pytesseract.pytesseract.tesseract_cmd = c
                        break

        # Validate
        try:
            _ = pytesseract.get_tesseract_version()
        except Exception as e:
            # Windows-specific: 3221225786 typically means the executable crashed (missing runtime / bad install)
            rc_hint = ""
            try:
                # pytesseract may raise CalledProcessError
                rc = getattr(e, "returncode", None)
                if rc is not None:
                    rc_hint = f" (return code: {rc})"
            except Exception:
                pass

            raise Exception(
                "tesseract is not installed, not in PATH, OR it failed to run"
                f"{rc_hint}. "
                "This is NOT related to the Python venv.\n"
                "Fix options:\n"
                "- Add Tesseract to PATH, then restart your terminal\n"
                '- Or set env var TESSERACT_CMD="C:\\Program Files\\Tesseract-OCR\\tesseract.exe"\n'
                "- If you see a Windows crash code (e.g. 3221225786), reinstall Tesseract (UB-Mannheim build recommended) "
                "and install the Microsoft Visual C++ 2015-2022 Redistributable.\n"
                f"Underlying error: {e}"
            )

    @staticmethod
    def _get_file_type(filename: str, content_type: str | None = None) -> str:
        ct = (content_type or "").lower().strip()
        if ct.startswith("image/"):
            return "image"
        if ct == "application/pdf":
            return "pdf"

        fn = (filename or "").lower()
        if fn.endswith((".png", ".jpg", ".jpeg", ".webp")):
            return "image"
        if fn.endswith(".pdf"):
            return "pdf"
        return "text"

    @staticmethod
    def _extract_text_from_pdf(pdf_bytes: bytes, max_pages: int = 3) -> str:
        if fitz is None:
            return ""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            out: list[str] = []
            for i in range(min(len(doc), max_pages)):
                out.append(doc.load_page(i).get_text("text") or "")
            return "\n".join(out)
        finally:
            doc.close()

    @staticmethod
    def _ocr_pdf(pdf_bytes: bytes, max_pages: int = 3) -> str:
        if fitz is None:
            raise Exception("PDF OCR not available (PyMuPDF not installed).")
        if pytesseract is None or Image is None:
            raise Exception("OCR not available (pytesseract/Pillow not installed).")

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            out: list[str] = []
            # Quality-first: render at 300 DPI (4x matrix) for maximum OCR accuracy
            # This is slower but significantly improves text recognition quality
            mat = fitz.Matrix(4, 4)  # ~300 DPI (high quality)
            for i in range(min(len(doc), max_pages)):
                page = doc.load_page(i)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                png_bytes = pix.tobytes("png")
                out.append(OCRService._ocr_image_bytes(png_bytes))
            return "\n".join(out)
        finally:
            doc.close()

    @staticmethod
    def _document_cleanup_opencv(image_bytes: bytes) -> Optional[bytes]:
        """
        OpenCV-based document cleanup pipeline:
        - Edge detection + largest quadrilateral detection
        - Perspective correction (warp)
        - Deskew (rotation correction)
        - Illumination normalization (shadow removal)
        - Contrast enhancement
        
        Returns cleaned image bytes, or None if OpenCV not available or fails.
        """
        if cv2 is None or np is None:
            return None
        
        try:
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return None
            
            # Convert to grayscale for processing
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # 1) Edge detection + find largest quadrilateral (document detection)
            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            # Canny edge detection
            edges = cv2.Canny(blurred, 50, 150, apertureSize=3)
            # Dilate edges to close gaps
            dilated = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
            
            # Find contours
            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                # No contours found, skip document detection
                doc_region = gray
            else:
                # Find largest contour (likely the document)
                largest_contour = max(contours, key=cv2.contourArea)
                # Approximate contour to polygon
                epsilon = 0.02 * cv2.arcLength(largest_contour, True)
                approx = cv2.approxPolyDP(largest_contour, epsilon, True)
                
                # If we have 4 points, it's likely a quadrilateral (document)
                if len(approx) == 4:
                    # Order points: top-left, top-right, bottom-right, bottom-left
                    pts = approx.reshape(4, 2)
                    rect = OCRService._order_points(pts)
                    
                    # Calculate dimensions of the document
                    (tl, tr, br, bl) = rect
                    width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
                    width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
                    max_width = max(int(width_a), int(width_b))
                    
                    height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
                    height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
                    max_height = max(int(height_a), int(height_b))
                    
                    # Destination points for perspective transform
                    dst = np.array([
                        [0, 0],
                        [max_width - 1, 0],
                        [max_width - 1, max_height - 1],
                        [0, max_height - 1]
                    ], dtype="float32")
                    
                    # Perspective transform (warp)
                    M = cv2.getPerspectiveTransform(rect, dst)
                    warped = cv2.warpPerspective(gray, M, (max_width, max_height))
                    doc_region = warped
                else:
                    # Not a clear quadrilateral, use full image
                    doc_region = gray
            
            # 2) Deskew (rotation correction)
            # Find the angle of rotation using HoughLines
            edges_skew = cv2.Canny(doc_region, 50, 150, apertureSize=3)
            lines = cv2.HoughLines(edges_skew, 1, np.pi / 180, 200)
            if lines is not None and len(lines) > 0:
                angles = []
                for rho, theta in lines[:20]:  # Check first 20 lines
                    angle = (theta * 180 / np.pi) - 90
                    if -45 < angle < 45:  # Only consider reasonable angles
                        angles.append(angle)
                
                if angles:
                    median_angle = np.median(angles)
                    if abs(median_angle) > 0.5:  # Only correct if angle > 0.5 degrees
                        (h, w) = doc_region.shape[:2]
                        center = (w // 2, h // 2)
                        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                        doc_region = cv2.warpAffine(doc_region, M, (w, h), 
                                                    flags=cv2.INTER_CUBIC, 
                                                    borderMode=cv2.BORDER_REPLICATE)
            
            # 3) Illumination normalization (shadow removal)
            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            normalized = clahe.apply(doc_region)
            
            # 4) Additional contrast enhancement
            # Apply adaptive thresholding for better text contrast
            adaptive = cv2.adaptiveThreshold(normalized, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                            cv2.THRESH_BINARY, 11, 2)
            
            # Convert back to PIL Image format (for compatibility)
            cleaned_img = Image.fromarray(adaptive)
            
            # Convert to bytes
            img_byte_arr = io.BytesIO()
            cleaned_img.save(img_byte_arr, format='PNG')
            return img_byte_arr.getvalue()
            
        except Exception as e:
            # If OpenCV processing fails, return None (fallback to basic preprocessing)
            print(f"[OCR] OpenCV cleanup failed: {e}")
            return None

    @staticmethod
    def _order_points(pts):
        """Order points: top-left, top-right, bottom-right, bottom-left."""
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]  # top-left
        rect[2] = pts[np.argmax(s)]  # bottom-right
        
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]  # top-right
        rect[3] = pts[np.argmax(diff)]  # bottom-left
        return rect

    @staticmethod
    def _quality_gate(image_bytes: bytes) -> tuple[bool, Optional[str]]:
        """
        Quality gate: check if image is suitable for OCR.
        Returns (is_valid, error_message).
        
        Checks:
        - Blur detection (Laplacian variance)
        - Brightness (too dark/too bright)
        """
        if cv2 is None or np is None:
            return True, None  # Skip quality gate if OpenCV not available
        
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
            if img is None:
                return False, "Invalid image format"
            
            # 1) Blur detection using Laplacian variance
            laplacian_var = cv2.Laplacian(img, cv2.CV_64F).var()
            # Threshold: < 100 is usually too blurry
            if laplacian_var < 100:
                return False, f"Image too blurry (variance: {laplacian_var:.1f}, threshold: 100). Please retake the photo with better focus."
            
            # 2) Brightness check
            mean_brightness = np.mean(img)
            # Too dark: < 50, Too bright: > 200
            if mean_brightness < 50:
                return False, f"Image too dark (brightness: {mean_brightness:.1f}, threshold: 50). Please retake with better lighting or enable flash."
            if mean_brightness > 200:
                return False, f"Image too bright (brightness: {mean_brightness:.1f}, threshold: 200). Please retake with less direct light."
            
            return True, None
        except Exception as e:
            # If quality check fails, allow processing (don't block)
            print(f"[OCR] Quality gate check failed: {e}")
            return True, None

    @staticmethod
    def _ocr_with_paddleocr(image_bytes: bytes) -> Optional[str]:
        """
        OCR using PaddleOCR (better for receipts/tickets than Tesseract).
        Returns extracted text or None if PaddleOCR not available.
        """
        if PaddleOCR is None:
            return None
        
        try:
            # Initialize PaddleOCR (lazy initialization, cache the instance)
            if not hasattr(OCRService, '_paddle_ocr_instance'):
                # Use French + English, use_gpu=False for CPU
                OCRService._paddle_ocr_instance = PaddleOCR(
                    use_angle_cls=True,
                    lang='fr',
                    use_gpu=False,
                    show_log=False
                )
            
            ocr = OCRService._paddle_ocr_instance
            
            # Run OCR
            result = ocr.ocr(image_bytes, cls=True)
            
            # Extract text from results
            if not result or not result[0]:
                return None
            
            # Combine all detected text
            texts = []
            for line in result[0]:
                if line and len(line) >= 2:
                    text = line[1][0] if isinstance(line[1], (list, tuple)) else str(line[1])
                    if text:
                        texts.append(text)
            
            return "\n".join(texts) if texts else None
            
        except Exception as e:
            print(f"[OCR] PaddleOCR failed: {e}")
            return None

    @staticmethod
    def _ocr_image_bytes(image_bytes: bytes) -> str:
        """
        High-quality OCR with progressive pipeline:
        1. Quality gate (blur/brightness check)
        2. OpenCV document cleanup (contours, perspective, deskew, illumination)
        3. PaddleOCR (preferred for receipts) or Tesseract (fallback)
        4. Fallback to basic preprocessing if advanced fails
        
        Prioritizes quality over speed.
        """
        # Quality gate: check if image is suitable
        is_valid, error_msg = OCRService._quality_gate(image_bytes)
        if not is_valid:
            raise Exception(error_msg or "Image quality too poor for OCR")
        
        # Try OpenCV document cleanup first
        cleaned_bytes = OCRService._document_cleanup_opencv(image_bytes)
        use_cleaned = cleaned_bytes is not None
        
        # Use cleaned image if available, otherwise original
        img_bytes_to_use = cleaned_bytes if use_cleaned else image_bytes
        
        # Try PaddleOCR first (better for receipts)
        paddle_result = OCRService._ocr_with_paddleocr(img_bytes_to_use)
        if paddle_result and len(paddle_result.strip()) > 10:
            return paddle_result
        
        # Fallback to Tesseract
        if pytesseract is None or Image is None:
            if paddle_result:
                return paddle_result  # Return PaddleOCR result even if short
            raise Exception("OCR not available (pytesseract/Pillow not installed).")
        
        # Convert to PIL Image for Tesseract
        img = Image.open(io.BytesIO(img_bytes_to_use))
        
        # Basic preprocessing for Tesseract (if OpenCV didn't clean it)
        if not use_cleaned:
            try:
                # 1) Fix EXIF orientation
                img = ImageOps.exif_transpose(img) if ImageOps is not None else img
                
                # 2) Convert to grayscale
                img = img.convert("L")
                
                # 3) Upscaling for quality
                if img.width < 2000:
                    scale = 2000 / max(1, img.width)
                    img = img.resize(
                        (int(img.width * scale), int(img.height * scale)),
                        Image.Resampling.LANCZOS
                    )
                
                # 4) Enhance contrast
                if ImageEnhance is not None:
                    enhancer = ImageEnhance.Contrast(img)
                    img = enhancer.enhance(1.2)
                    
                    enhancer = ImageEnhance.Sharpness(img)
                    img = enhancer.enhance(1.1)
                
                # 5) Adaptive binarization
                if np is not None:
                    img_array = np.array(img)
                    threshold = int(np.median(img_array) * 0.85)
                    img = img.point(lambda p: 0 if p < threshold else 255, mode="1")
                else:
                    img = img.point(lambda p: 0 if p < 180 else 255, mode="1")
            except Exception:
                # If preprocessing fails, use image as-is
                pass
        
        # Tesseract OCR
        config_default = "--oem 3 --psm 6"
        config = os.getenv("TESSERACT_CONFIG", config_default)
        lang = os.getenv("TESSERACT_LANG", "fra+eng")
        
        result_primary = pytesseract.image_to_string(img, lang=lang, config=config)
        
        # Try alternative PSM modes if result is poor
        if len(result_primary.strip()) < 50:
            for psm_mode in ["11", "4"]:
                try:
                    alt_config = f"--oem 3 --psm {psm_mode}"
                    result_alt = pytesseract.image_to_string(img, lang=lang, config=alt_config)
                    if len(result_alt.strip()) > len(result_primary.strip()) * 1.2:
                        result_primary = result_alt
                        break
                except Exception:
                    continue
        
        # Return Tesseract result, or PaddleOCR if Tesseract failed
        if result_primary and len(result_primary.strip()) > 10:
            return result_primary
        elif paddle_result:
            return paddle_result
        else:
            return result_primary  # Return whatever we have

    @staticmethod
    def _norm_amount(s: str) -> Optional[float]:
        if not s:
            return None
        v = s.strip()
        # Remove currency and spaces, normalize decimal comma
        v = v.replace("€", "").replace("EUR", "").replace("\u00a0", " ").strip()
        v = re.sub(r"[^\d,.\-]", "", v)
        # If both comma and dot, assume comma is thousand sep if dot last? keep simple:
        if v.count(",") == 1 and v.count(".") == 0:
            v = v.replace(",", ".")
        try:
            return float(v)
        except Exception:
            return None

    @staticmethod
    def _extract_date(text: str) -> Optional[str]:
        """
        Extract date with multiple format patterns (quality-first: try all patterns).
        """
        # Try ISO format first (YYYY-MM-DD)
        m = re.search(r"\b(\d{4}[-/]\d{2}[-/]\d{2})\b", text)
        if m:
            raw = m.group(1).replace("/", "-")
            try:
                dt = date_parser.parse(raw, fuzzy=False)
                return dt.strftime("%Y-%m-%d")
            except Exception:
                pass
        
        # Try DD/MM/YYYY or DD-MM-YYYY (French format)
        patterns = [
            r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b",  # DD/MM/YYYY
            r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2})\b",  # DD/MM/YY
            r"\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b",  # YYYY/MM/DD
        ]
        for pattern in patterns:
            matches = list(re.finditer(pattern, text))
            for m in matches:
                raw = m.group(1)
                try:
                    dt = date_parser.parse(raw, dayfirst=True, fuzzy=False)
                    # Validate reasonable date (not too old, not future)
                    if dt.year >= 2000 and dt.year <= 2100:
                        return dt.strftime("%Y-%m-%d")
                except Exception:
                    continue
        
        # Try written dates (e.g., "15 janvier 2024")
        try:
            dt = date_parser.parse(text, fuzzy=True, default=None)
            if dt and dt.year >= 2000 and dt.year <= 2100:
                return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
        
        return None

    @staticmethod
    def _is_valid_shop_name(name: str) -> bool:
        """Validate shop name: must not be a label, must have letters, reasonable length."""
        if not name or len(name) < 2:
            return False
        name_lower = name.lower().strip()
        # Reject known invalid labels
        if name_lower in INVALID_SHOP_NAMES:
            return False
        # Reject if it's just a label (contains ":" or ";" at the end)
        if name_lower.endswith((":", ";", " :", " ;")):
            return False
        # Must contain at least one letter
        if not any(ch.isalpha() for ch in name):
            return False
        # Reject if it's mostly digits (likely an address/phone)
        digit_ratio = sum(ch.isdigit() for ch in name) / max(1, len(name))
        if digit_ratio > 0.4:
            return False
        # Reject if it looks like a date
        if re.match(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", name):
            return False
        # Reject if it's too short (likely a label)
        if len(name.strip()) < 3:
            return False
        return True

    @staticmethod
    def _is_valid_customer_name(name: str) -> bool:
        """Validate customer name: must not be a label, must have letters, reasonable length."""
        if not name or len(name) < 2:
            return False
        name_lower = name.lower().strip()
        # Reject known invalid labels
        if name_lower in INVALID_CUSTOMER_NAMES:
            return False
        # Reject if it's just a label (contains ":" or ";" at the end)
        if name_lower.endswith((":", ";", " :", " ;")):
            return False
        # Must contain at least one letter
        if not any(ch.isalpha() for ch in name):
            return False
        # Reject if it's mostly digits (likely an address/phone)
        digit_ratio = sum(ch.isdigit() for ch in name) / max(1, len(name))
        if digit_ratio > 0.3:
            return False
        # Reject if it contains @ (email)
        if "@" in name:
            return False
        # Reject if it looks like a date
        if re.match(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", name):
            return False
        # Reject if it's too short
        if len(name.strip()) < 2:
            return False
        return True

    @staticmethod
    def _looks_like_company_name(name: str) -> bool:
        """Check if a name looks like a company/enterprise rather than a person."""
        if not name or len(name) < 3:
            return False
        name_upper = name.upper()
        # Company indicators
        company_indicators = ("SARL", "SAS", "SA", "SRL", "LTD", "LLC", "INC", "CORP", "GMBH", 
                             "SOCIÉTÉ", "SOCIETE", "SOCIETY", "COMPANY", "CO", "ENTREPRISE",
                             "EURL", "SNC", "SC", "SCA", "SCS", "SCI", "ASSOCIATION", "ASSO")
        if any(ind in name_upper for ind in company_indicators):
            return True
        # If it's long and has multiple words, likely a company
        words = name.split()
        if len(words) >= 3 and len(name) > 15:
            return True
        # If it contains common business words
        business_words = ("SERVICES", "SOLUTIONS", "TECHNOLOGIES", "SYSTEMS", "GROUP", 
                         "GROUPEMENT", "HOLDING", "INTERNATIONAL", "FRANCE", "EUROPE")
        if any(word in name_upper for word in business_words):
            return True
        return False

    @staticmethod
    def _looks_like_person_name(name: str) -> bool:
        """Check if a name looks like a person's name (first/last name only)."""
        if not name:
            return False
        # Short names (1-2 words, < 20 chars) without company indicators are likely persons
        words = name.split()
        if len(words) <= 2 and len(name) < 20:
            name_upper = name.upper()
            # If it doesn't have company indicators, likely a person
            company_indicators = ("SARL", "SAS", "SA", "SRL", "LTD", "LLC", "INC", "CORP")
            if not any(ind in name_upper for ind in company_indicators):
                # Check if it's mostly letters (not an address)
                if sum(ch.isalpha() for ch in name) / max(1, len(name)) > 0.7:
                    return True
        return False

    @staticmethod
    def _is_valid_vat_number(vat: str) -> bool:
        """Validate VAT number: must not be a misread label."""
        if not vat or len(vat) < 4:
            return False
        vat_lower = vat.lower().strip()
        # Reject known invalid values
        if vat_lower in INVALID_VAT_NUMBERS:
            return False
        # Reject if it contains common words that shouldn't be in a VAT number
        invalid_words = ("quantité", "quantite", "quantity", "tva", "vat", "description", "prix")
        if any(word in vat_lower for word in invalid_words):
            return False
        return True

    @staticmethod
    def _extract_shop_name(text: str) -> str:
        """
        Extract shop/vendor name with multiple heuristics including logo detection.
        Prioritizes company names, logos, and structured sections.
        """
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        text_upper = text.upper()
        
        # Skip common header words and section labels
        skip_keywords = (
            "FACTURE", "INVOICE", "DEVIS", "REÇU", "RECU", "TICKET", "BON",
            "DATE", "CLIENT", "CUSTOMER", "ADRESSE", "ADDRESS", "TÉL", "TEL",
            "SIRET", "SIREN", "TVA", "VAT", "IBAN", "BIC", "N°", "NUMERO",
            "FOURNI PAR", "PROVIDED BY", "FACTURÉ À", "FACTURE À", "BILLED TO",
            "MERCI", "THANK YOU", "A BIENTOT", "SEE YOU SOON"
        )
        
        # Strategy 1: Look for known company names / brand names (logo detection via text)
        # Common French companies and patterns
        known_companies = (
            "ELECTRA", "TOTAL", "ESSO", "SHELL", "BP", "AVIA", "CARREFOUR",
            "LECLERC", "AUCHAN", "CASINO", "MONOPRIX", "INTERMARCHE",
            "CENTRE DE LAVAGE", "WASH", "STATION", "RELAIS"
        )
        for company in known_companies:
            # Look for company name in first few lines (where logos usually are)
            for i, ln in enumerate(lines[:10]):
                if company in ln.upper() and OCRService._is_valid_shop_name(ln):
                    # Extract the full line or just the company name
                    if len(ln) < 50:
                        return ln[:120]
                    # If line is long, try to extract just the company part
                    parts = re.split(r"[,\s]+", ln)
                    for part in parts:
                        if company in part.upper() and OCRService._is_valid_shop_name(part):
                            return part[:120]
        
        # Strategy 2: Look for "Fourni par" / "Provided by" and take the next line
        for i, ln in enumerate(lines[:25]):
            up = ln.upper()
            if any(k in up for k in ("FOURNI PAR", "PROVIDED BY", "FOURNISSEUR", "SUPPLIER")):
                # Take the next non-empty line after the label
                for j in range(i + 1, min(i + 5, len(lines))):
                    candidate = lines[j].strip()
                    if not candidate:
                        continue
                    # Skip if it's another label
                    if any(sk in candidate.upper() for sk in skip_keywords):
                        continue
                    # Skip if too many digits (likely address/phone)
                    digit_ratio = sum(ch.isdigit() for ch in candidate) / max(1, len(candidate))
                    if digit_ratio > 0.3:
                        continue
                    # Validate candidate
                    if OCRService._is_valid_shop_name(candidate):
                        return candidate[:120]
        
        # Strategy 3: First substantial line in top section (logo position)
        # Usually logos are in the first 3-5 lines
        for i, ln in enumerate(lines[:8]):
            up = ln.upper()
            # Skip if it's a header keyword or section label
            if any(k in up for k in skip_keywords):
                continue
            # Skip if too many digits (likely address/phone)
            digit_ratio = sum(ch.isdigit() for ch in ln) / max(1, len(ln))
            if digit_ratio > 0.3:
                continue
            # Skip if too short
            if len(ln) < 3:
                continue
            # Skip if looks like date
            if re.match(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", ln):
                continue
            # Skip if it's an email
            if "@" in ln:
                continue
            # Validate candidate
            if OCRService._is_valid_shop_name(ln):
                # Prefer longer names (more likely to be company names)
                if len(ln) >= 5:
                    return ln[:120]
        
        # Strategy 4: Look for lines with "Raison sociale", "Nom", "Entreprise"
        for ln in lines[:30]:
            up = ln.upper()
            if any(k in up for k in ("RAISON SOCIALE", "NOM", "ENTREPRISE", "SOCIÉTÉ", "SOCIETE", "COMPANY")):
                # Try to extract the value after the label
                parts = re.split(r"[:;]", ln, 1)
                if len(parts) > 1:
                    candidate = parts[1].strip()
                    if OCRService._is_valid_shop_name(candidate):
                        return candidate[:120]
        
        # Strategy 5: Look for company indicators (SARL, SAS, SA, etc.) in first lines
        company_indicators = ("SARL", "SAS", "SA", "SRL", "LTD", "LLC", "INC", "CORP", "GMBH")
        for i, ln in enumerate(lines[:15]):
            up = ln.upper()
            if any(ind in up for ind in company_indicators):
                # Extract the company name (usually before the indicator)
                parts = re.split(r"\s+(?:SARL|SAS|SA|SRL|LTD|LLC|INC|CORP|GMBH)", up, 1)
                if parts and parts[0]:
                    candidate = parts[0].strip()
                    if OCRService._is_valid_shop_name(candidate) and len(candidate) >= 3:
                        return candidate[:120]
                # Or take the full line if it contains the indicator
                if OCRService._is_valid_shop_name(ln):
                    return ln[:120]
        
        return ""

    def _find_total(self, text: str, labels: list[str]) -> Optional[float]:
        """
        Find amounts near labels with multiple patterns (quality-first).
        Prefers last match (usually the final total at bottom).
        """
        # Pattern 1: Label followed by amount (flexible spacing)
        for lab in labels:
            patterns = [
                rf"(?i)\b{re.escape(lab)}\s*[:;]?\s*(-?\d[\d\s\u00a0]*[.,]?\d{{0,2}})\s*(€|eur)?",
                rf"(?i)\b{re.escape(lab)}\b[^\d\-]{{0,50}}(-?\d[\d\s\u00a0]*[.,]?\d{{0,2}})\s*(€|eur)?",
                rf"(?i)(-?\d[\d\s\u00a0]*[.,]?\d{{0,2}})\s*(€|eur)?\s*\b{re.escape(lab)}\b",
            ]
            for pattern in patterns:
                matches = list(re.finditer(pattern, text))
                if matches:
                    # Prefer last match (usually the final total)
                    for m in reversed(matches):
                        amt_str = m.group(1) if m.lastindex >= 1 else None
                        if amt_str:
                            amt = self._norm_amount(amt_str)
                            if amt is not None and amt > 0:
                                return amt
        return None

    def _find_vat_amount(self, text: str) -> Optional[float]:
        """
        Find VAT amount (not rate) with specific patterns to avoid percentages.
        """
        # Pattern 1: "TVA 20%" followed by amount (e.g., "TVA 20% 1,29 €")
        patterns = [
            r"(?i)\bTVA\s+\d+%\s+(-?\d[\d\s\u00a0]*[.,]?\d{0,2})\s*(€|eur)?",
            r"(?i)\bTVA\s+\d+%\s*[:;]?\s*(-?\d[\d\s\u00a0]*[.,]?\d{0,2})\s*(€|eur)?",
            # Pattern 2: "TVA" with amount (but not percentage)
            r"(?i)\bTVA\s*[:;]?\s*(-?\d[\d\s\u00a0]*[.,]?\d{0,2})\s*(€|eur)?",
            r"(?i)\bTVA\b[^\d%\-]{0,30}(-?\d[\d\s\u00a0]*[.,]?\d{0,2})\s*(€|eur)?",
        ]
        for pattern in patterns:
            matches = list(re.finditer(pattern, text))
            if matches:
                # Prefer last match (usually the final VAT amount)
                for m in reversed(matches):
                    amt_str = m.group(1) if m.lastindex >= 1 else None
                    if amt_str:
                        amt = self._norm_amount(amt_str)
                        # Filter out percentages (should be small amounts, not 20, 10, etc.)
                        if amt is not None and amt > 0 and amt < 1000:  # VAT amounts are typically < 1000
                            return amt
        return None

    @staticmethod
    def _parse_items(text: str) -> list[dict[str, Any]]:
        """
        Enhanced items parsing with multiple patterns (quality-first).
        Handles both structured tables and free-form text.
        """
        items: list[dict[str, Any]] = []
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        # Find items section start
        start_idx = 0
        header_keywords = (
            "DESCRIPTION", "DESIGNATION", "DÉSIGNATION", "LIBELLÉ", "LIBELLE",
            "QTE", "QTÉ", "QUANTITÉ", "QUANTITE", "QUANTITY", "QTY",
            "PRIX", "UNIT", "UNITAIRE", "MONTANT", "TOTAL", "ÉNERGIE", "ENERGIE"
        )
        header_line_idx = -1
        for i, ln in enumerate(lines):
            up = ln.upper()
            if any(k in up for k in header_keywords):
                start_idx = i + 1
                header_line_idx = i
                break

        # Try to detect table structure from header line
        header_line = lines[header_line_idx] if header_line_idx >= 0 else ""
        is_table = any(k in header_line.upper() for k in ("DESCRIPTION", "QUANTITÉ", "QUANTITE", "PRIX HT", "PRIX TTC", "TVA"))

        # Stop when totals section begins
        stop_tokens = ("PRIX TOTAL HT", "PRIX TOTAL TTC", "TOTAL HT", "TOTAL TTC", "NET A PAYER", "NET À PAYER", "TVA", "VAT", "SOUS-TOTAL")
        items_section = []
        for ln in lines[start_idx:]:
            up = ln.upper()
            if any(tok in up for tok in stop_tokens) and any(ch.isdigit() for ch in ln):
                break
            items_section.append(ln)

        # If table structure detected, parse as table
        if is_table and items_section:
            items.extend(OCRService._parse_table_items(items_section))
        
        # Also try free-form parsing for items not captured by table parser
        if not items:
            items.extend(OCRService._parse_freeform_items(items_section))
        
        # Limit to reasonable number of items
        return items[:50]

    @staticmethod
    def _parse_table_items(lines: list[str]) -> list[dict[str, Any]]:
        """Parse items from a structured table (columns: Description, TVA, Quantité, Prix HT, Prix TTC)."""
        items: list[dict[str, Any]] = []
        
        for ln in lines:
            if not ln or len(ln) < 3:
                continue
            
            # Skip header-like lines
            up = ln.upper()
            if any(k in up for k in ("DESCRIPTION", "TVA", "QUANTITÉ", "QUANTITE", "PRIX", "TOTAL")):
                continue
            
            # Try to extract columns: Description | TVA | Quantité | Prix HT | Prix TTC
            # Pattern: description (text) | TVA (percentage or amount) | quantity (number with unit) | price_ht | price_ttc
            # Since OCR may not preserve exact column alignment, try flexible patterns
            
            # Pattern 1: Look for quantity with unit (e.g., "26,695 kWh")
            qty_match = re.search(r"(\d+[.,]\d+|\d+)\s*(kwh|kg|g|ml|l|m|cm|mm|unité|unit|pcs|pièce|pièces)", ln, re.I)
            if qty_match:
                qty_str = qty_match.group(1).replace(",", ".")
                try:
                    qty = float(qty_str)
                except:
                    qty = 1
            else:
                # Try simple number
                qty_match = re.search(r"\b(\d+[.,]\d+|\d+)\b", ln)
                if qty_match:
                    qty_str = qty_match.group(1).replace(",", ".")
                    try:
                        qty = float(qty_str)
                    except:
                        qty = 1
                else:
                    qty = 1
            
            # Extract prices (look for amounts with €)
            prices = re.findall(r"(\d+[.,]\d+|\d+)\s*(?:€|eur)", ln, re.I)
            if len(prices) >= 2:
                # Usually: Prix HT, Prix TTC
                price_ht_str = prices[0].replace(",", ".")
                price_ttc_str = prices[1].replace(",", ".")
                try:
                    price_ht = float(price_ht_str)
                    price_ttc = float(price_ttc_str)
                    # Description is everything before the first price
                    desc = re.split(r"\d+[.,]?\d*\s*(?:€|eur)", ln, 1)[0].strip()
                    # Validate description (not a label, has letters, reasonable length)
                    if desc and len(desc) >= 2 and any(ch.isalpha() for ch in desc):
                        # Skip if it's a known label
                        desc_upper = desc.upper()
                        if not any(k in desc_upper for k in ("DESCRIPTION", "TVA", "QUANTITÉ", "QUANTITE", "PRIX", "TOTAL")):
                            items.append({
                                "description": desc[:200],
                                "quantity": qty,
                                "unit_price": price_ht / qty if qty > 0 else price_ht,
                                "total": price_ttc,
                            })
                            continue
                except:
                    pass
            
            # Pattern 2: Single price (Prix TTC)
            if len(prices) == 1:
                price_str = prices[0].replace(",", ".")
                try:
                    price_ttc = float(price_str)
                    desc = re.split(r"\d+[.,]?\d*\s*(?:€|eur)", ln, 1)[0].strip()
                    # Validate description
                    if desc and len(desc) >= 2 and any(ch.isalpha() for ch in desc):
                        desc_upper = desc.upper()
                        if not any(k in desc_upper for k in ("DESCRIPTION", "TVA", "QUANTITÉ", "QUANTITE", "PRIX", "TOTAL")):
                            items.append({
                                "description": desc[:200],
                                "quantity": qty,
                                "unit_price": price_ttc / qty if qty > 0 else price_ttc,
                                "total": price_ttc,
                            })
                except:
                    pass
        
        return items

    @staticmethod
    def _parse_freeform_items(items_section: list[str]) -> list[dict[str, Any]]:
        """Parse items from free-form text (fallback method)."""
        items: list[dict[str, Any]] = []
        
        # Pattern 1: "Qty x Unit Price = Total" or "Desc Qty Unit Total"
        for ln in items_section:
            if not ln or len(ln) < 3:
                continue
            
            # Skip if looks like a header or total line
            up = ln.upper()
            if any(k in up for k in ("TOTAL", "SOUS-TOTAL", "TVA", "VAT", "NET")):
                continue
            
            # Pattern 1: Try to extract qty, unit_price, total
            # "2 x 15.50 = 31.00" or "2 x 15,50 € = 31,00 €"
            pattern1 = r"(\d+)\s*x\s*(\d[\d\s\u00a0]*[.,]?\d{0,2})\s*(?:€|eur)?\s*[=:]\s*(\d[\d\s\u00a0]*[.,]?\d{0,2})\s*(?:€|eur)?"
            m1 = re.search(pattern1, ln, re.I)
            if m1:
                qty = int(m1.group(1))
                unit_price = OCRService._norm_amount(m1.group(2))
                total = OCRService._norm_amount(m1.group(3))
                desc = re.sub(pattern1, "", ln, flags=re.I).strip()
                if desc and total is not None:
                    items.append({
                        "description": desc[:200],
                        "quantity": qty,
                        "unit_price": unit_price if unit_price is not None else (total / qty if qty > 0 else 0),
                        "total": total,
                    })
                    continue
            
            # Pattern 2: "Desc ... Amount" (simple, most common)
            # Look for amount at end of line
            pattern2 = r"(.+?)\s+(-?\d[\d\s\u00a0]*[.,]?\d{0,2})\s*(€|eur)?\s*$"
            m2 = re.search(pattern2, ln, re.I)
            if m2:
                desc = m2.group(1).strip()
                total = OCRService._norm_amount(m2.group(2))
                # Filter out false positives (dates, phone numbers, etc.)
                if desc and total is not None and total > 0 and len(desc) >= 3:
                    # Skip if desc is mostly numbers (likely not an item)
                    if sum(ch.isdigit() for ch in desc) / max(1, len(desc)) < 0.5:
                        items.append({
                            "description": desc[:200],
                            "quantity": 1,
                            "unit_price": total,
                            "total": total,
                        })
                        continue
            
            # Pattern 3: Try to find quantity at start: "2 Description ... Amount"
            pattern3 = r"^(\d+)\s+(.+?)\s+(-?\d[\d\s\u00a0]*[.,]?\d{0,2})\s*(€|eur)?\s*$"
            m3 = re.search(pattern3, ln, re.I)
            if m3:
                qty = int(m3.group(1))
                desc = m3.group(2).strip()
                total = OCRService._norm_amount(m3.group(3))
                if desc and total is not None and total > 0:
                    items.append({
                        "description": desc[:200],
                        "quantity": qty,
                        "unit_price": total / qty if qty > 0 else total,
                        "total": total,
                    })
        
        return items

        # Pattern 1: "Qty x Unit Price = Total" or "Desc Qty Unit Total"
        # Pattern 2: "Desc ... Amount" (simple)
        # Pattern 3: "Desc\nQty Unit Total" (multi-line)
        for ln in items_section:
            if not ln or len(ln) < 3:
                continue
            
            # Skip if looks like a header or total line
            up = ln.upper()
            if any(k in up for k in ("TOTAL", "SOUS-TOTAL", "TVA", "VAT", "NET")):
                continue
            
            # Pattern 1: Try to extract qty, unit_price, total
            # "2 x 15.50 = 31.00" or "2 x 15,50 € = 31,00 €"
            pattern1 = r"(\d+)\s*x\s*(\d[\d\s\u00a0]*[.,]?\d{0,2})\s*(?:€|eur)?\s*[=:]\s*(\d[\d\s\u00a0]*[.,]?\d{0,2})\s*(?:€|eur)?"
            m1 = re.search(pattern1, ln, re.I)
            if m1:
                qty = int(m1.group(1))
                unit_price = OCRService._norm_amount(m1.group(2))
                total = OCRService._norm_amount(m1.group(3))
                desc = re.sub(pattern1, "", ln, flags=re.I).strip()
                if desc and total is not None:
                    items.append({
                        "description": desc[:200],
                        "quantity": qty,
                        "unit_price": unit_price if unit_price is not None else (total / qty if qty > 0 else 0),
                        "total": total,
                    })
                    continue
            
            # Pattern 2: "Desc ... Amount" (simple, most common)
            # Look for amount at end of line
            pattern2 = r"(.+?)\s+(-?\d[\d\s\u00a0]*[.,]?\d{0,2})\s*(€|eur)?\s*$"
            m2 = re.search(pattern2, ln, re.I)
            if m2:
                desc = m2.group(1).strip()
                total = OCRService._norm_amount(m2.group(2))
                # Filter out false positives (dates, phone numbers, etc.)
                if desc and total is not None and total > 0 and len(desc) >= 3:
                    # Skip if desc is mostly numbers (likely not an item)
                    if sum(ch.isdigit() for ch in desc) / max(1, len(desc)) < 0.5:
                        items.append({
                            "description": desc[:200],
                            "quantity": 1,
                            "unit_price": total,
                            "total": total,
                        })
                        continue
            
            # Pattern 3: Try to find quantity at start: "2 Description ... Amount"
            pattern3 = r"^(\d+)\s+(.+?)\s+(-?\d[\d\s\u00a0]*[.,]?\d{0,2})\s*(€|eur)?\s*$"
            m3 = re.search(pattern3, ln, re.I)
            if m3:
                qty = int(m3.group(1))
                desc = m3.group(2).strip()
                total = OCRService._norm_amount(m3.group(3))
                # Validate description
                if desc and total is not None and total > 0 and len(desc) >= 2 and any(ch.isalpha() for ch in desc):
                    desc_upper = desc.upper()
                    if not any(k in desc_upper for k in ("DESCRIPTION", "TVA", "QUANTITÉ", "QUANTITE", "PRIX", "TOTAL")):
                        items.append({
                            "description": desc[:200],
                            "quantity": qty,
                            "unit_price": total / qty if qty > 0 else total,
                            "total": total,
                        })
        
        # Limit to reasonable number of items
        return items[:50]

    @staticmethod
    def _extract_customer_name(text: str) -> str:
        """
        Extract customer/client name (prefer company/enterprise over person name).
        Smart logic: if first match is a person name, look for company name instead.
        """
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        
        # Strategy 1: Look for "Facturé à" / "Billed to" section
        for i, ln in enumerate(lines[:30]):
            up = ln.upper()
            if any(k in up for k in ("FACTURÉ À", "FACTURE À", "BILLED TO", "CLIENT", "CUSTOMER")):
                candidates = []
                
                # Collect all valid candidates from the next few lines
                for j in range(i + 1, min(i + 8, len(lines))):
                    candidate = lines[j].strip()
                    if not candidate:
                        continue
                    # Skip if it's another label
                    if any(sk in candidate.upper() for sk in ("ADRESSE", "ADDRESS", "EMAIL", "TEL", "TÉL", "DATE", "FOURNI PAR", "PROVIDED BY")):
                        continue
                    # Skip if too many digits (likely address/phone)
                    digit_ratio = sum(ch.isdigit() for ch in candidate) / max(1, len(candidate))
                    if digit_ratio > 0.3:
                        continue
                    # Skip if contains @ (email)
                    if "@" in candidate:
                        continue
                    # Skip if looks like a date
                    if re.match(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", candidate):
                        continue
                    # Validate candidate
                    if OCRService._is_valid_customer_name(candidate):
                        candidates.append(candidate)
                
                # Smart selection: prefer company name over person name
                if candidates:
                    # Score each candidate
                    scored_candidates = []
                    for candidate in candidates:
                        score = 0
                        # Higher score for company names
                        if OCRService._looks_like_company_name(candidate):
                            score += 100
                        # Lower score for person names
                        if OCRService._looks_like_person_name(candidate):
                            score -= 50
                        # Higher score for longer names (more likely to be complete)
                        score += min(len(candidate), 50)  # Cap at 50
                        # Higher score if it contains multiple words
                        score += len(candidate.split()) * 5
                        scored_candidates.append((score, candidate))
                    
                    # Sort by score (highest first)
                    scored_candidates.sort(reverse=True, key=lambda x: x[0])
                    
                    # If best candidate is a company, use it
                    if scored_candidates and OCRService._looks_like_company_name(scored_candidates[0][1]):
                        return scored_candidates[0][1][:150]
                    
                    # If best candidate is a person, check if there's a company in the list
                    if scored_candidates:
                        best_candidate = scored_candidates[0][1]
                        if OCRService._looks_like_person_name(best_candidate):
                            # Look for a company in other candidates
                            for score, candidate in scored_candidates[1:]:
                                if OCRService._looks_like_company_name(candidate):
                                    return candidate[:150]
                            # If no company found, check if there's a longer/more complete name
                            for score, candidate in scored_candidates[1:]:
                                if len(candidate) > len(best_candidate) + 10:
                                    return candidate[:150]
                            # Last resort: if person name is very short (< 10 chars), try to find something better
                            if len(best_candidate) < 10:
                                for score, candidate in scored_candidates[1:]:
                                    if len(candidate) >= 10 and not OCRService._looks_like_person_name(candidate):
                                        return candidate[:150]
                            # Return the person name only if it's reasonable
                            return best_candidate[:150]
                        else:
                            # Best candidate is not clearly a person, use it
                            return best_candidate[:150]
                
                # If label is on same line, extract after colon
                if ":" in ln or ";" in ln:
                    parts = re.split(r"[:;]", ln, 1)
                    if len(parts) > 1:
                        candidate = parts[1].strip()
                        if OCRService._is_valid_customer_name(candidate):
                            if not OCRService._looks_like_person_name(candidate) or OCRService._looks_like_company_name(candidate):
                                return candidate[:150]
        
        # Strategy 2: Look for "Raison sociale", "Entreprise", "Company" labels
        for ln in lines[:30]:
            up = ln.upper()
            if any(k in up for k in ("RAISON SOCIALE", "ENTREPRISE", "SOCIÉTÉ", "SOCIETE", "COMPANY", "SOCIETY")):
                parts = re.split(r"[:;]", ln, 1)
                if len(parts) > 1:
                    candidate = parts[1].strip()
                    if OCRService._is_valid_customer_name(candidate):
                        return candidate[:150]
        
        # Strategy 3: Look for "Nom:", "Name:" labels (fallback)
        for ln in lines[:30]:
            up = ln.upper()
            if any(k in up for k in ("NOM", "NAME", "ACHETEUR", "BUYER")):
                parts = re.split(r"[:;]", ln, 1)
                if len(parts) > 1:
                    candidate = parts[1].strip()
                    if OCRService._is_valid_customer_name(candidate):
                        return candidate[:150]
        
        return ""

    @staticmethod
    def _extract_invoice_number(text: str) -> str:
        """Extract invoice/ticket number."""
        # Pattern 1: "N°", "Numéro", "No", "Number" followed by alphanumeric
        patterns = [
            r"(?i)(?:N[°º]|NUM[ÉE]RO|NO|NUMBER|REF|R[ÉE]F[ÉE]RENCE)\s*[:;]?\s*([A-Z0-9\-/]+)",
            r"(?i)(?:FACTURE|INVOICE|TICKET)\s*(?:N[°º]|#)?\s*([A-Z0-9\-/]+)",
        ]
        for pattern in patterns:
            matches = list(re.finditer(pattern, text))
            for m in matches:
                candidate = m.group(1).strip()
                if 2 <= len(candidate) <= 50:
                    return candidate[:50]
        return ""

    @staticmethod
    def _extract_ticket_number(text: str) -> str:
        """Extract ticket number (for receipts)."""
        # Look for "Ticket", "Bon", "Reçu" followed by number
        patterns = [
            r"(?i)(?:TICKET|BON|RE[ÇC]U)\s*(?:N[°º]|#)?\s*([0-9\-/]+)",
            r"(?i)(?:N[°º]|NUM[ÉE]RO)\s*[:;]?\s*([0-9\-/]+)",
        ]
        for pattern in patterns:
            matches = list(re.finditer(pattern, text))
            for m in matches:
                candidate = m.group(1).strip()
                if 1 <= len(candidate) <= 30:
                    return candidate[:30]
        return ""

    @staticmethod
    def _is_valid_iban(iban: str) -> bool:
        """
        Validate IBAN with strict rules and checksum validation.
        IBAN format: 2 letters (country) + 2 digits (check) + up to 30 alphanumeric
        French IBAN: FR + 2 digits + 23 alphanumeric (total 27 chars)
        """
        if not iban or len(iban) < 15:
            return False
        iban_upper = re.sub(r"\s+", "", iban.upper().strip())
        
        # Must start with 2 letters (country code)
        if len(iban_upper) < 4 or not iban_upper[:2].isalpha():
            return False
        
        # Must have 2 digits after country code (checksum)
        if not iban_upper[2:4].isdigit():
            return False
        
        # Country-specific length validation
        country = iban_upper[:2]
        country_lengths = {
            "FR": 27,  # France
            "BE": 16,  # Belgium
            "DE": 22,  # Germany
            "IT": 27,  # Italy
            "ES": 24,  # Spain
            "NL": 18,  # Netherlands
            "GB": 22,  # UK
        }
        if country in country_lengths:
            if len(iban_upper) != country_lengths[country]:
                return False
        else:
            # General: 15-34 characters
            if len(iban_upper) < 15 or len(iban_upper) > 34:
                return False
        
        # Must be alphanumeric (letters and digits only)
        if not iban_upper.isalnum():
            return False
        
        # French IBAN specific: must have letters in the account part (not just digits)
        if country == "FR":
            if len(iban_upper) != 27:
                return False
            # Account part (after FR + 2 digits) should have some letters
            account_part = iban_upper[4:]
            if account_part.isdigit():
                return False  # French IBAN always has letters in account part
        
        # IBAN checksum validation (mod 97)
        try:
            # Move first 4 chars to end
            rearranged = iban_upper[4:] + iban_upper[:4]
            # Convert letters to numbers (A=10, B=11, ..., Z=35)
            numeric = ""
            for char in rearranged:
                if char.isdigit():
                    numeric += char
                else:
                    numeric += str(ord(char) - ord('A') + 10)
            # Calculate mod 97
            remainder = int(numeric) % 97
            if remainder != 1:
                return False  # Invalid checksum
        except (ValueError, OverflowError):
            return False  # Can't validate checksum
        
        # Reject if it looks like a VAT number (FR + only digits, short)
        if country == "FR" and len(iban_upper) < 20 and iban_upper[2:].isdigit():
            return False
        
        return True

    @staticmethod
    def _extract_iban(text: str) -> str:
        """
        Extract IBAN with strict validation.
        IBAN format: 2 letters (country) + 2 digits (check) + up to 30 alphanumeric
        French IBAN: FR + 2 digits + 23 alphanumeric (total 27 chars)
        """
        # Strategy 1: Look for IBAN/RIB label (most reliable)
        patterns_labeled = [
            r"(?i)(?:IBAN|RIB|COMPTE|ACCOUNT)\s*[:;]?\s*([A-Z]{2}\d{2}[A-Z0-9\s]{10,30})",
            r"(?i)(?:IBAN|RIB)\s*[:;]?\s*([A-Z]{2}\s?\d{2}\s?[A-Z0-9\s]{10,30})",
        ]
        for pattern in patterns_labeled:
            matches = list(re.finditer(pattern, text))
            for m in matches:
                candidate = re.sub(r"\s+", "", m.group(1).upper())
                if OCRService._is_valid_iban(candidate):
                    return candidate[:34]
        
        # Strategy 2: Look for IBAN pattern anywhere (but be more strict)
        # Only match if it's clearly separated (word boundaries)
        iban_pattern = r"\b([A-Z]{2}\d{2}[A-Z0-9]{10,30})\b"
        matches = list(re.finditer(iban_pattern, text))
        for m in matches:
            candidate = m.group(1).upper()
            # Additional context check: should not be part of a longer alphanumeric string
            start, end = m.span()
            # Check if surrounded by spaces/punctuation (not part of another word)
            if start > 0 and text[start-1].isalnum():
                continue
            if end < len(text) and text[end].isalnum():
                continue
            if OCRService._is_valid_iban(candidate):
                return candidate[:34]
        
        return ""

    @staticmethod
    def _extract_siret(text: str) -> str:
        """Extract SIRET (14 digits) or SIREN (9 digits)."""
        # SIRET: 14 digits, often formatted as XXX XXX XXX XXXXXX
        # SIREN: 9 digits (first 9 digits of SIRET)
        patterns = [
            r"(?i)(?:SIRET|SIREN)\s*[:;]?\s*([0-9\s]{9,14})",
            r"\b([0-9]{3}\s?[0-9]{3}\s?[0-9]{3}\s?[0-9]{5})\b",  # SIRET formatted: 3-3-3-5
            r"\b([0-9]{9,14})\b",  # Unformatted SIRET/SIREN
        ]
        for pattern in patterns:
            matches = list(re.finditer(pattern, text))
            for m in matches:
                candidate = re.sub(r"\s+", "", m.group(1))
                # Prefer SIRET (14 digits) over SIREN (9 digits)
                if len(candidate) == 14 and candidate.isdigit():
                    return candidate
                elif len(candidate) == 9 and candidate.isdigit():
                    # SIREN found, but keep looking for full SIRET
                    continue
        # If no 14-digit found, return the 9-digit SIREN if found
        for pattern in patterns:
            matches = list(re.finditer(pattern, text))
            for m in matches:
                candidate = re.sub(r"\s+", "", m.group(1))
                if len(candidate) == 9 and candidate.isdigit():
                    return candidate
        return ""

    @staticmethod
    def _extract_vat_number(text: str) -> str:
        """Extract VAT intracommunity number."""
        # Format: FR + 2 digits + 9 alphanumeric (for France)
        # Or: country code + alphanumeric
        # Also look for numbers like "FR45891624884" (11 digits after FR)
        patterns = [
            r"(?i)(?:TVA|VAT)\s*(?:INTRA|INTRA[-\s]?COMMUNAUTAIRE)?\s*[:;]?\s*([A-Z]{2}[A-Z0-9\s]{2,15})",
            r"\b([A-Z]{2}\d{11})\b",  # French format: FR + 11 digits (e.g., FR45891624884)
            r"\b([A-Z]{2}\d{2}[A-Z0-9\s]{7,11})\b",  # General format
        ]
        for pattern in patterns:
            matches = list(re.finditer(pattern, text))
            for m in matches:
                candidate = re.sub(r"\s+", "", m.group(1).upper())
                if 4 <= len(candidate) <= 20 and OCRService._is_valid_vat_number(candidate):
                    return candidate[:20]
        return ""

    @staticmethod
    def _detect_document_type(text: str) -> str:
        """
        Detect document type: invoice, receipt, gas_station_ticket, etc.
        Returns: 'invoice', 'receipt', 'gas_station_ticket', 'parking_ticket', 'unknown'
        """
        text_upper = text.upper()
        
        # Gas station / fuel ticket indicators
        gas_keywords = (
            "STATION", "ESSENCE", "CARBURANT", "GAZOLE", "DIESEL", "SP95", "SP98", "E10", "E85",
            "LITRE", "LITRES", "L", "KM", "KILOMETRE", "KILOMETRES", "KILOMETRAGE",
            "PUMP", "POMPE", "NOZZLE", "BUSE", "STATION ID", "STATIONID"
        )
        if any(kw in text_upper for kw in gas_keywords):
            return "gas_station_ticket"
        
        # Parking ticket indicators
        parking_keywords = (
            "PARKING", "PARK", "TICKET PARKING", "HORODATEUR", "HORODATAGE",
            "ENTREE", "SORTIE", "ENTRÉE", "SORTIE", "DURÉE", "DUREE"
        )
        if any(kw in text_upper for kw in parking_keywords):
            return "parking_ticket"
        
        # Receipt / ticket de caisse indicators
        receipt_keywords = (
            "TICKET CLIENT", "TICKET DE CAISSE", "RECU", "REÇU", "RECEIPT",
            "CAISSE", "CASHIER", "CAISSIER", "CAISSIERE", "TICKET N", "TICKET:",
            "ARTICLE", "ARTICLES", "TOTAL:", "MERCI", "THANK YOU"
        )
        if any(kw in text_upper for kw in receipt_keywords):
            return "receipt"
        
        # Invoice indicators
        invoice_keywords = (
            "FACTURE", "INVOICE", "FACTURE N", "FACTURE N°", "INVOICE N",
            "DATE DE FACTURATION", "DATE D'ÉCHÉANCE", "DATE D'ECHEANCE",
            "FOURNI PAR", "PROVIDED BY", "FACTURÉ À", "BILLED TO",
            "PRIX HT", "PRIX TTC", "TVA", "VAT", "TOTAL HT", "TOTAL TTC"
        )
        if any(kw in text_upper for kw in invoice_keywords):
            return "invoice"
        
        # Estimate / quote indicators
        if any(kw in text_upper for kw in ("DEVIS", "QUOTE", "ESTIMATE", "ESTIMATION")):
            return "estimate"
        
        return "unknown"

    def _parse_invoice_text(self, text: str) -> Dict[str, Any]:
        """
        Comprehensive invoice parsing with all fields (quality-first).
        """
        # Detect document type first
        document_type = self._detect_document_type(text)
        
        shop_name = self._extract_shop_name(text)
        customer_name = self._extract_customer_name(text)
        date = self._extract_date(text) or ""
        invoice_number = self._extract_invoice_number(text)
        ticket_number = self._extract_ticket_number(text)
        iban = self._extract_iban(text)
        siret = self._extract_siret(text)
        vat_number = self._extract_vat_number(text)

        # Enhanced total extraction with more labels
        total_ttc = self._find_total(text, [
            "TOTAL TTC", "TTC", "NET A PAYER", "NET À PAYER", "TOTAL",
            "MONTANT TTC", "À PAYER", "A PAYER", "TOTAL GÉNÉRAL"
        ])
        total_ht = self._find_total(text, [
            "TOTAL HT", "HT", "SOUS-TOTAL", "SUBTOTAL", "MONTANT HT",
            "TOTAL HORS TAXE", "HORS TAXE"
        ])
        # Extract VAT amount (not rate) - look for "TVA 20%" followed by amount, or "TVA" with amount
        vat = self._find_vat_amount(text)

        items = self._parse_items(text)

        # Heuristics / corrections
        # 1) If VAT missing but totals present, compute it.
        if (vat is None or vat == 0) and total_ttc is not None and total_ht is not None:
            vat = max(0.0, float(total_ttc) - float(total_ht))

        # 2) If TTC < HT, they are likely swapped or OCR mis-read; swap if it makes VAT consistent.
        if total_ttc is not None and total_ht is not None and total_ttc < total_ht:
            ttc, ht = float(total_ttc), float(total_ht)
            vat_val = float(vat or 0)
            diff_curr = abs((ttc - ht) - vat_val)
            diff_swap = abs((ht - ttc) - vat_val)
            if diff_swap < diff_curr:
                total_ttc, total_ht = total_ht, total_ttc

        return {
            "document_type": document_type,
            "shop_name": shop_name,
            "customer_name": customer_name,
            "date": date,
            "invoice_number": invoice_number,
            "ticket_number": ticket_number,
            "iban": iban,
            "siret": siret,
            "vat_number": vat_number,
            "total_ht": total_ht if total_ht is not None else 0,
            "total_ttc": total_ttc if total_ttc is not None else 0,
            "vat": vat if vat is not None else 0,
            "items": items,
        }

