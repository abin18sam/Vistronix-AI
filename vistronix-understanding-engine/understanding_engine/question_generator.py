"""
question_generator.py
======================
FEATURE IMPLEMENTED: #13 Question Generation.

WHY THIS FILE EXISTS (beginner explanation):
Students learn best when they test themselves. This module asks the LLM
to act like an exam-setting teacher and produce a full spread of question
types (MCQs with a correct answer marked, short-answer, long-answer,
true/false, and fill-in-the-blanks) that are directly answerable using
the document's content - no outside knowledge required.
"""

from understanding_engine.config import get_logger
from understanding_engine.llm_client import llm_client
from understanding_engine.schemas import QuestionSet
from understanding_engine.utils import get_full_text

logger = get_logger(__name__)


SYSTEM_PROMPT = """You are an experienced exam-setting teacher. Given the full text of an
educational document, generate a complete question set that a teacher could hand out as a
worksheet or quiz. Every question must be answerable using ONLY the document's content.

Generate:
1. mcqs - 5 multiple-choice questions, each an object with:
     - question: string
     - options: a list of exactly 4 answer choices (strings)
     - correct_answer: the correct option, copied exactly from "options"
2. short_answer_questions - 5 questions answerable in 1-3 sentences
3. long_answer_questions - 3 questions requiring a paragraph-length answer
4. true_false - 5 true/false statements (phrase them as statements, not questions)
5. fill_in_the_blanks - 5 sentences with a key term replaced by "_____"

Respond with ONLY a valid JSON object matching this exact schema, no markdown fences, no extra text:
{
  "mcqs": [{"question": "string", "options": ["string", "string", "string", "string"], "correct_answer": "string"}, ...],
  "short_answer_questions": ["string", ...],
  "long_answer_questions": ["string", ...],
  "true_false": ["string", ...],
  "fill_in_the_blanks": ["string", ...]
}
"""


def generate_questions(document: dict) -> QuestionSet:
    """
    Generates MCQs, short/long answer questions, true/false, and fill-in-the-blanks.

    Args:
        document: The parsed_document.json content as a Python dict.

    Returns:
        A validated QuestionSet object.
    """
    logger.info("Generating question set...")
    full_text = get_full_text(document)

    user_prompt = f"""Full document text:
\"\"\"
{full_text}
\"\"\"

Generate the full question set as described in your instructions."""

    raw_result = llm_client.generate_json(SYSTEM_PROMPT, user_prompt)

    try:
        questions = QuestionSet(**raw_result)
    except Exception as exc:
        logger.error(f"Failed to validate QuestionSet: {exc}")
        raise

    logger.info(
        f"Generated {len(questions.mcqs)} MCQs, {len(questions.short_answer_questions)} short-answer, "
        f"{len(questions.long_answer_questions)} long-answer, {len(questions.true_false)} true/false, "
        f"{len(questions.fill_in_the_blanks)} fill-in-the-blank questions"
    )
    return questions
