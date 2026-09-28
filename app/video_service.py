import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.config import settings


class Scene(BaseModel):
    scene_number: int
    title: str
    description: str
    narration: str
    estimated_seconds: int


class ScenePlan(BaseModel):
    scene_plan: list[Scene] = Field(default_factory=list)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_title_from_topic(key: str, fallback: str) -> str:
    key = key.strip()
    return key if key else fallback


def _knowledge_graph_path(document_dir: Path) -> Path:
    understanding_path = document_dir / "understanding" / "knowledge_graph.json"
    return understanding_path if understanding_path.exists() else document_dir / "knowledge_graph.json"


def build_scene_plan(document_id: str, document_dir: Path) -> ScenePlan:
    parsed = _read_json(document_dir / "parsed_document.json")
    graph = _read_json(_knowledge_graph_path(document_dir))
    doc_title = parsed.get("document_name", "Document")
    entities = graph.get("entities", [])
    concepts = [ent.get("name", "Concept") for ent in entities[:3] if ent.get("name")]
    learning = graph.get("learning_objectives", []) or ["Explain the main ideas."]

    full_text = []
    for page in parsed.get("pages", []):
        for element in page.get("elements", []):
            text = element.get("text")
            if text:
                full_text.append(text)

    intro = "Introduction to the document"
    if concepts:
        intro = f"Introduction to {concepts[0]}"

    scenes = [
        Scene(
            scene_number=1,
            title=intro,
            description=f"Open with the core ideas of {doc_title} and the main concept of the lesson.",
            narration=f"This lesson introduces the main ideas in {doc_title}. We will examine the central concepts and why they matter.",
            estimated_seconds=15,
        ),
        Scene(
            scene_number=2,
            title=_build_title_from_topic(learning[0], "Key concept explanation"),
            description="Explain the primary concept using the document summary and knowledge graph relationships.",
            narration="The document highlights the central concept and connects it to the key learning objective for this section.",
            estimated_seconds=20,
        ),
    ]

    if concepts:
        scenes.append(
            Scene(
                scene_number=3,
                title=f"Explore {concepts[0]}",
                description=f"Break down {concepts[0]} and show its relationship to the document’s evidence and claims.",
                narration=f"Let’s focus on {concepts[0]} and how it connects to the ideas presented in the document.",
                estimated_seconds=20,
            )
        )

    scenes.append(
        Scene(
            scene_number=len(scenes) + 1,
            title="Review and recap",
            description="Close by summarizing the lesson and the key takeaways from the document.",
            narration="In review, the document emphasizes the key insights and the central ideas we explored together.",
            estimated_seconds=15,
        )
    )

    scene_plan = ScenePlan(scene_plan=scenes)
    path = document_dir / "scene_plan.json"
    path.write_text(scene_plan.model_dump_json(indent=2), encoding="utf-8")
    return scene_plan


