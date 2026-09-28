"""
topic_extractor.py
==================
FEATURES IMPLEMENTED: #2 Topic Extraction, #17 Concept Relationships.

WHY THIS FILE EXISTS (beginner explanation):
A chapter is rarely about just ONE thing - it's a tree of topics and
subtopics (e.g. "Motion" -> "Velocity", "Acceleration", "Force"). This
module asks the LLM to break the document down into that tree, and also
to figure out how concepts CONNECT to each other (e.g. "Mass affects
Force", "Force causes Acceleration"). Those connections are what let us
later draw a concept relationship graph for students.
"""

from understanding_engine.config import get_logger
from understanding_engine.llm_client import llm_client
from understanding_engine.schemas import TopicExtraction
from understanding_engine.utils import get_full_text, get_headings

logger = get_logger(__name__)


SYSTEM_PROMPT = """You are an expert curriculum designer. Given the full text and heading
structure of an educational document, extract:

1. main_topics - a list of the main topics covered (short phrases, e.g. "Velocity", "Force")
2. subtopics - a list of objects, each with:
     - name: subtopic name
     - description: a one-sentence description of what it covers
3. concept_relationships - how key concepts relate to or depend on each other, as a list of:
     - from_concept: string
     - to_concept: string
     - relationship: a short verb phrase, e.g. "leads to", "depends on", "is used to calculate"

Respond with ONLY a valid JSON object matching this exact schema, no markdown fences, no extra text:
{
  "main_topics": ["string", ...],
  "subtopics": [{"name": "string", "description": "string"}, ...],
  "concept_relationships": [{"from_concept": "string", "to_concept": "string", "relationship": "string"}, ...]
}
"""


def extract_topics(document: dict) -> TopicExtraction:
    """
    Extracts the topic/subtopic tree and concept relationships for a document.

    Args:
        document: The parsed_document.json content as a Python dict.

    Returns:
        A validated TopicExtraction object.
    """
    logger.info("Extracting topics and concept relationships...")
    full_text = get_full_text(document)
    headings = get_headings(document)
    heading_outline = "\n".join(f"- (Page {h['page_number']}) {h['text']}" for h in headings)

    user_prompt = f"""Document heading outline:
{heading_outline}

Full document text:
\"\"\"
{full_text}
\"\"\"

Extract the topics, subtopics, and concept relationships as described in your instructions."""

    raw_result = llm_client.generate_json(SYSTEM_PROMPT, user_prompt)

    try:
        topics = TopicExtraction(**raw_result)
    except Exception as exc:
        logger.error(f"Failed to validate TopicExtraction: {exc}")
        raise

    logger.info(f"Extracted {len(topics.main_topics)} main topics, {len(topics.subtopics)} subtopics")
    return topics
