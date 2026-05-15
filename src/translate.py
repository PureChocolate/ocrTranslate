"""Translation via Ollama. Strips furigana before sending to model."""

from __future__ import annotations

import re
from typing import Optional

import requests

from src.config import (
    API_CHAT,
    TEMPERATURE,
    TRANSLATION_MODEL,
    REQUEST_TIMEOUT,
    TRANSLATE_SYSTEM_PROMPT,
    TRANSLATE_USER_PROMPT_TEMPLATE,
    TRANSLATE_BATCH_SYSTEM_PROMPT,
    TRANSLATE_BATCH_USER_PROMPT,
)


def _strip_furigana(text: str) -> str:
    """Remove kana-only parenthetical readings: 漢字(かんじ) → 漢字."""
    return re.sub(r'\([ぁ-ゟァ-ヿー]+\)', '', text)


def _post(model: str, messages: list[dict], timeout: int) -> str:
    """Send chat request, return response content or raise RuntimeError."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "keep_alive": 0,
        "options": {"temperature": TEMPERATURE},
    }
    try:
        r = requests.post(API_CHAT, json=payload, timeout=timeout)
    except requests.exceptions.ConnectionError:
        raise RuntimeError(f"Cannot connect to Ollama at {API_CHAT}.")
    except requests.exceptions.Timeout:
        raise RuntimeError(f"Translation timed out after {timeout}s.")

    if r.status_code != 200:
        detail = r.text
        if "model not found" in detail.lower():
            raise RuntimeError(f"Model '{model}' not downloaded. Run: ollama pull {model}")
        raise RuntimeError(f"Ollama API error ({r.status_code}): {detail}")

    return r.json().get("message", {}).get("content", "").strip()


def translate_text(
    text: str,
    model: Optional[str] = None,
    verbose: bool = False,
) -> str:
    """Translate a single page's text."""
    model = model or TRANSLATION_MODEL
    clean = _strip_furigana(text)

    if verbose and clean != text:
        print(f"[Translate] Stripped furigana: {len(text)} → {len(clean)} chars", flush=True)

    prompt = TRANSLATE_USER_PROMPT_TEMPLATE.format(text=clean)
    messages = [
        {"role": "system", "content": TRANSLATE_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    if verbose:
        print(f"[Translate] Model: {model} ({len(text)} chars)", flush=True)

    result = _post(model, messages, REQUEST_TIMEOUT)

    if verbose:
        print(f"[Translate] Response ({len(result)} chars)", flush=True)

    return result


def translate_text_batch(
    all_texts: list[tuple[str, str]],
    model: Optional[str] = None,
    verbose: bool = False,
) -> str:
    """Translate all pages in one call. all_texts = [(filename, text), ...]."""
    model = model or TRANSLATION_MODEL

    parts = []
    for i, (name, text) in enumerate(all_texts, 1):
        clean = _strip_furigana(text)
        parts.append(f"=== PAGE {i}: {name} ===\n{clean}")
    text_block = "\n\n".join(parts)

    total = sum(len(t) for _, t in all_texts)
    if total > 12000:
        print(f"  Warning: {total} chars may exceed context window.")

    if verbose:
        print(f"[Translate batch] {len(all_texts)} pages, {total} chars", flush=True)

    prompt = TRANSLATE_BATCH_USER_PROMPT.format(text=text_block)
    messages = [
        {"role": "system", "content": TRANSLATE_BATCH_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    result = _post(model, messages, REQUEST_TIMEOUT * 5)

    if verbose:
        print(f"[Translate batch] Response ({len(result)} chars)", flush=True)

    return result
