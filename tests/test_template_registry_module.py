from __future__ import annotations

import json
from pathlib import Path

from src import template_registry as tr


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_template_registry_config_has_minimum_templates_and_required_fields():
    rows = tr.load_registry(path=PROJECT_ROOT / "config" / "template_registry.json")
    assert len(rows) >= 10
    required = {
        "id",
        "name",
        "description",
        "genres",
        "font_pairing",
        "color_palette",
        "element_positioning",
        "prompt_modifier",
    }
    for row in rows:
        assert required.issubset(row.keys())
        assert row["id"]
        assert isinstance(row["genres"], list)
        assert row["prompt_modifier"]


def test_template_registry_filter_and_get_by_id(tmp_path: Path):
    registry_path = tmp_path / "template_registry.json"
    registry_path.write_text(
        json.dumps(
            [
                {
                    "id": "thriller_dark",
                    "name": "Thriller",
                    "description": "dark",
                    "genres": ["thriller", "mystery"],
                    "font_pairing": {"title": "A", "author": "B"},
                    "color_palette": {"primary": "#000"},
                    "element_positioning": {"title": "top"},
                    "prompt_modifier": "dark suspense",
                },
                {
                    "id": "romance_soft",
                    "name": "Romance",
                    "description": "soft",
                    "genres": ["romance"],
                    "font_pairing": {"title": "A", "author": "B"},
                    "color_palette": {"primary": "#fff"},
                    "element_positioning": {"title": "top"},
                    "prompt_modifier": "soft warm",
                },
            ]
        ),
        encoding="utf-8",
    )
    thriller = tr.list_templates(path=registry_path, genre="thriller")
    assert len(thriller) == 1
    assert thriller[0]["id"] == "thriller_dark"

    unknown = tr.list_templates(path=registry_path, genre="not_a_genre")
    assert len(unknown) == 2

    fetched = tr.get_template(path=registry_path, template_id="romance_soft")
    assert fetched is not None
    assert fetched["name"] == "Romance"

