r"""
equation_detector.py
========================
Very simple, rule-based detector for equation/formula-like text.

We do NOT attempt to parse or solve math here - the goal (per spec) is
just to flag text blocks that *look like* a formula so downstream tools
(or a human) can treat them specially. This works well for typical
notes/textbook PDFs like "F = ma" or "6CO2 + 6H2O -> C6H12O6 + 6O2".

Rules used to flag a block of text as an equation:
    1. Contains a mathematical operator/symbol: = + - / ^ * ∑ √ ± ≤ ≥ ≠ →
    2. Contains a LaTeX-like pattern: \frac, \sum, $...$, ^{...}, _{...}
    3. Is short-ish (equations are rarely long paragraphs) AND has a
       decent ratio of symbol/digit characters to letters.

Any text block whose "type" is currently "text" (not already a heading)
and matches these rules gets reclassified with type = "equation".
Headings are left alone, since a heading like "Chapter 2: Equations of
Motion" shouldn't be mislabeled just because it contains a colon or digit.
"""

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger("vistronix.equation_detector")

# Symbols/operators that strongly suggest a mathematical or chemical formula.
EQUATION_SYMBOLS = re.compile(r"[=+\-/^∑√±≤≥≠→×÷∫∂∆πθα β]")

# LaTeX-style formula markers.
LATEX_PATTERNS = re.compile(r"(\\frac|\\sum|\\int|\$.+\$|\^\{.*\}|_\{.*\})")

# Maximum word count for a block to still be considered "equation-like".
# Long paragraphs that merely happen to contain a "-" or "/" should NOT
# be flagged as equations.
MAX_EQUATION_WORDS = 15

# Minimum ratio of (digits + symbols) to total non-space characters for a
# short line to be considered equation-like, avoiding false positives on
# short but ordinary sentences (e.g. "See page 5-6.").
MIN_SYMBOL_DIGIT_RATIO = 0.15


def _looks_like_equation(text: str) -> bool:
    """Apply the rule set described above to decide if `text` is equation-like."""
    stripped = text.strip()
    if not stripped:
        return False

    word_count = len(stripped.split())
    if word_count > MAX_EQUATION_WORDS:
        return False

    has_latex = bool(LATEX_PATTERNS.search(stripped))
    if has_latex:
        return True

    has_symbol = bool(EQUATION_SYMBOLS.search(stripped))
    if not has_symbol:
        return False

    non_space_chars = [c for c in stripped if not c.isspace()]
    if not non_space_chars:
        return False

    symbol_or_digit_count = sum(
        1 for c in non_space_chars if c.isdigit() or EQUATION_SYMBOLS.match(c)
    )
    ratio = symbol_or_digit_count / len(non_space_chars)

    return ratio >= MIN_SYMBOL_DIGIT_RATIO


def tag_equations(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Scan every "text" element across all pages and reclassify equation-like
    ones as type = "equation".

    Args:
        pages: The list of page dicts (already containing text/heading/
               image/table elements).

    Returns:
        The same `pages` list, with some "text" elements' "type" changed
        to "equation" where the heuristic matched.
    """
    equation_count = 0

    for page in pages:
        for element in page.get("elements", []):
            if element.get("type") != "text":
                continue  # only re-classify plain text blocks, not headings/images/tables

            if _looks_like_equation(element["text"]):
                element["type"] = "equation"
                equation_count += 1

    logger.info("Tagged %d element(s) as equations", equation_count)
    return pages
