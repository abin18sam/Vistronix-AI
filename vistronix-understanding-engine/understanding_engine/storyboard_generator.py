"""
storyboard_generator.py
=======================
Phase 3: Storyboard Generation.

This module transforms the existing scene plan into a richer storyboard format
that can drive visual asset creation, voiceovers, and video rendering.
"""

import json
from typing import List, Dict, Any

from understanding_engine.config import get_logger
from understanding_engine.schemas import SceneOutput, StoryboardOutput, StoryboardScene

logger = get_logger(__name__)


def generate_storyboard(document: Dict[str, Any], scene_plan: List[Dict[str, Any]] | None = None) -> StoryboardOutput:
    """Create a storyboard structure from the scene plan and document context."""
    logger.info("Generating storyboard from scene plan...")

    if scene_plan is None:
        scene_plan = []

    storyboard_scenes: List[StoryboardScene] = []
    for idx, scene in enumerate(scene_plan, start=1):
        title = scene.get("title", f"Scene {idx}")
        narration = scene.get("narration", "")
        description = scene.get("description", "")
        estimated_seconds = int(scene.get("estimated_seconds", 20))

        storyboard_scenes.append(
            StoryboardScene(
                scene_number=idx,
                title=title,
                description=description,
                narration=narration,
                estimated_seconds=estimated_seconds,
                visual_prompt=f"Create a concise teaching visual for: {title}",
                asset_hint="simple educational illustration",
            )
        )

    storyboard = StoryboardOutput(scene_plan=storyboard_scenes)
    logger.info(f"Storyboard created with {len(storyboard_scenes)} scenes")
    return storyboard
