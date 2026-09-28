"""
pdf_detector.py
================
Detects whether each PAGE of a PDF is "digital" (has selectable text) or
"scanned" (image-only, needs OCR).

This used to only sample the first 3 pages and label the *whole document*
with one type. That breaks on mixed documents - e.g. a typed cover page
followed by scanned handwritten notes, or a digital report with a few
scanned signature pages stapled in. This version instead classifies
EVERY page independently, so mixed documents route each page to the
correct parser (digital_parser vs scanned_parser).

Heuristic used per page:
    - Extract the raw text from that page using PyMuPDF (fitz).
    - Count "meaningful" characters (letters/digits).
    - If that count is above a threshold, classify the page as "digital".
      Otherwise "scanned".

This is intentionally simple (as requested) but works well in practice:
scanned pages almost always return empty or near-empty text from
fitz's get_text(), while digital pages return real sentences.
"""

import logging
from typing import Dict, List

import fitz  # PyMuPDF

logger = logging.getLogger("vistronix.pdf_detector")

# Minimum number of alphanumeric characters we need to see on a SINGLE
# page before we trust that page has real embedded text rather than
# just stray metadata/whitespace.
PAGE_MEANINGFUL_CHAR_THRESHOLD = 20


def detect_page_type(page: "fitz.Page") -> str:
    """
    Detect whether a single PyMuPDF page is digital or scanned.

    Args:
        page: An already-loaded fitz.Page object.

    Returns:
        "digital" if the page appears to contain selectable text,
        "scanned" if it appears to be image-only (or unreadable text).
    """
    raw_text = page.get_text("text") or ""

    # Count only alphanumeric characters - this avoids being fooled by
    # whitespace, page numbers, or stray punctuation that some scanned
    # pages still embed as metadata text.
    meaningful_chars = sum(ch.isalnum() for ch in raw_text)

    page_type = (
        "digital" if meaningful_chars >= PAGE_MEANINGFUL_CHAR_THRESHOLD else "scanned"
    )
    logger.debug(
        "Page detection: %d meaningful chars -> %s", meaningful_chars, page_type
    )
    return page_type


def detect_page_types(pdf_path: str) -> List[Dict[str, str]]:
    """
    Detect the type of EVERY page in a PDF individually.

    Args:
        pdf_path: Path to the PDF file on disk.

    Returns:
        A list like:
            [
                {"page_number": 1, "pdf_type": "digital"},
                {"page_number": 2, "pdf_type": "scanned"},
                ...
            ]
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        logger.error("Could not open PDF for type detection: %s", exc)
        # If we can't even open it, we can't know per-page types - return
        # an empty list and let the caller default every page to "scanned"
        # (the OCR pipeline rasterizes pages, so it gets a fair shot).
        return []

    try:
        results = []
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            page_type = detect_page_type(page)
            results.append({"page_number": page_index + 1, "pdf_type": page_type})

        digital_count = sum(1 for r in results if r["pdf_type"] == "digital")
        scanned_count = len(results) - digital_count
        logger.info(
            "Per-page detection complete: %d digital page(s), %d scanned page(s)",
            digital_count,
            scanned_count,
        )
        return results

    finally:
        doc.close()


def detect_pdf_type(pdf_path: str) -> str:
    """
    Convenience wrapper that returns ONE overall label for the whole
    document, derived from the per-page results:

        - "digital"  -> every page detected as digital
        - "scanned"  -> every page detected as scanned
        - "mixed"    -> some pages digital, some scanned

    Kept for callers that just want a simple top-level summary (this is
    what gets stored as the "pdf_type" field in parsed_document.json).
    """
    page_types = detect_page_types(pdf_path)

    if not page_types:
        return "scanned"

    distinct_types = {p["pdf_type"] for p in page_types}

    if len(distinct_types) == 1:
        return distinct_types.pop()
    return "mixed"
