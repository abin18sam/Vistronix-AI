import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

os.environ["QUEUE_MODE"] = "eager"
os.environ["ENABLE_OCR"] = "false"

import fitz
from fastapi.testclient import TestClient

from app.config import settings
from app.db import SessionLocal, init_db
from app.main import app
from app.models import Document, Job
from app.tasks import generate_video_job
from app.video_service import validate_video


init_db()
client = TestClient(app)


def _cleanup() -> None:
    session = SessionLocal()
    try:
        session.query(Job).delete()
        session.query(Document).delete()
        session.commit()
    finally:
        session.close()
    for path in settings.documents_root.iterdir():
        if path.is_dir():
            shutil.rmtree(path)


def setup_function() -> None:
    _cleanup()


def teardown_function() -> None:
    _cleanup()


def _pdf_bytes(topic: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), topic)
    page.insert_text((72, 110), f"{topic} is the central subject of this lesson.")
    payload = document.tobytes()
    document.close()
    return payload


def _upload(topic: str) -> str:
    response = client.post("/documents", files={"file": (f"{topic}.pdf", _pdf_bytes(topic), "application/pdf")})
    assert response.status_code == 202, response.text
    document_id = response.json()["document_id"]
    status = client.get(f"/documents/{document_id}/status")
    assert status.json()["status"] == "completed", status.text
    return document_id


def _prepare_understanding(document_id: str) -> None:
    response = client.post(f"/documents/{document_id}/understand")
    assert response.status_code == 202, response.text
    graph = client.get(f"/documents/{document_id}/knowledge-graph")
    assert graph.status_code == 200, graph.text


def test_full_api_multimedia_workflow_is_document_scoped_and_authenticated() -> None:
    first_id = _upload("Orbital Mechanics")
    second_id = _upload("Cellular Biology")
    _prepare_understanding(first_id)
    _prepare_understanding(second_id)

    with patch("app.tasks.generate_video_job.delay", return_value=None):
        first_response = client.post(f"/documents/{first_id}/generate-video")
        second_response = client.post(f"/documents/{second_id}/generate-video")
    assert first_response.status_code == 202, first_response.text
    assert second_response.status_code == 202, second_response.text
    jobs = [first_response.json(), second_response.json()]

    job_ids = [job["job_id"] for job in jobs]
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda pair: generate_video_job(pair[0], pair[1]), zip([first_id, second_id], job_ids)))

    assert {job["document_id"] for job in jobs} == {first_id, second_id}
    for document_id, topic in ((first_id, "Orbital Mechanics"), (second_id, "Cellular Biology")):
        directory = settings.documents_root / document_id
        status = client.get(f"/documents/{document_id}/status")
        assert status.json()["status"] == "completed", status.text
        assert (directory / "scene_plan.json").exists()
        assert (directory / "audio" / "narration.wav").stat().st_size > 0
        captions = (directory / "captions" / "captions.srt").read_text(encoding="utf-8")
        assert topic in captions
        validation = validate_video(directory / "final.mp4")
        assert validation["ok"]
        assert validation["has_audio"]
        assert validation["duration_seconds"] > 0
        assert client.get(f"/documents/{document_id}/download").status_code == 401
        download = client.get(
            f"/documents/{document_id}/download",
            headers={"Authorization": "Bearer dev-video-token"},
        )
        assert download.status_code == 200, download.text
        assert download.content == (directory / "final.mp4").read_bytes()

    first_scene = (settings.documents_root / first_id / "scene_plan.json").read_text(encoding="utf-8")
    second_scene = (settings.documents_root / second_id / "scene_plan.json").read_text(encoding="utf-8")
    assert first_scene != second_scene
    assert first_id != second_id