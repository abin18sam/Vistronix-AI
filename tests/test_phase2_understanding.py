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
from app.models import Document, Job, ModuleRun
from app.understanding.llm import StructuredResponse
from app.understanding.pipeline import build_knowledge_graph


init_db()
client = TestClient(app)


class FakeLLM:
    def __init__(self, fail_module: str | None = None):
        self.fail_module = fail_module

    def generate_structured(self, *, prompt_version, system_prompt, user_prompt):
        module = next(name for name in ("summary", "entities", "claims", "relationships", "learning_objectives") if name in system_prompt)
        if module == self.fail_module:
            raise TimeoutError("provider timeout")
        responses = {
            "summary": {"summary": "A concise summary.", "key_points": ["Point"]},
            "entities": {"entities": [{"entity_id": "e1", "name": "Force", "entity_type": "concept", "description": "A push."}, {"entity_id": "e2", "name": "Mass", "entity_type": "concept", "description": "Matter amount."}]},
            "claims": {"claims": [{"claim_id": "c1", "text": "Force affects motion."}]},
            "relationships": {"relationships": [{"relationship_id": "r1", "source_entity_id": "e1", "target_entity_id": "e2", "relationship": "acts on"}]},
            "learning_objectives": {"prerequisites": ["Algebra"], "learning_objectives": ["Explain force."]},
        }
        return StructuredResponse(data=responses[module], input_tokens=10, output_tokens=5, model="fake", provider_request_id="test-request")


class CountingFakeLLM(FakeLLM):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def generate_structured(self, **kwargs):
        self.calls += 1
        return super().generate_structured(**kwargs)


def _cleanup():
    session = SessionLocal()
    try:
        session.query(ModuleRun).delete()
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


def _document() -> tuple[str, Path, Job]:
    document_id = str(uuid4())
    directory = settings.documents_root / document_id
    directory.mkdir(parents=True)
    parsed = {"document_name": "sample.pdf", "pdf_type": "digital", "pages": [{"page_number": 1, "elements": [{"type": "heading", "text": "Physics"}, {"type": "text", "text": "Force and mass."}]}]}
    (directory / "parsed_document.json").write_text(json.dumps(parsed), encoding="utf-8")
    session = SessionLocal()
    document = Document(id=document_id, original_filename="sample.pdf", storage_directory=str(directory.resolve()), status="completed")
    job = Job(document_id=document_id, kind="understand", status="running")
    session.add_all([document, job])
    session.commit()
    session.refresh(job)
    session.close()
    return document_id, directory, job


def test_modular_pipeline_saves_valid_artifacts_and_metrics():
    document_id, directory, job = _document()
    session = SessionLocal()
    graph = build_knowledge_graph(session, job, document_id, directory, FakeLLM())
    assert graph.document_id == document_id
    assert len(graph.entities) == 2
    assert (directory / "understanding" / "chunks.json").exists()
    assert (directory / "understanding" / "knowledge_graph.json").exists()
    assert session.query(ModuleRun).filter_by(job_id=job.id, status="completed").count() == 5
    session.close()


def test_failed_relationship_preserves_successful_entity_artifact():
    document_id, directory, job = _document()
    session = SessionLocal()
    try:
        build_knowledge_graph(session, job, document_id, directory, FakeLLM(fail_module="relationships"))
    except TimeoutError:
        pass
    else:
        raise AssertionError("Expected relationship failure")
    assert (directory / "understanding" / "entities.json").exists()
    assert not (directory / "understanding" / "relationships.json").exists()
    assert session.query(ModuleRun).filter_by(job_id=job.id, module_name="entities", status="completed").one()
    assert session.query(ModuleRun).filter_by(job_id=job.id, module_name="relationships", status="failed").one().attempt_count == 3
    session.close()


def test_completed_modules_are_reused_when_inputs_and_prompt_are_unchanged():
    document_id, directory, job = _document()
    session = SessionLocal()
    client = CountingFakeLLM()
    build_knowledge_graph(session, job, document_id, directory, client)
    first_call_count = client.calls
    build_knowledge_graph(session, job, document_id, directory, client)
    assert first_call_count == 5
    assert client.calls == first_call_count
    session.close()


def test_understand_endpoint_is_idempotent_for_completed_job():
    document_id, directory, job = _document()
    session = SessionLocal()
    session.close()
    response = client.post(f"/documents/{document_id}/understand")
    assert response.status_code == 202
    assert response.json()["job_id"] == job.id
    assert client.post(f"/documents/{document_id}/understand").json()["job_id"] == job.id


def test_knowledge_graph_endpoint_returns_only_valid_saved_graph():
    document_id, directory, job = _document()
    session = SessionLocal()
    graph = build_knowledge_graph(session, job, document_id, directory, FakeLLM())
    job = session.get(Job, job.id)
    job.status = "completed"
    job.progress = 100
    session.commit()
    session.close()

    response = client.get(f"/documents/{document_id}/knowledge-graph")
    assert response.status_code == 200
    assert response.json()["document_id"] == document_id
    assert response.json()["entities"] == graph.model_dump()["entities"]
