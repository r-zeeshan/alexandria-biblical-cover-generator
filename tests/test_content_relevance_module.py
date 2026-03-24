from __future__ import annotations

from src import content_relevance as cr


def test_is_generic_text_flags_known_placeholder_markers():
    assert cr.is_generic_text("Iconic turning point from Emma")
    assert cr.is_generic_text("Central protagonist")
    assert not cr.is_generic_text("Eve")
    assert not cr.is_generic_text("Romeo and Juliet share a moonlit balcony meeting in Verona")


def test_resolve_prompt_context_prefers_specific_motif_data_for_known_books():
    context = cr.resolve_prompt_context(
        {
            "title": "Romeo and Juliet",
            "author": "William Shakespeare",
            "genre": "drama",
            "enrichment": {
                "protagonist": "Central protagonist",
                "iconic_scenes": ["Iconic turning point from Romeo and Juliet"],
                "era": "Historically grounded era aligned to original publication context",
            },
        }
    )

    assert "Romeo and Juliet" in context["scene"] or "Verona" in context["scene"]
    assert context["protagonist"] in {"Romeo and Juliet", "Romeo", "Juliet"}
    assert "Central protagonist" not in context["scene_with_protagonist"]


def test_ensure_prompt_book_context_injects_critical_scene_requirement_for_generic_prompt():
    prompt = "Book cover illustration only — no text. Atmospheric setting moment that signals the themes of Emma."
    enriched = {
        "protagonist": "Emma Woodhouse",
        "iconic_scenes": ["Emma Woodhouse standing in Hartfield's drawing room overlooking Highbury"],
        "era": "Regency England",
    }

    resolved = cr.ensure_prompt_book_context(
        prompt=prompt,
        book={"title": "Emma", "author": "Jane Austen", "genre": "romance", "enrichment": enriched},
        require_scene_anchor=False,
    )

    assert "CRITICAL SCENE REQUIREMENT" in resolved
    assert "Emma Woodhouse" in resolved
    assert "Hartfield" in resolved


def test_extract_character_name_and_inject_protagonist_strip_biography_text():
    protagonist = "Juliet Capulet — a young woman with long, flowing dark hair, dressed in a delicate white gown"
    scene = "Juliet stands on a moonlit balcony in Verona"

    assert cr.extract_character_name(protagonist) == "Juliet Capulet"
    injected = cr.inject_protagonist("A moonlit balcony scene in Verona", protagonist)
    assert injected.endswith("Depicted prominently: Juliet Capulet.")
    assert "long, flowing dark hair" not in injected
    assert cr.inject_protagonist(scene, protagonist) == scene
