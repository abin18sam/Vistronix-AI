"""
scene_generator.py
====================
FEATURES IMPLEMENTED: #18 Scene Suggestions, #19 Voice Narration Script,
#20 Time Estimation.

WHY THIS FILE EXISTS (beginner explanation):
VisTronix AI's longer-term goal is to turn a document into a teaching
VIDEO. Before any video can be generated, someone (or something) needs to
plan it out like a storyboard: what happens in each scene, what the
narrator says while it happens, and how long it should last. This module
asks the LLM to act like a video director/scriptwriter and produce
exactly that plan, grounded in the document's actual teaching flow.
"""

from understanding_engine.config import get_logger
from understanding_engine.llm_client import llm_client
from understanding_engine.schemas import SceneOutput
from understanding_engine.utils import get_full_text

logger = get_logger(__name__)


SYSTEM_PROMPT = """You are a scriptwriter and instructional video director. Given the full
text of an educational document, storyboard a short teaching video covering the entire
document. Produce 5-10 scenes. Each scene is an object with:

- scene_number: sequential integer starting at 1
- title: a short scene title (e.g. "Teacher Introduction", "Show Block on Table")
- description: what visually happens on screen during this scene
- narration: the exact words a voice narrator would say during this scene (1-3 sentences,
  natural spoken tone, no stage directions)
- estimated_seconds: a realistic integer duration for this scene based on how long the
  narration would take to speak aloud plus time to absorb any visual (typically 10-45)

Cover the document's content in the same order it should be taught (introduction, core
concepts, examples/diagrams/equations, real-world applications, and a short recap/quiz scene).

Respond with ONLY a valid JSON object matching this exact schema, no markdown fences, no extra text:
{
  "scene_plan": [
    {"scene_number": 1, "title": "string", "description": "string", "narration": "string", "estimated_seconds": 20},
    ...
  ]
}
"""


def generate_scene_plan(document: dict) -> SceneOutput:
    """
    Generates a scene-by-scene video storyboard with narration and timing.

    Args:
        document: The parsed_document.json content as a Python dict.

    Returns:
        A validated SceneOutput object.
    """
    logger.info("Generating scene plan, narration, and timing...")
    full_text = get_full_text(document)

    user_prompt = f"""Full document text:
\"\"\"
{full_text}
\"\"\"

Storyboard a teaching video for this document as described in your instructions."""

    raw_result = llm_client.generate_json(SYSTEM_PROMPT, user_prompt)

    try:
        scenes = SceneOutput(**raw_result)
    except Exception as exc:
        logger.error(f"Failed to validate SceneOutput: {exc}")
        raise

    total_seconds = sum(s.estimated_seconds for s in scenes.scene_plan)
    logger.info(f"Generated {len(scenes.scene_plan)} scenes, total estimated runtime {total_seconds}s")
    return scenes
