import os
import shutil
from pathlib import Path

os.environ["QUEUE_MODE"] = "eager"
os.environ["ENABLE_OCR"] = "false"
os.environ["ENABLE_TABLE_EXTRACTION"] = "false"

from fastapi.testclient import TestClient

from app.config import settings
from app.db import SessionLocal, init_db
from app.main import app
from app.models import Document, Job


init_db()
client = TestClient(app)


def _pdf_bytes() -> bytes:
    return b"%PDF-1.7\nnot-a-complete-pdf"


def _cleanup() -> None:
    session = SessionLocal()
    try:
        session.query(Job).delete()
        session.query(Document).delete()
        session.commit()
    finally:
        session.close()
    for directory in settings.documents_root.iterdir():
        if directory.is_dir():
            shutil.rmtree(directory)


def setup_function() -> None:
    _cleanup()


def teardown_function() -> None:
    _cleanup()


def test_rejects_non_pdf_signature() -> None:
    response = client.post("/documents", files={"file": ("notes.pdf", b"not a pdf", "application/pdf")})
    assert response.status_code == 400
    assert response.json()["detail"] == "File does not have a valid PDF signature"


def test_upload_creates_isolated_document_and_failed_job_for_malformed_pdf() -> None:
    response = client.post("/documents", files={"file": ("../unsafe.pdf", _pdf_bytes(), "application/pdf")})
    assert response.status_code == 202
    payload = response.json()
    document_dir = settings.documents_root / payload["document_id"]
    assert Path(document_dir).resolve().parent == settings.documents_root.resolve()
    assert (document_dir / "original.pdf").exists()
    assert not (document_dir / "../unsafe.pdf").exists()

    status_response = client.get(f"/documents/{payload['document_id']}/status")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "failed"

    parsed_response = client.get(f"/documents/{payload['document_id']}/parsed-document")
    assert parsed_response.status_code == 409


def test_missing_document_returns_404() -> None:
    assert client.get("/documents/00000000-0000-0000-0000-000000000000/status").status_code == 404
