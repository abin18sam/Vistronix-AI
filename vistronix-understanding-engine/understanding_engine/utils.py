"""
utils.py
========
Helper functions that pull specific pieces of content (plain text,
equations, images, tables, headings) out of the raw `parsed_document.json`
structure produced by the PDF Parser module.

WHY THIS FILE EXISTS (beginner explanation):
`parsed_document.json` mixes many element types together (heading, text,
equation, image, table) inside a nested "pages -> elements" structure.
Most of our understanding modules only care about ONE type of element
(e.g. equation_understanding.py only needs equations). Rather than making
every module re-write the same loop to dig through pages/elements, we
write that loop ONCE here.
"""

from typing import Any, Dict, List
from understanding_engine.config import get_logger

logger = get_logger(__name__)


def load_parsed_document(path: str) -> Dict[str, Any]:
    """Reads and returns the parsed_document.json file as a Python dict."""
    import json

    logger.info(f"Loading parsed document from: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"Loaded document '{data.get('document_name')}' with {len(data.get('pages', []))} pages")
    return data


def get_full_text(document: Dict[str, Any]) -> str:
    """
    Concatenates all heading + text elements across every page into one
    plain-text blob, in reading order. This is what we feed to the LLM
    for high-level tasks like classification, summarization, and topic
    extraction, where page-by-page detail doesn't matter.
    """
    chunks: List[str] = []
    for page in document.get("pages", []):
        page_num = page.get("page_number")
        for element in page.get("elements", []):
            el_type = element.get("type")
            if el_type in ("heading", "text"):
                text = element.get("text", "").strip()
                if text:
                    chunks.append(f"[Page {page_num}] {text}")
    return "\n".join(chunks)


def get_headings(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Returns every heading element with its page number, in document order."""
    headings = []
    for page in document.get("pages", []):
        page_num = page.get("page_number")
        for element in page.get("elements", []):
            if element.get("type") == "heading":
                headings.append({"page_number": page_num, "text": element.get("text", "")})
    return headings


def get_text_paragraphs(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Returns every plain 'text' element (not headings) with its page number."""
    paragraphs = []
    for page in document.get("pages", []):
        page_num = page.get("page_number")
        for element in page.get("elements", []):
            if element.get("type") == "text":
                paragraphs.append({"page_number": page_num, "text": element.get("text", "")})
    return paragraphs


def get_equations(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Returns every equation element with its page number."""
    equations = []
    for page in document.get("pages", []):
        page_num = page.get("page_number")
        for element in page.get("elements", []):
            if element.get("type") == "equation":
                equations.append({"page_number": page_num, "text": element.get("text", "")})
    return equations


def get_images(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Returns every image element with its page number and filename."""
    images = []
    for page in document.get("pages", []):
        page_num = page.get("page_number")
        for element in page.get("elements", []):
            if element.get("type") == "image":
                images.append({"page_number": page_num, "file": element.get("file", "")})
    return images


def get_tables(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Returns every table element with its page number, headers, and rows."""
    tables = []
    for page in document.get("pages", []):
        page_num = page.get("page_number")
        for element in page.get("elements", []):
            if element.get("type") == "table":
                tables.append(
                    {
                        "page_number": page_num,
                        "headers": element.get("headers", []),
                        "rows": element.get("rows", []),
                    }
                )
    return tables


def find_nearby_context(document: Dict[str, Any], page_number: int, max_chars: int = 600) -> str:
    """
    Given a page number, returns the surrounding heading + text elements on
    that page. Useful for giving the LLM local context when explaining a
    single equation, image, or table (e.g. "what section is this equation
    part of?") without needing to send the entire document every time.
    """
    context_parts = []
    for page in document.get("pages", []):
        if page.get("page_number") == page_number:
            for element in page.get("elements", []):
                if element.get("type") in ("heading", "text"):
                    context_parts.append(element.get("text", ""))
    joined = " ".join(context_parts)
    return joined[:max_chars]
