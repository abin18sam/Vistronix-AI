"""
table_understanding.py
========================
FEATURE IMPLEMENTED: #8 Table Understanding.

WHY THIS FILE EXISTS (beginner explanation):
Tables pack in a lot of information very densely (rows and columns), but
students often struggle to "read" what a table is actually telling them.
This module converts each raw table (headers + rows) into a natural,
spoken-language explanation - the kind of sentence a teacher would say
while pointing at the table.
"""

from typing import List

from understanding_engine.config import get_logger
from understanding_engine.llm_client import llm_client
from understanding_engine.schemas import TableExplanation
from understanding_engine.utils import get_tables, find_nearby_context

logger = get_logger(__name__)


SYSTEM_PROMPT = """You are a teacher explaining a data table to a student. Given a table's
headers, rows, and surrounding page context, produce:

1. table_summary - a one-sentence factual summary of what the table contains
2. natural_language_explanation - 2-4 sentences explaining the table's meaning and any
   trend, comparison, or pattern visible in the data, in plain spoken language
   (e.g. "The table shows that force increases when mass increases.")

Respond with ONLY a valid JSON object matching this exact schema, no markdown fences, no extra text:
{
  "table_summary": "string",
  "natural_language_explanation": "string"
}
"""


def _format_table_as_text(headers: list, rows: list) -> str:
    """Turns a headers/rows table structure into a readable plain-text grid for the prompt."""
    lines = [" | ".join(str(h) for h in headers)]
    for row in rows:
        lines.append(" | ".join(str(cell) for cell in row))
    return "\n".join(lines)


def _explain_single_table(table_text: str, context: str) -> dict:
    """Calls the LLM to explain one table and returns the raw explanation dict."""
    user_prompt = f"""Table:
{table_text}

Surrounding page context: "{context}"

Explain this table as described in your instructions."""
    return llm_client.generate_json(SYSTEM_PROMPT, user_prompt)


def generate_table_explanations(document: dict) -> List[TableExplanation]:
    """
    Converts every table in the document into a natural-language explanation.

    Args:
        document: The parsed_document.json content as a Python dict.

    Returns:
        A list of validated TableExplanation objects.
    """
    logger.info("Analyzing tables...")
    tables = get_tables(document)

    results: List[TableExplanation] = []
    for i, table in enumerate(tables):
        logger.info(f"  Explaining table {i + 1}/{len(tables)} (page {table['page_number']})")
        table_text = _format_table_as_text(table["headers"], table["rows"])
        context = find_nearby_context(document, table["page_number"])

        try:
            raw = _explain_single_table(table_text, context)
            results.append(
                TableExplanation(
                    table_summary=raw.get("table_summary", ""),
                    natural_language_explanation=raw.get("natural_language_explanation", ""),
                    source_page=table["page_number"],
                )
            )
        except Exception as exc:
            logger.error(f"  Failed to explain table on page {table['page_number']}: {exc}")

    logger.info(f"Generated explanations for {len(results)} tables")
    return results
