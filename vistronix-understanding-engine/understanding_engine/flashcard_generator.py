"""
flashcard_generator.py
=======================
FEATURE IMPLEMENTED: #14 Flashcards.

WHY THIS FILE EXISTS (beginner explanation):
Flashcards are one of the most effective ways to memorize facts, terms,
and formulas. This module distills the document down into short
question -> answer pairs a student could flip through while revising -
much more compact than the full question set in question_generator.py.
"""

from understanding_engine.config import get_logger
from understanding_engine.llm_client import llm_client
from understanding_engine.schemas import FlashcardOutput
from understanding_engine.utils import get_full_text

logger = get_logger(__name__)


SYSTEM_PROMPT = """You are a teacher creating revision flashcards for students. Given the full
text of an educational document, generate 10 flashcards covering its most important terms,
definitions, formulas, and facts. Each flashcard must have:
- question: a short prompt (a term, "What is...?", "Define...", or "State the formula for...")
- answer: a concise, accurate answer (1-2 sentences or a formula)

Cover a good spread of the document's content - don't repeat the same concept twice.

Respond with ONLY a valid JSON object matching this exact schema, no markdown fences, no extra text:
{
  "flashcards": [{"question": "string", "answer": "string"}, ...]
}
"""


def generate_flashcards(document: dict) -> FlashcardOutput:
    """
    Generates revision flashcards (question/answer pairs) for the document.

    Args:
        document: The parsed_document.json content as a Python dict.

    Returns:
        A validated FlashcardOutput object.
    """
    logger.info("Generating flashcards...")
    full_text = get_full_text(document)

    user_prompt = f"""Full document text:
\"\"\"
{full_text}
\"\"\"

Generate 10 flashcards as described in your instructions."""

    raw_result = llm_client.generate_json(SYSTEM_PROMPT, user_prompt)

    try:
        flashcards = FlashcardOutput(**raw_result)
    except Exception as exc:
        logger.error(f"Failed to validate FlashcardOutput: {exc}")
        raise

    logger.info(f"Generated {len(flashcards.flashcards)} flashcards")
    return flashcards
