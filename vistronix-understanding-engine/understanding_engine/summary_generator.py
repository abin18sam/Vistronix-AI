"""
summary_generator.py
=====================
FEATURES IMPLEMENTED: #4 Automatic Summary, #11 Important Points.

WHY THIS FILE EXISTS (beginner explanation):
Different situations need different lengths of summary - a busy teacher
wants a one-line summary, a student revising before an exam wants a
detailed one, and a struggling student wants it explained super simply.
This module generates all three, plus three focused "point lists" that
help with revision and exam prep specifically.
"""

from understanding_engine.config import get_logger
from understanding_engine.llm_client import llm_client
from understanding_engine.schemas import SummaryOutput
from understanding_engine.utils import get_full_text

logger = get_logger(__name__)


SYSTEM_PROMPT = """You are an experienced teacher preparing study materials for your students.
Given the full text of an educational document, generate:

1. short_summary - a 2-3 sentence summary capturing the essence of the document
2. detailed_summary - a thorough paragraph-level summary covering every major section
3. student_friendly_explanation - the same content explained in very simple, encouraging
   language suitable for a student encountering this topic for the first time
4. important_points - an object with three lists:
     - most_important: the 3-6 most critical points a student must remember
     - revision_points: bullet points ideal for last-minute revision
     - exam_points: points that are commonly tested in exams

Respond with ONLY a valid JSON object matching this exact schema, no markdown fences, no extra text:
{
  "short_summary": "string",
  "detailed_summary": "string",
  "student_friendly_explanation": "string",
  "important_points": {
    "most_important": ["string", ...],
    "revision_points": ["string", ...],
    "exam_points": ["string", ...]
  }
}
"""


def generate_summary(document: dict) -> SummaryOutput:
    """
    Generates short/detailed/student-friendly summaries plus revision points.

    Args:
        document: The parsed_document.json content as a Python dict.

    Returns:
        A validated SummaryOutput object.
    """
    logger.info("Generating summaries and important points...")
    full_text = get_full_text(document)

    user_prompt = f"""Full document text:
\"\"\"
{full_text}
\"\"\"

Generate the summaries and important points as described in your instructions."""

    raw_result = llm_client.generate_json(SYSTEM_PROMPT, user_prompt)

    try:
        summary = SummaryOutput(**raw_result)
    except Exception as exc:
        logger.error(f"Failed to validate SummaryOutput: {exc}")
        raise

    logger.info("Summary generation complete")
    return summary
