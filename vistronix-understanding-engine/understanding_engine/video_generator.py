"""
video_generator.py
==================
Phase 6: Video Generation.

This module creates a lightweight HTML-based preview and a manifest describing
how the storyboard, assets, and voiceover should be stitched together.
"""

import json
import os
from typing import Any

from understanding_engine.config import get_logger
from understanding_engine.schemas import StoryboardOutput, VisualAssetOutput, VoiceoverOutput, VideoOutput

logger = get_logger(__name__)


def generate_video(storyboard: StoryboardOutput, assets: VisualAssetOutput, voiceover: VoiceoverOutput, output_dir: str = "output") -> VideoOutput:
    """Create a preview HTML file and video manifest."""
    logger.info("Generating video preview assets...")
    os.makedirs(output_dir, exist_ok=True)

    preview_path = os.path.join(output_dir, "video_preview.html")
    manifest_path = os.path.join(output_dir, "video_manifest.json")

    html = """<!doctype html>
<html>
  <head><meta charset='utf-8'><title>VisTronix Video Preview</title></head>
  <body>
    <h1>VisTronix AI Video Preview</h1>
    <p>This preview is generated from storyboard scenes, visual assets, and voiceover notes.</p>
  </body>
</html>"""
    with open(preview_path, "w", encoding="utf-8") as handle:
        handle.write(html)

    manifest = {
        "storyboard_scene_count": len(storyboard.scene_plan),
        "asset_count": len(assets.assets),
        "voiceover_file": voiceover.voiceover_file,
        "preview_file": preview_path,
        "scenes": [
            {
                "scene_number": scene.scene_number,
                "title": scene.title,
                "asset": asset.file_name if asset else None,
            }
            for scene, asset in zip(storyboard.scene_plan, assets.assets)
        ],
    }
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    logger.info(f"Video preview generated at {preview_path}")
    return VideoOutput(preview_file=preview_path, manifest_file=manifest_path, manifest=manifest)
