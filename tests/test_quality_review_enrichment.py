from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace
import types

from PIL import Image

sys.modules.setdefault("pikepdf", types.SimpleNamespace())
from scripts import quality_review as qr
from src import config
from src import image_generator


def test_enrichment_health_payload_counts_real_generic_and_missing(tmp_path: Path):
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir()
    data_dir.mkdir()
    catalog_path = config_dir / "book_catalog_demo.json"
    catalog_path.write_text(
        json.dumps(
            [
                {"number": 1, "title": "Romeo and Juliet", "author": "William Shakespeare"},
                {"number": 2, "title": "Emma", "author": "Jane Austen"},
                {"number": 3, "title": "Moby Dick", "author": "Herman Melville"},
            ]
        ),
        encoding="utf-8",
    )
    enriched_path = config.enriched_catalog_path(catalog_id="demo", config_dir=config_dir)
    enriched_path.write_text(
        json.dumps(
            [
                {
                    "number": 1,
                    "title": "Romeo and Juliet",
                    "enrichment": {
                        "protagonist": "Romeo Montague",
                        "iconic_scenes": ["Romeo and Juliet meet on a moonlit Verona balcony"],
                        "era": "Renaissance Verona, noble households in conflict",
                    },
                },
                {
                    "number": 2,
                    "title": "Emma",
                    "enrichment": {
                        "protagonist": "Central protagonist",
                        "iconic_scenes": ["Iconic turning point from Emma"],
                        "era": "Historically grounded era aligned to original publication context",
                    },
                },
            ]
        ),
        encoding="utf-8",
    )
    usage_path = config.llm_usage_path(catalog_id="demo", data_dir=data_dir)
    usage_path.write_text(
        json.dumps({"last_run": {"timestamp": "2026-03-11T14:30:00Z"}}),
        encoding="utf-8",
    )

    runtime = SimpleNamespace(
        catalog_id="demo",
        book_catalog_path=catalog_path,
        config_dir=config_dir,
        data_dir=data_dir,
    )

    payload = qr._enrichment_health_payload(runtime=runtime)  # type: ignore[arg-type]
    assert payload["total_books"] == 3
    assert payload["enriched_real"] == 1
    assert payload["enriched_generic"] == 1
    assert payload["no_enrichment"] == 1
    assert payload["health"] == "critical"
    assert payload["last_enrichment_run"] == "2026-03-11T14:30:00Z"


def test_serialize_generation_results_promotes_durable_raw_art_path(tmp_path: Path):
    runtime = SimpleNamespace(
        tmp_dir=tmp_path / "tmp",
        output_dir=tmp_path / "Output Covers",
    )
    generated = runtime.tmp_dir / "generated" / "2" / "model-a" / "variant_1.png"
    generated.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 64), (12, 34, 56)).save(generated, format="PNG")

    rows = qr._serialize_generation_results(
        runtime=runtime,  # type: ignore[arg-type]
        book=2,
        job_id="job-token",
        results=[
            image_generator.GenerationResult(
                book_number=2,
                variant=1,
                prompt="Scene from Emma",
                model="model-a",
                image_path=generated,
                success=True,
                error=None,
                generation_time=1.2,
                cost=0.02,
                provider="openrouter",
            )
        ],
    )

    expected_raw = runtime.output_dir / "raw_art" / "2" / "job-token_variant_1_model-a.png"
    assert rows[0]["image_path"] == str(expected_raw)
    assert rows[0]["raw_art_path"] == str(expected_raw)
    assert rows[0]["generated_path"] == str(generated)


def test_current_run_generated_paths_keeps_generated_path_when_image_path_is_durable(tmp_path: Path):
    runtime = SimpleNamespace(
        tmp_dir=tmp_path / "tmp",
        output_dir=tmp_path / "Output Covers",
    )
    generated = runtime.tmp_dir / "generated" / "2" / "model-a" / "variant_1.png"
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_bytes(b"generated")
    durable = runtime.output_dir / "raw_art" / "2" / "job-token_variant_1_model-a.png"
    durable.parent.mkdir(parents=True, exist_ok=True)
    durable.write_bytes(b"durable")

    keep_paths = qr._current_run_generated_paths(
        runtime=runtime,  # type: ignore[arg-type]
        rows=[{"image_path": str(durable), "generated_path": str(generated)}],
    )

    assert generated.resolve() in keep_paths


def test_resolve_composited_candidate_supports_job_scoped_generated_paths(tmp_path: Path):
    runtime = SimpleNamespace(
        tmp_dir=tmp_path / "tmp",
        output_dir=tmp_path / "Output Covers",
    )
    image_path = runtime.tmp_dir / "generated" / "job-123" / "2" / "model-a" / "variant_3.png"
    expected = runtime.tmp_dir / "composited" / "job-123" / "2" / "model-a" / "variant_3.jpg"

    candidate = qr._resolve_composited_candidate(image_path, runtime=runtime)  # type: ignore[arg-type]

    assert candidate == expected


def test_job_result_rows_normalize_legacy_tmp_asset_paths():
    job = qr.job_store.JobRecord(
        id="job-1",
        idempotency_key="key-1",
        job_type="generate_cover",
        status="completed",
        catalog_id="classics",
        book_number=2,
        payload={},
        result={
            "results": [
                {
                    "image_path": "tmp/generated/2/model-a/variant_1.png",
                    "raw_art_path": "Output Covers/raw_art/2/job-token_variant_1_model-a.png",
                    "composited_path": "tmp/composited/2/model-a/variant_1.jpg",
                    "saved_composited_path": "Output Covers/saved_composites/2/job-token_variant_1_model-a.jpg",
                    "success": True,
                }
            ]
        },
        error={},
        attempts=1,
        max_attempts=3,
        priority=0,
        retry_after="",
        created_at="2026-03-19T00:00:00Z",
        updated_at="2026-03-19T00:00:00Z",
        started_at="2026-03-19T00:00:00Z",
        finished_at="2026-03-19T00:00:00Z",
        worker_id="worker-1",
    )

    row = qr._job_result_rows(job)[0]

    assert row["image_path"] == "Output Covers/raw_art/2/job-token_variant_1_model-a.png"
    assert row["generated_path"] == "tmp/generated/2/model-a/variant_1.png"
    assert row["composited_path"] == "Output Covers/saved_composites/2/job-token_variant_1_model-a.jpg"
