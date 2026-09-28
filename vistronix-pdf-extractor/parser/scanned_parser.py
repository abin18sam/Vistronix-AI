"""
scanned_parser.py
====================
Extracts text (with bounding boxes) from a *scanned* (image-based) PDF
using Tesseract OCR.

Pipeline for each page:
    1. Render the PDF page to a high-resolution image using PyMuPDF
       (avoids needing poppler/pdf2image as a hard dependency, though
       pdf2image is listed in requirements.txt as an alternative).
    2. Run pytesseract's `image_to_data` on that image, which returns
       OCR'd words *along with* their bounding boxes and confidence.
    3. Group OCR'd words into lines, then lines into paragraph blocks
       (re-using the same grouping approach as the digital parser, but
       working in pixel coordinates instead of PDF points).
    4. Classify each block as "heading" or "text" using a simple relative
       block-height heuristic (OCR does not reliably expose font size,
       so we approximate using the pixel height of the text bounding box
       as a stand-in for "font size").

Output shape matches the digital parser's output so both can be merged
identically by main.py / json_builder.py.
"""

import logging
import os
from statistics import median
from typing import Any, Dict, List

import fitz  # PyMuPDF, used to rasterize pages
import pytesseract
from PIL import Image

logger = logging.getLogger("vistronix.scanned_parser")

# Make sure pytesseract can find the Tesseract binary on Windows installs.
# This avoids failures when the executable is installed but not on PATH.
_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(_TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_PATH

# Render pages at this zoom factor for better OCR accuracy.
# zoom=2 roughly corresponds to ~144 DPI (72 * 2); higher = sharper but slower.
RENDER_ZOOM = 2.0

# Minimum OCR confidence (0-100) to keep a word. Low-confidence noise is discarded.
MIN_OCR_CONFIDENCE = 40

# Vertical gap (in pixels) beyond which lines are split into separate blocks.
LINE_GROUPING_GAP_PX = 12

# A block is treated as a "heading" if its average line-height is at least
# this many times taller than the page's median line-height.
HEADING_HEIGHT_RATIO = 1.3


def _render_page_to_image(page: "fitz.Page") -> Image.Image:
    """Render a single PDF page into a PIL Image at RENDER_ZOOM resolution."""
    matrix = fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM)
    pix = page.get_pixmap(matrix=matrix)
    mode = "RGB" if pix.n < 4 else "RGBA"
    image = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
    if mode == "RGBA":
        image = image.convert("RGB")
    return image


def _ocr_page_to_lines(image: Image.Image) -> List[Dict[str, Any]]:
    """
    Run Tesseract OCR on a page image and group the resulting words into
    visual lines using Tesseract's own line/block/paragraph indices.
    """
    ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

    # Group words by (block_num, par_num, line_num) - Tesseract already
    # tells us which line each word belongs to, which is more reliable
    # than re-deriving it from raw coordinates.
    line_groups: Dict[tuple, List[int]] = {}
    n_boxes = len(ocr_data["text"])
    for i in range(n_boxes):
        word_text = ocr_data["text"][i].strip()
        try:
            confidence = float(ocr_data["conf"][i])
        except (ValueError, TypeError):
            confidence = -1

        if not word_text or confidence < MIN_OCR_CONFIDENCE:
            continue

        key = (ocr_data["block_num"][i], ocr_data["par_num"][i], ocr_data["line_num"][i])
        line_groups.setdefault(key, []).append(i)

    lines = []
    # Sort by block/paragraph/line number to preserve top-to-bottom reading order.
    for key in sorted(line_groups.keys()):
        indices = line_groups[key]
        words_text = [ocr_data["text"][i] for i in indices]
        xs0 = [ocr_data["left"][i] for i in indices]
        ys0 = [ocr_data["top"][i] for i in indices]
        xs1 = [ocr_data["left"][i] + ocr_data["width"][i] for i in indices]
        ys1 = [ocr_data["top"][i] + ocr_data["height"][i] for i in indices]
        heights = [ocr_data["height"][i] for i in indices]

        lines.append(
            {
                "text": " ".join(words_text),
                "bbox": [min(xs0), min(ys0), max(xs1), max(ys1)],
                "height": median(heights) if heights else 0,
            }
        )

    return lines


