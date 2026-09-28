"""
document_classifier.py
=======================
FEATURES IMPLEMENTED: #1 Document Classification, #15 Prerequisite
Detection, #16 Learning Objectives.

WHY THIS FILE EXISTS (beginner explanation):
Before we can teach a student anything, we need to know WHAT the document
is about at a high level - like a teacher glancing at a chapter and
immediately knowing "oh, this is a Beginner Physics chapter on Motion."

This module sends the document's full text to the LLM and asks it to act
like an experienced teacher doing exactly that: identifying the subject,
chapter, topic, difficulty, domain, what a student needs to already know
(prerequisites), and what they should be able to do afterward (learning
objectives).
"""

from understanding_engine.config import get_logger
from understanding_engine.llm_client import llm_client
from understanding_engine.schemas import DocumentClassification
from understanding_engine.utils import get_full_text

logger = get_logger(__name__)


SYSTEM_PROMPT = """You are a Senior Teacher and Curriculum Expert with decades of experience
classifying educational documents across all subjects (Physics, Computer Science,
Mathematics, Biology, Chemistry, etc.).

Given the full text of an educational document, analyze it exactly like a teacher
preparing to teach this chapter to students. Determine:

1. subject - the broad academic subject (e.g. "Physics", "Computer Science", "Deep Learning")
2. chapter - the chapter or unit name this content belongs to
3. topic - the specific main topic covered
4. difficulty_level - one of: "Beginner", "Intermediate", "Advanced"
5. educational_domain - the broader domain (e.g. "STEM", "Computer Science", "Humanities")
6. learning_objectives - a list of 3-6 concrete things a student will be able to DO after
   studying this document (start each with a verb, e.g. "Explain...", "Calculate...", "Derive...")
7. prerequisites - a list of concepts/skills a student should already know before starting
   this document (e.g. "Basic algebra", "Understanding of neural network layers")

Respond with ONLY a valid JSON object matching this exact schema, no markdown fences, no extra text:
{
  "subject": "string",
  "chapter": "string",
  "topic": "string",
  "difficulty_level": "string",
  "educational_domain": "string",
  "learning_objectives": ["string", ...],
  "prerequisites": ["string", ...]
}
"""


def classify_document(document: dict) -> DocumentClassification:
    """
    Classifies the document's subject/chapter/topic/difficulty, and
    generates prerequisites + learning objectives.

    Args:
        document: The parsed_document.json content as a Python dict.

    Returns:
        A validated DocumentClassification object.
    """
    logger.info("Classifying document...")
    full_text = get_full_text(document)

    user_prompt = f"""Document name: {document.get('document_name', 'Unknown')}

Full document text:
\"\"\"
{full_text}
\"\"\"

Analyze this document and return the classification JSON described in your instructions."""

    raw_result = llm_client.generate_json(SYSTEM_PROMPT, user_prompt)

    try:
        classification = DocumentClassification(**raw_result)
    except Exception as exc:
        logger.error(f"Failed to validate DocumentClassification: {exc}")
        raise

    logger.info(
        f"Classified as subject='{classification.subject}' "
        f"chapter='{classification.chapter}' difficulty='{classification.difficulty_level}'"
    )
    return classification
