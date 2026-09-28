import hashlib
import json
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Job, ModuleRun
from app.schemas import ParsedDocument
from app.understanding.chunking import build_chunks, normalize_name
from app.understanding.llm import LLMClient, ProviderLLMClient, StructuredResponse
from app.understanding.schemas import (
    ClaimsResult, EntitiesResult, Entity, KnowledgeGraph, LearningObjectivesResult,
    RelationshipsResult, SummaryResult,
)

PROMPT_VERSION = "phase2-v1"
MODULES = ("summary", "entities", "claims", "relationships", "learning_objectives")
PRICING_USD_PER_MILLION = {"gpt-4o-mini": {"input": 0.15, "output": 0.60}}


def _artifact_dir(document_dir: Path) -> Path:
    path = document_dir / "understanding"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _atomic_write(model: BaseModel, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)


def _prompt(module: str, chunks: list[dict[str, Any]]) -> tuple[str, str]:
    system = f"You are the VisTronix {module} module. Prompt version: {PROMPT_VERSION}. Return only JSON matching the requested schema."
    user = json.dumps({"module": module, "chunks": chunks}, ensure_ascii=False)
    return system, user


def _response(client: LLMClient, module: str, chunks: list[dict[str, Any]], schema: type[BaseModel]) -> tuple[BaseModel, StructuredResponse]:
    system, user = _prompt(module, chunks)
    response = client.generate_structured(prompt_version=PROMPT_VERSION, system_prompt=system, user_prompt=user)
    return schema.model_validate(response.data), response


def _save_module(session: Session, job: Job, name: str, input_hash: str, artifact: Path, client: LLMClient, chunks: list[dict[str, Any]], schema: type[BaseModel]) -> BaseModel:
    run = session.query(ModuleRun).filter_by(job_id=job.id, module_name=name).one_or_none()
    if (
        run is not None
        and run.status == "completed"
        and run.prompt_version == PROMPT_VERSION
        and run.input_hash == input_hash
        and artifact.exists()
    ):
        try:
            return schema.model_validate_json(artifact.read_text(encoding="utf-8"))
        except Exception:
            pass
    if run is None:
        run = ModuleRun(job_id=job.id, module_name=name, prompt_version=PROMPT_VERSION, input_hash=input_hash)
        session.add(run)
    run.status = "running"
    run.started_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    session.commit()
    started = time.perf_counter()
    last_error: Exception | None = None
    for attempt in range(settings.llm_max_retries):
        run.attempt_count = (run.attempt_count or 0) + 1
        session.commit()
        try:
            result, response = _response(client, name, chunks, schema)
            break
        except Exception as exc:
            last_error = exc
            if attempt + 1 < settings.llm_max_retries:
                run.retry_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                session.commit()
                time.sleep(min(2 ** attempt, 8))
    else:
        result = None
        response = None

    try:
        if result is None or response is None:
            raise last_error or RuntimeError("Module failed without an error")
        run.status = "completed"
        run.input_tokens = response.input_tokens
        run.output_tokens = response.output_tokens
        run.total_tokens = (response.input_tokens or 0) + (response.output_tokens or 0)
        prices = PRICING_USD_PER_MILLION.get(response.model or settings.openai_model, PRICING_USD_PER_MILLION[settings.openai_model])
        run.estimated_cost = ((response.input_tokens or 0) * prices["input"] + (response.output_tokens or 0) * prices["output"]) / 1_000_000
        run.model = response.model
        run.provider_request_id = response.provider_request_id
        run.duration_ms = int((time.perf_counter() - started) * 1000)
        run.finished_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        _atomic_write(result, artifact)
        session.commit()
        return result
    except Exception as exc:
        session.rollback()
        run = session.query(ModuleRun).filter_by(job_id=job.id, module_name=name).one()
        run.status = "failed"
        run.error = str(exc)[:4000]
        run.retryable = isinstance(exc, (TimeoutError, ConnectionError)) or any(term in str(exc).lower() for term in ("timeout", "rate limit", "temporar", "connection"))
        run.duration_ms = int((time.perf_counter() - started) * 1000)
        run.finished_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        session.commit()
        raise


def build_knowledge_graph(session: Session, job: Job, document_id: str, document_dir: Path, client: LLMClient | None = None) -> KnowledgeGraph:
    parsed = ParsedDocument.model_validate_json((document_dir / "parsed_document.json").read_text(encoding="utf-8"))
    chunks = build_chunks(parsed)
    if not chunks:
        raise ValueError("Parsed document has no usable text chunks")
    artifact_dir = _artifact_dir(document_dir)
    chunks_path = artifact_dir / "chunks.json"
    chunks_payload = {"prompt_version": PROMPT_VERSION, "chunks": [chunk.model_dump() for chunk in chunks]}
    chunks_path.write_text(json.dumps(chunks_payload, indent=2), encoding="utf-8")
    chunk_dicts = [chunk.model_dump() for chunk in chunks]
    input_hash = hashlib.sha256(json.dumps(chunk_dicts, sort_keys=True).encode()).hexdigest()
    client = client or ProviderLLMClient()

    summary = _save_module(session, job, "summary", input_hash, artifact_dir / "summary.json", client, chunk_dicts, SummaryResult)
    entities = _save_module(session, job, "entities", input_hash, artifact_dir / "entities.json", client, chunk_dicts, EntitiesResult)
    claims = _save_module(session, job, "claims", input_hash, artifact_dir / "claims.json", client, chunk_dicts, ClaimsResult)
    entity_context = [{"entities": entities.model_dump(), "claims": claims.model_dump(), "chunks": chunk_dicts}]
    relationships = _save_module(session, job, "relationships", input_hash, artifact_dir / "relationships.json", client, entity_context, RelationshipsResult)
    entity_ids = {entity.entity_id for entity in entities.entities}
    if any(item.source_entity_id not in entity_ids or item.target_entity_id not in entity_ids for item in relationships.relationships):
        relationship_artifact = artifact_dir / "relationships.json"
        relationship_artifact.unlink(missing_ok=True)
        run = session.query(ModuleRun).filter_by(job_id=job.id, module_name="relationships").one()
        run.status = "failed"
        run.error = "Relationship references an entity not present in the entity result"
        session.commit()
        raise ValueError(run.error)
    learning = _save_module(session, job, "learning_objectives", input_hash, artifact_dir / "learning_objectives.json", client, chunk_dicts, LearningObjectivesResult)

    deduped: dict[str, Entity] = {}
    for entity in entities.entities:
        key = normalize_name(entity.name)
        if key in deduped:
            deduped[key].aliases.extend([entity.name, *entity.aliases])
        else:
            deduped[key] = entity
    graph = KnowledgeGraph(
        document_id=document_id,
        summary=summary,
        entities=list(deduped.values()),
        claims=claims.claims,
        relationships=relationships.relationships,
        prerequisites=learning.prerequisites,
        learning_objectives=learning.learning_objectives,
    )
    _atomic_write(graph, artifact_dir / "knowledge_graph.json")
    return graph
