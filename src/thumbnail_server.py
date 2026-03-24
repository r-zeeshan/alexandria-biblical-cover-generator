"""On-demand thumbnail generation and lookup."""

from __future__ import annotations

import functools
import hashlib
import mimetypes
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, unquote, urlparse

from PIL import Image

try:
    from src.logger import get_logger
except Exception:  # pragma: no cover - fallback when package imports are unavailable
    import logging

    def get_logger(name: str):  # type: ignore[no-redef]
        return logging.getLogger(name)


logger = get_logger(__name__)


_ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


@functools.lru_cache(maxsize=50)
def _read_thumbnail_cached(path: str, mtime_ns: int, size_bytes: int) -> bytes:
    del mtime_ns, size_bytes
    return Path(path).read_bytes()


def normalize_relative_path_token(relative_path: str) -> str:
    token = str(relative_path or "").strip()
    if not token:
        return ""
    raw = token
    try:
        parsed = urlparse(raw)
        if parsed.path in {"/api/thumbnail", "/api/asset"}:
            api_path = str(parse_qs(parsed.query).get("path", [""])[0] or "").strip()
            if api_path:
                raw = api_path
    except Exception:
        raw = token
    try:
        raw = unquote(str(raw or ""))
    except Exception:
        raw = str(raw or "")
    raw = raw.split("#", 1)[0].split("?", 1)[0]
    return raw.lstrip("/").strip()


def _matches_magic_bytes(source: Path) -> bool:
    try:
        head = source.read_bytes()[:16]
    except OSError:
        return False
    if len(head) < 3:
        return False
    if head.startswith(b"\xff\xd8\xff"):  # JPEG
        return True
    if head.startswith(b"\x89PNG\r\n\x1a\n"):  # PNG
        return True
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":  # WEBP
        return True
    return False


class ThumbnailServer:
    SIZES = {
        "small": 200,
        "medium": 400,
        "large": 800,
    }

    def __init__(self, *, project_root: Path, cache_dir: Path, allowed_roots: Iterable[Path] | None = None):
        self.project_root = project_root.resolve()
        self.cache_dir = cache_dir.resolve()
        roots = list(allowed_roots or [self.project_root])
        self.allowed_roots = [Path(root).resolve() for root in roots]
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _is_allowed_source(self, source: Path) -> bool:
        for root in self.allowed_roots:
            try:
                source.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def _resolve_source(self, relative_path: str) -> Path | None:
        token = normalize_relative_path_token(relative_path)
        if not token:
            return None
        if "\x00" in token:
            return None
        if ".." in token.replace("\\", "/"):
            return None
        source = (self.project_root / token).resolve()
        try:
            source.relative_to(self.project_root)
        except ValueError:
            return None
        if not self._is_allowed_source(source):
            return None
        if not source.exists() or not source.is_file():
            return None
        mime_type, _encoding = mimetypes.guess_type(str(source))
        if str(mime_type or "").strip().lower() not in _ALLOWED_MIME_TYPES:
            return None
        if not _matches_magic_bytes(source):
            return None
        return source

    def thumbnail_for(self, *, relative_path: str, size: str) -> Path | None:
        source = self._resolve_source(relative_path)
        if source is None:
            return None
        if size not in self.SIZES:
            return None

        rel = source.relative_to(self.project_root)
        digest = hashlib.sha1(str(rel).encode("utf-8"), usedforsecurity=False).hexdigest()[:16]
        target = self.cache_dir / size / rel.parent / f"{rel.stem}-{digest}.jpg"
        if target.exists():
            return target

        max_dim = self.SIZES[size]
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with Image.open(source) as img:
                img.verify()
            with Image.open(source) as img:
                rgb = img.convert("RGB")
                rgb.thumbnail((max_dim, max_dim), Image.LANCZOS)
                rgb.save(target, format="JPEG", quality=82, optimize=True)
        except Exception as exc:
            # Non-image/corrupt sources should fail closed without bubbling to API handlers.
            logger.warning("Thumbnail generation rejected source: %s", exc)
            try:
                if target.exists():
                    target.unlink()
            except Exception as cleanup_exc:
                logger.warning("Thumbnail cleanup failed: %s", cleanup_exc)
            return None
        return target

    def thumbnail_bytes_for(self, *, relative_path: str, size: str) -> bytes | None:
        thumb = self.thumbnail_for(relative_path=relative_path, size=size)
        if thumb is None:
            return None
        try:
            stat = thumb.stat()
        except OSError:
            return None
        try:
            return _read_thumbnail_cached(str(thumb), int(stat.st_mtime_ns), int(stat.st_size))
        except OSError:
            return None
