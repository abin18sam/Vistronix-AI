import os
from datetime import datetime, timezone
from pathlib import Path

from celery import Celery

from app.config import settings
from app.db import SessionLocal
from app.models import Document, Job
from app.parser_service import parse_to_storage, validate_pdf
from app.understanding.pipeline import build_knowledge_graph
from app.video_service import build_scene_plan, render_video, validate_video

celery_app = Celery("vistronix", broker=settings.redis_url)
celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    worker_pool="solo" if os.name == "nt" else "prefork",
    worker_concurrency=1,
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
)
if settings.queue_mode == "eager":
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _elapsed_ms(start: datetime, end: datetime) -> int:
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return max(0, int((end - start).total_seconds() * 1000))


@celery_app.task(name="vistronix.parse_document")
def parse_document_job(document_id: str, job_id: str) -> None:
    """Worker entry point. It deliberately opens its own SQLAlchemy session."""
    session = SessionLocal()
    try:
        document = session.get(Document, document_id)
        job = session.get(Job, job_id)
        if document is None or job is None:
            raise ValueError("Document or job no longer exists")

        job.status = "running"
        job.progress = 10
        job.started_at = _now()
        document.status = "running"
        session.commit()

        directory = Path(document.storage_directory)
        pdf_path = directory / "original.pdf"
        validate_pdf(pdf_path)
        job.progress = 30
        session.commit()

        parse_to_storage(pdf_path, directory, document.original_filename)
        job.status = "completed"
        job.progress = 100
        job.finished_at = _now()
        document.status = "completed"
        session.commit()
    except Exception as exc:
        session.rollback()
        job = session.get(Job, job_id)
        document = session.get(Document, document_id)
        if job is not None:
            job.status = "failed"
            job.error = str(exc)[:4000]
            job.finished_at = _now()
        if document is not None:
            document.status = "failed"
        session.commit()
        raise
    finally:
        session.close()


@celery_app.task(name="vistronix.understand_document")
def understand_document_job(document_id: str, job_id: str) -> None:
    session = SessionLocal()
    try:
        document = session.get(Document, document_id)
        job = session.get(Job, job_id)
        if document is None or job is None:
            raise ValueError("Document or understanding job no longer exists")
        if document.status != "completed":
            raise ValueError("Parsing must be completed before understanding")
        job.status = "running"
        job.progress = 5
        job.started_at = _now()
        job.queue_wait_ms = _elapsed_ms(job.created_at, job.started_at)
        session.commit()
        started = _now()
        build_knowledge_graph(session, job, document_id, Path(document.storage_directory))
        job.status = "completed"
        job.progress = 100
        job.finished_at = _now()
        job.duration_ms = _elapsed_ms(started, job.finished_at)
        session.commit()
    except Exception as exc:
        session.rollback()
        job = session.get(Job, job_id)
        if job is not None:
            job.status = "failed"
            job.error = str(exc)[:4000]
            job.finished_at = _now()
            if job.started_at is not None:
                job.duration_ms = _elapsed_ms(job.started_at, job.finished_at)
            session.commit()
        raise
    finally:
        session.close()


@celery_app.task(name="vistronix.generate_video")
def generate_video_job(document_id: str, job_id: str) -> None:
    session = SessionLocal()
    try:
        document = session.get(Document, document_id)
        job = session.get(Job, job_id)
        if document is None or job is None:
            raise ValueError("Document or video job no longer exists")

        document_dir = Path(document.storage_directory)
        graph_path = document_dir / "understanding" / "knowledge_graph.json"
        if not graph_path.exists():
            graph_path = document_dir / "knowledge_graph.json"
        if not (document_dir / "parsed_document.json").exists() or not graph_path.exists():
            raise ValueError("Document must have parsed_document.json and knowledge_graph.json before rendering")

        job.status = "running"
        job.progress = 10
        job.started_at = _now()
        session.commit()

        scene_plan = build_scene_plan(document_id, document_dir)
        job.progress = 50
        session.commit()

        final_mp4 = render_video(document_id, document_dir)
        validation = validate_video(final_mp4)
        if not validation["ok"]:
            raise ValueError(f"Generated MP4 failed validation: {validation}")

        job.status = "completed"
        job.progress = 100
        job.finished_at = _now()
        job.error = None
        document.status = "completed"
        session.commit()
    except Exception as exc:
        session.rollback()
        job = session.get(Job, job_id)
        if job is not None:
            job.status = "failed"
            job.error = str(exc)[:4000]
            job.finished_at = _now()
            session.commit()
        raise
    finally:
        session.close()