def _group_lines_into_blocks(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge consecutive OCR lines into paragraph blocks based on vertical gap."""
    if not lines:
        return []

    blocks = []
    current = [lines[0]]

    for prev_line, line in zip(lines, lines[1:]):
        gap = line["bbox"][1] - prev_line["bbox"][3]
        if gap > LINE_GROUPING_GAP_PX:
            blocks.append(_finalize_block(current))
            current = [line]
        else:
            current.append(line)

    blocks.append(_finalize_block(current))
    return blocks


def _finalize_block(block_lines: List[Dict[str, Any]]) -> Dict[str, Any]:
    text = " ".join(l["text"] for l in block_lines)
    x0 = min(l["bbox"][0] for l in block_lines)
    y0 = min(l["bbox"][1] for l in block_lines)
    x1 = max(l["bbox"][2] for l in block_lines)
    y1 = max(l["bbox"][3] for l in block_lines)
    avg_height = median(l["height"] for l in block_lines) if block_lines else 0

    return {
        "text": text,
        "bbox": [x0, y0, x1, y1],
        "height": avg_height,
    }


def _classify_blocks(blocks: List[Dict[str, Any]], zoom: float) -> List[Dict[str, Any]]:
    """
    Classify OCR blocks as heading/text using relative line height as a
    stand-in for font size (OCR doesn't give us real font metadata).
    The bbox is scaled back down by `zoom` so coordinates roughly match
    PDF point space, keeping output consistent with the digital parser.
    """
    if not blocks:
        return []

    body_height = median(b["height"] for b in blocks if b["height"] > 0) or 1

    elements = []
    for block in blocks:
        is_heading = block["height"] >= body_height * HEADING_HEIGHT_RATIO
        # Approximate a "font size" in points from the pixel height and zoom.
        approx_font_size = round((block["height"] / zoom) * 0.75, 2)  # px -> pt approx
        scaled_bbox = [round(coord / zoom, 2) for coord in block["bbox"]]

        elements.append(
            {
                "type": "heading" if is_heading else "text",
                "text": block["text"].strip(),
                "font": approx_font_size,
                "bbox": scaled_bbox,
            }
        )
    return elements


def parse_scanned_page(page: "fitz.Page", page_number: int) -> Dict[str, Any]:
    """
    Parse a SINGLE scanned page (a fitz.Page object) using OCR, returning
    our standard page dict shape:

        {
            "page_number": 1,
            "elements": [ {type, text, font, bbox}, ... ]
        }

    This is the building block used both by parse_scanned_pdf() (for
    all-scanned documents) and by the mixed-document orchestrator in
    main.py, which routes individual pages of a MIXED document (some
    digital, some scanned) to the right parser per page.

    Requires Tesseract OCR to be installed on the host system (see
    README.md for installation instructions on Windows/Linux/macOS).
    """
    try:
        image = _render_page_to_image(page)
        lines = _ocr_page_to_lines(image)
        blocks = _group_lines_into_blocks(lines)
        elements = _classify_blocks(blocks, zoom=RENDER_ZOOM)
        elements = [e for e in elements if e["text"]]
    except pytesseract.TesseractNotFoundError:
        logger.error(
            "Tesseract is not installed or not on PATH. "
            "See README.md for installation instructions."
        )
        raise
    except Exception:
        logger.exception("OCR failed on page %d", page_number)
        elements = []

    logger.info(
        "Page %d (OCR): extracted %d text element(s)", page_number, len(elements)
    )
    return {"page_number": page_number, "elements": elements}


def parse_scanned_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Parse an ALL-scanned PDF page by page using OCR, returning the same
    page/element structure produced by parse_digital_pdf().

    Note: for MIXED documents (some pages digital, some scanned), use
    parse_scanned_page() directly per-page instead - see main.py's
    per-page orchestration.
    """
    pages_output: List[Dict[str, Any]] = []

    try:
        doc = fitz.open(pdf_path)
    except Exception:
        logger.exception("Could not open scanned PDF: %s", pdf_path)
        raise

    try:
        for page_index in range(doc.page_count):
            page_number = page_index + 1
            page = doc.load_page(page_index)
            pages_output.append(parse_scanned_page(page, page_number))
    finally:
        doc.close()

    return pages_output
