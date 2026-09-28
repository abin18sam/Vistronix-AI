"""
main.py
=======
FastAPI application exposing the AI Document Understanding Engine - stage 2
of the VisTronix AI pipeline.

WHY THIS FILE EXISTS (beginner explanation):
This is the "front door" of the second module, and it's built to sit
directly next to your existing PDF Parser module as a sibling folder:

    vistronix-pdf-extractor/        <- stage 1 (already built)
      main.py                          GET / , POST /upload-pdf
      output/parsed_document.json      <- writes this
      extracted_images/                <- writes these

    vistronix-understanding-engine/ <- stage 2 (this project)
      main.py                          GET / , POST /understand-latest  <- reads the above
      output/knowledge_graph.json      <- writes this

Endpoints:
    GET  /                       - health check (same convention as the PDF Parser's main.py)
    GET  /health                 - alias for the above
    POST /understand-latest      - zero-argument convenience call: reads
                                    parsed_document.json + extracted_images/ straight
                                    from the PDF Parser module's output folders and
                                    runs the full pipeline. This is the "just call it"
                                    endpoint for local dev, mirroring /upload-pdf.
    POST /process-document       - upload a parsed_document.json file directly
    POST /process-document-path  - point to a parsed_document.json anywhere on disk

Run locally with:
    uvicorn main:app --reload --port 8000
"""

import json
import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from understanding_engine.config import settings, configure_logging, get_logger
from understanding_engine.knowledge_graph_builder import build_knowledge_graph, save_knowledge_graph
from understanding_engine.storyboard_generator import generate_storyboard
from understanding_engine.visual_asset_generator import generate_visual_assets
from understanding_engine.voice_generator import generate_voiceover
from understanding_engine.video_generator import generate_video

configure_logging()
logger = get_logger(__name__)

# ----------------------------------------------------------------------
# Directory constants
# ----------------------------------------------------------------------
# Mirrors the UPLOAD_DIR / IMAGE_DIR / OUTPUT_DIR pattern used in the PDF
# Parser module's main.py, but pointed at the PARSER's folders (this
# engine reads from them) and this engine's OWN output folder (it writes
# there). Defaults come from understanding_engine/config.py and can be
# overridden via .env - see settings.PARSER_PROJECT_DIR.
PARSER_OUTPUT_JSON = settings.INPUT_JSON_PATH      # e.g. ../vistronix-pdf-extractor/output/parsed_document.json
PARSER_IMAGES_DIR = settings.PARSER_IMAGES_DIR      # e.g. ../vistronix-pdf-extractor/extracted_images
OUTPUT_DIR = os.path.dirname(settings.OUTPUT_JSON_PATH) or "output"

app = FastAPI(
    title="VisTronix AI - Document Understanding Engine",
    description=(
        "Stage 2 of the VisTronix AI pipeline. Reads parsed_document.json (written by "
        "the PDF Parser module, vistronix-pdf-extractor) and produces knowledge_graph.json: "
        "a teacher-quality structured understanding of the document's educational content."
    ),
    version="1.0.0",
)


def _health_payload() -> dict:
    return {
        "status": "ok",
        "service": "understanding-engine",
        "llm_provider": settings.LLM_PROVIDER,
        "parser_output_json": os.path.abspath(PARSER_OUTPUT_JSON),
        "parser_output_json_exists": os.path.exists(PARSER_OUTPUT_JSON),
        "parser_images_dir": os.path.abspath(PARSER_IMAGES_DIR),
    }


@app.get("/")
def health_check_root():
    """Health check at the root path, same convention as the PDF Parser module's main.py."""
    return _health_payload()


@app.get("/health")
def health_check():
    """Alias for GET / - some tools/monitors expect a dedicated /health path."""
    return _health_payload()


