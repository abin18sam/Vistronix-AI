"""
image_extractor.py
=====================
Extracts embedded raster images from every page of a PDF using PyMuPDF,
saves them to disk (extracted_images/), and appends "image" elements to
the corresponding page's element list.

Each saved image is named: page{N}_img{K}.png
Each image element looks like:

    {
        "type": "image",
        "file": "page1_img1.png",
        "bbox": [x1, y1, x2, y2]   # or null if bbox could not be determined
    }
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

import fitz  # PyMuPDF

logger = logging.getLogger("vistronix.image_extractor")


def extract_images(
    pdf_path: str,
    pages: List[Dict[str, Any]],
    output_dir: str,
) -> List[Dict[str, Any]]:
    """
    Extract images from every page of the PDF and merge them into the
    existing `pages` structure (produced by digital_parser/scanned_parser).

    Args:
        pdf_path: Path to the source PDF.
        pages: The list of page dicts already containing text elements.
        output_dir: Directory where extracted images should be saved.

    Returns:
        The same `pages` list, with "image" elements appended to each
        page's "elements" list.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Build a quick lookup so we can append to the right page dict by number.
    pages_by_number = {p["page_number"]: p for p in pages}

    try:
        doc = fitz.open(pdf_path)
    except Exception:
        logger.exception("Could not open PDF for image extraction: %s", pdf_path)
        return pages

    try:
        for page_index in range(doc.page_count):
            page_number = page_index + 1
            page = doc.load_page(page_index)

            try:
                image_list = page.get_images(full=True)
            except Exception:
                logger.exception("Failed to list images on page %d", page_number)
                continue

            if not image_list:
                continue

            # Ensure this page exists in our pages structure (it always
            # should, since digital/scanned parser initializes every page).
            if page_number not in pages_by_number:
                pages_by_number[page_number] = {"page_number": page_number, "elements": []}
                pages.append(pages_by_number[page_number])

            for img_index, img in enumerate(image_list, start=1):
                xref = img[0]
                try:
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image.get("ext", "png")

                    file_name = f"page{page_number}_img{img_index}.{image_ext}"
                    file_path = output_path / file_name

                    with open(file_path, "wb") as f:
                        f.write(image_bytes)

                    # Try to find the image's bounding box on the page.
                    bbox = None
                    try:
                        rects = page.get_image_rects(xref)
                        if rects:
                            r = rects[0]
                            bbox = [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)]
                    except Exception:
                        bbox = None

                    pages_by_number[page_number]["elements"].append(
                        {
                            "type": "image",
                            "file": file_name,
                            "bbox": bbox,
                        }
                    )
                    logger.info(
                        "Extracted image %s (page %d)", file_name, page_number
                    )

                except Exception:
                    logger.exception(
                        "Failed to extract image xref=%s on page %d", xref, page_number
                    )

    finally:
        doc.close()

    return pages
