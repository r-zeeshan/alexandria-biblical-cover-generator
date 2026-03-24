from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import textwrap
from urllib.parse import parse_qs, urlparse

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run_app_hook(hook_name: str, payload):
    if shutil.which("node") is None:
        pytest.skip("node not installed")

    node_script = textwrap.dedent(
        f"""
        const fs = require('fs');
        const vm = require('vm');
        const payload = {json.dumps(payload)};

        global.window = {{
          Pages: {{}},
          __APP_TEST_HOOKS__: {{}},
          __INITIAL_PAGE__: 'iterate',
          innerWidth: 1280,
          location: {{ hash: '#iterate', origin: 'https://example.test' }},
          addEventListener: () => {{}},
        }};
        global.location = global.window.location;
        global.document = {{
          getElementById: () => null,
          querySelectorAll: () => [],
          createElement: () => ({{
            appendChild() {{}},
            addEventListener() {{}},
            remove() {{}},
            click() {{}},
            classList: {{ add() {{}}, remove() {{}}, toggle() {{}} }},
            style: {{}},
          }}),
          head: {{ appendChild() {{}} }},
          body: {{ appendChild() {{}} }},
        }};
        global.DB = {{
          getSetting: () => 0,
          dbPut: () => {{}},
          dbCount: () => 0,
          openDB: async () => {{}},
          initDefaults: async () => {{}},
          loadPrompts: async () => {{}},
        }};
        global.Drive = {{
          downloadCoverForBook: async () => ({{ img: null }}),
          validateCoverTemplate: () => null,
          catalogCacheStatus: async () => ({{ cached: false }}),
          syncCatalog: async () => {{}},
          loadCachedCatalog: async () => {{}},
          refreshCatalogCache: async () => {{}},
        }};
        global.OpenRouter = {{ init: async () => {{}}, MODEL_COSTS: {{}} }};
        global.Quality = {{ getDetailedScores: async () => ({{ overall: 1 }}) }};
        global.fetch = async () => ({{
          ok: true,
          headers: {{ get: () => 'image/jpeg' }},
          blob: async () => new Blob([], {{ type: 'image/jpeg' }}),
        }});
        global.Image = class {{
          set src(_value) {{
            if (this.onload) this.onload();
          }}
        }};
        global.URL = URL;
        global.URL.createObjectURL = () => 'blob:test';
        global.URL.revokeObjectURL = () => {{}};
        global.crypto = {{ randomUUID: () => 'uuid-test-1' }};
        global.setTimeout = () => 0;
        global.setInterval = () => 0;

        const source = fs.readFileSync('src/static/js/app.js', 'utf8');
        vm.runInThisContext(source, {{ filename: 'app.js' }});
        const fn = window.__APP_TEST_HOOKS__[{json.dumps(hook_name)}];
        const result = Array.isArray(payload) ? fn(...payload) : fn(payload);
        process.stdout.write(JSON.stringify(result));
        """
    )
    proc = subprocess.run(
        ["node", "-e", node_script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout)


def test_project_relative_asset_path_strips_encoding_and_cachebuster_query():
    result = _run_app_hook(
        "projectRelativeAssetPath",
        "/Output%20Covers/saved_composites/4/cover%20image.jpg?v=2026-03-10T18%3A40%3A00Z",
    )

    assert result == "Output Covers/saved_composites/4/cover image.jpg"


def test_build_project_asset_url_normalizes_encoded_local_path():
    result = _run_app_hook(
        "buildProjectAssetUrl",
        ["/Output%20Covers/saved_composites/4/cover%20image.jpg?v=1", "2026-03-10T18:40:00Z"],
    )

    parsed = urlparse(result)
    query = parse_qs(parsed.query)
    assert parsed.path == "/api/asset"
    assert query["path"] == ["Output Covers/saved_composites/4/cover image.jpg"]
    assert query["v"] == ["2026-03-10T18:40:00Z"]


def test_resolve_full_resolution_composite_source_rewrites_thumbnail_url_to_asset_endpoint():
    result = _run_app_hook(
        "resolveFullResolutionCompositeSource",
        "/api/thumbnail?path=Output%20Covers%2Fsaved_composites%2F4%2Fcover%20image.jpg%3Fv%3Dold&size=large&v=current",
    )

    parsed = urlparse(result)
    query = parse_qs(parsed.query)
    assert parsed.path == "/api/asset"
    assert query["path"] == ["Output Covers/saved_composites/4/cover image.jpg"]
    assert query["v"] == ["current"]


def test_resolve_full_resolution_composite_source_preserves_existing_asset_url_and_version():
    result = _run_app_hook(
        "resolveFullResolutionCompositeSource",
        "/api/asset?path=Output%20Covers%2Fsaved_composites%2F4%2Fcover%20image.jpg&v=2026-03-19T16%3A00%3A00Z",
    )

    parsed = urlparse(result)
    query = parse_qs(parsed.query)
    assert parsed.path == "/api/asset"
    assert query["path"] == ["Output Covers/saved_composites/4/cover image.jpg"]
    assert query["v"] == ["2026-03-19T16:00:00Z"]


def test_build_retry_prompt_returns_original_prompt_for_retries():
    result = _run_app_hook(
        "buildRetryPrompt",
        ["Book cover illustration — no text, no lettering. Scene: Emma in Highbury.", 2],
    )

    assert result == "Book cover illustration — no text, no lettering. Scene: Emma in Highbury."


def test_build_retry_prompt_preserves_existing_prompt_text_verbatim():
    result = _run_app_hook(
        "buildRetryPrompt",
        ["Book cover illustration. IMPORTANT: This must be a circular vignette illustration centered and fully contained.", 1],
    )

    assert result == "Book cover illustration. IMPORTANT: This must be a circular vignette illustration centered and fully contained."


def test_thumbnail_version_token_prefers_completed_at_when_present():
    result = _run_app_hook(
        "thumbnailVersionToken",
        {
            "id": "job-42",
            "completed_at": "2026-03-19T12:40:00Z",
            "updated_at": "2026-03-19T12:39:00Z",
        },
    )

    assert result == "2026-03-19T12:40:00Z"


def test_load_image_with_retry_retries_until_success():
    if shutil.which("node") is None:
        pytest.skip("node not installed")

    node_script = textwrap.dedent(
        """
        const fs = require('fs');
        const vm = require('vm');
        let attemptCount = 0;
        const retryDelays = [];

        global.window = {
          Pages: {},
          __APP_TEST_HOOKS__: {},
          __INITIAL_PAGE__: 'iterate',
          innerWidth: 1280,
          location: { hash: '#iterate', origin: 'https://example.test' },
          addEventListener: () => {},
        };
        global.location = global.window.location;
        global.document = {
          getElementById: () => null,
          querySelectorAll: () => [],
          createElement: () => ({
            appendChild() {},
            addEventListener() {},
            remove() {},
            click() {},
            classList: { add() {}, remove() {}, toggle() {} },
            style: {},
          }),
          head: { appendChild() {} },
          body: { appendChild() {} },
        };
        global.DB = {
          getSetting: () => 0,
          dbPut: () => {},
          dbCount: () => 0,
          openDB: async () => {},
          initDefaults: async () => {},
          loadPrompts: async () => {},
        };
        global.Drive = {
          downloadCoverForBook: async () => ({ img: null }),
          validateCoverTemplate: () => null,
          catalogCacheStatus: async () => ({ cached: false }),
          syncCatalog: async () => {},
          loadCachedCatalog: async () => {},
          refreshCatalogCache: async () => {},
        };
        global.OpenRouter = { init: async () => {}, MODEL_COSTS: {} };
        global.Quality = { getDetailedScores: async () => ({ overall: 1 }) };
        global.fetch = async () => ({
          ok: true,
          headers: { get: () => 'image/jpeg' },
          blob: async () => new Blob([], { type: 'image/jpeg' }),
        });
        global.Image = class {
          set src(_value) {
            attemptCount += 1;
            if (attemptCount < 3) {
              if (this.onerror) this.onerror(new Error('broken'));
              return;
            }
            if (this.onload) this.onload();
          }
        };
        global.URL = URL;
        global.URL.createObjectURL = () => 'blob:test';
        global.URL.revokeObjectURL = () => {};
        global.crypto = { randomUUID: () => 'uuid-test-1' };
        global.setTimeout = (fn, delay) => {
          retryDelays.push(delay);
          fn();
          return 0;
        };
        global.setInterval = () => 0;

        const source = fs.readFileSync('src/static/js/app.js', 'utf8');
        vm.runInThisContext(source, { filename: 'app.js' });
        window.loadImageWithRetry('/broken.jpg', 3).then(() => {
          process.stdout.write(JSON.stringify({ attemptCount, retryDelays }));
        }).catch((err) => {
          process.stderr.write(String(err && err.message || err));
          process.exit(1);
        });
        """
    )
    proc = subprocess.run(
        ["node", "-e", node_script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["attemptCount"] == 3
    assert payload["retryDelays"] == [2000, 4000]


def test_generation_in_progress_conflict_detector_matches_backend_409_error():
    result = _run_app_hook(
        "isGenerationInProgressConflict",
        'Generation request failed: 409 {"error_code":"GENERATION_IN_PROGRESS","message":"Generation already in progress for book 2"}',
    )

    assert result is True


def test_next_runnable_queue_index_skips_same_book_from_different_batch():
    result = _run_app_hook(
        "nextRunnableQueueIndex",
        {
            "queue": [
                {"id": "job-1", "book_id": 2, "batch_id": "batch-b"},
                {"id": "job-2", "book_id": 3, "batch_id": "batch-b"},
            ],
            "running": [
                {"id": "running-1", "book_id": 2, "batch_id": "batch-a"},
            ],
        },
    )

    assert result == 1


def test_next_runnable_queue_index_allows_same_book_within_same_batch():
    result = _run_app_hook(
        "nextRunnableQueueIndex",
        {
            "queue": [
                {"id": "job-1", "book_id": 2, "batch_id": "batch-a"},
                {"id": "job-2", "book_id": 3, "batch_id": "batch-a"},
            ],
            "running": [
                {"id": "running-1", "book_id": 2, "batch_id": "batch-a"},
            ],
        },
    )

    assert result == 0


def test_preferred_backend_result_path_prefers_durable_output_over_tmp_image_path():
    result = _run_app_hook(
        "preferredBackendResultPath",
        {
            "row": {
                "image_path": "tmp/generated/2/model/variant_1.png",
                "raw_art_path": "Output Covers/raw_art/2/job_variant_1.png",
            },
            "keys": ["raw_art_path", "image_path"],
        },
    )

    assert result == "Output Covers/raw_art/2/job_variant_1.png"


def test_resolve_backend_asset_url_routes_project_paths_through_asset_api():
    result = _run_app_hook(
        "resolveBackendAssetUrl",
        ["Output Covers/saved_composites/2/job_variant_1.jpg", "stamp-1"],
    )

    parsed = urlparse(result)
    query = parse_qs(parsed.query)
    assert parsed.path == "/api/asset"
    assert query["path"] == ["Output Covers/saved_composites/2/job_variant_1.jpg"]
    assert query["v"] == ["stamp-1"]
