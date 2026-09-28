import logging
import secrets
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db, init_db
from app.external import dependency_report
from app.models import Document, Job
from app.schemas import DocumentResponse, JobResponse, ParsedDocument, ReadinessResponse, UnderstandingJobResponse, VideoResponse
from app.tasks import understand_document_job, parse_document_job
from app.understanding.schemas import KnowledgeGraph
from app.video_service import build_scene_plan, render_video, validate_video

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("vistronix.app")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="VisTronix AI MVP", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "vistronix-mvp"}


@app.get("/ready", response_model=ReadinessResponse)
def readiness() -> ReadinessResponse:
    ready, checks = dependency_report()
    return JSONResponse(status_code=200 if ready else 503, content={"status": "ready" if ready else "not_ready", "checks": checks})


@app.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_document(file: UploadFile = File(...), db: Session = Depends(get_db)) -> DocumentResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .pdf uploads are accepted")

    document_id = str(uuid4())
    directory = settings.documents_root / document_id
    directory.mkdir(parents=True, exist_ok=False)
    pdf_path = directory / "original.pdf"

    try:
        header = await file.read(5)
        if header != b"%PDF-":
            raise HTTPException(status_code=400, detail="File does not have a valid PDF signature")
        await file.seek(0)
        total = 0
        with pdf_path.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > settings.max_upload_bytes:
                    raise HTTPException(status_code=413, detail="PDF exceeds the upload size limit")
                destination.write(chunk)

        document = Document(id=document_id, original_filename=Path(file.filename).name, storage_directory=str(directory.resolve()))
        job = Job(document_id=document_id, kind="parse", status="queued")
        db.add_all([document, job])
        db.commit()
        db.refresh(job)

        try:
            parse_document_job.delay(document_id, job.id)
        except Exception as exc:
            job.status = "failed"
            job.error = f"Could not queue parsing job: {exc}"
            document.status = "failed"
            db.commit()
            raise HTTPException(status_code=503, detail="Parsing queue is unavailable") from exc
        return DocumentResponse(document_id=document_id, filename=document.original_filename, status="queued", job_id=job.id)
    except HTTPException:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    except Exception as exc:
        db.rollback()
        shutil.rmtree(directory, ignore_errors=True)
        logger.exception("Upload failed")
        raise HTTPException(status_code=500, detail="Could not store document") from exc
    finally:
        await file.close()


def _get_document_or_404(document_id: str, db: Session) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@app.get("/documents/{document_id}/status", response_model=JobResponse)
def document_status(document_id: str, db: Session = Depends(get_db)) -> JobResponse:
    document = _get_document_or_404(document_id, db)
    job = db.scalar(select(Job).where(Job.document_id == document_id).order_by(Job.created_at.desc()))
    if job is None:
        raise HTTPException(status_code=500, detail="Document has no processing job")
    return JobResponse(job_id=job.id, document_id=document.id, status=job.status, progress=job.progress, error=job.error, created_at=job.created_at, started_at=job.started_at, finished_at=job.finished_at)


@app.get("/documents/{document_id}/parsed-document", response_model=ParsedDocument)
def parsed_document(document_id: str, db: Session = Depends(get_db)) -> ParsedDocument:
    document = _get_document_or_404(document_id, db)
    if document.status in {"queued", "running"}:
        raise HTTPException(status_code=202, detail="Parsing is not complete")
    if document.status == "failed":
        raise HTTPException(status_code=409, detail="Parsing failed; inspect document status")
    path = Path(document.storage_directory) / "parsed_document.json"
    if not path.exists():
        raise HTTPException(status_code=500, detail="Completed document output is missing")
    try:
        return ParsedDocument.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Stored parsed document is invalid") from exc


