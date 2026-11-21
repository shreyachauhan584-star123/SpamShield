"""Secure, in-memory handling of user-uploaded screenshots. Nothing is written to disk."""
from __future__ import annotations

import warnings
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from config import MAX_IMAGE_MB, MAX_IMAGE_PIXELS, MIN_IMAGE_SIDE

ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}


class ImageValidationError(ValueError):
    """`.code`: empty | too_large | not_an_image | unsupported_format | too_many_pixels | too_small"""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


def validate_image(data) -> Image.Image:
    """Return a safe RGB image or raise ImageValidationError. Checks size, real format (not the file name),
    pixel budget (decompression bombs), orientation; metadata (EXIF/GPS) is discarded because we never re-save the file."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ImageValidationError("empty")
    if len(data) > MAX_IMAGE_MB * 1024 * 1024:
        raise ImageValidationError("too_large")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            probe = Image.open(BytesIO(data))
            fmt, (w, h) = probe.format, probe.size
            probe.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageValidationError("not_an_image") from exc
    if fmt not in ALLOWED_FORMATS:
        raise ImageValidationError("unsupported_format")
    if w * h > MAX_IMAGE_PIXELS:
        raise ImageValidationError("too_many_pixels")
    if min(w, h) < MIN_IMAGE_SIDE:
        raise ImageValidationError("too_small")
    try:
        img = Image.open(BytesIO(data))
        img.load()
    except (OSError, SyntaxError, ValueError) as exc:
        raise ImageValidationError("not_an_image") from exc
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, rgba)
    return img.convert("RGB")


def preprocess_variants(img: Image.Image) -> list[tuple[str, Image.Image]]:
    """Grayscale variants that help OCR on phone screenshots: contrast-stretched, dark-mode inverted, adaptive threshold."""
    g = ImageOps.grayscale(img)
    w, h = g.size
    if w < 1000:
        g = g.resize((1000, max(1, int(h * 1000 / w))), Image.LANCZOS)
    elif w > 2400:
        g = g.resize((2400, max(1, int(h * 2400 / w))), Image.LANCZOS)
    g = ImageOps.autocontrast(g)
    variants = []
    mean = sum(g.resize((64, 64)).getdata()) / (64 * 64)
    if mean < 110:                                   # dark-mode chat: light text on dark background
        variants.append(("inverted", ImageOps.invert(g)))
    variants.append(("contrast", g))
    try:
        import cv2
        import numpy as np
        arr = np.array(variants[0][1])
        th = cv2.adaptiveThreshold(arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)
        variants.append(("threshold", Image.fromarray(th)))
    except Exception:  # noqa: BLE001 - OpenCV is optional
        pass
    return variants
