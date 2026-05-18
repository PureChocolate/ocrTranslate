from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def _parse_sections(stdout: str) -> tuple[str, str]:
    """Extract both OCR text and translation from run.py output."""
    extracted = ""
    translation = ""
    m = re.search(r'EXTRACTED TEXT:\n─+\n(.+?)\n─+', stdout, re.DOTALL)
    if m:
        extracted = m.group(1).strip()
    else:
        parts = re.split(r'\n─{10,}\n', stdout)
        extracted = parts[-1].strip() if parts else stdout.strip()
    m = re.search(r'TRANSLATION:\n─+\n(.+?)\n─+', stdout, re.DOTALL)
    if m:
        translation = m.group(1).strip()
    return extracted, translation

def _run_full(image_path: str) -> tuple[str, str, str]:
    """OCR + translate. Returns (extracted, translation, stderr)."""
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [sys.executable, "run.py", image_path],
        capture_output=True, text=True, encoding="utf-8",
        env=env,
        timeout=180,
        cwd=Path(__file__).parent,
    )
    extracted, translation = _parse_sections(result.stdout)
    return extracted, translation, result.stderr

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/translate", methods=["POST"])
def translate_image():
    if "image" not in request.files:
        return jsonify({"error": "no image file"}), 400

    file = request.files["image"]
    suffix = Path(file.filename).suffix or ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        file.save(f.name)
        tmp = f.name

    try:
        extracted, translation, stderr = _run_full(tmp)
        return jsonify({
            "extracted": extracted,
            "translation": translation,
            "error": stderr.strip() if stderr else None,
        })
    finally:
        Path(tmp).unlink(missing_ok=True)

@app.route("/api/translate-text", methods=["POST"])
def translate_text():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "no text provided"}), 400

    result = subprocess.run(
        [sys.executable, "run.py", "--translate-only", text],
        capture_output=True, text=True, timeout=60,
        cwd=Path(__file__).parent,
    )
    # strip the "TRANSLATION:" prefix from stdout
    out = result.stdout.replace("TRANSLATION:\n", "").strip()
    return jsonify({"translation": out, "error": result.stderr.strip() if result.stderr else None})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)