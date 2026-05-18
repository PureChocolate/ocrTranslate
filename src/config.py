"""Configuration from .env. All settings centralized here."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parent.parent
_env_path = _project_root / ".env"
load_dotenv(_env_path) if _env_path.exists() else load_dotenv()

OLLAMA_HOST: Final[str] = os.getenv("OLLAMA_HOST", "http://localhost:11434")
VISION_MODEL: Final[str] = os.getenv("VISION_MODEL", "minicpm-v:latest")
TRANSLATION_MODEL: Final[str] = os.getenv("TRANSLATION_MODEL", "llama3.1:8b")
SOURCE_LANG: Final[str] = os.getenv("SOURCE_LANG", "Japanese")
TARGET_LANG: Final[str] = os.getenv("TARGET_LANG", "English")
MAX_IMAGE_DIMENSION: Final[int] = int(os.getenv("MAX_IMAGE_DIMENSION", "2048"))
REQUEST_TIMEOUT: Final[int] = int(os.getenv("REQUEST_TIMEOUT", "120"))
TEMPERATURE: Final[float] = float(os.getenv("TEMPERATURE", "0.5"))

API_CHAT: Final[str] = f"{OLLAMA_HOST.rstrip('/')}/api/chat"
API_TAGS: Final[str] = f"{OLLAMA_HOST.rstrip('/')}/api/tags"

# ── OCR prompts ────────────────────────────────────────────────────────
OCR_SYSTEM_PROMPT: Final[str] = (
    "Extract text from images. Ignore furigana/ruby text. Output only the main text."
)
OCR_USER_PROMPT: Final[str] = (
    "Extract all text from this page. Ignore any small furigana or ruby readings next to characters. Output only the main text."
)
OCR_BUBBLE_SYSTEM_PROMPT: Final[str] = ""
OCR_BUBBLE_USER_PROMPT: Final[str] = (
    "Output only the raw Japanese text from each speech bubble. "
    "No translations, no descriptions, no commentary. "
    "Ignore any small furigana/ruby text next to kanji. "
    "Just the main text."
)

# ── Translation prompts ────────────────────────────────────────────────
TRANSLATE_SYSTEM_PROMPT: Final[str] = (
    "You are a translator. Output only the translation, nothing else."
)
TRANSLATE_USER_PROMPT_TEMPLATE: Final[str] = (
    "Translate this Japanese text to English. Output only the translation.\n\n{text}"
)
TRANSLATE_BATCH_SYSTEM_PROMPT: Final[str] = (
    "You are a translator. Output only the translation, nothing else."
)
TRANSLATE_BATCH_USER_PROMPT: Final[str] = (
    "Translate these pages to English. "
    "Keep the === PAGE N === markers. Output only the translation.\n\n{text}"
)
