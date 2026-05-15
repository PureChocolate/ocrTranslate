# OCR Translate

**AI-powered manga/comic translation pipeline** — extracts Japanese text from images using a local vision-language model and translates it via a separate local LLM. No cloud APIs, no Tesseract, no manual preprocessing.

---

## Overview

OCR Translate processes comic and manga pages through a two-stage AI pipeline:

1. **Vision Model** (Qwen3-VL 8B) scans the raw image and extracts speech bubble text
2. **Language Model** (TranslateGemma 12B) translates the extracted text to natural English

Both models run locally through [Ollama](https://ollama.com), keeping all data on-device with zero external API calls. The pipeline handles vertical Japanese text, varied bubble layouts, sound effects, and NSFW content without censorship (with appropriate model selection).

---

## Features

- **Zero preprocessing** — raw images go directly to the vision model; no grayscale, thresholding, or denoising required
- **Vertical text support** — vision models natively understand right-to-left Japanese reading order
- **Streaming batch mode** — processes 50+ pages sequentially with immediate file writes per page; survives crashes without data loss
- **Minimal prompts** — deliberately terse instructions (2–3 lines) to minimize token waste and prevent model confusion
- **Configurable models** — any Ollama vision model for extraction, any Ollama text model for translation
- **GPU-accelerated** — vision encoding and text generation both run on GPU when properly configured
- **563 lines of Python** — light, maintainable, no framework overhead

---

## Architecture

```
images/                   # Input: .png, .jpg, .webp pages
    │
    ▼
┌─────────────────────────────────────────────┐
│  src/preprocess.py  (43 lines)              │
│  Loads image, downscales to config size,    │
│  encodes to base64 for Ollama API           │
└────────────────┬────────────────────────────┘
                 │ base64
                 ▼
┌─────────────────────────────────────────────┐
│  src/ocr.py  (94 lines)                     │
│  POST /api/chat to vision model             │
│  Returns extracted Japanese text             │
└────────────────┬────────────────────────────┘
                 │ raw text
                 ▼
┌─────────────────────────────────────────────┐
│  src/translate.py  (113 lines)              │
│  Strips furigana, POST /api/chat to LLM    │
│  Returns natural English translation         │
└────────────────┬────────────────────────────┘
                 │
                 ▼
            outputs/                          
       batch_translation.txt
```

**Data flow between modules:**
- `preprocess.py` → `ocr.py`: base64-encoded image string
- `ocr.py` → `translate.py`: raw Japanese text (furigana annotations stripped before sending)
- All modules import from `config.py`, which loads settings from `.env`

---

## Quickstart

### Prerequisites

- [Ollama](https://ollama.com) installed and running
- Python 3.10+

### 1. Pull models

```bash
ollama pull qwen3-vl:8b         # Vision model for text extraction
ollama pull translategemma:12b  # Translation model
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure

Copy `.env.example` to `.env` and edit if needed:

```env
OLLAMA_HOST=http://localhost:11434
VISION_MODEL=qwen3-vl:8b
TRANSLATION_MODEL=translategemma:12b
SOURCE_LANG=Japanese
TARGET_LANG=English
MAX_IMAGE_DIMENSION=1024
TEMPERATURE=0.5
REQUEST_TIMEOUT=120
```

### 4. Run

```bash
# Single image
python run.py images/comic.png

# Batch process a folder (streaming writes, survives crashes)
python run.py images/chapter1/ --batch

# Extract text only (no translation)
python run.py images/chapter1/ --batch --ocr-only

# Translate a text string directly
python run.py --translate-only "こんにちは"
```

---

## Commands

| Command | Description |
|---|---|
| `run.py <image>` | Extract text and translate |
| `run.py <dir> --batch` | Process all images in a directory |
| `run.py <image> --ocr-only` | Extract text only |
| `run.py --translate-only "text"` | Translate a text string |
| `run.py --setup` | Show model setup instructions |
| `run.py --list-models` | List installed Ollama models |
| `run.py --verbose` | Print detailed API request/response info |
| `run.py --output <path>` | Save output to file |

---

## Configuration (.env)

| Setting | Default | Purpose |
|---|---|---|
| `VISION_MODEL` | `qwen3-vl:8b` | Model that reads text from images (must support vision) |
| `TRANSLATION_MODEL` | `translategemma:12b` | Model that translates text |
| `MAX_IMAGE_DIMENSION` | `1024` | Downscale images larger than this (pixels) |
| `TEMPERATURE` | `0.5` | Translation creativity (0.0 = deterministic, 1.0 = creative) |
| `REQUEST_TIMEOUT` | `120` | API request timeout in seconds |
| `SOURCE_LANG` | `Japanese` | Source language hint |
| `TARGET_LANG` | `English` | Target language |

---

## How It Works

### Text Extraction (Vision Model)

The system sends a base64-encoded image to Ollama's `/api/chat` endpoint with a minimal prompt:

> *"Output only the raw Japanese text from each speech bubble. No translations, no descriptions, no commentary. Ignore any small furigana/ruby text next to kanji. Just the main text."*

The vision model returns the extracted text directly. No scene descriptions, no formatting — just the raw dialogue. The response is parsed (handles context/text splitting on `---` delimiters for single-image mode, or returns text directly for batch mode).

### Furigana Stripping

Japanese manga often includes small reading characters (furigana) next to kanji. Before sending extracted text to the translator, a regex strips kana-only parenthetical content:

```python
# 同(おな)じ顔(かお) → 同じ顔
re.sub(r'\([ぁ-ゟァ-ヿー]+\)', '', text)
```

This ensures the translator sees clean, uninterrupted Japanese without reading annotations that would confuse tokenization.

### Translation (Language Model)

Clean text is sent to the translation model with a minimal prompt:

> *"Translate Japanese manga dialogue to natural English." / "Translate this manga text to English. Output only the translation."*

For batch mode, all pages are consolidated into one request with `=== PAGE N ===` markers. The translation model reads the full narrative arc before translating each page, producing contextually aware translations.

### Batch Mode Resilience

Batch processing writes each page's extracted text to `outputs/batch_extracted.txt` immediately after extraction. If the process crashes on page 40 of 58, pages 1–39 are already saved. Restarting continues from where it left off (the output file is rewritten each batch run, so restart from the beginning — no duplicate pages are possible).

---

## Supported Image Formats

PNG, JPEG, WebP, BMP, TIFF — anything [Pillow](https://python-pillow.org) can open.

---

## Dependencies

| Package | Purpose |
|---|---|
| `Pillow` | Image loading, resizing, base64 encoding |
| `requests` | HTTP client for Ollama API |
| `python-dotenv` | Configuration via `.env` file |

No OCR library, no OpenCV, no CUDA SDKs. The AI models handle everything.

---

## Performance Notes

- **GPU**: Vision encoding and LLM inference both require GPU for acceptable speed. CPU-only inference is 10–50x slower.
- **AMD GPUs**: Ollama supports AMD via HIP SDK on Windows. If inference is slow (40s+/page), verify GPU utilization in Task Manager.
- **Batch speed**: With `keep_alive`, the vision model loads once and stays in VRAM. 58 pages typically complete in 10–25 minutes depending on GPU.

---

## Project Structure

```
ocrTranslate/
├── .env                    # Local config (gitignored)
├── .env.example            # Config template
├── requirements.txt        # Python dependencies
├── run.py                  # CLI entry point
├── README.md
├── images/                 # Input images
├── outputs/                # Generated files (gitignored)
└── src/
    ├── __init__.py
    ├── config.py           # Central config + AI prompts
    ├── preprocess.py       # Image load/resize/base64
    ├── ocr.py              # Vision model text extraction
    └── translate.py        # Translation + furigana stripping
```
