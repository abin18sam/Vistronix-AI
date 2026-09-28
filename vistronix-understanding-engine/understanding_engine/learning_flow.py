"""
learning_flow.py
=================
FEATURE IMPLEMENTED: #6 Learning Flow Detection.

WHY THIS FILE EXISTS (beginner explanation):
Good teachers don't dump every fact on a student at once - they follow an
order: introduce the idea, define it, show an example, show a diagram,
show the equation, explain where it's used, then test understanding.
This module asks the LLM to look at the whole document and lay out that
teaching order as a numbered sequence of stages, using the document's own
content (not a generic template) wherever possible.
"""

from typing import List

from understanding_engine.config import get_logger
from understanding_engine.llm_client import llm_client
from understanding_engine.schemas import LearningFlowStep
from understanding_engine.utils import get_full_text, get_headings

logger = get_logger(__name__)


SYSTEM_PROMPT = """You are an instructional designer who plans the exact order in which a
topic should be taught to a student for maximum understanding. Given the full text and
heading outline of an educational document, produce an ordered "learning_flow" - a list of
teaching stages such as: Introduction, Definition, Example, Diagram, Equation, Application,
Quiz (you may use a different set of stage names if the document's structure calls for it,
and you may repeat a stage type if the document revisits it, e.g. two "Example" stages).

Each stage should be an object with:
- order: the step number, starting at 1
- stage: the stage's name/type (short, e.g. "Introduction", "Definition", "Worked Example")
- description: one sentence describing what specifically happens at this stage, referencing
  the document's actual content (not generic filler)

Respond with ONLY a valid JSON object matching this exact schema, no markdown fences, no extra text:
{
  "learning_flow": [
    {"order": 1, "stage": "string", "description": "string"},
    ...
  ]
}
"""


def detect_learning_flow(document: dict) -> List[LearningFlowStep]:
    """
    Determines the ideal teaching order for the document's content.

    Args:
        document: The parsed_document.json content as a Python dict.

    Returns:
        A list of validated LearningFlowStep objects, in teaching order.
    """
    logger.info("Detecting learning flow...")
    full_text = get_full_text(document)
    headings = get_headings(document)
    heading_outline = "\n".join(f"- (Page {h['page_number']}) {h['text']}" for h in headings)

    user_prompt = f"""Document heading outline:
{heading_outline}

Full document text:
\"\"\"
{full_text}
\"\"\"

Lay out the ideal learning flow as described in your instructions."""

    raw_result = llm_client.generate_json(SYSTEM_PROMPT, user_prompt)

    try:
        steps = [LearningFlowStep(**step) for step in raw_result.get("learning_flow", [])]
    except Exception as exc:
        logger.error(f"Failed to validate learning flow steps: {exc}")
        raise

    logger.info(f"Detected a {len(steps)}-step learning flow")
    return steps
