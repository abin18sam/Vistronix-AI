"""
config.py
=========
Central configuration for the AI Document Understanding Engine.

WHY THIS FILE EXISTS (beginner explanation):
Instead of scattering API keys, model names, and settings across every
module, we keep them in ONE place. Every other module imports `settings`
from here. If you ever need to switch from OpenAI to Gemini, or change
the model name, you only edit this file.

Environment variables are loaded from a `.env` file (if present) using
python-dotenv, so secrets never need to be hard-coded.
"""

import os
import logging
from dotenv import load_dotenv

# Load variables from a .env file in the project root, if one exists.
load_dotenv()


class Settings:
    """
    Holds every configurable value the engine needs.
    Reads from environment variables with sensible defaults.
    """

    # ------------------------------------------------------------------
    # LLM Provider Selection
    # ------------------------------------------------------------------
    # "openai" or "gemini". This lets you swap providers without touching
    # any module other than llm_client.py.
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai").lower()

    # --- OpenAI settings ---
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # --- Gemini settings ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

    # ------------------------------------------------------------------
    # LLM behavior
    # ------------------------------------------------------------------
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))

    # ------------------------------------------------------------------
    # File paths
    # ------------------------------------------------------------------
    # This project (vistronix-understanding-engine) is a SIBLING folder of
    # your existing PDF Parser module (vistronix-pdf-extractor), i.e.:
    #
    #   vistronix-pdf-extractor/
    #     output/parsed_document.json      <- PDF Parser writes this
    #     extracted_images/                <- PDF Parser writes these
    #   vistronix-understanding-engine/
    #     output/knowledge_graph.json      <- WE write this
    #
    # These three settings point at the parser's output by default, so this
    # engine can run immediately after the parser with zero extra config.
    # Override any of them in .env if your folder layout is different
    # (e.g. if both projects live under one monorepo root, or on separate
    # machines).
    PARSER_PROJECT_DIR: str = os.getenv(
        "PARSER_PROJECT_DIR", os.path.join("..", "vistronix-pdf-extractor")
    )
    INPUT_JSON_PATH: str = os.getenv(
        "INPUT_JSON_PATH", os.path.join(PARSER_PROJECT_DIR, "output", "parsed_document.json")
    )
    PARSER_IMAGES_DIR: str = os.getenv(
        "PARSER_IMAGES_DIR", os.path.join(PARSER_PROJECT_DIR, "extracted_images")
    )
    OUTPUT_JSON_PATH: str = os.getenv("OUTPUT_JSON_PATH", "output/knowledge_graph.json")

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()


def configure_logging() -> None:
    """
    Sets up a consistent logging format across every module.
    Call this once, from main.py, before anything else runs.
    """
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_logger(name: str) -> logging.Logger:
    """Convenience helper so every module gets a logger named after itself."""
    return logging.getLogger(name)
