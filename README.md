# OCR Translate

**AI-powered manga/comic translation pipeline** — extracts Japanese text from images using a local vision-language model and translates it via a separate local LLM. Ships with a Flask API server and is live at [gurkirat.net](https://gurkirat.net/#projects). No cloud APIs, no Tesseract, no manual preprocessing.

---

## Overview

OCR Translate processes comic and manga pages through a two-stage AI pipeline:

1. **Vision Model** (Qwen3-VL 8B) scans the raw image and extracts speech bubble text
2. **Language Model** (TranslateGemma 12B) translates the extracted text to natural English

Both models run locally through [Ollama](https://ollama.com), keeping all data on-device with zero external API calls. The pipeline handles vertical Japanese text, varied bubble layouts, sound effects, and NSFW content without censorship (with appropriate model selection).

A lightweight Flask server (`ocr_server.py`) exposes the pipeline over HTTP, deployed behind Cloudflare Tunnel with automatic HTTPS. Live demo forms are integrated into the author's portfolio site.

---

## Features

- **Zero preprocessing** — raw images go directly to the vision model; no grayscale, thresholding, or denoising required
- **Vertical text support** — vision models natively understand right-to-left Japanese reading order
- **Streaming batch mode** — processes 50+ pages sequentially with immediate file writes per page; survives crashes without data loss
- **Deterministic output** — temperature-controlled for both OCR extraction and translation (set to 0.3 for consistent results)
- **Furigana-aware prompts** — instructions tell the vision model to ignore ruby/furigana text at extraction time, with regex fallback in the translation module
- **Configurable models** — any Ollama vision model for extraction, any Ollama text model for translation
- **GPU-accelerated** — vision encoding and text generation both run on GPU when properly configured
- **Web API + live demo** — Flask server with 3 endpoints (image OCR+translate, text translate, health check); integrated into portfolio site via Cloudflare Tunnel
- **~650 lines of Python** (pipeline + server) — light, maintainable, no framework overhead beyond Flask

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Web Layer                             │
│                                                              │
│  gurkirat.net (GitHub Pages)                                 │
│    │  fetch() POST /api/translate                            │
│    │  fetch() POST /api/translate-text                       │
│    ▼                                                         │
│  ocr.gurkirat.net (Cloudflare Tunnel → auto-HTTPS)           │
│    │                                                         │
│    ▼                                                         │
│  ocr_server.py (Flask, port 5000)                            │
│    │  /api/translate       → run.py <image>  (full pipeline) │
│    │  /api/translate-text  → run.py --translate-only         │
│    │  /api/health          → {"status": "ok"}                │
└────────────────────────────────┬─────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                      Pipeline Layer                         │
│                                                             │
│  run.py (CLI entry point, 249 lines)                        │
│      │                                                      │
│      ▼                                                      │
│  ┌─────────────────────────────────────────┐                │
│  │  src/ocr.py  (96 lines)                 │                │
│  │  POST /api/chat to vision model         │                │
│  │  Temperature-controlled via config      │                │
│  │  Returns extracted Japanese text        │                │
│  └────────────────┬────────────────────────┘                │
│                   │ raw text                                │
│                   ▼                                         │
│  ┌─────────────────────────────────────────┐                │
│  │  src/translate.py  (113 lines)          │                │
│  │  Strips furigana, POST /api/chat to LLM │                │
│  │  Temperature-controlled via config      │                │
│  │  Returns natural English translation    │                │
│  └────────────────┬────────────────────────┘                │
│                   │                                         │
│                   ▼                                         │
│              outputs/                                       │
│         batch_translation.txt                               │
└─────────────────────────────────────────────────────────────┘
```

**Data flow between modules:**
- `preprocess.py` → `ocr.py`: base64-encoded image string
- `ocr.py` → `translate.py`: raw Japanese text (furigana stripped before sending)
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
# For web server:
pip install flask flask-cors
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
TEMPERATURE=0.3
REQUEST_TIMEOUT=120
```

### 4. Run

```bash
# CLI — single image (OCR + translate)
python run.py images/comic.png

# CLI — batch process a folder
python run.py images/chapter1/ --batch

# CLI — OCR only (extract, no translation)
python run.py images/comic.png --ocr-only

# CLI — translate text directly
python run.py --translate-only "こんにちは"

# CLI — pipe text via stdin (avoids encoding issues on Windows)
echo "こんにちは" | python run.py --translate-only -

# Web server
python ocr_server.py
# → http://localhost:5000
# → /api/translate (image upload → OCR + translation)
# → /api/translate-text (text → translation)
# → /api/health (status check)
```

---

## Web API

| Endpoint | Method | Input | Response |
|----------|--------|-------|----------|
| `/api/health` | GET | — | `{"status": "ok"}` |
| `/api/translate` | POST | `multipart/form-data` (field: `image`) | `{"extracted": "...", "translation": "...", "error": null}` |
| `/api/translate-text` | POST | `application/json` (`{"text": "..."}`) | `{"translation": "...", "error": null}` |

### Public Deployment

The included `deploy.yaml` works with [DeployBox](https://github.com/PureChocolate/deploybox) for Docker deployment. For public access, pair `ocr_server.py` with [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/):

```powershell
cloudflared tunnel create ocr-translate
cloudflared tunnel route dns ocr-translate ocr.gurkirat.net
cloudflared tunnel run ocr-translate
```

---

## Commands

| Command | Description |
|---|---|
| `run.py <image>` | Extract text and translate |
| `run.py <dir> --batch` | Process all images in a directory |
| `run.py <image> --ocr-only` | Extract text only |
| `run.py --translate-only "text"` | Translate a text string |
| `run.py --translate-only -` | Translate text from stdin (avoids Windows encoding issues) |
| `run.py --setup` | Show model setup instructions |
| `run.py --list-models` | List installed Ollama models |
| `run.py --verbose` | Print detailed API request/response info |
| `run.py --output <path>` | Save output to file |
| `ocr_server.py` | Start Flask API server on port 5000 |

---

## Configuration (.env)

| Setting | Default | Purpose |
|---|---|---|
| `VISION_MODEL` | `qwen3-vl:8b` | Model that reads text from images (must support vision) |
| `TRANSLATION_MODEL` | `translategemma:12b` | Model that translates text |
| `MAX_IMAGE_DIMENSION` | `1024` | Downscale images larger than this (pixels) |
| `TEMPERATURE` | `0.3` | Controls output consistency for both OCR and translation (0.0 = deterministic, 1.0 = creative) |
| `REQUEST_TIMEOUT` | `120` | API request timeout in seconds |
| `SOURCE_LANG` | `Japanese` | Source language hint |
| `TARGET_LANG` | `English` | Target language |

---

## How It Works

### Text Extraction (Vision Model)

The system sends a base64-encoded image to Ollama's `/api/chat` endpoint with temperature control:

> *"Extract all text from this page. Ignore any small furigana or ruby readings next to characters. Output only the main text."*

The vision model returns the extracted text directly. No scene descriptions, no formatting — just the raw dialogue. The response is parsed (handles context/text splitting on `---` delimiters for single-image mode, or returns text directly for batch mode).

Temperature is applied to both OCR and translation (same config value) for consistent, deterministic output.

### Furigana Stripping (Two Layers)

Japanese manga often includes small reading characters (furigana) next to kanji. Two layers handle this:

1. **Prompt layer** — the vision model is instructed to ignore furigana/ruby text
2. **Regex fallback** — before translation, a regex strips kana-only parenthetical content:
   ```python
   # 同(おな)じ顔(かお) → 同じ顔
   re.sub(r'\([ぁ-ゟァ-ヿー]+\)', '', text)
   ```

This ensures the translator sees clean, uninterrupted Japanese without reading annotations that would confuse tokenization.

### Translation (Language Model)

Clean text is sent to the translation model with neutral prompts (works for general Japanese, not just manga):

> *System: "You are a translator. Output only the translation, nothing else."*
> *User: "Translate this Japanese text to English. Output only the translation."*

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
| `flask` | Web API server (`ocr_server.py`) |
| `flask-cors` | CORS headers for cross-origin requests |

No OCR library, no OpenCV, no CUDA SDKs. The AI models handle everything.

---

## Performance Notes

- **GPU**: Vision encoding and LLM inference both require GPU for acceptable speed. CPU-only inference is 10–50x slower.
- **AMD GPUs**: Ollama supports AMD via HIP SDK on Windows. If inference is slow (40s+/page), verify GPU utilization in Task Manager.
- **Batch speed**: With `keep_alive`, the vision model loads once and stays in VRAM. 58 pages typically complete in 10–25 minutes depending on GPU.
- **Temperature**: Set to 0.3 for consistent, near-deterministic output. Increase for more creative/varied translations.

---

## Project Structure

```
ocrTranslate/
├── .env                    # Local config (gitignored)
├── .env.example            # Config template
├── requirements.txt        # Python dependencies
├── run.py                  # CLI entry point (249 lines)
├── ocr_server.py           # Flask API server (88 lines)
├── deploy.yaml             # DeployBox Docker config
├── README.md
├── images/                 # Input images
├── outputs/                # Generated files (gitignored)
└── src/
    ├── __init__.py
    ├── config.py           # Central config + AI prompts (55 lines)
    ├── preprocess.py       # Image load/resize/base64
    ├── ocr.py              # Vision model text extraction (96 lines)
    └── translate.py        # Translation + furigana stripping (113 lines)
```