@app.post("/understand-latest")
def understand_latest():
    """
    Zero-argument convenience endpoint for local development.

    Reads parsed_document.json directly from the PDF Parser module's output
    folder (settings.INPUT_JSON_PATH, defaults to
    ../vistronix-pdf-extractor/output/parsed_document.json) and uses its
    extracted_images/ folder for image analysis. This lets you run the two
    modules back-to-back with a single call each:

        POST http://localhost:8001/upload-pdf   (PDF Parser module)
        POST http://localhost:8002/understand-latest   (this module)

    with no file copying or path-typing in between.
    """
    if not os.path.exists(PARSER_OUTPUT_JSON):
        raise HTTPException(
            status_code=404,
            detail=(
                f"No parsed_document.json found at '{os.path.abspath(PARSER_OUTPUT_JSON)}'. "
                "Run the PDF Parser module first (POST /upload-pdf on vistronix-pdf-extractor), "
                "or override the path via the PARSER_PROJECT_DIR / INPUT_JSON_PATH settings in .env."
            ),
        )

    try:
        with open(PARSER_OUTPUT_JSON, "r", encoding="utf-8") as f:
            document = json.load(f)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"parsed_document.json is not valid JSON: {exc}") from exc

    logger.info(f"Reading parsed_document.json from PDF Parser output: {PARSER_OUTPUT_JSON}")
    return _run_pipeline_and_respond(document, images_directory=PARSER_IMAGES_DIR)


@app.post("/process-document")
async def process_document(file: UploadFile = File(...)):
    """
    Accepts an uploaded parsed_document.json file, runs the full understanding
    pipeline on it, and returns the resulting knowledge_graph.json content directly
    in the response (it is also saved to disk under settings.OUTPUT_JSON_PATH).

    Note: since no local image folder is known for an uploaded file, image
    understanding falls back to context-only inference. Use /understand-latest
    instead if you want real vision analysis against the parser's saved images.
    """
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Please upload a .json file (parsed_document.json).")

    try:
        raw_bytes = await file.read()
        document = json.loads(raw_bytes)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Uploaded file is not valid JSON: {exc}") from exc

    return _run_pipeline_and_respond(document)


@app.post("/generate-multimedia")
def generate_multimedia(path: str = "", images_directory: str = ""):
    """Generate a storyboard, visual assets, voiceover, and video preview from the latest knowledge graph."""
    output_dir = os.path.dirname(settings.OUTPUT_JSON_PATH) or "output"

    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            document = json.load(handle)
    else:
        if not os.path.exists(PARSER_OUTPUT_JSON):
            raise HTTPException(status_code=404, detail="No parsed document found for multimedia generation")
        with open(PARSER_OUTPUT_JSON, "r", encoding="utf-8") as handle:
            document = json.load(handle)

    scene_plan = [
        {"scene_number": idx, "title": f"Scene {idx}", "description": "Educational scene", "narration": f"Narration for scene {idx}", "estimated_seconds": 20}
        for idx in range(1, 4)
    ]
    storyboard = generate_storyboard(document, scene_plan)
    assets = generate_visual_assets(storyboard, output_dir=output_dir)
    voiceover = generate_voiceover(storyboard, output_dir=output_dir)
    video = generate_video(storyboard, assets, voiceover, output_dir=output_dir)

    return JSONResponse(
        content={
            "message": "Multimedia assets generated successfully",
            "output_dir": os.path.abspath(output_dir),
            "storyboard": storyboard.model_dump(),
            "assets": assets.model_dump(),
            "voiceover": voiceover.model_dump(),
            "video": video.model_dump(),
        }
    )


@app.post("/process-document-path")
def process_document_path(path: str, images_directory: str = ""):
    """
    Points to a parsed_document.json file anywhere on disk, with an optional
    images_directory (e.g. an extracted_images/ folder) for real vision analysis.

    Example: POST /process-document-path?path=C:/data/parsed_document.json&images_directory=C:/data/extracted_images
    """
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            document = json.load(f)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"File is not valid JSON: {exc}") from exc

    return _run_pipeline_and_respond(document, images_directory=images_directory)


def _run_pipeline_and_respond(document: dict, images_directory: str = "") -> JSONResponse:
    """Shared logic: runs the pipeline, saves the output, and returns it as JSON."""
    try:
        knowledge_graph = build_knowledge_graph(document, images_directory=images_directory)
        output_path = save_knowledge_graph(knowledge_graph)
    except Exception as exc:
        logger.error(f"Pipeline failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Understanding engine failed: {exc}") from exc

    return JSONResponse(
        content={
            "message": "knowledge_graph.json generated successfully",
            "output_path": os.path.abspath(output_path),
            "knowledge_graph": knowledge_graph.model_dump(),
        }
    )


if __name__ == "__main__":
    import uvicorn

    # Runs on 8001 by default so it doesn't collide with the PDF Parser module
    # if you run both locally at the same time (that one typically uses 8000).
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
