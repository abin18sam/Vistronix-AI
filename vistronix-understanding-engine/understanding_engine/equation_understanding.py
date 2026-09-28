"""
equation_understanding.py
==========================
FEATURE IMPLEMENTED: #9 Equation Understanding.

WHY THIS FILE EXISTS (beginner explanation):
An equation like "F = ma" means nothing to a student unless someone
explains what each letter stands for, what units it uses, and how it
connects to something they can picture in real life. This module takes
every equation the parser found and, using the surrounding page text for
context, asks the LLM to break it down completely - including a
suggested animation idea, which is useful later if VisTronix generates
teaching videos.
"""

from typing import List

from understanding_engine.config import get_logger
from understanding_engine.llm_client import llm_client
from understanding_engine.schemas import EquationExplanation
from understanding_engine.utils import get_equations, find_nearby_context

logger = get_logger(__name__)


SYSTEM_PROMPT = """You are a physics/math/engineering teacher explaining an equation to a
student for the first time. Given an equation and the surrounding page context, extract:

1. formula - the equation exactly as written
2. variables - a list of strings, one per variable, in the form "symbol: what it represents"
3. meaning - a plain-English sentence explaining what the equation calculates
4. units - the units involved (e.g. "Force in Newtons (N), Mass in kg, Acceleration in m/s^2")
   or "N/A" if not applicable (e.g. for a pure math/ML equation)
5. real_life_explanation - a relatable real-world example showing this equation in action
6. suggested_animation - a one-sentence idea for a simple animation/visual that would help
   teach this equation (e.g. "A person pushing a box across a floor, with arrows showing force and acceleration")

Respond with ONLY a valid JSON object matching this exact schema, no markdown fences, no extra text:
{
  "variables": ["string", ...],
  "meaning": "string",
  "units": "string",
  "real_life_explanation": "string",
  "suggested_animation": "string"
}
"""


def _explain_single_equation(formula: str, context: str) -> dict:
    """Calls the LLM to explain one equation and returns the raw explanation dict."""
    user_prompt = f"""Equation: {formula}

Surrounding page context: "{context}"

Explain this equation as described in your instructions."""

    return llm_client.generate_json(SYSTEM_PROMPT, user_prompt)


def generate_equation_explanations(document: dict) -> List[EquationExplanation]:
    """
    Analyzes every equation in the document and produces a full explanation for each.

    Args:
        document: The parsed_document.json content as a Python dict.

    Returns:
        A list of validated EquationExplanation objects.
    """
    logger.info("Analyzing equations...")
    equations = get_equations(document)

    results: List[EquationExplanation] = []
    for i, eq in enumerate(equations):
        logger.info(f"  Explaining equation {i + 1}/{len(equations)}: {eq['text']}")
        context = find_nearby_context(document, eq["page_number"])
        try:
            raw = _explain_single_equation(eq["text"], context)
            results.append(
                EquationExplanation(
                    formula=eq["text"],
                    variables=raw.get("variables", []),
                    meaning=raw.get("meaning", ""),
                    units=raw.get("units", "N/A"),
                    real_life_explanation=raw.get("real_life_explanation", ""),
                    suggested_animation=raw.get("suggested_animation", ""),
                    source_page=eq["page_number"],
                )
            )
        except Exception as exc:
            logger.error(f"  Failed to explain equation '{eq['text']}': {exc}")

    logger.info(f"Generated explanations for {len(results)} equations")
    return results
