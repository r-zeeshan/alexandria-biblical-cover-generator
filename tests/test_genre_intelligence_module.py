from __future__ import annotations

from src import genre_intelligence as gi


def _prompts() -> dict:
    return {
        "science_fiction": {
            "positive_modifier": "space scale",
            "negative_modifier": "pastoral",
        },
        "literary_fiction": {
            "positive_modifier": "subtle symbolism",
            "negative_modifier": "generic stock",
        },
        "aliases": {"sci_fi": "science_fiction"},
        "keyword_rules": [{"match": ["galaxy", "starship"], "genre": "science_fiction"}],
        "default_genre": "literary_fiction",
    }


def test_infer_genre_prefers_metadata_then_keyword_then_default():
    prompts = _prompts()
    metadata = gi.infer_genre(
        title="Any Title",
        author="Any Author",
        metadata_genre="sci_fi",
        prompts=prompts,
    )
    assert metadata["genre"] == "science_fiction"
    assert metadata["source"] == "metadata"

    keyword = gi.infer_genre(
        title="Starship over the Galaxy",
        author="",
        metadata_genre="",
        prompts=prompts,
    )
    assert keyword["genre"] == "science_fiction"
    assert keyword["source"] == "keyword_rule"
    assert "galaxy" in keyword["matched_keywords"] or "starship" in keyword["matched_keywords"]

    default = gi.infer_genre(
        title="Quiet Reflections",
        author="Unknown",
        metadata_genre="",
        prompts=prompts,
    )
    assert default["genre"] == "literary_fiction"
    assert default["source"] == "default"


def test_compose_prompt_includes_positive_and_negative_components():
    payload = gi.compose_prompt(
        base_style_prompt="classical medallion illustration",
        template_modifier="dark dramatic lighting",
        genre_modifier="space scale and cosmic texture",
        title_keywords=["starship", "nebula"],
        negative_prompt="text, watermark",
        genre_negative_modifier="pastoral realism",
    )
    assert "classical medallion illustration" in payload["prompt"]
    assert "dark dramatic lighting" in payload["prompt"]
    assert "starship" in payload["prompt"]
    assert "avoid:" in payload["prompt"]
    assert "watermark" in payload["negative"]

