#!/usr/bin/env python3
"""OCR Translate — Extract and translate manga text via Ollama."""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import requests

from src.config import OLLAMA_HOST, API_TAGS, VISION_MODEL, TRANSLATION_MODEL


def _natural_key(path: Path) -> int:
    """Sort key: leading number in filename (1.webp, 2.webp, ...)."""
    m = re.match(r'(\d+)', path.name)
    return int(m.group(1)) if m else 0


def _check_ollama() -> bool:
    try:
        requests.get(f"{OLLAMA_HOST.rstrip('/')}/", timeout=5)
        return True
    except requests.exceptions.ConnectionError:
        return False


def _process_single(
    image_path: Path, model_vision: str, model_translate: str,
    ocr_only: bool, verbose: bool,
    page_num: int | None = None, total_pages: int | None = None,
) -> tuple[str, str, str, str]:
    """Single image: OCR → translate. Returns (name, context, extracted, translation)."""
    from src.ocr import extract_text
    from src.translate import translate_text

    label = f"[{page_num}/{total_pages}] {image_path.name}" if page_num else image_path.name
    print(f"\n[1/2] {label}")
    print(f"      Model: {model_vision}")

    context, extracted = extract_text(image_path=image_path, model=model_vision, verbose=verbose)
    print(f"      Extracted {len(extracted)} chars" + (f", context {len(context)} chars" if context else ""))

    if not verbose:
        if context:
            print(f"{'─' * 55}\nCONTEXT:\n{'─' * 55}\n{context}\n")
        print(f"{'─' * 55}\nEXTRACTED TEXT:\n{'─' * 55}\n{extracted}\n{'─' * 55}")

    if ocr_only:
        return (image_path.name, context, extracted, "")

    print(f"\n[2/2] Translating...")
    print(f"      Model: {model_translate}")

    translated = translate_text(text=extracted, model=model_translate, verbose=verbose)

    if not verbose:
        print(f"\n{'─' * 55}\nTRANSLATION:\n{'─' * 55}\n{translated}\n{'─' * 55}")

    return (image_path.name, context, extracted, translated)


def _list_models():
    try:
        r = requests.get(API_TAGS, timeout=10)
        if r.status_code == 200:
            models = r.json().get("models", [])
            if not models:
                print("No models installed. Pull: ollama pull <name>")
                return
            print("Installed models:")
            print("-" * 45)
            for m in models:
                print(f"  {m['name']:<30} {m.get('size', 0) / 1e9:.1f} GB")
            return
        print(f"Error: {r.text}")
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to Ollama.")
        sys.exit(1)


def _setup(vision: str, translate: str):
    print("OCR Translate — Setup\n" + "=" * 45)
    if not _check_ollama():
        print("\nOllama not running. Install: curl -fsSL https://ollama.com/install.sh | sh")
        print("Start: ollama serve")
        sys.exit(1)
    print(f"\n✓ Ollama at {OLLAMA_HOST}")
    print(f"\nModels in .env:")
    print(f"  Vision:      {vision}")
    print(f"  Translation: {translate}")
    print(f"\nPull commands:")
    print(f"  ollama pull {vision}")
    print(f"  ollama pull {translate}")


