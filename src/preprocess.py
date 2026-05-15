"""Image loading, resizing, and base64 encoding for Ollama API."""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Union

from PIL import Image


def load_image(image_path: Union[str, Path], max_dimension: int = 2048) -> Image.Image:
    """Load an image, downscale if largest side exceeds max_dimension."""
    image_path = Path(image_path)
    if not image_path.is_file():
        raise FileNotFoundError(f"Image file not found: {image_path.resolve()}")

    image = Image.open(image_path)
    if image.mode not in ("RGB", "RGBA", "L", "P", "CMYK"):
        image = image.convert("RGB")

    width, height = image.size
    largest = max(width, height)
    if 0 < max_dimension < largest:
        scale = max_dimension / largest
        image = image.resize((int(width * scale), int(height * scale)), Image.LANCZOS)

    return image if image.mode == "RGB" else image.convert("RGB")


def encode_image(image: Image.Image, fmt: str = "PNG") -> str:
    """Encode PIL Image to raw base64 (no data URI prefix)."""
    if image.mode != "RGB":
        image = image.convert("RGB")
    buf = io.BytesIO()
    image.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def image_to_base64(image_path: Union[str, Path], max_dimension: int = 2048) -> str:
    """Load image from disk and return base64 encoding."""
    return encode_image(load_image(image_path, max_dimension))
