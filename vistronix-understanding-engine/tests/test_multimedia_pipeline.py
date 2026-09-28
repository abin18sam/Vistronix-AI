import tempfile
import unittest
from pathlib import Path

from understanding_engine.storyboard_generator import generate_storyboard
from understanding_engine.visual_asset_generator import generate_visual_assets
from understanding_engine.voice_generator import generate_voiceover
from understanding_engine.video_generator import generate_video


class MultimediaPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = {
            "document_name": "Sample Document",
            "content": [
                {"type": "heading", "text": "Introduction to Physics"},
                {"type": "paragraph", "text": "Physics studies motion and energy."},
            ],
        }
        self.scene_plan = [
            {"scene_number": 1, "title": "Introduction", "description": "Introduce the topic", "narration": "Welcome to the lesson.", "estimated_seconds": 20},
            {"scene_number": 2, "title": "Core Concept", "description": "Explain motion", "narration": "Motion is the change in position.", "estimated_seconds": 25},
        ]

    def test_storyboard_generation_returns_scenes(self) -> None:
        storyboard = generate_storyboard(self.document, self.scene_plan)
        self.assertGreaterEqual(len(storyboard.scene_plan), 1)
        self.assertEqual(storyboard.scene_plan[0].scene_number, 1)

    def test_visual_and_voice_assets_are_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            storyboard = generate_storyboard(self.document, self.scene_plan)
            assets = generate_visual_assets(storyboard, output_dir=tmp_dir)
            self.assertGreaterEqual(len(assets.assets), 1)
            self.assertTrue(Path(tmp_dir, "scene_001.svg").exists())

            voice = generate_voiceover(storyboard, output_dir=tmp_dir)
            self.assertTrue(Path(tmp_dir, "voiceover.txt").exists())
            self.assertTrue(Path(tmp_dir, "voiceover.json").exists())

    def test_video_generation_creates_preview_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            storyboard = generate_storyboard(self.document, self.scene_plan)
            assets = generate_visual_assets(storyboard, output_dir=tmp_dir)
            voice = generate_voiceover(storyboard, output_dir=tmp_dir)
            video = generate_video(storyboard, assets, voice, output_dir=tmp_dir)
            self.assertTrue(Path(tmp_dir, "video_preview.html").exists())
            self.assertTrue(Path(tmp_dir, "video_manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