def main():
    parser = argparse.ArgumentParser(description="OCR Translate — Manga OCR + translation via Ollama")
    parser.add_argument("image", nargs="?", help="Path to image file or directory (with --batch)")
    parser.add_argument("--ocr-only", action="store_true", help="Skip translation")
    parser.add_argument("--translate-only", type=str, metavar="TEXT", help="Translate a text string")
    parser.add_argument("--model-vision", type=str, default=VISION_MODEL, help=f"Vision model (default: {VISION_MODEL})")
    parser.add_argument("--model-translate", type=str, default=TRANSLATION_MODEL, help=f"Translation model (default: {TRANSLATION_MODEL})")
    parser.add_argument("--source-lang", type=str, help="Source language override")
    parser.add_argument("--target-lang", type=str, help="Target language override")
    parser.add_argument("--output", type=str, help="Output file path")
    parser.add_argument("--batch", action="store_true", help="Process all images in a directory")
    parser.add_argument("--setup", action="store_true", help="Show setup guide")
    parser.add_argument("--list-models", action="store_true", help="List installed Ollama models")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    if args.list_models:
        return _list_models()
    if args.setup:
        return _setup(args.model_vision, args.model_translate)

    # Translate-only mode
    if args.translate_only is not None:
        text_input = args.translate_only
        if text_input == "-":
            text_input = sys.stdin.read()
        if not _check_ollama():
            sys.exit("ERROR: Ollama not running. Start: ollama serve")
        from src.translate import translate_text
        try:
            result = translate_text(text=text_input, model=args.model_translate, verbose=args.verbose)
            print(f"TRANSLATION:\n{result}")
            if args.output:
                Path(args.output).write_text(result, encoding="utf-8")
                print(f"\nSaved: {args.output}")
        except RuntimeError as e:
            sys.exit(f"ERROR: {e}")
        return

    if not args.image:
        parser.print_help()
        sys.exit(1)

    image_path = Path(args.image)

    if not _check_ollama():
        sys.exit("ERROR: Ollama not running. Start: ollama serve")

    # ── Batch mode ──────────────────────────────────────────────────────
    if args.batch:
        if not image_path.is_dir():
            sys.exit(f"ERROR: --batch needs a directory, got: {args.image}")

        exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
        images = sorted(
            [p for p in image_path.iterdir() if p.is_file() and p.suffix.lower() in exts],
            key=_natural_key,
        )
        if not images:
            sys.exit(f"ERROR: No images in {args.image}")

        total = len(images)
        from src.ocr import extract_text as ocr
        from src.config import OCR_BUBBLE_SYSTEM_PROMPT, OCR_BUBBLE_USER_PROMPT

        out_dir = Path("outputs")
        out_dir.mkdir(parents=True, exist_ok=True)
        combined = out_dir / "batch_extracted.txt"
        with open(combined, 'w', encoding='utf-8') as f:
            f.write(f"Batch — {total} pages from {image_path.name}\nModel: {args.model_vision}\n{'─' * 45}\n\n")

        all_texts: list[tuple[str, str]] = []
        success = 0
        t0 = time.time()

        for i, img in enumerate(images, 1):
            sys.stdout.write(f"  [{i}/{total}] {img.name:<30}")
            sys.stdout.flush()

            text = ""
            for attempt in range(3):
                try:
                    _, text = ocr(
                        image_path=img, model=args.model_vision,
                        source_lang=args.source_lang,
                        custom_prompt=OCR_BUBBLE_USER_PROMPT,
                        custom_system_prompt=OCR_BUBBLE_SYSTEM_PROMPT,
                        verbose=False,
                    )
                    break
                except RuntimeError:
                    if attempt < 2:
                        time.sleep(3)
                    else:
                        text = "[ERROR: empty after 3 attempts]"

            with open(combined, 'a', encoding='utf-8') as f:
                f.write(f"=== PAGE {i}: {img.name} ===\n{text}\n\n")

            all_texts.append((img.name, text))
            if "[ERROR" not in text and text.strip():
                success += 1

            elapsed = time.time() - t0
            spd = f"{elapsed / i:.0f}s/pg" if elapsed else ""
            ok = "✓" if text.strip() else "✗"
            sys.stdout.write(f"\r  [{i}/{total}] {img.name}: {len(text)} chars ({spd}) {ok}\n")
            sys.stdout.flush()

        print(f"\n{'─' * 45}")
        print(f"Extracted: {success}/{total} pages ({sum(len(t) for _, t in all_texts)} chars)")

        if args.ocr_only:
            return print(f"Saved: {combined}")

        from src.translate import translate_text_batch

        print(f"\nTranslating all {total} pages...", flush=True)
        translated = translate_text_batch(
            all_texts=all_texts, model=args.model_translate, verbose=args.verbose,
        )

        out = Path(args.output or "outputs/batch_translation.txt")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(translated, encoding="utf-8")
        pages_found = len(re.findall(r'=== PAGE \d+ ===', translated))
        print(f"COMPLETE: {pages_found} pages")
        print(f"Saved: {out}")
        return

    # ── Single-image mode ───────────────────────────────────────────────
    if not image_path.is_file():
        sys.exit(f"ERROR: Image not found: {args.image}")

    try:
        name, context, extracted, translated = _process_single(
            image_path, args.model_vision, args.model_translate,
            args.ocr_only, args.verbose,
        )
        if args.output:
            out = Path(args.output)
            content = f"CONTEXT: {context}\n\n{translated or extracted}" if context else (translated or extracted)
            out.with_suffix(".trans.txt" if translated else ".txt").write_text(content, encoding="utf-8")
            print(f"Saved: {out}")
    except RuntimeError as e:
        sys.exit(f"ERROR: {e}")


if __name__ == "__main__":
    main()
