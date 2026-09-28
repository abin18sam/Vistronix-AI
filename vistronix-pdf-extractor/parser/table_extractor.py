"""
table_extractor.py
=====================
Extracts tables from a PDF using Camelot and appends "table" elements to
the corresponding page's element list.

Camelot works on the "lattice" (bordered tables) and "stream"
(whitespace-separated tables) strategies. We try "lattice" first since it
is more accurate for well-formatted tables, and fall back to "stream" if
lattice finds nothing on a page.

Each table element looks like:

    {
        "type": "table",
        "headers": ["Name", "Age", "City"],
        "rows": [["Alice", "30", "NY"], ["Bob", "25", "LA"]]
    }

Note: Camelot requires Ghostscript to be installed on the system
(see README.md for installation instructions).
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger("vistronix.table_extractor")

try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    # Camelot (and its Ghostscript dependency) is optional. If it's not
    # installed, we simply skip table extraction rather than crashing
    # the whole pipeline.
    CAMELOT_AVAILABLE = False
    logger.warning(
        "Camelot is not installed. Table extraction will be skipped. "
        "Install with: pip install camelot-py[cv] (and Ghostscript)."
    )


def _camelot_table_to_dict(table) -> Dict[str, Any]:
    """Convert a camelot Table object's DataFrame into our headers/rows format."""
    df = table.df

    if df.empty:
        return {"headers": [], "rows": []}

    headers = [str(cell).strip() for cell in df.iloc[0].tolist()]
    rows = [
        [str(cell).strip() for cell in row.tolist()]
        for _, row in df.iloc[1:].iterrows()
    ]
    return {"headers": headers, "rows": rows}


def extract_tables(pdf_path: str, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extract tables from the PDF and merge them into the existing `pages`
    structure.

    Args:
        pdf_path: Path to the source PDF.
        pages: The list of page dicts already containing text/image elements.

    Returns:
        The same `pages` list, with "table" elements appended where found.
    """
    if not CAMELOT_AVAILABLE:
        return pages

    pages_by_number = {p["page_number"]: p for p in pages}

    try:
        # "all" tells Camelot to scan every page of the PDF.
        tables = camelot.read_pdf(pdf_path, pages="all", flavor="lattice")

        if len(tables) == 0:
            # Fall back to stream mode, which works better for tables
            # without visible borders/lines.
            tables = camelot.read_pdf(pdf_path, pages="all", flavor="stream")

    except Exception:
        # Camelot can throw various errors (e.g. missing Ghostscript,
        # malformed PDFs, no tables found in some edge cases).
        logger.exception("Table extraction failed for %s", pdf_path)
        return pages

    for table in tables:
        try:
            page_number = int(table.page)
            table_dict = _camelot_table_to_dict(table)

            if not table_dict["headers"] and not table_dict["rows"]:
                continue

            if page_number not in pages_by_number:
                pages_by_number[page_number] = {"page_number": page_number, "elements": []}
                pages.append(pages_by_number[page_number])

            pages_by_number[page_number]["elements"].append(
                {
                    "type": "table",
                    "headers": table_dict["headers"],
                    "rows": table_dict["rows"],
                }
            )
            logger.info("Extracted table on page %d", page_number)

        except Exception:
            logger.exception("Failed to convert a detected table to JSON")

    return pages
