# VisTronix AI MVP

This workspace now has a reliable document-ingestion foundation around the existing PDF extractor.
The API owns document/job state in SQLite, stores every document under a UUID directory, and sends parsing work to a persistent Celery worker through Redis.

## Layout

```text
app/                         FastAPI API, database, worker, readiness checks
vistronix-pdf-extractor/     Existing Stage 1 extraction implementation
tests/                       MVP API tests
storage/documents/<uuid>/    original.pdf and parsed_document.json
requirements.in              Direct dependencies
requirements.txt             Install entry point
requirements-dev.txt         Runtime plus pytest
pyproject.toml               Package and test configuration
docker-compose.yml           Redis, API, and Celery worker
```

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

The core environment supports digital and scanned PDF parsing. Tesseract is required when `ENABLE_OCR=true` (the default MVP setting). Table extraction is opt-in because Camelot has platform-specific native dependencies; set `ENABLE_TABLE_EXTRACTION=true` only after installing its optional package and Ghostscript. FFmpeg is required only when `ENABLE_MULTIMEDIA=true`.

Check external dependencies:

```powershell
.\.venv\Scripts\python.exe -c "from app.external import dependency_report; print(dependency_report())"
```

Run API and worker in separate terminals:

```powershell
uvicorn app.main:app --reload --port 8000
celery -A app.tasks.celery_app worker --loglevel=INFO
```

Or run the full local stack:

```powershell
docker compose up --build
```

## MVP API

- `GET /health` basic process health.
- `GET /ready` dependency readiness; returns `503` when an enabled required binary is missing.
- `POST /documents` accepts a PDF and returns `202` with `document_id` and `job_id`.
- `GET /documents/{document_id}/status` returns database-backed job progress.
- `GET /documents/{document_id}/parsed-document` returns the validated parsed contract after successful parsing.
- `POST /documents/{document_id}/understand` queues an idempotent modular understanding job.
- `GET /documents/{document_id}/knowledge-graph` returns the validated graph after understanding completes.

Example upload:

```powershell
curl.exe -X POST http://127.0.0.1:8000/documents -F "file=@sample.pdf"
```

The upload is stored as:

```text
storage/documents/<server-generated-uuid>/original.pdf
storage/documents/<server-generated-uuid>/parsed_document.json
storage/documents/<server-generated-uuid>/images/
```

The original filename is retained only as database metadata. It never controls a filesystem path.

Phase 2 writes partial, document-specific results under `understanding/`: chunks, summary, entities, claims, relationships, learning objectives, and the final knowledge graph. Each module is independently validated, retried with bounded backoff, and recorded in the `module_runs` table with attempt, token, duration, model, and request metadata.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests
$env:PYTHONPATH = "$PWD\vistronix-understanding-engine"
.\.venv\Scripts\python.exe -m pytest -q vistronix-understanding-engine\tests
```
