from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


JobStatus = Literal["queued", "running", "completed", "failed"]


class Element(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    text: str | None = None
    bbox: list[float] | None = None


class ParsedPage(BaseModel):
    page_number: int = Field(ge=1)
    elements: list[Element] = Field(default_factory=list)
    pdf_type: str | None = None


class ParsedDocument(BaseModel):
    document_name: str
    pdf_type: Literal["digital", "scanned", "mixed"]
    pages: list[ParsedPage]


class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    status: JobStatus
    job_id: str


class JobResponse(BaseModel):
    job_id: str
    document_id: str
    status: JobStatus
    progress: int
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, dict[str, Any]]


class UnderstandingJobResponse(JobResponse):
    pass


class VideoResponse(BaseModel):
    job_id: str
    document_id: str
    status: JobStatus
    progress: int
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    output_path: str | None = None
