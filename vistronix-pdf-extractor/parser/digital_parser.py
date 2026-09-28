"""
digital_parser.py
===================
Extracts structured text content from a *digital* (text-selectable) PDF.

For every page we use pdfplumber to pull out individual "words" grouped
into lines, along with font size information, and we use that to:

    - Reconstruct paragraph-like text blocks (grouping lines by their
      vertical proximity into blocks).
    - Record the bounding box (x1, y1, x2, y2) of every block.
    - Record the dominant font size of every block.
    - Decide whether a block looks like a "heading" or plain "text",
      based on font size and boldness (see the heading heuristic below).

Output shape (per page) - a list of "elements", each looking like:

    {
        "type": "heading" | "text",
        "text": "...",
        "font": 18.0,
        "bbox": [x1, y1, x2, y2],
        "page_number": 1
    }

These elements are later merged with images/tables/equations by main.py.
"""

import logging
from statistics import median
from typing import Any, Dict, List

import pdfplumber

logger = logging.getLogger("vistronix.digital_parser")

# If a text block's font size is this many points larger than the page's
# median (body) font size, we treat it as a heading.
HEADING_FONT_DELTA = 2.0

# Vertical gap (in PDF points) beyond which we consider two lines to belong
# to different paragraph blocks rather than the same one.
LINE_GROUPING_GAP = 5.0


def _extract_lines_with_metadata(page) -> List[Dict[str, Any]]:
    """
    Use pdfplumber's word-level extraction to reconstruct lines, each with
    its text, average font size, boldness guess, and bounding box.
    """
    words = page.extract_words(
        extra_attrs=["size", "fontname"],
        use_text_flow=False,
        keep_blank_chars=False,
    )

    if not words:
        return []

    # Group words into lines using their "top" (vertical position) value.
    # Words on the same visual line will have very similar "top" values.
    lines: List[Dict[str, Any]] = []
    current_line_words: List[Dict[str, Any]] = []
    current_top = None
    line_tolerance = 3.0  # points

    for word in sorted(words, key=lambda w: (round(w["top"], 1), w["x0"])):
        if current_top is None or abs(word["top"] - current_top) <= line_tolerance:
            current_line_words.append(word)
            current_top = word["top"] if current_top is None else current_top
        else:
            lines.append(_build_line(current_line_words))
            current_line_words = [word]
            current_top = word["top"]

    if current_line_words:
        lines.append(_build_line(current_line_words))

    return lines


def _build_line(words: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Combine a list of word dicts (on the same visual line) into one line dict."""
    text = " ".join(w["text"] for w in words)
    x0 = min(w["x0"] for w in words)
    x1 = max(w["x1"] for w in words)
    top = min(w["top"] for w in words)
    bottom = max(w["bottom"] for w in words)
    sizes = [w.get("size", 0) for w in words if w.get("size")]
    avg_size = sum(sizes) / len(sizes) if sizes else 0
    fontnames = [w.get("fontname", "") for w in words]
    is_bold = any("bold" in fn.lower() for fn in fontnames)

    return {
        "text": text,
        "bbox": [round(x0, 2), round(top, 2), round(x1, 2), round(bottom, 2)],
        "font_size": round(avg_size, 2),
        "is_bold": is_bold,
    }


def _group_lines_into_blocks(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge consecutive lines into paragraph blocks when they are close
    together vertically and share a similar font size. A large vertical
    gap (or a big change in font size) starts a new block.
    """
    if not lines:
        return []

    blocks: List[Dict[str, Any]] = []
    current_block_lines = [lines[0]]

    for prev_line, line in zip(lines, lines[1:]):
        vertical_gap = line["bbox"][1] - prev_line["bbox"][3]  # top - prev.bottom
        font_changed = abs(line["font_size"] - prev_line["font_size"]) > 1.0

        if vertical_gap > LINE_GROUPING_GAP or font_changed:
            blocks.append(_finalize_block(current_block_lines))
            current_block_lines = [line]
        else:
            current_block_lines.append(line)

    blocks.append(_finalize_block(current_block_lines))
    return blocks


def _finalize_block(block_lines: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Combine lines belonging to one block into a single text element dict."""
    text = " ".join(l["text"] for l in block_lines)
    x0 = min(l["bbox"][0] for l in block_lines)
    y0 = min(l["bbox"][1] for l in block_lines)
    x1 = max(l["bbox"][2] for l in block_lines)
    y1 = max(l["bbox"][3] for l in block_lines)
    font_size = median(l["font_size"] for l in block_lines) if block_lines else 0
    is_bold = any(l["is_bold"] for l in block_lines)

    return {
        "text": text,
        "bbox": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
        "font_size": round(font_size, 2),
        "is_bold": is_bold,
    }


def _classify_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Decide heading vs text for each block using the page's median font
    size as the "body text" baseline.
    """
    if not blocks:
        return []

    body_font_size = median(b["font_size"] for b in blocks if b["font_size"] > 0) or 12

    elements = []
    for block in blocks:
        is_heading = (
            block["font_size"] >= body_font_size + HEADING_FONT_DELTA
            or (block["is_bold"] and block["font_size"] >= body_font_size)
        )
        elements.append(
            {
                "type": "heading" if is_heading else "text",
                "text": block["text"].strip(),
                "font": block["font_size"],
                "bbox": block["bbox"],
            }
        )
    return elements


def parse_digital_page(page: "pdfplumber.page.Page", page_number: int) -> Dict[str, Any]:
    """
    Parse a SINGLE digital page (a pdfplumber Page object) into our
    standard page dict shape:

        {
            "page_number": 1,
            "elements": [ {type, text, font, bbox}, ... ]
        }

    This is the building block used both by parse_digital_pdf() (for
    all-digital documents) and by the mixed-document orchestrator in
    main.py, which routes individual pages of a MIXED document (some
    digital, some scanned) to the right parser per page.
    """
    try:
        lines = _extract_lines_with_metadata(page)
        blocks = _group_lines_into_blocks(lines)
        elements = _classify_blocks(blocks)
        # Drop empty text blocks (can happen with stray whitespace).
        elements = [e for e in elements if e["text"]]
    except Exception:
        logger.exception("Failed parsing page %d", page_number)
        elements = []

    logger.info("Page %d: extracted %d text element(s)", page_number, len(elements))
    return {"page_number": page_number, "elements": elements}


def parse_digital_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Parse an ALL-digital PDF page by page, returning a list of page dicts:

        [
            {
                "page_number": 1,
                "elements": [ {type, text, font, bbox}, ... ]
            },
            ...
        ]

    Elements are ordered top-to-bottom (left-to-right within a line) since
    that is the natural order in which pdfplumber's words are extracted
    and grouped above.

    Note: for MIXED documents (some pages digital, some scanned), use
    parse_digital_page() directly per-page instead - see main.py's
    per-page orchestration.
    """
    pages_output: List[Dict[str, Any]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages):
            page_number = page_index + 1
            pages_output.append(parse_digital_page(page, page_number))

    return pages_output
