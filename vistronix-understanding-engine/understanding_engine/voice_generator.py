"""
voice_generator.py
==================
Phase 5: Voice Generation.

This module produces a lightweight voiceover package consisting of a plain-text
script and a JSON manifest that can be used by downstream video tooling.
"""

import json
import os
from typing import Dict, Any

from understanding_engine.config import get_logger
from understanding_engine.schemas import StoryboardOutput, VoiceoverOutput

logger = get_logger(__name__)


def generate_voiceover(storyboard: StoryboardOutput, output_dir: str = "output") -> VoiceoverOutput:
    """Create a voiceover script and manifest for a storyboard."""
    logger.info("Generating voiceover script...")
    os.makedirs(output_dir, exist_ok=True)

    script_lines = []
    for scene in storyboard.scene_plan:
        script_lines.append(f"Scene {scene.scene_number}: {scene.narration}")

    script_text = "\n\n".join(script_lines)
    voiceover_path = os.path.join(output_dir, "voiceover.txt")
    manifest_path = os.path.join(output_dir, "voiceover.json")

    with open(voiceover_path, "w", encoding="utf-8") as handle:
        handle.write(script_text)

    manifest = {
        "voiceover_file": voiceover_path,
        "scene_count": len(storyboard.scene_plan),
        "script": script_text,
    }
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    logger.info(f"Wrote voiceover files to {output_dir}")
    return VoiceoverOutput(voiceover_file=voiceover_path, manifest_file=manifest_path, script=script_text)
