"""
teacher_explainer.py
=====================
FEATURE IMPLEMENTED: #5 Teacher Explanation.

WHY THIS FILE EXISTS (beginner explanation):
Textbook paragraphs are often written densely. This module takes EVERY
plain-text paragraph from the document and rewrites it the way a friendly
teacher would explain it out loud to a school student - short sentences,
everyday words, and a relatable tone.

We process paragraphs individually (rather than the whole document at
once) so each explanation stays tightly linked to its source page, and so
long documents don't overflow a single LLM call.
"""

from typing import List

from understanding_engine.config import get_logger
from understanding_engine.llm_client import llm_client
from understanding_engine.schemas import SimplifiedParagraph
from understanding_engine.utils import get_text_paragraphs

logger = get_logger(__name__)


SYSTEM_PROMPT = """You are a friendly, patient school teacher. A student has given you one
paragraph from their textbook and is confused. Rewrite it in very simple language, as if
explaining it out loud to a school student who has never seen this topic before. Use short
sentences, everyday words, and (if helpful) a simple analogy. Keep the meaning 100% accurate -
never simplify to the point of being wrong.

Respond with ONLY a valid JSON object matching this exact schema, no markdown fences, no extra text:
{
  "simple_explanation": "string"
}
"""


def _explain_single_paragraph(paragraph_text: str) -> str:
    """Calls the LLM to simplify one paragraph and returns the plain-language explanation."""
    user_prompt = f"""Original textbook paragraph:
\"\"\"
{paragraph_text}
\"\"\"

Rewrite this in very simple teaching language as described in your instructions."""

    raw_result = llm_client.generate_json(SYSTEM_PROMPT, user_prompt)
    return raw_result.get("simple_explanation", "")


def generate_teacher_explanations(document: dict) -> List[SimplifiedParagraph]:
    """
    Rewrites every text paragraph in the document using simple teaching language.

    Args:
        document: The parsed_document.json content as a Python dict.

    Returns:
        A list of validated SimplifiedParagraph objects, one per paragraph.
    """
    logger.info("Generating teacher-style simplified explanations for every paragraph...")
    paragraphs = get_text_paragraphs(document)

    results: List[SimplifiedParagraph] = []
    for i, para in enumerate(paragraphs):
        logger.info(f"  Simplifying paragraph {i + 1}/{len(paragraphs)} (page {para['page_number']})")
        try:
            simple_explanation = _explain_single_paragraph(para["text"])
        except Exception as exc:
            logger.error(f"  Failed to simplify paragraph on page {para['page_number']}: {exc}")
            simple_explanation = "(Explanation generation failed for this paragraph.)"

        results.append(
            SimplifiedParagraph(
                page_number=para["page_number"],
                original_text=para["text"],
                simple_explanation=simple_explanation,
            )
        )

    logger.info(f"Generated {len(results)} simplified paragraph explanations")
    return results
