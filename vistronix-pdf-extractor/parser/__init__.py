"""
VisTronix AI - parser package

Contains all the individual modules responsible for one stage of the
PDF parsing pipeline each:

    pdf_detector.py      -> digital vs scanned detection
    digital_parser.py    -> text extraction for digital PDFs
    scanned_parser.py    -> OCR-based extraction for scanned PDFs
    image_extractor.py   -> extracting embedded images
    table_extractor.py   -> extracting tables
    equation_detector.py -> tagging equation-like text
    json_builder.py       -> assembling + saving the final JSON
"""
