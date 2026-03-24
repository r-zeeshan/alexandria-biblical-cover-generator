#!/usr/bin/env python3
"""Validate enriched book prompts contain book-specific content."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_ENRICHED_PATH = Path("config/book_catalog_enriched.json")
KNOWN_BOOKS = (
    {
        "label": "Gulliver's Travels",
        "match": lambda normalized_title: "gulliver" in normalized_title and "travel" in normalized_title,
        "keyword_groups": (("gulliver",), ("lilliput", "lilliputian")),
    },
    {
        "label": "Moby-Dick",
        "match": lambda normalized_title: "moby" in normalized_title and "dick" in normalized_title,
        "keyword_groups": (("ahab",), ("whale", "white whale", "whaling")),
    },
    {
        "label": "Dracula",
        "match": lambda normalized_title: normalized_title == "dracula",
        "keyword_groups": (("dracula",), ("castle", "transylvania")),
    },
    {
        "label": "Pride and Prejudice",
        "match": lambda normalized_title: "pride" in normalized_title and "prejudice" in normalized_title,
        "keyword_groups": (("elizabeth",), ("darcy",)),
    },
    {
        "label": "Frankenstein",
        "match": lambda normalized_title: "frankenstein" in normalized_title and "modern prometheus" in normalized_title,
        "keyword_groups": (("creature", "monster"),),
    },
)
BANNED = [
    "Central protagonist",
    "Iconic turning point",
    "Period-appropriate settings",
    "Historically grounded era",
    "Defining confrontation involving Central",
    "Supporting cast",
    "Antagonistic force",
    "Mentor/foil",
]


def _load_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def validate_rows(rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for row in rows:
        title = str(row.get("title", "")).strip()
        enrichment = row.get("enrichment", {})
        if not isinstance(enrichment, dict) or not enrichment:
            errors.append(f"Book '{title or '?'}': NO enrichment data")
            continue

        text = json.dumps(enrichment, ensure_ascii=False)
        for phrase in BANNED:
            if phrase in text:
                errors.append(f"Book '{title or '?'}': contains BANNED phrase '{phrase}'")

        normalized_title = _normalize_text(title)
        normalized_text = _normalize_text(text)
        for known in KNOWN_BOOKS:
            if known["match"](normalized_title):
                for group in known["keyword_groups"]:
                    if not any(keyword in normalized_text for keyword in group):
                        joined = " or ".join(group)
                        errors.append(f"Book '{title}': missing keyword '{joined}'")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate enriched book prompts contain book-specific content")
    parser.add_argument("--input", type=Path, default=DEFAULT_ENRICHED_PATH)
    args = parser.parse_args()

    rows = _load_rows(args.input)
    errors = validate_rows(rows)
    if errors:
        print(f"FAILED — {len(errors)} issues:")
        for error in errors[:30]:
            print(f"  x {error}")
        if len(errors) > 30:
            print(f"  ... {len(errors) - 30} more")
        return 1

    print(f"PASSED — All {len(rows)} books have content-relevant enrichment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
