"""
llm_client.py
=============
A single, unified "gateway" that every other module uses to talk to an LLM
(OpenAI or Gemini).

WHY THIS FILE EXISTS (beginner explanation):
Every module in this project (document_classifier, topic_extractor,
equation_understanding, etc.) needs to ask an LLM a question and get back
clean JSON. Instead of copy-pasting API call code into all 13 modules,
we write it ONCE here. Every module just calls:

    from understanding_engine.llm_client import llm_client
    result = llm_client.generate_json(system_prompt, user_prompt)

and gets back a Python dict, guaranteed to be valid JSON (or a clear
error if the LLM misbehaves after all retries).

This file also handles:
- Automatic retries with exponential backoff (LLMs occasionally hiccup)
- Stripping markdown code fences ( ```json ... ``` ) that models sometimes
  wrap around JSON even when told not to
- Provider switching (OpenAI vs Gemini) based on config.py
"""

import json
import re
from typing import Any, Dict, Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from understanding_engine.config import settings, get_logger

logger = get_logger(__name__)


class LLMGenerationError(Exception):
    """Raised when the LLM fails to produce valid JSON after all retries."""
    pass


class LLMClient:
    """
    Thin wrapper that abstracts away *which* LLM provider we're using.
    Modules never talk to OpenAI/Gemini directly - they always go through
    this class, so switching providers later is a one-line config change.
    """

    def __init__(self) -> None:
        self.provider = settings.LLM_PROVIDER
        self._openai_client = None
        self._gemini_model = None

        if self.provider not in {"openai", "gemini"}:
            raise ValueError(
                f"Unsupported LLM_PROVIDER '{self.provider}'. Use 'openai' or 'gemini'."
            )

    def _ensure_client(self) -> None:
        if self.provider == "openai" and self._openai_client is None:
            self._init_openai()
        elif self.provider == "gemini" and self._gemini_model is None:
            self._init_gemini()

    # ------------------------------------------------------------------
    # Provider initialization
    # ------------------------------------------------------------------
    def _init_openai(self) -> None:
        from openai import OpenAI  # imported lazily so gemini-only installs don't need it

        if not settings.OPENAI_API_KEY:
            logger.warning(
                "OPENAI_API_KEY is not set. Set it in your .env file before making real calls."
            )
        self._openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        logger.info(f"LLMClient initialized with provider=openai model={settings.OPENAI_MODEL}")

    def _init_gemini(self) -> None:
        import google.generativeai as genai  # imported lazily

        if not settings.GEMINI_API_KEY:
            logger.warning(
                "GEMINI_API_KEY is not set. Set it in your .env file before making real calls."
            )
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self._gemini_model = genai.GenerativeModel(settings.GEMINI_MODEL)
        logger.info(f"LLMClient initialized with provider=gemini model={settings.GEMINI_MODEL}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @retry(
        stop=stop_after_attempt(settings.LLM_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type(LLMGenerationError),
        reraise=True,
    )
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Sends a prompt to the configured LLM and returns a parsed JSON dict.

        Args:
            system_prompt: Instructions describing the AI's role and the
                            exact JSON schema it must return.
            user_prompt:   The actual content to analyze (e.g. document text).
            temperature:   Optional override for creativity level.

        Returns:
            A Python dict parsed from the LLM's JSON response.

        Raises:
            LLMGenerationError: if the LLM never returns valid JSON, even
                                 after retries.
        """
        temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
        self._ensure_client()

        raw_text = (
            self._call_openai(system_prompt, user_prompt, temp)
            if self.provider == "openai"
            else self._call_gemini(system_prompt, user_prompt, temp)
        )

        return self._safe_parse_json(raw_text)

    # ------------------------------------------------------------------
    # Provider-specific calls
    # ------------------------------------------------------------------
    def _call_openai(self, system_prompt: str, user_prompt: str, temperature: float) -> str:
        try:
            response = self._openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                temperature=temperature,
                response_format={"type": "json_object"},  # forces valid JSON output
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
            return response.choices[0].message.content
        except Exception as exc:
            logger.error(f"OpenAI call failed: {exc}")
            raise LLMGenerationError(str(exc)) from exc

    def _call_gemini(self, system_prompt: str, user_prompt: str, temperature: float) -> str:
        try:
            full_prompt = f"{system_prompt}\n\n{user_prompt}\n\nRespond with ONLY valid JSON, no markdown fences."
            response = self._gemini_model.generate_content(
                full_prompt,
                generation_config={"temperature": temperature, "response_mime_type": "application/json"},
            )
            return response.text
        except Exception as exc:
            logger.error(f"Gemini call failed: {exc}")
            raise LLMGenerationError(str(exc)) from exc

    # ------------------------------------------------------------------
    # JSON safety net
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_parse_json(raw_text: str) -> Dict[str, Any]:
        """
        LLMs sometimes wrap JSON in ```json ... ``` fences despite instructions.
        This strips those fences before parsing, and raises a clear error
        if the result still isn't valid JSON (which triggers a retry).
        """
        if raw_text is None:
            raise LLMGenerationError("LLM returned an empty response.")

        cleaned = raw_text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.warning(f"Failed to parse LLM output as JSON: {exc}. Raw text: {raw_text[:300]}")
            raise LLMGenerationError(f"Invalid JSON returned by LLM: {exc}") from exc


# A single shared instance every module imports. This avoids re-initializing
# an API client on every function call.
llm_client = LLMClient()
