"""
knowledge_graph_builder.py
============================
THE PIPELINE ENTRY POINT.

WHY THIS FILE EXISTS (beginner explanation):
Every other module in this package does ONE job well (classify the
document, extract topics, explain equations, etc.). This file is the
"conductor" that calls each of them in the right order, passes the
parsed_document.json input to each one, collects every result, and
assembles the final knowledge_graph.json contract (the KnowledgeGraph
Pydantic model from schemas.py).

If one module fails, we log the error clearly and re-raise, so main.py
(the API layer) can turn it into a proper HTTP error instead of a
half-built, silently-broken output file.
"""

import json
import os
from typing import Any, Dict

from understanding_engine.config import settings, get_logger
from understanding_engine.schemas import KnowledgeGraph

from understanding_engine.document_classifier import classify_document
from understanding_engine.topic_extractor import extract_topics
from understanding_engine.concept_extractor import extract_concepts
from understanding_engine.summary_generator import generate_summary
from understanding_engine.teacher_explainer import generate_teacher_explanations
from understanding_engine.learning_flow import detect_learning_flow
from understanding_engine.equation_understanding import generate_equation_explanations
from understanding_engine.image_understanding import generate_image_explanations
from understanding_engine.table_understanding import generate_table_explanations
from understanding_engine.question_generator import generate_questions
from understanding_engine.flashcard_generator import generate_flashcards
from understanding_engine.scene_generator import generate_scene_plan
from understanding_engine.storyboard_generator import generate_storyboard
from understanding_engine.visual_asset_generator import generate_visual_assets
from understanding_engine.voice_generator import generate_voiceover
from understanding_engine.video_generator import generate_video

logger = get_logger(__name__)


def build_knowledge_graph(document: Dict[str, Any], images_directory: str = "") -> KnowledgeGraph:
    """
    Runs the full understanding pipeline on a parsed document and returns
    the assembled KnowledgeGraph object.

    Args:
        document: The parsed_document.json content as a Python dict.
        images_directory: Optional folder containing extracted image files,
                           passed through to image_understanding.py so it can
                           attempt real vision-based analysis when possible.

    Returns:
        A fully populated, validated KnowledgeGraph object.

    Raises:
        Exception: re-raises the first module failure encountered, after logging it.
    """
    document_name = document.get("document_name", "Unknown Document")
    logger.info(f"===== Starting knowledge graph pipeline for '{document_name}' =====")

    try:
        logger.info("[1/9] Classifying document (subject, chapter, difficulty, objectives)...")
        classification = classify_document(document)

        logger.info("[2/9] Extracting topics and concept relationships...")
        topics = extract_topics(document)

        logger.info("[3/9] Extracting key concepts, keywords, definitions, misconceptions...")
        concepts = extract_concepts(document)

        logger.info("[4/9] Generating summaries and important points...")
        summary = generate_summary(document)

        logger.info("[5/9] Generating teacher-style simplified explanations...")
        teacher_explanations = generate_teacher_explanations(document)

        logger.info("[6/9] Detecting the ideal learning flow...")
        learning_flow = detect_learning_flow(document)

        logger.info("[7/9] Explaining equations, images, and tables...")
        equations = generate_equation_explanations(document)
        image_explanations = generate_image_explanations(document, images_directory=images_directory)
        table_explanations = generate_table_explanations(document)

        logger.info("[8/9] Generating questions and flashcards...")
        questions = generate_questions(document)
        flashcards = generate_flashcards(document)

        logger.info("[9/10] Generating scene plan, narration, and time estimates...")
        scenes = generate_scene_plan(document)

        logger.info("[10/10] Generating storyboard, assets, voiceover, and video preview...")
        storyboard = generate_storyboard(document, [scene.model_dump() for scene in scenes.scene_plan])
        assets = generate_visual_assets(
            storyboard,
            output_dir=settings.OUTPUT_JSON_PATH.rsplit("/", 1)[0] if "/" in settings.OUTPUT_JSON_PATH else "output",
        )
        voiceover = generate_voiceover(
            storyboard,
            output_dir=settings.OUTPUT_JSON_PATH.rsplit("/", 1)[0] if "/" in settings.OUTPUT_JSON_PATH else "output",
        )
        video = generate_video(
            storyboard,
            assets,
            voiceover,
            output_dir=settings.OUTPUT_JSON_PATH.rsplit("/", 1)[0] if "/" in settings.OUTPUT_JSON_PATH else "output",
        )

    except Exception as exc:
        logger.error(f"Knowledge graph pipeline FAILED for '{document_name}': {exc}")
        raise

    knowledge_graph = KnowledgeGraph(
        document_name=document_name,
        subject=classification.subject,
        chapter=classification.chapter,
        topic=classification.topic,
        difficulty_level=classification.difficulty_level,
        educational_domain=classification.educational_domain,
        learning_objectives=classification.learning_objectives,
        prerequisites=classification.prerequisites,
        summary=summary,
        topics=topics,
        concepts=concepts,
        teacher_explanations=teacher_explanations,
        learning_flow=learning_flow,
        equations=equations,
        image_explanations=image_explanations,
        table_explanations=table_explanations,
        questions=questions,
        flashcards=flashcards.flashcards,
        scene_plan=scenes.scene_plan,
        storyboard=storyboard,
        visual_assets=assets,
        voiceover=voiceover,
        video=video,
    )

    logger.info(f"===== Knowledge graph pipeline COMPLETE for '{document_name}' =====")
    return knowledge_graph


def save_knowledge_graph(knowledge_graph: KnowledgeGraph, output_path: str = None) -> str:
    """
    Writes the KnowledgeGraph object to disk as knowledge_graph.json.

    Args:
        knowledge_graph: The KnowledgeGraph object to save.
        output_path: Optional override path. Defaults to settings.OUTPUT_JSON_PATH.

    Returns:
        The path the file was actually written to.
    """
    path = output_path or settings.OUTPUT_JSON_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(knowledge_graph.model_dump(), f, indent=2, ensure_ascii=False)

    logger.info(f"Saved knowledge_graph.json to: {path}")
    return path
