"""
image_understanding.py
=======================
FEATURE IMPLEMENTED: #7 Image Understanding.

WHY THIS FILE EXISTS (beginner explanation):
A diagram in a textbook (like a neural network architecture or a labeled
picture of a leaf) carries meaning that plain text extraction misses.
This module explains every image the PDF Parser found.

TWO MODES ARE SUPPORTED:
1. Vision mode (preferred, if the image file exists on disk and the
   configured model supports images): we send the actual image to the
   LLM so it can "see" it and describe it accurately.
2. Context-only fallback: if the image file isn't available (e.g. only
   the filename was recorded, or you're using a text-only model), we
   infer the likely purpose of the image from its surrounding page text
   and the image's filename/position. This is clearly labeled as an
   inference so it's never confused with a verified visual description.
"""

import base64
import os
from typing import List, Optional

from understanding_engine.config import get_logger, settings
from understanding_engine.llm_client import llm_client, LLMGenerationError
from understanding_engine.schemas import ImageExplanation
from understanding_engine.utils import get_images, find_nearby_context

logger = get_logger(__name__)


SYSTEM_PROMPT_VISION = """You are an education specialist analyzing a textbook image. Look at the
image and, using the surrounding page text as extra context, describe:

1. description - what the image actually shows, in clear detail
2. educational_purpose - why this image is included in the lesson (what it teaches)
3. suggested_explanation - a one-sentence, student-friendly caption a teacher could say
   while pointing at this image (e.g. "This diagram shows the internal parts of a leaf.")

Respond with ONLY a valid JSON object matching this exact schema, no markdown fences, no extra text:
{
  "description": "string",
  "educational_purpose": "string",
  "suggested_explanation": "string"
}
"""

SYSTEM_PROMPT_CONTEXT_ONLY = """You are an education specialist. You do NOT have direct access to
the image file itself - only its filename, position on the page, and the surrounding page text.
Based on this context, infer the LIKELY educational content and purpose of the image. Be clear
this is an inference from context, not a verified visual description.

1. description - your best inference of what the image likely shows, based on context
2. educational_purpose - why an image would likely be included at this point in the lesson
3. suggested_explanation - a plausible one-sentence caption a teacher might use

Respond with ONLY a valid JSON object matching this exact schema, no markdown fences, no extra text:
{
  "description": "string",
  "educational_purpose": "string",
  "suggested_explanation": "string"
}
"""


def _image_to_base64(image_path: str) -> Optional[str]:
    """Reads an image file from disk and returns a base64-encoded string, or None if missing."""
    if not os.path.exists(image_path):
        return None
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _explain_with_vision(image_path: str, context: str) -> dict:
    """
    Uses OpenAI's vision-capable chat completion to describe an actual image.
    Only used when provider is OpenAI and the image file is found on disk.
    """
    b64_image = _image_to_base64(image_path)
    if b64_image is None:
        raise FileNotFoundError(f"Image not found on disk: {image_path}")

    response = llm_client._openai_client.chat.completions.create(  # pylint: disable=protected-access
        model=settings.OPENAI_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_VISION},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Surrounding page context: {context}"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}},
                ],
            },
        ],
    )
    return llm_client._safe_parse_json(response.choices[0].message.content)  # pylint: disable=protected-access


def _explain_context_only(file_name: str, context: str) -> dict:
    """Fallback: infers the image's likely content purely from filename + surrounding text."""
    user_prompt = f"""Image filename: {file_name}
Surrounding page context: "{context}"

Infer the image's likely content and purpose as described in your instructions."""
    return llm_client.generate_json(SYSTEM_PROMPT_CONTEXT_ONLY, user_prompt)


def generate_image_explanations(document: dict, images_directory: str = "") -> List[ImageExplanation]:
    """
    Analyzes every image referenced in the document and produces an explanation for each.

    Args:
        document: The parsed_document.json content as a Python dict.
        images_directory: Optional folder where extracted image files live, so we can
                           attempt real vision-based analysis. If empty or files aren't
                           found, we gracefully fall back to context-only inference.

    Returns:
        A list of validated ImageExplanation objects.
    """
    logger.info("Analyzing images...")
    images = get_images(document)

    results: List[ImageExplanation] = []
    for i, img in enumerate(images):
        logger.info(f"  Explaining image {i + 1}/{len(images)}: {img['file']}")
        context = find_nearby_context(document, img["page_number"])
        image_path = os.path.join(images_directory, img["file"]) if images_directory else img["file"]

        raw = None
        if settings.LLM_PROVIDER == "openai" and os.path.exists(image_path):
            try:
                raw = _explain_with_vision(image_path, context)
            except (LLMGenerationError, FileNotFoundError, Exception) as exc:  # noqa: BLE001
                logger.warning(f"  Vision analysis failed for {img['file']}, falling back to context-only: {exc}")

        if raw is None:
            try:
                raw = _explain_context_only(img["file"], context)
            except Exception as exc:
                logger.error(f"  Context-only analysis also failed for {img['file']}: {exc}")
                continue

        results.append(
            ImageExplanation(
                file=img["file"],
                description=raw.get("description", ""),
                educational_purpose=raw.get("educational_purpose", ""),
                suggested_explanation=raw.get("suggested_explanation", ""),
                source_page=img["page_number"],
            )
        )

    logger.info(f"Generated explanations for {len(results)} images")
    return results
