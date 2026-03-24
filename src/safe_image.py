"""Robust image read/write helpers for generated art and compositor paths."""

from __future__ import annotations

from contextlib import contextmanager
import io
import logging
import os
from pathlib import Path
import tempfile
import threading
import time

from PIL import Image, ImageFile, UnidentifiedImageError

logger = logging.getLogger(__name__)

_RECOVERABLE_IMAGE_ERRORS = (OSError, UnidentifiedImageError)
_TRUNCATED_IMAGE_LOCK = threading.Lock()


@contextmanager
def _allow_truncated_images():
    with _TRUNCATED_IMAGE_LOCK:
        previous = bool(ImageFile.LOAD_TRUNCATED_IMAGES)
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        try:
            yield
        finally:
            ImageFile.LOAD_TRUNCATED_IMAGES = previous


def _clone_loaded_image(image: Image.Image) -> Image.Image:
    image.load()
    return image.copy()


def _output_format_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "JPEG"
    return "PNG"


def _normalized_image_for_format(image: Image.Image, *, output_format: str) -> Image.Image:
    if output_format == "JPEG" and image.mode not in {"RGB", "L"}:
        return image.convert("RGB")
    return image.copy()


def _open_image_from_bytes(data: bytes, *, allow_truncated: bool = False) -> Image.Image:
    stream = io.BytesIO(data)
    if allow_truncated:
        with _allow_truncated_images():
            with Image.open(stream) as image:
                return _clone_loaded_image(image)
    with Image.open(stream) as image:
        return _clone_loaded_image(image)


def _open_image_from_path(path: Path, *, allow_truncated: bool = False) -> Image.Image:
    if allow_truncated:
        with _allow_truncated_images():
            with Image.open(path) as image:
                return _clone_loaded_image(image)
    with Image.open(path) as image:
        return _clone_loaded_image(image)


def atomic_save_image(path: str | Path, image: Image.Image, *, format: str | None = None, **save_kwargs) -> None:
    target = Path(path)
    output_format = str(format or _output_format_for_path(target)).upper()
    normalized = _normalized_image_for_format(image, output_format=output_format)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w+b",
        dir=str(target.parent),
        prefix=f".{target.name}.",
        suffix=f"{target.suffix or '.tmp'}",
        delete=False,
    ) as handle:
        normalized.save(handle, format=output_format, **save_kwargs)
        handle.flush()
        os.fsync(handle.fileno())
        tmp_name = handle.name
    os.replace(tmp_name, target)


def atomic_write_image_bytes(path: str | Path, image_bytes: bytes) -> None:
    target = Path(path)
    output_format = _output_format_for_path(target)
    try:
        decoded = _open_image_from_bytes(image_bytes)
    except _RECOVERABLE_IMAGE_ERRORS as exc:
        decoded = _open_image_from_bytes(image_bytes, allow_truncated=True)
        logger.warning("Recovered truncated image bytes before writing %s: %s", target, exc)
    atomic_save_image(target, decoded, format=output_format)


def load_image(
    path: str | Path,
    *,
    mode: str | None = None,
    strict_attempts: int = 2,
    retry_delay_seconds: float = 0.05,
    repair: bool = True,
) -> Image.Image:
    target = Path(path)
    last_exc: Exception | None = None
    attempts = max(1, int(strict_attempts))

    for attempt in range(1, attempts + 1):
        try:
            image = _open_image_from_path(target)
            if mode and image.mode != mode:
                image = image.convert(mode)
            return image
        except _RECOVERABLE_IMAGE_ERRORS as exc:
            last_exc = exc
            if attempt < attempts:
                time.sleep(max(0.0, float(retry_delay_seconds)) * attempt)

    image_bytes = target.read_bytes()
    try:
        recovered = _open_image_from_bytes(image_bytes, allow_truncated=True)
    except _RECOVERABLE_IMAGE_ERRORS:
        if last_exc is not None:
            raise last_exc
        raise

    if mode and recovered.mode != mode:
        recovered = recovered.convert(mode)

    if repair:
        try:
            atomic_save_image(target, recovered, format=_output_format_for_path(target))
        except Exception as repair_exc:  # pragma: no cover - defensive logging only
            logger.warning("Recovered truncated image %s but failed to rewrite normalized copy: %s", target, repair_exc)
        else:
            logger.warning("Recovered and repaired truncated image file: %s", target)

    return recovered
