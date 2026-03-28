"""Tests for biblical prompt generation using enrichment data."""
import json
from pathlib import Path
import pytest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.prompt_generator import _motif_for_book, BookMotif


def _sample_biblical_book():
    """Return a minimal biblical book dict with enrichment."""
    return {
        "number": 1,
        "title": "Gospel of Bartholomew",
        "author": "Traditionally attributed to Bartholomew the Apostle",
        "enrichment": {
            "iconic_scenes": [
                "Christ standing at the edge of a fiery abyss, arms raised, as the sky splits open",
                "A massive angelic figure with six wings hovering above a crumbling ancient city",
            ],
            "visual_motifs": [
                "a shaft of divine light piercing absolute darkness",
                "ancient scrolls and weathered manuscripts",
                "winged celestial beings in luminous robes",
            ],
            "symbolic_elements": [
                "a shaft of divine light piercing absolute darkness",
                "ancient scrolls and weathered manuscripts",
            ],
            "color_palette_suggestion": "deep crimson and molten gold against charcoal darkness",
            "art_period_match": "classical oil painting / Renaissance religious illustration",
            "emotional_tone": "sacred mystery and hidden revelation",
            "setting_primary": "the heavenly throne room bathed in blinding divine light",
            "key_characters": ["Christ / The Savior", "Satan / Beliar"],
        },
    }


def test_motif_from_enrichment():
    book = _sample_biblical_book()
    motif = _motif_for_book(book)
    assert "fiery abyss" in motif.iconic_scene or "Christ" in motif.iconic_scene
    assert "pivotal narrative tableau" not in motif.iconic_scene


def test_motif_uses_visual_motifs():
    book = _sample_biblical_book()
    motif = _motif_for_book(book)
    assert motif.symbolic_theme != ""
    assert "core themes represented by allegorical objects" not in motif.symbolic_theme


def test_motif_fallback_without_enrichment():
    book = {"title": "Unknown Book", "author": "Unknown"}
    motif = _motif_for_book(book)
    assert "pivotal narrative tableau" in motif.iconic_scene


def test_motif_from_real_catalog():
    catalog_path = Path(__file__).resolve().parent.parent / "config" / "book_catalog.json"
    if not catalog_path.exists():
        pytest.skip("book_catalog.json not found")
    with open(catalog_path, encoding="utf-8") as f:
        books = json.load(f)
    book = next((b for b in books if b.get("enrichment", {}).get("iconic_scenes")), None)
    if not book:
        pytest.skip("No books with enrichment found")
    motif = _motif_for_book(book)
    assert "pivotal narrative tableau" not in motif.iconic_scene


def test_biblical_templates_file_valid():
    """Biblical prompt templates file should exist and have correct structure."""
    path = Path(__file__).resolve().parent.parent / "config" / "prompt_templates_biblical.json"
    assert path.exists(), "prompt_templates_biblical.json not found"

    with open(path, encoding="utf-8") as f:
        templates = json.load(f)

    assert "style_groups" in templates
    assert "variants" in templates
    assert "negative_prompt" in templates
    assert "generation_params" in templates
    assert len(templates["variants"]) == 5

    for key, variant in templates["variants"].items():
        assert "name" in variant, f"Variant {key} missing 'name'"
        assert "template" in variant, f"Variant {key} missing 'template'"
        assert "style_group" in variant, f"Variant {key} missing 'style_group'"

    neg = templates["negative_prompt"].lower()
    assert "modern" in neg or "contemporary" in neg


def test_catalog_has_prompt_templates_field():
    """Biblical catalog entry should reference its own prompt templates file."""
    catalogs_path = Path(__file__).resolve().parent.parent / "config" / "catalogs.json"
    with open(catalogs_path, encoding="utf-8") as f:
        data = json.load(f)

    biblical = next((c for c in data["catalogs"] if c["id"] == "biblical"), None)
    assert biblical is not None
    assert "prompt_templates_file" in biblical
    assert biblical["prompt_templates_file"] == "config/prompt_templates_biblical.json"

    templates_path = Path(__file__).resolve().parent.parent / biblical["prompt_templates_file"]
    assert templates_path.exists()


def test_generate_all_biblical_prompts():
    """Generate prompts for all 211 books and verify none are generic fallback."""
    from src.prompt_generator import generate_prompts_for_book

    catalog_path = Path(__file__).resolve().parent.parent / "config" / "book_catalog.json"
    templates_path = Path(__file__).resolve().parent.parent / "config" / "prompt_templates_biblical.json"

    if not catalog_path.exists() or not templates_path.exists():
        pytest.skip("Required files not found")

    with open(catalog_path, encoding="utf-8") as f:
        books = json.load(f)
    with open(templates_path, encoding="utf-8") as f:
        templates = json.load(f)

    enriched_count = 0
    total_prompts = 0

    for book in books:
        prompts = generate_prompts_for_book(book, templates)
        assert len(prompts) == 5, f"Book #{book['number']} should have 5 prompts"
        total_prompts += 5

        if book.get("enrichment", {}).get("iconic_scenes"):
            enriched_count += 1
            assert "pivotal narrative tableau" not in prompts[0].prompt

    assert total_prompts == len(books) * 5
    assert enriched_count >= 200, f"Only {enriched_count} books had enrichment data"
