"""
mixed_parser.py
==================
Orchestrates PAGE-LEVEL parsing so a single PDF can contain a mix of
digital pages and scanned pages (e.g. a typed cover page followed by
scanned handwritten notes, or a digital report with a few scanned
signature/annexure pages stapled in).

Previously, the whole document was classified once ("digital" or
"scanned") and entirely routed to one parser. That silently mis-parsed
any page that didn't match the document's dominant type. This module
instead:

    1. Runs pdf_detector.detect_page_types() to classify EVERY page.
    2. For each page, calls parse_digital_page() or parse_scanned_page()
       individually, based on that page's own detected type.
    3. Tags each page dict with its own "pdf_type" so the final JSON is
       transparent about which pages were digital vs scanned.
    4. Computes one overall document-level pdf_type:
           "digital" -> every page was digital
           "scanned" -> every page was scanned
           "mixed"   -> some of each
"""

import logging
from typing import Any, Dict, List, Tuple

import fitz  # PyMuPDF
import pdfplumber

from parser.pdf_detector import detect_page_types
from parser.digital_parser import parse_digital_page
from parser.scanned_parser import parse_scanned_page

logger = logging.getLogger("vistronix.mixed_parser")


def parse_pdf_per_page(pdf_path: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Parse every page of a PDF using the correct parser for that specific
    page, supporting documents that mix digital and scanned pages.

    Args:
        pdf_path: Path to the PDF file on disk.

    Returns:
        A tuple of (pages, overall_pdf_type):
            pages: list of page dicts, each shaped like
                {
                    "page_number": 1,
                    "pdf_type": "digital" | "scanned",
                    "elements": [ ... ]
                }
            overall_pdf_type: "digital" | "scanned" | "mixed"
    """
    page_type_info = detect_page_types(pdf_path)
    types_by_page = {entry["page_number"]: entry["pdf_type"] for entry in page_type_info}

    pages_output: List[Dict[str, Any]] = []

    # Open both readers once and reuse them for every page, rather than
    # re-opening the file per page (which would be slow for large PDFs).
    with pdfplumber.open(pdf_path) as plumber_doc:
        fitz_doc = fitz.open(pdf_path)
        try:
            total_pages = fitz_doc.page_count

            for page_index in range(total_pages):
                page_number = page_index + 1
                # Default to "scanned" if detection somehow didn't cover
                # this page (e.g. detector failed to open the file) - the
                # OCR path can still attempt to rasterize + read it.
                page_type = types_by_page.get(page_number, "scanned")

                if page_type == "digital":
                    plumber_page = plumber_doc.pages[page_index]
                    page_result = parse_digital_page(plumber_page, page_number)
                else:
                    fitz_page = fitz_doc.load_page(page_index)
                    page_result = parse_scanned_page(fitz_page, page_number)

                # Tag the page with which parser actually handled it, so
                # the final JSON shows per-page provenance.
                page_result["pdf_type"] = page_type
                pages_output.append(page_result)

        finally:
            fitz_doc.close()

    distinct_types = {p["pdf_type"] for p in pages_output}
    if not distinct_types:
        overall_pdf_type = "scanned"
    elif len(distinct_types) == 1:
        overall_pdf_type = distinct_types.pop()
    else:
        overall_pdf_type = "mixed"

    logger.info(
        "Parsed %d page(s): overall pdf_type=%s (per-page types: %s)",
        len(pages_output),
        overall_pdf_type,
        [p["pdf_type"] for p in pages_output],
    )

    return pages_output, overall_pdf_type
