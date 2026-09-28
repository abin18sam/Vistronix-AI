"""
visual_asset_generator.py
=========================
Phase 4: Visual Asset Generation.

This module creates lightweight SVG-based visual asset placeholders that can be
used as the basis for later video generation.
"""

import os
from pathlib import Path
from typing import List, Dict, Any

from understanding_engine.config import get_logger
from understanding_engine.schemas import StoryboardOutput, VisualAssetOutput, VisualAsset

logger = get_logger(__name__)


def generate_visual_assets(storyboard: StoryboardOutput, output_dir: str = "output") -> VisualAssetOutput:
    """Create SVG placeholder assets for each storyboard scene."""
    logger.info("Generating visual assets...")
    os.makedirs(output_dir, exist_ok=True)

    assets: List[VisualAsset] = []
    for scene in storyboard.scene_plan:
        file_name = f"scene_{scene.scene_number:03d}.svg"
        file_path = os.path.join(output_dir, file_name)

        svg_content = f"""<svg xmlns='http://www.w3.org/2000/svg' width='1280' height='720'>
  <rect width='100%' height='100%' fill='#0f172a'/>
  <rect x='60' y='60' width='1160' height='600' rx='24' fill='#1e293b'/>
  <text x='80' y='180' fill='#f8fafc' font-size='40' font-family='Arial'>{scene.title}</text>
  <text x='80' y='260' fill='#cbd5e1' font-size='24' font-family='Arial'>{scene.description}</text>
  <text x='80' y='330' fill='#94a3b8' font-size='20' font-family='Arial'>Narration: {scene.narration}</text>
</svg>"""

        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write(svg_content)

        assets.append(
            VisualAsset(
                scene_number=scene.scene_number,
                title=scene.title,
                file_name=file_name,
                file_path=file_path,
                asset_type="svg",
                prompt=scene.visual_prompt,
            )
        )

    logger.info(f"Created {len(assets)} visual assets in {output_dir}")
    return VisualAssetOutput(assets=assets)
