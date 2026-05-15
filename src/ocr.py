"""Vision-based OCR via Ollama chat API."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple, Union

import requests

from src.config import (
    API_CHAT,
    VISION_MODEL,
    MAX_IMAGE_DIMENSION,
    REQUEST_TIMEOUT,
    OCR_SYSTEM_PROMPT,
    OCR_USER_PROMPT,
)
from src.preprocess import image_to_base64


def _parse_response(raw: str) -> Tuple[str, str]:
    """Split response into (context, text) on '---' delimiter."""
    parts = re.split(r'\n---+\n', raw, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return "", raw.strip()


def _make_message(user_prompt: str, system_prompt: str, image_b64: str) -> list[dict]:
    """Build message list, skipping empty system prompt."""
    msgs = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    msgs.append({"role": "user", "content": user_prompt, "images": [image_b64]})
    return msgs


def extract_text(
    image_path: Union[str, Path],
    model: Optional[str] = None,
    source_lang: Optional[str] = None,
    custom_prompt: Optional[str] = None,
    custom_system_prompt: Optional[str] = None,
    keep_alive: str = "30m",
    verbose: bool = False,
) -> Tuple[str, str]:
    """Send image to vision model, return (context, extracted_text)."""
    model = model or VISION_MODEL
    image_b64 = image_to_base64(image_path, max_dimension=MAX_IMAGE_DIMENSION)

    user_prompt = custom_prompt if custom_prompt is not None else OCR_USER_PROMPT
    system_prompt = custom_system_prompt if custom_system_prompt is not None else OCR_SYSTEM_PROMPT

    if source_lang:
        user_prompt = user_prompt.replace(
            "Extract all text", f"Extract all {source_lang} text"
        )

    payload = {
        "model": model,
        "messages": _make_message(user_prompt, system_prompt, image_b64),
        "stream": False,
        "keep_alive": keep_alive,
    }

    if verbose:
        print(f"[OCR] Model: {model}", flush=True)
        print(f"[OCR] Prompt: {user_prompt[:300]}...", flush=True)

    try:
        response = requests.post(API_CHAT, json=payload, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.ConnectionError:
        raise RuntimeError(f"Cannot connect to Ollama at {API_CHAT}. Is it running?")
    except requests.exceptions.Timeout:
        raise RuntimeError(f"OCR timed out after {REQUEST_TIMEOUT}s.")

    if response.status_code != 200:
        detail = response.text
        if "model not found" in detail.lower():
            raise RuntimeError(f"Model '{model}' not downloaded. Run: ollama pull {model}")
        raise RuntimeError(f"Ollama API error ({response.status_code}): {detail}")

    raw = response.json().get("message", {}).get("content", "")

    if verbose:
        print(f"[OCR] Response ({len(raw)} chars):", flush=True)
        print(raw[:800], flush=True)

    if not raw.strip():
        raise RuntimeError(f"Model '{model}' returned empty text. Verify it supports vision.")

    context, text = _parse_response(raw)
    return context, text.strip()
