import hashlib
import re

from app.schemas import ParsedDocument
from app.understanding.schemas import Chunk


def build_chunks(document: ParsedDocument, max_chars: int = 6000, overlap_chars: int = 500) -> list[Chunk]:
    """Group page content at page/heading boundaries with bounded overlap."""
    chunks: list[Chunk] = []
    current_text: list[str] = []
    current_pages: list[int] = []
    current_heading: str | None = None

    def flush() -> None:
        nonlocal current_text, current_pages, current_heading
        text = "\n".join(current_text).strip()
        if text:
            chunk_id = "chunk-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            chunks.append(Chunk(chunk_id=chunk_id, page_numbers=sorted(set(current_pages)), text=text, heading=current_heading))
        current_text, current_pages, current_heading = [], [], None

    for page in document.pages:
        for element in page.elements:
            text = (element.text or "").strip()
            if not text:
                continue
            if element.type == "heading" and current_text:
                flush()
            if element.type == "heading":
                current_heading = text
            current_text.append(f"[Page {page.page_number}] {text}")
            current_pages.append(page.page_number)
            if len("\n".join(current_text)) >= max_chars:
                prior = "\n".join(current_text)[-overlap_chars:]
                flush()
                if prior:
                    current_text = [prior]
                    current_pages = [page.page_number]
    flush()
    return chunks


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())