def _ffmpeg_executable() -> str | None:
    candidates = [
        shutil.which("ffmpeg"),
        os.environ.get("FFMPEG_PATH"),
        str(Path(__file__).resolve().parent.parent / ".venv" / "Lib" / "site-packages" / "imageio_ffmpeg" / "binaries" / "ffmpeg-win-x86_64-v7.1.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def _ffprobe_executable() -> str | None:
    candidates = [
        shutil.which("ffprobe"),
        os.environ.get("FFPROBE_PATH"),
        str(Path(__file__).resolve().parent.parent / ".venv" / "Lib" / "site-packages" / "imageio_ffmpeg" / "binaries" / "ffprobe.exe"),
        str(Path(__file__).resolve().parent.parent / ".venv" / "Lib" / "site-packages" / "imageio_ffmpeg" / "binaries" / "ffprobe-win-x86_64-v7.1.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def _ensure_ffmpeg() -> bool:
    return _ffmpeg_executable() is not None


def _generate_audio(scene_plan: ScenePlan, output_path: Path) -> None:
    text = " ".join(scene.narration.strip() for scene in scene_plan.scene_plan if scene.narration.strip())
    if not text:
        raise ValueError("Scene plan contains no narration")
    text_path = output_path.with_suffix(".txt")
    temporary = output_path.with_suffix(".tmp.wav")
    text_path.write_text(text, encoding="utf-8")
    environment = os.environ.copy()
    environment["VIS_TRONIX_TTS_TEXT"] = str(text_path.resolve())
    environment["VIS_TRONIX_TTS_OUTPUT"] = str(temporary.resolve())
    command = (
        "Add-Type -AssemblyName System.Speech; "
        "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$synth.SetOutputToWaveFile($env:VIS_TRONIX_TTS_OUTPUT); "
        "$synth.Speak((Get-Content -Raw -LiteralPath $env:VIS_TRONIX_TTS_TEXT)); "
        "$synth.Dispose()"
    )
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        if not temporary.exists() or temporary.stat().st_size == 0:
            raise RuntimeError("TTS engine did not produce narration audio")
        temporary.replace(output_path)
    finally:
        text_path.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)


def _write_captions(scene_plan: ScenePlan, output_path: Path) -> None:
    def timestamp(seconds: int) -> str:
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},000"

    current = 0
    entries = []
    for number, scene in enumerate(scene_plan.scene_plan, start=1):
        duration = max(1, scene.estimated_seconds)
        entries.append(f"{number}\n{timestamp(current)} --> {timestamp(current + duration)}\n{scene.narration.strip()}\n")
        current += duration
    temporary = output_path.with_suffix(".tmp.srt")
    temporary.write_text("\n".join(entries), encoding="utf-8")
    temporary.replace(output_path)


def render_video(document_id: str, document_dir: Path) -> Path:
    ffmpeg_path = _ffmpeg_executable()
    if ffmpeg_path is None:
        raise RuntimeError("ffmpeg not installed; cannot render MP4")

    audio_dir = document_dir / "audio"
    captions_dir = document_dir / "captions"
    audio_dir.mkdir(exist_ok=True)
    captions_dir.mkdir(exist_ok=True)

    narration_path = audio_dir / "narration.wav"
    caption_path = captions_dir / "captions.srt"
    mp4_path = document_dir / "final.mp4"

    scene_plan = ScenePlan.model_validate_json((document_dir / "scene_plan.json").read_text(encoding="utf-8"))
    _generate_audio(scene_plan, narration_path)
    _write_captions(scene_plan, caption_path)

    temp_video = document_dir / "tmp_video.mp4"
    subprocess.run([
        ffmpeg_path, "-y",
        "-f", "lavfi", "-i", "color=c=blue:s=1280x720",
        "-i", str(narration_path),
        "-shortest",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-movflags", "+faststart",
        str(temp_video),
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    subprocess.run([
        ffmpeg_path, "-y",
        "-i", str(temp_video),
        "-map", "0:v:0",
        "-map", "0:a:0",
        "-c:v", "copy",
        "-c:a", "copy",
        str(mp4_path),
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    temp_video.unlink(missing_ok=True)
    return mp4_path


def validate_video(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)

    ffprobe_path = _ffprobe_executable()
    if ffprobe_path:
        result = subprocess.run([
            ffprobe_path,
            "-v", "error",
            "-show_entries", "stream=codec_type,codec_name",
            "-show_entries", "format=duration",
            "-of", "json",
            str(path),
        ], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            payload = json.loads(result.stdout)
            streams = payload.get("streams", [])
            duration = float(payload.get("format", {}).get("duration", 0) or 0)
            codecs = [stream.get("codec_type") for stream in streams if stream.get("codec_type")]
            return {
                "has_video": "video" in codecs,
                "has_audio": "audio" in codecs,
                "duration_seconds": duration,
                "stream_count": len(streams),
                "ok": duration > 0 and "video" in codecs and "audio" in codecs,
            }

    ffmpeg_path = _ffmpeg_executable()
    if ffmpeg_path is None:
        raise RuntimeError("ffmpeg not installed; cannot validate MP4")

    result = subprocess.run([
        ffmpeg_path,
        "-hide_banner",
        "-i", str(path),
        "-f", "null",
        "-",
    ], capture_output=True, text=True, check=False)
    text = f"{result.stderr}\n{result.stdout}"
    has_video = "Video:" in text or ("Stream #0:0" in text and "Video" in text)
    has_audio = "Audio:" in text or ("Stream #0:1" in text and "Audio" in text)
    duration_match = re.search(r"Duration:\s+(\d+):(\d+):(\d+\.\d+)", text)
    duration = 0.0
    if duration_match:
        hours, minutes, seconds = duration_match.groups()
        duration = float(hours) * 3600 + float(minutes) * 60 + float(seconds)
    if duration == 0.0 and "time=" in text:
        time_match = re.search(r"time=\s*(\d+):(\d+):(\d+\.\d+)", text)
        if time_match:
            hours, minutes, seconds = time_match.groups()
            duration = float(hours) * 3600 + float(minutes) * 60 + float(seconds)
    return {
        "has_video": has_video,
        "has_audio": has_audio,
        "duration_seconds": duration,
        "stream_count": max(1, text.count("Stream #0:")),
        "ok": duration > 0 and has_video and has_audio,
    }
