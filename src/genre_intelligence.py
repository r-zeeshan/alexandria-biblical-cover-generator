"""Genre detection + prompt composition helpers for iterate generation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src import config, safe_json


_STOPWORDS = {
    "a",
    "an",
    "the",
    "of",
    "or",
    "and",
    "to",
    "for",
    "on",
    "in",
    "with",
    "from",
    "by",
    "at",
    "into",
    "other",
    "stories",
    "complete",
}

_TITLE_KEYWORD_OVERRIDES: dict[str, list[str]] = {
    "a room with a view": ["room", "view", "window", "italian villa", "florentine landscape"],
    "moby dick or the whale": ["whale", "ocean", "ship", "harpoon", "vast sea"],
    "crime and punishment": ["guilt", "justice", "urban poverty", "st petersburg"],
}


def _slug(value: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return token


def _clean_text(value: str) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def genre_prompts_path(*, config_dir: Path | None = None) -> Path:
    root = config_dir or config.CONFIG_DIR
    return root / "genre_prompts.json"


def load_genre_prompts(*, path: Path | None = None, config_dir: Path | None = None) -> dict[str, Any]:
    payload = safe_json.load_json(path or genre_prompts_path(config_dir=config_dir), {})
    return payload if isinstance(payload, dict) else {}


def normalize_genre(raw_genre: str | None, *, prompts: dict[str, Any] | None = None) -> str:
    token = _slug(str(raw_genre or ""))
    if not token:
        return ""
    rows = prompts if isinstance(prompts, dict) else {}
    aliases = rows.get("aliases", {}) if isinstance(rows.get("aliases", {}), dict) else {}
    if token in aliases:
        return _slug(str(aliases.get(token, "")))
    for alias, mapped in aliases.items():
        if _slug(alias) == token:
            return _slug(str(mapped))
    return token


def infer_genre(
    *,
    title: str,
    author: str = "",
    metadata_genre: str = "",
    prompts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prompts = prompts if isinstance(prompts, dict) else {}
    explicit = normalize_genre(metadata_genre, prompts=prompts)
    if explicit:
        return {"genre": explicit, "source": "metadata", "matched_keywords": []}

    haystack = f"{_clean_text(title)} {_clean_text(author)}".strip()
    rules = prompts.get("keyword_rules", []) if isinstance(prompts.get("keyword_rules", []), list) else []
    for row in rules:
        if not isinstance(row, dict):
            continue
        matches = row.get("match", [])
        if not isinstance(matches, list):
            continue
        tokens = [str(item).strip().lower() for item in matches if str(item).strip()]
        hit = [token for token in tokens if token and token in haystack]
        if not hit:
            continue
        mapped = normalize_genre(str(row.get("genre", "")), prompts=prompts)
        if mapped:
            return {"genre": mapped, "source": "keyword_rule", "matched_keywords": hit}

    default_genre = normalize_genre(str(prompts.get("default_genre", "literary_fiction")), prompts=prompts)
    return {"genre": default_genre or "literary_fiction", "source": "default", "matched_keywords": []}


def extract_title_keywords(*, title: str, limit: int = 6) -> list[str]:
    cleaned = _clean_text(title)
    if not cleaned:
        return []

    override = _TITLE_KEYWORD_OVERRIDES.get(cleaned)
    if override:
        return override[: max(1, int(limit))]

    words = [token for token in cleaned.split(" ") if token and token not in _STOPWORDS and len(token) > 2]
    seen: set[str] = set()
    out: list[str] = []
    for token in words:
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
        if len(out) >= max(1, int(limit)):
            break
    return out


def genre_modifiers_for(genre: str, *, prompts: dict[str, Any]) -> tuple[str, str]:
    token = normalize_genre(genre, prompts=prompts)
    row = prompts.get(token, {}) if isinstance(prompts.get(token), dict) else {}
    positive = str(row.get("positive_modifier", "")).strip()
    negative = str(row.get("negative_modifier", "")).strip()
    return positive, negative


def compose_prompt(
    *,
    base_style_prompt: str,
    template_modifier: str,
    genre_modifier: str,
    title_keywords: list[str],
    negative_prompt: str = "",
    genre_negative_modifier: str = "",
) -> dict[str, Any]:
    parts = [
        str(base_style_prompt or "").strip(),
        str(template_modifier or "").strip(),
        str(genre_modifier or "").strip(),
        ", ".join([str(item).strip() for item in (title_keywords or []) if str(item).strip()]),
    ]
    positive_parts = [part for part in parts if part]
    positive_prompt = ", ".join(positive_parts)

    negatives = [str(negative_prompt or "").strip(), str(genre_negative_modifier or "").strip()]
    negative_joined = ", ".join([part for part in negatives if part])
    full_prompt = positive_prompt if not negative_joined else f"{positive_prompt}, avoid: {negative_joined}"
    return {
        "base": str(base_style_prompt or "").strip(),
        "template": str(template_modifier or "").strip(),
        "genre": str(genre_modifier or "").strip(),
        "title_keywords": [str(item).strip() for item in (title_keywords or []) if str(item).strip()],
        "negative": negative_joined,
        "positive_prompt": positive_prompt,
        "prompt": full_prompt,
    }
