import sys
from pathlib import Path

from app.config import settings
from app.schemas import ParsedDocument


EXTRACTOR_ROOT = Path(__file__).resolve().parents[1] / "vistronix-pdf-extractor"
if str(EXTRACTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(EXTRACTOR_ROOT))

from parser.digital_parser import parse_digital_page  # noqa: E402,F401
from parser.equation_detector import tag_equations  # noqa: E402
from parser.image_extractor import extract_images  # noqa: E402
from parser.json_builder import build_final_json  # noqa: E402
from parser.mixed_parser import parse_pdf_per_page  # noqa: E402
from parser.table_extractor import extract_tables  # noqa: E402


def parse_to_storage(pdf_path: Path, document_directory: Path, original_filename: str) -> Path:
    """Run Stage 1 inside one document directory and validate before writing JSON."""
    images_dir = document_directory / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    pages, pdf_type = parse_pdf_per_page(str(pdf_path))
    pages = extract_images(str(pdf_path), pages, str(images_dir))
    if settings.enable_table_extraction:
        pages = extract_tables(str(pdf_path), pages)
    pages = tag_equations(pages)

    parsed = ParsedDocument.model_validate(
        build_final_json(document_name=original_filename, pdf_type=pdf_type, pages=pages)
    )
    output_path = document_directory / "parsed_document.json"
    output_path.write_text(parsed.model_dump_json(indent=2), encoding="utf-8")
    return output_path


def validate_pdf(pdf_path: Path) -> None:
    import fitz

    with fitz.open(pdf_path) as document:
        if document.page_count < 1:
            raise ValueError("PDF contains no pages")
