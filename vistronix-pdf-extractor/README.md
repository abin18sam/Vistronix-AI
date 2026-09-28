# VisTronix AI — PDF Extractor / Parser Engine

An end-to-end Python service that accepts a PDF upload, detects whether it's
**digital** (selectable text) or **scanned** (image-only), extracts text,
headings, images, tables, and simple equations, and produces a single
structured `parsed_document.json`.

## Project Structure

```
project/
│
├── main.py                      # FastAPI app + orchestration pipeline
├── requirements.txt
├── parser/
│   ├── pdf_detector.py          # PER-PAGE digital vs scanned detection
│   ├── digital_parser.py        # text/heading extraction (pdfplumber)
│   ├── scanned_parser.py        # OCR extraction (Tesseract + PyMuPDF)
│   ├── mixed_parser.py          # orchestrates per-page routing (handles mixed docs)
│   ├── image_extractor.py       # embedded image extraction (PyMuPDF)
│   ├── table_extractor.py       # table extraction (Camelot)
│   ├── equation_detector.py     # rule-based equation tagging
│   └── json_builder.py          # assembles + saves final JSON
│
├── uploads/                     # uploaded PDFs land here
├── extracted_images/            # images pulled out of PDFs land here
└── output/                      # parsed_document.json lands here
```

## 1. Install Python dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Install system dependencies

Two of the libraries used here (`pytesseract` and `camelot-py`) are just
Python *wrappers* — they need real programs installed on your machine.

### Tesseract OCR (required for scanned PDFs)

**Windows:**
1. Download the installer from the UB-Mannheim Tesseract build:
   https://github.com/UB-Mannheim/tesseract/wiki
2. Install it (default path is usually `C:\Program Files\Tesseract-OCR`).
3. Either add that folder to your `PATH`, or point pytesseract at it directly
   in code:
   ```python
   import pytesseract
   pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
   ```

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

### Ghostscript (required for Camelot table extraction)

**Windows:** download and install from https://ghostscript.com/releases/gsdnld.html

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get install ghostscript python3-tk
```

**macOS:**
```bash
brew install ghostscript
```

### Poppler (only needed if you switch to `pdf2image` instead of PyMuPDF rendering)

**Linux:** `sudo apt-get install poppler-utils`
**macOS:** `brew install poppler`
**Windows:** download poppler binaries and add the `bin/` folder to `PATH`.

> The code as written uses PyMuPDF (`fitz`) to rasterize scanned pages, so
> Poppler is **not required** unless you choose to swap in `pdf2image`.

## 3. Run the server

```bash
uvicorn main:app --reload
```

The API will be live at `http://127.0.0.1:8000`. Interactive docs (Swagger UI)
are available at `http://127.0.0.1:8000/docs`.

## 4. Test the upload endpoint

```bash
curl -X POST "http://127.0.0.1:8000/upload-pdf" -F "file=@sample.pdf"
```

This will:
1. Save `sample.pdf` into `uploads/`.
2. Detect digital vs scanned.
3. Extract text/headings, images, tables, and tag equations.
4. Write the result to `output/parsed_document.json`.
5. Return the same JSON as the HTTP response.

## Handling mixed documents (digital + scanned pages together)

Earlier versions of this pipeline detected ONE type for the whole document
by sampling its first few pages. That silently mis-parsed documents where,
say, a typed cover page was followed by scanned/handwritten pages (or vice
versa) - the minority pages would get routed to the wrong parser.

This is now fixed with **per-page detection**:

- `pdf_detector.detect_page_types()` classifies **every single page**
  independently (not just a sample), returning a `digital`/`scanned` label
  per page.
- `mixed_parser.parse_pdf_per_page()` uses those labels to send each page to
  the correct parser individually - `digital_parser.parse_digital_page()`
  for digital pages, `scanned_parser.parse_scanned_page()` for scanned ones
  - and stitches the results back together in page order.
- The top-level `pdf_type` field in `parsed_document.json` becomes:
    - `"digital"` if every page was digital
    - `"scanned"` if every page was scanned
    - `"mixed"` if the document contains both
- Each page in the output also carries its own `"pdf_type"` field, so you
  can see exactly which pages were OCR'd vs digitally parsed:

```json
{
  "document_name": "sample.pdf",
  "pdf_type": "mixed",
  "pages": [
    { "page_number": 1, "pdf_type": "digital", "elements": [...] },
    { "page_number": 2, "pdf_type": "scanned", "elements": [...] }
  ]
}
```

## How each stage works (quick summary)

- **`pdf_detector.py`** checks EVERY page (via PyMuPDF) and counts real
  alphanumeric characters on that page. Enough characters → "digital",
  otherwise → "scanned". See "Handling mixed documents" above.
- **`mixed_parser.py`** ties detection + both parsers together, routing
  each page to `digital_parser.parse_digital_page()` or
  `scanned_parser.parse_scanned_page()` based on that page's own type.
- **`digital_parser.py`** uses `pdfplumber` to pull out words with their
  font size and position, groups them into lines then paragraph blocks, and
  flags a block as a "heading" if its font is notably larger or bold
  relative to the page's body text.
- **`scanned_parser.py`** rasterizes each page with PyMuPDF and runs
  `pytesseract.image_to_data`, which returns OCR'd words with bounding
  boxes. Words are grouped into lines/blocks the same way, using text
  height as a stand-in for font size.
- **`image_extractor.py`** uses PyMuPDF's `get_images()` / `extract_image()`
  to pull out every embedded raster image and save it under
  `extracted_images/`.
- **`table_extractor.py`** runs Camelot in `lattice` mode first (for
  bordered tables), falling back to `stream` mode if nothing is found.
- **`equation_detector.py`** is a lightweight regex/rule-based classifier —
  no ML, no equation solving. It just flags short text blocks containing
  math-like symbols (`=`, `+`, `√`, `→`, etc.) or LaTeX-like patterns.
- **`json_builder.py`** merges everything, sorts elements top-to-bottom
  within each page using bounding boxes, and writes `parsed_document.json`.

## Notes & Limitations

- The heading/equation detection is intentionally rule-based and simple, as
  requested — it will not catch every edge case in complex, messy PDFs.
- Table extraction quality depends heavily on how the source PDF is
  formatted; Camelot works best on PDFs with clear grid lines or clean
  whitespace-separated columns.
- OCR accuracy for scanned PDFs depends on scan quality; increasing
  `RENDER_ZOOM` in `scanned_parser.py` can improve results on low-resolution
  scans at the cost of speed.
