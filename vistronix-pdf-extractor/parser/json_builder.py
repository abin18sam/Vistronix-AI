"""
json_builder.py
==================
Assembles the final structured JSON document and saves it to disk.

Final shape:

    {
        "document_name": "sample.pdf",
        "pdf_type": "digital",
        "pages": [
            {
                "page_number": 1,
                "elements": [ {...}, {...} ]
            },
            ...
        ]
    }

Element ordering within a page:
    Text/heading/equation elements are already in top-to-bottom,
    left-to-right order (produced by digital_parser/scanned_parser).
    Image and table elements are appended after them by
    image_extractor.py / table_extractor.py. To respect the "preserve
    layout order" requirement as closely as possible without a full
    layout-analysis engine, we do a final sort pass that orders all
    elements within a page by their bbox's top (y0) coordinate where a
    bbox is available, keeping elements without a bbox (e.g. some OCR
    edge cases) in their original relative position.
"""

import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger("vistronix.json_builder")


def _sort_key(element: Dict[str, Any], fallback_index: int):
    """
    Sort elements by vertical position (top y-coordinate of their bbox).
    Elements without a bbox (e.g. a table with no bbox, or an image with
    bbox=None) keep their original insertion order via fallback_index.
    """
    bbox = element.get("bbox")
    if bbox and isinstance(bbox, list) and len(bbox) == 4:
        return (bbox[1], bbox[0])
    return (fallback_index, 0)


def _order_page_elements(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reorder a page's elements top-to-bottom / left-to-right using bbox data."""
    indexed = list(enumerate(elements))
    indexed.sort(key=lambda pair: _sort_key(pair[1], pair[0]))
    return [element for _, element in indexed]


def build_final_json(
    document_name: str,
    pdf_type: str,
    pages: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build the final JSON-serializable dict describing the parsed document.

    Args:
        document_name: Original uploaded file name (e.g. "sample.pdf").
        pdf_type: "digital" or "scanned".
        pages: List of page dicts with "page_number" and "elements".

    Returns:
        A dict matching the required parsed_document.json schema.
    """
    # Sort pages by page_number just in case they were appended out of order.
    sorted_pages = sorted(pages, key=lambda p: p["page_number"])

    final_pages = []
    for page in sorted_pages:
        ordered_elements = _order_page_elements(page.get("elements", []))
        page_dict = {
            "page_number": page["page_number"],
            "elements": ordered_elements,
        }
        # If per-page detection tagged this page (digital/scanned), keep
        # that on the page so mixed documents are transparent about which
        # parser handled which page.
        if "pdf_type" in page:
            page_dict["pdf_type"] = page["pdf_type"]
        final_pages.append(page_dict)

    result = {
        "document_name": document_name,
        "pdf_type": pdf_type,
        "pages": final_pages,
    }

    logger.info(
        "Built final JSON for '%s': %d page(s), pdf_type=%s",
        document_name,
        len(final_pages),
        pdf_type,
    )
    return result


def save_json(data: Dict[str, Any], output_path: str) -> None:
    """Save the given dict as pretty-printed JSON to output_path."""
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Saved JSON output to %s", output_path)
    except Exception:
        logger.exception("Failed to save JSON output to %s", output_path)
        raise