@app.post("/documents/{document_id}/understand", response_model=UnderstandingJobResponse, status_code=status.HTTP_202_ACCEPTED)
def understand_document(document_id: str, db: Session = Depends(get_db)) -> UnderstandingJobResponse:
    document = _get_document_or_404(document_id, db)
    if document.status != "completed":
        raise HTTPException(status_code=409, detail="Parsing must be completed before understanding")
    active_or_done = db.scalar(
        select(Job).where(
            Job.document_id == document_id,
            Job.kind == "understand",
            Job.status.in_(["queued", "running", "completed"]),
        ).order_by(Job.created_at.desc())
    )
    if active_or_done is not None:
        return UnderstandingJobResponse(
            job_id=active_or_done.id, document_id=document_id, status=active_or_done.status,
            progress=active_or_done.progress, error=active_or_done.error,
            created_at=active_or_done.created_at, started_at=active_or_done.started_at,
            finished_at=active_or_done.finished_at,
        )

    job = Job(document_id=document_id, kind="understand", status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        understand_document_job.delay(document_id, job.id)
    except Exception as exc:
        job.status = "failed"
        job.error = f"Could not queue understanding job: {exc}"
        db.commit()
        raise HTTPException(status_code=503, detail="Understanding queue is unavailable") from exc
    return UnderstandingJobResponse(
        job_id=job.id, document_id=document_id, status=job.status, progress=job.progress,
        error=job.error, created_at=job.created_at, started_at=job.started_at, finished_at=job.finished_at,
    )


@app.get("/documents/{document_id}/knowledge-graph", response_model=KnowledgeGraph)
def knowledge_graph(document_id: str, db: Session = Depends(get_db)) -> KnowledgeGraph:
    document = _get_document_or_404(document_id, db)
    job = db.scalar(
        select(Job).where(Job.document_id == document_id, Job.kind == "understand")
        .order_by(Job.created_at.desc())
    )
    if job is None or job.status in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="Understanding is not complete")
    if job.status == "failed":
        raise HTTPException(status_code=409, detail="Understanding failed; inspect job status")
    path = Path(document.storage_directory) / "understanding" / "knowledge_graph.json"
    if not path.exists():
        raise HTTPException(status_code=500, detail="Knowledge graph output is missing")
    try:
        return KnowledgeGraph.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Stored knowledge graph is invalid") from exc


def _require_video_download_token(authorization: str | None = Header(default=None)) -> None:
    expected = settings.video_download_token
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Valid bearer token required", headers={"WWW-Authenticate": "Bearer"})


@app.post("/documents/{document_id}/generate-video", response_model=VideoResponse, status_code=status.HTTP_202_ACCEPTED)
def generate_video(document_id: str, db: Session = Depends(get_db)) -> VideoResponse:
    document = _get_document_or_404(document_id, db)
    document_dir = Path(document.storage_directory)
    parsed_path = document_dir / "parsed_document.json"
    graph_path = document_dir / "understanding" / "knowledge_graph.json"
    if not graph_path.exists():
        graph_path = document_dir / "knowledge_graph.json"
    if not parsed_path.exists() or not graph_path.exists():
        raise HTTPException(status_code=409, detail="Document must have parsed and knowledge-graph outputs before video generation")

    active = db.scalar(
        select(Job).where(Job.document_id == document_id, Job.kind == "video")
        .order_by(Job.created_at.desc())
    )
    if active is not None:
        return VideoResponse(
            job_id=active.id, document_id=document_id, status=active.status,
            progress=active.progress, error=active.error,
            created_at=active.created_at, started_at=active.started_at, finished_at=active.finished_at,
            output_path=str((document_dir / "final.mp4").resolve()) if (document_dir / "final.mp4").exists() else None,
        )

    job = Job(document_id=document_id, kind="video", status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        from app.tasks import generate_video_job
        generate_video_job.delay(document_id, job.id)
    except Exception as exc:
        job.status = "failed"
        job.error = f"Could not queue video job: {exc}"
        db.commit()
        raise HTTPException(status_code=503, detail="Video queue is unavailable") from exc

    return VideoResponse(
        job_id=job.id, document_id=document_id, status=job.status,
        progress=job.progress, error=job.error,
        created_at=job.created_at, started_at=job.started_at, finished_at=job.finished_at,
    )


@app.get("/documents/{document_id}/download", dependencies=[Depends(_require_video_download_token)])
def download_document_video(document_id: str, db: Session = Depends(get_db)):
    document = _get_document_or_404(document_id, db)
    video_path = Path(document.storage_directory) / "final.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video output not found")
    return FileResponse(video_path, media_type="video/mp4", filename=f"{document_id}.mp4")
