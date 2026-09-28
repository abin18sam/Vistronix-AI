import shutil
from typing import Any

from app.config import settings


def _check_binary(name: str, required: bool) -> dict[str, Any]:
    path = shutil.which(name)
    return {"required": required, "available": path is not None, "path": path}


def dependency_report() -> tuple[bool, dict[str, dict[str, Any]]]:
    checks = {
        "tesseract": _check_binary("tesseract", settings.enable_ocr),
        "ghostscript": _check_binary("gswin64c" if shutil.which("gswin64c") else "gs", settings.enable_table_extraction),
        "ffmpeg": _check_binary("ffmpeg", settings.enable_multimedia),
        "storage": {
            "required": True,
            "available": settings.storage_root.exists() and settings.storage_root.is_dir(),
            "path": str(settings.storage_root.resolve()),
        },
    }
    ready = all(not item["required"] or item["available"] for item in checks.values())
    return ready, checks
