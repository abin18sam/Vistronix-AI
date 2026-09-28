"""
concept_extractor.py
=====================
FEATURES IMPLEMENTED: #3 Key Concept Extraction, #10 Definition Detection,
#12 Keyword Extraction, #22 Misconceptions, #23 Practical Applications.

WHY THIS FILE EXISTS (beginner explanation):
This module digs deeper than topic_extractor.py - instead of just naming
topics, it identifies the actual important CONCEPTS a student must
understand (e.g. "Mass", "Force"), explains each one, rates how hard it
is, and connects it to a real-world use. It also separately detects
DEFINITIONS ("what is a technical term?"), a keyword list (good for
search/tagging), and common student MISCONCEPTIONS with corrections.
"""

from understanding_engine.config import get_logger
from understanding_engine.llm_client import llm_client
from understanding_engine.schemas import ConceptExtraction
from understanding_engine.utils import get_full_text

logger = get_logger(__name__)


SYSTEM_PROMPT = """You are a subject-matter expert and experienced teacher. Given the full
text of an educational document, extract:

1. key_concepts - a list of objects, each with:
     - name: the concept name
     - explanation: a clear, accurate explanation of the concept
     - difficulty: "Easy", "Medium", or "Hard"
     - practical_application: one sentence on where this concept is used in real life
2. keywords - a flat list of 8-15 important keywords/tags for this document
3. definitions - a list of objects for every technical term explicitly or implicitly
   defined in the text, each with:
     - term: string
     - definition: string (in the document's own meaning, but clearly written)
     - source_page: the page number where it appears (integer, or null if unclear)
4. misconceptions - a list of 2-5 objects describing COMMON mistakes or misunderstandings
   students have about this material, each with:
     - misconception: what students commonly get wrong
     - clarification: the correct understanding

Respond with ONLY a valid JSON object matching this exact schema, no markdown fences, no extra text:
{
  "key_concepts": [{"name": "string", "explanation": "string", "difficulty": "string", "practical_application": "string"}, ...],
  "keywords": ["string", ...],
  "definitions": [{"term": "string", "definition": "string", "source_page": 1}, ...],
  "misconceptions": [{"misconception": "string", "clarification": "string"}, ...]
}
"""


def extract_concepts(document: dict) -> ConceptExtraction:
    """
    Extracts key concepts, keywords, definitions, and misconceptions.

    Args:
        document: The parsed_document.json content as a Python dict.

    Returns:
        A validated ConceptExtraction object.
    """
    logger.info("Extracting key concepts, keywords, definitions, and misconceptions...")
    full_text = get_full_text(document)

    user_prompt = f"""Full document text:
\"\"\"
{full_text}
\"\"\"

Extract the key concepts, keywords, definitions, and misconceptions as described in your instructions."""

    raw_result = llm_client.generate_json(SYSTEM_PROMPT, user_prompt)

    try:
        concepts = ConceptExtraction(**raw_result)
    except Exception as exc:
        logger.error(f"Failed to validate ConceptExtraction: {exc}")
        raise

    logger.info(
        f"Extracted {len(concepts.key_concepts)} concepts, {len(concepts.keywords)} keywords, "
        f"{len(concepts.definitions)} definitions, {len(concepts.misconceptions)} misconceptions"
    )
    return concepts
