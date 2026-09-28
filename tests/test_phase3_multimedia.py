import json
import os
import shutil
from pathlib import Path
from uuid import uuid4

os.environ["QUEUE_MODE"] = "eager"
os.environ["ENABLE_OCR"] = "false"

from fastapi.testclient import TestClient

from app.config import settings
from app.db import SessionLocal, init_db
from app.main import app
from app.models import Document, Job
from app.video_service import build_scene_plan

init_db()
client = TestClient(app)


def _cleanup():
    session = SessionLocal()
    try:
        session.query(Job).delete()
        session.query(Document).delete()
        session.commit()
    finally:
        session.close()
    if settings.documents_root.exists():
        for path in settings.documents_root.iterdir():
            if path.is_dir():
                shutil.rmtree(path)


def setup_function():
    _cleanup()


def teardown_function():
    _cleanup()


def _document() -> tuple[str, Path]:
    document_id = str(uuid4())
    directory = settings.documents_root / document_id
    directory.mkdir(parents=True, exist_ok=True)

    parsed = {
        "document_name": "forces.pdf",
        "pdf_type": "digital",
        "pages": [
            {"page_number": 1, "elements": [{"type": "heading", "text": "Forces and Motion"}, {"type": "text", "text": "Force is a push or pull that changes motion. Mass measures how much matter is in an object."}]}
        ],
    }
    graph = {
        "document_id": document_id,
        "summary": {"summary": "Forces change motion.", "key_points": ["Forces alter motion.", "Mass resists change."]},
        "entities": [
            {"entity_id": "e1", "name": "Force", "entity_type": "concept", "description": "A push or pull."},
            {"entity_id": "e2", "name": "Mass", "entity_type": "concept", "description": "The amount of matter."},
        ],
        "claims": [{"claim_id": "c1", "text": "Force affects motion.", "source_chunk_ids": []}],
        "relationships": [],
        "prerequisites": [],
        "learning_objectives": ["Explain force and mass."],
    }

    (directory / "parsed_document.json").write_text(json.dumps(parsed), encoding="utf-8")
    (directory / "knowledge_graph.json").write_text(json.dumps(graph), encoding="utf-8")

    session = SessionLocal()
    document = Document(id=document_id, original_filename="forces.pdf", storage_directory=str(directory.resolve()), status="completed")
    job = Job(document_id=document_id, kind="understand", status="completed")
    session.add_all([document, job])
    session.commit()
    session.close()
    return document_id, directory


def test_phase3_scene_plan_uses_document_and_knowledge_graph():
    document_id, directory = _document()
    scene_plan = build_scene_plan(document_id, directory)
    assert len(scene_plan.scene_plan) >= 3
    titles = [scene.title.lower() for scene in scene_plan.scene_plan]
    assert any("force" in title or "mass" in title for title in titles)
    assert (directory / "scene_plan.json").exists()


def test_video_generation_endpoint_creates_an_mp4_and_download():
    document_id, directory = _document()
    response = client.post(f"/documents/{document_id}/generate-video")
    assert response.status_code == 202, response.text

    job_response = client.get(f"/documents/{document_id}/status")
    assert job_response.status_code == 200, job_response.text
    status = job_response.json()["status"]
    assert status in {"queued", "running", "completed"}

    final_mp4 = directory / "final.mp4"
    assert final_mp4.exists(), "Expected final.mp4 to be created"

    download = client.get(f"/documents/{document_id}/download", headers={"Authorization": "Bearer dev-video-token"})
    assert download.status_code == 200, download.text
    assert download.headers["content-type"].startswith("video/") or "octet-stream" in download.headers.get("content-type", "")
