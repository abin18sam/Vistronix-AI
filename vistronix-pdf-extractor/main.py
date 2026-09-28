"""
VisTronix AI - PDF Extractor Engine
=====================================
main.py

This is the FastAPI application entrypoint. It exposes a single endpoint,
POST /upload-pdf, which:

    1. Accepts a PDF file upload from the user.
    2. Validates that the uploaded file is actually a PDF.
    3. Saves the file into the uploads/ directory.
    4. Detects whether EACH PAGE is "digital" (text-based) or "scanned"
       (image-based) - this is done per page, not once for the whole
       file, so mixed documents (e.g. a typed cover page followed by
       scanned notes) are handled correctly.
    5. Routes each page individually to the correct parser (digital_parser
       or scanned_parser) based on that page's own detected type.
    6. Extracts images and tables from the PDF.
    7. Runs a simple equation detector over the extracted text blocks.
    8. Builds the final structured JSON and saves it as output/parsed_document.json.
    9. Returns the JSON back to the caller as the API response.

Run the server with:
    uvicorn main:app --reload

Then test with:
    curl -X POST "http://127.0.0.1:8000/upload-pdf" -F "file=@sample.pdf"
"""

import logging
import shutil
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from parser.mixed_parser import parse_pdf_per_page
from parser.image_extractor import extract_images
from parser.table_extractor import extract_tables
from parser.equation_detector import tag_equations
from parser.json_builder import build_final_json, save_json

# ----------------------------------------------------------------------------
# Logging setup
# ----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("vistronix.main")

# ----------------------------------------------------------------------------
# Directory setup
# ----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
IMAGE_DIR = BASE_DIR / "extracted_images"
OUTPUT_DIR = BASE_DIR / "output"

for directory in (UPLOAD_DIR, IMAGE_DIR, OUTPUT_DIR):
    directory.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------------
# FastAPI app
# ----------------------------------------------------------------------------
app = FastAPI(
    title="VisTronix AI - PDF Extractor Engine",
    description="Detects digital vs scanned PDFs and extracts structured content "
                 "(text, headings, images, tables, equations) into JSON.",
    version="1.0.0",
)


@app.get("/")
def root():
    """Simple health-check endpoint."""
    return {"status": "ok", "service": "VisTronix PDF Extractor"}


@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload a PDF, parse it, and return structured JSON.

    Steps:
        1. Validate the uploaded file is a PDF (by extension + content-type).
        2. Save it to uploads/.
        3. Detect digital vs scanned.
        4. Extract text blocks (digital or OCR).
        5. Extract images.
        6. Extract tables.
        7. Tag equation-like text.
        8. Assemble everything into parsed_document.json.
    """

    # --- 1. Validate file type ---
    if file.content_type != "application/pdf" or not file.filename.lower().endswith(".pdf"):
        logger.warning("Rejected upload: %s (content_type=%s)", file.filename, file.content_type)
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # --- 2. Save uploaded file ---
    saved_path = UPLOAD_DIR / file.filename
    try:
        with saved_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info("Saved uploaded file to %s", saved_path)
    except Exception as exc:
        logger.exception("Failed to save uploaded file")
        raise HTTPException(status_code=500, detail=f"Could not save file: {exc}") from exc
    finally:
        file.file.close()

    try:
        # --- 3 & 4. Detect type PER PAGE and extract text blocks accordingly ---
        # This handles mixed documents (some pages digital, some scanned)
        # by routing each individual page to the correct parser, rather
        # than guessing one type for the whole file.
        pages, pdf_type = parse_pdf_per_page(str(saved_path))
        logger.info(
            "Detected PDF type for %s: %s (per-page routing used)",
            file.filename,
            pdf_type,
        )

        # --- 5. Extract images per page and merge into pages structure ---
        pages = extract_images(str(saved_path), pages, str(IMAGE_DIR))

        # --- 6. Extract tables per page and merge into pages structure ---
        pages = extract_tables(str(saved_path), pages)

        # --- 7. Detect and tag equation-like text blocks ---
        pages = tag_equations(pages)

        # --- 8. Build and save final JSON ---
        final_json = build_final_json(
            document_name=file.filename,
            pdf_type=pdf_type,
            pages=pages,
        )
        output_path = OUTPUT_DIR / "parsed_document.json"
        save_json(final_json, str(output_path))
        logger.info("Saved parsed output to %s", output_path)

        return JSONResponse(content=final_json)

    except Exception as exc:
        logger.exception("Failed while processing PDF %s", file.filename)
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {exc}") from exc
