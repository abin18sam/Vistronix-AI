# VisTronix AI — Document Understanding Engine (Stage 2)

This project is a **sibling folder** of your existing PDF Parser module and
picks up exactly where it leaves off:

```
dev/
├── vistronix-pdf-extractor/            <- Stage 1 (already built)
│   ├── main.py                             GET / , POST /upload-pdf
│   ├── parser/                             detector, digital/scanned parsers,
│   │                                       image/table/equation extraction
│   ├── uploads/                            your uploaded PDFs land here
│   ├── extracted_images/                   page{N}_img{K}.png files
│   └── output/
│       └── parsed_document.json        <- Stage 1's OUTPUT
│
└── vistronix-understanding-engine/     <- Stage 2 (THIS project)
    ├── main.py                             GET / , POST /understand-latest
    ├── understanding_engine/               classification, topics, concepts,
    │                                       summaries, equations, images, tables,
    │                                       questions, flashcards, scenes...
    └── output/
        └── knowledge_graph.json        <- Stage 2's OUTPUT (final result)
```

`vistronix-understanding-engine` reads `parsed_document.json` straight out of
`vistronix-pdf-extractor/output/`, and reads images straight out of
`vistronix-pdf-extractor/extracted_images/` — no manual copying between the
two projects.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your OPENAI_API_KEY (or GEMINI_API_KEY + LLM_PROVIDER=gemini)
```

By default, `PARSER_PROJECT_DIR=../vistronix-pdf-extractor` in `.env` — this
assumes the two projects sit side by side in the same parent folder, exactly
like the diagram above. If your layout differs, change that one line.

## Run the two modules back-to-back

```bash
# Terminal 1 - PDF Parser module (stage 1), typically on port 8000
cd vistronix-pdf-extractor
uvicorn main:app --reload --port 8000

# Terminal 2 - Understanding Engine (stage 2), runs on 8001 to avoid clashing
cd vistronix-understanding-engine
uvicorn main:app --reload --port 8001
```

Then:

```bash
# Stage 1: parse a PDF
curl -X POST http://localhost:8000/upload-pdf -F "file=@mydoc.pdf"
# -> writes vistronix-pdf-extractor/output/parsed_document.json
#    and vistronix-pdf-extractor/extracted_images/*.png

# Stage 2: understand it (zero arguments needed - it finds stage 1's output automatically)
curl -X POST http://localhost:8001/understand-latest
# -> writes vistronix-understanding-engine/output/knowledge_graph.json
```

## All endpoints

- `GET /` / `GET /health` — health check. Also reports whether it can currently
  see the parser's `parsed_document.json` (useful for debugging path issues).
- `POST /understand-latest` — **the main entry point.** Reads
  `parsed_document.json` + `extracted_images/` directly from the PDF Parser
  module's output folders (via `PARSER_PROJECT_DIR` in `.env`) and runs the
  full pipeline. No arguments needed.
- `POST /process-document` — upload a `parsed_document.json` file directly
  (e.g. from a different machine). Falls back to context-only image inference
  since there's no local image folder to look at.
- `POST /process-document-path?path=...&images_directory=...` — point at any
  `parsed_document.json` + images folder on disk, anywhere.
- `POST /generate-multimedia?path=...` — generate the new Phase 3-6 outputs:
  storyboard JSON, SVG visual assets, voiceover text/manifest, and a video preview manifest.

## Run without the API (quick test)

```python
import json
from understanding_engine.knowledge_graph_builder import build_knowledge_graph, save_knowledge_graph
from understanding_engine.config import settings

document = json.load(open(settings.INPUT_JSON_PATH))   # reads from the parser's output
kg = build_knowledge_graph(document, images_directory=settings.PARSER_IMAGES_DIR)
save_knowledge_graph(kg)
```

A standalone example input (no parser required) is also included at
`sample_input/parsed_document.json` if you want to test the engine in
isolation, e.g. `document = json.load(open("sample_input/parsed_document.json"))`.

## Project structure

```
main.py                                 FastAPI app - reads Stage 1's output, writes knowledge_graph.json
understanding_engine/
  config.py                             All settings + PARSER_PROJECT_DIR wiring, .env driven
  llm_client.py                         Unified OpenAI/Gemini gateway + retries + JSON safety
  schemas.py                            Pydantic contracts for every module + final KnowledgeGraph
  utils.py                              Shared helpers for reading parsed_document.json
  document_classifier.py                #1 Classification, #15 Prerequisites, #16 Objectives
  topic_extractor.py                    #2 Topics/Subtopics, #17 Concept Relationships
  concept_extractor.py                  #3 Key Concepts, #10 Definitions, #12 Keywords, #22 Misconceptions
  summary_generator.py                  #4 Summaries, #11 Important Points
  teacher_explainer.py                  #5 Teacher-style paragraph rewrites
  learning_flow.py                      #6 Learning Flow Detection
  equation_understanding.py             #9 Equation Understanding (+ animation suggestions)
  image_understanding.py                #7 Image Understanding (real vision against
                                         extracted_images/, or context fallback)
  table_understanding.py                #8 Table Understanding
  question_generator.py                 #13 MCQ / short / long / T-F / fill-in-the-blank
  flashcard_generator.py                #14 Flashcards
  scene_generator.py                    #18 Scenes, #19 Narration, #20 Time Estimation
  knowledge_graph_builder.py            Orchestrates every module -> knowledge_graph.json
sample_input/parsed_document.json       Standalone example input (no parser needed)
output/                                 knowledge_graph.json is written here
```

## Notes on design decisions

- **Reads Stage 1's output directly** — `settings.INPUT_JSON_PATH` and
  `settings.PARSER_IMAGES_DIR` are derived from `PARSER_PROJECT_DIR`, so this
  engine finds `parsed_document.json` and `extracted_images/` with zero
  manual wiring, mirroring how the parser's own `main.py` uses
  `UPLOAD_DIR` / `IMAGE_DIR` / `OUTPUT_DIR` constants.
- **One LLM gateway (`llm_client.py`)** — every module calls
  `llm_client.generate_json(...)`. Switching OpenAI -> Gemini is one `.env` edit.
- **Pydantic everywhere** — every LLM response is validated immediately against
  a strict schema, so malformed output fails loudly at the source.
- **Per-item calls for equations/images/tables** — each gets its own focused
  LLM call with local page context, so one bad item doesn't sink the whole document.
- **Image understanding has a real vision path** — when running via
  `/understand-latest`, images are read straight from the parser's
  `extracted_images/page{N}_img{K}.png` files and actually looked at (OpenAI
  vision). Falls back to context-only inference if a file is missing or you're
  on Gemini/text-only.
- **`knowledge_graph_builder.py` is the only file that knows the full pipeline
  order** — every module is independent and testable on its own.
