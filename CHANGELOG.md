# Changelog

All notable changes to Alexandria Cover Designer are documented here.

## [2.1.1] - 2026-03-01

### UX Design Lock Reinforcement
- Updated static asset revision token to `20260302-designlock` across all page HTML links.
- Added a strict design-lock block to `src/static/shared.css` with `!important` sidebar/layout rules so legacy page CSS cannot force the old top navigation layout.
- Added compatibility CSS token aliases (`--gold-500`, `--gold-400`, `--text-secondary`) to stabilize modern page styles under shared theming.

### Medallion Bleed Prevention Hardening
- Tightened medallion opening derivation in `src/cover_compositor.py`:
  - `DETECTION_OPENING_RATIO` reduced to `0.758`.
  - Added `MIN_OPENING_MARGIN_PX = 72` guard so punch/opening cannot invade ornament ring.
  - Updated fallback opening radius logic to use conservative ratio/margin policy.
- Replaced `config/compositing_mask.png` with a stricter inner-opening mask to enforce scene-only render area.
- Added compositor regression test to ensure resolved opening radius remains safely inside outer ring geometry.

### Dashboard Reliability
- Hardened `scripts/quality_review.py::_project_path_if_exists` to resolve legacy root-relative persisted paths (e.g. `/tmp/...`) back to project-relative assets when present.
- Added dashboard recent-results filesystem fallback scan (`tmp/composited` then `Output Covers`) so cards can populate on cold starts when record history is empty.
- Added regression test for root-relative persisted path resolution.

### Generation Artifact Guardrails
- Increased content rejection strictness in `src/image_generator.py`:
  - kept `MAX_CONTENT_VIOLATION_SCORE` at `0.24` to avoid false-positive rejection storms.
  - tightened issue thresholds for text/ring/frame/dull outputs.
- Strengthened scene-only guardrail wording (explicitly blocks inscriptions/calligraphy/seals/emblems).
- Expanded prompt constraints in `src/prompt_generator.py` to reinforce anti-text and anti-frame generation behavior.
- Synthetic fallback runs now bypass strict content-guardrail hard rejects (real providers remain strict), preventing no-key demo environments from failing every generation attempt.
- Fixed prompt assembly quality in `src/image_generator.py`:
  - removed duplicated provider/model signature output (prevents `openrouter/openrouter/...` token noise),
  - cleaned malformed `\", no,\"` prompt artifacts that were diluting generation directives,
  - guardrail text is now injected once (deduplicated) while remaining explicit.

### Documentation Refresh
- Updated root project docs with current production behavior and enforcement rules:
  - `PROJECT-STATE.md`
  - `Project state Alexandria Cover designer.md`
  - `DEPLOY.md`
  - `QA-CHECKLIST.md`

### Verification Snapshot
- Full `pytest` pass after the above changes.
- Local endpoint checks passed:
  - `GET /api/health` -> ok
  - `GET /api/iterate-data?catalog=classics` -> includes all configured Gemini image IDs
- Local visual proof captured:
  - `tmp/proof-local-iterate-ui-20260301-v211.png`
  - `tmp/proof-local-dashboard-ui-20260301-v211.png`

### Delivery Protocol Hardening
- Updated root project docs to explicitly require every delivery to include:
  1. direct deployed webapp link, and
  2. visual proof report path(s).

## [2.1.0] - 2026-03-01

### Design Lock + Deployment Consistency
- Enforced static asset anti-stale policy in `scripts/quality_review.py`:
  - `.css`, `.js`, `.html` now serve with `Cache-Control: no-store`.
  - image/static binaries keep short cache windows only.
- Added global design-version query tokens across all web UI pages in `src/static/*.html`:
  - `?v=20260301-newdesign` on shared/page CSS + `navbar.js`.
- Result: new sidebar-first iterate UI is forced after deploy and old cached UI is prevented.

### Medallion Placement Reliability (Ornaments Always On Top)
- Kept compositor v9 flow in `src/cover_compositor.py` as hard default:
  - per-cover medallion auto-detection from ring pixels.
  - opening radius derived from detected outer ring.
  - content-aware zoom/crop for sparse outputs.
  - synthetic inner gold seam ring.
  - top-cover punched overlay composited last, preserving ornaments in front.
- Added/retained compositor regression tests for shifted medallion + sparse-content cases.

### Generation Guardrails + Provider Hardening
- Prompt sanitization tightened in `src/image_generator.py` and `src/prompt_generator.py`:
  - strips medallion/frame/ornament wording from generation prompts.
  - enforces scene-only/no-text/no-border constraints.
  - injects vivid color direction for stronger variation.
- OpenRouter call path remains modality-aware (`image` vs `both`) with 429 backoff honoring `Retry-After`.
- Artifact rejection remains strict for text/banner/frame contamination with retry-friendly error flow.

### Gemini Model Coverage + Env Compatibility
- Extended model coverage to always include all Gemini image models in `src/config.py`:
  - `openrouter/google/gemini-3-pro-image-preview`
  - `openrouter/google/gemini-3.1-flash-image-preview`
  - `openrouter/google/gemini-2.5-flash-image`
  - `google/gemini-3-pro-image-preview`
  - `google/gemini-3.1-flash-image-preview`
  - `google/gemini-2.5-flash-image`
- Added env alias support in `src/config.py`:
  - `DRIVE_SOURCE_FOLDER_ID` -> `gdrive_source_folder_id`
  - `DRIVE_OUTPUT_FOLDER_ID` -> `gdrive_output_folder_id`
  - `BUDGET_LIMIT_USD` -> runtime budget limit (`max_cost_usd`)

### Dashboard + Prompt UX
- Latest dashboard cards remain composited-first with persisted prompt + style tags (`scripts/quality_review.py` + `src/static/dashboard.html`).
- Iterate result cards continue to show:
  - full prompt text under each generated card,
  - one-click `Save Prompt`,
  - style tags for quick scanning.

### Tests + Proof
- Added config regression coverage in `tests/test_config_module.py` for:
  - guaranteed Gemini model presence.
  - env alias compatibility.
- Re-ran full test suite before redeploy.
- Captured visual proof artifacts under `tmp/` (iterate UI + composited medallion checks).

## [2.0.0] - 2026-02-22

### Prompt 17 - Multi-Catalog and Batch Jobs
- Added multi-catalog runtime support and catalog-aware APIs.
- Added persistent async job queue/state with worker service mode.
- Added SSE/event infrastructure for long-running operations.
- Added book metadata support (tags/notes) and compare/job pages.

### Prompt 18 - Analytics and Reporting
- Added cost ledger analytics (totals, by book, by model, timeline).
- Added budget management with warning and hard-stop controls.
- Added quality analytics (trend/distribution/model comparison).
- Added audit log, completion metrics, and report export/list APIs.

### Prompt 19 - Drive Sync, Exports, and Delivery Automation
- Added `src/drive_manager.py` for push/pull/bidirectional sync orchestration.
- Added platform export modules:
  - `src/export_amazon.py`
  - `src/export_ingram.py`
  - `src/export_social.py`
  - `src/export_web.py`
  - `src/export_utils.py`
- Added `src/delivery_pipeline.py` with delivery status/tracking hooks.
- Added export/delivery/archive/storage endpoints and manifest plumbing.

### Prompt 20 - Scale to 2,500
- Added SQLite schema and bootstrap in `src/database.py`.
- Added pooled DB access layer in `src/db.py`.
- Added repository abstraction with JSON and SQLite implementations in `src/repository.py`.
- Added migration script: `scripts/migrate_to_sqlite.py`.
- Added pagination/filter/sort support across all high-volume list endpoints.
- Added scale/performance fixture and tests (`tests/fixtures/scale`, `tests/test_performance.py`).
- Added load-test utility `scripts/load_test.py`.

### Prompt 21 - Final Production Audit and Hardening
- Added `src/security.py` sanitization/path/key-scrubbing utilities.
- Added response security headers and tightened rate-limit tiers.
- Removed unrestricted static/repo file serving fallback in `scripts/quality_review.py`; now only explicit safe asset roots are served.
- Added safe `/static/*` alias mapping to `src/static/*` with path sanitization.
- Standardized API JSON responses with explicit `success` boolean on all responses.
- Hardened float/input validation for non-finite values (`NaN`, `Infinity`) and null-byte/length checks for non-empty text validators.
- Hardened thumbnail handling to allow only configured image roots and fail closed on non-image sources.
- Fixed delivery completion semantics in `src/delivery_pipeline.py` to evaluate `fully_delivered` against required platforms for each run (including subset-platform deliveries).
- Added explicit gdrive `skipped` state when Drive auto-push is disabled, avoiding false incomplete delivery states.
- Hardened Drive selected-file handling in `src/drive_manager.py` by blocking path traversal outside `output_root` for both local mirror and Google API push paths.
- Expanded Drive sync conflict/skip/error branch tests and social export edge-path tests (catalog+platform normalization+error paths).
- Added dedicated `tests/test_export_utils_module.py` and raised `src/export_utils.py` to full focused coverage.
- Expanded web-export edge-path tests and raised `src/export_web.py` to full focused coverage.
- Hardened `src/config.py` JSON loading to fail closed on invalid config payloads instead of raising unhandled decode errors.
- Added dedicated `tests/test_config_module.py` for catalog resolution, template loading, scope parsing, and runtime method behavior.
- Added startup/runtime validation enhancements in health payloads.
- Added environment validation script `scripts/validate_environment.py`.
- Added API contract test coverage in `tests/test_api_contracts.py`.
- Added docs-to-runtime GET route matrix test (`tests/test_api_docs_route_matrix.py`) to prevent undocumented 5xx regressions.
- Expanded repository and delivery regression tests (`tests/test_database_repository_module.py`, `tests/test_delivery_pipeline_module.py`) for edge-path reliability.
- Updated release docs and deployment docs for v2.0.
- Added post-audit hardening iteration for `src/audit_log.py`, `src/book_metadata.py`, `src/safe_json.py`, `src/prompt_generator.py`, and `src/gdrive_sync.py` edge branches.
- Added/expanded module test files:
  - `tests/test_audit_log.py`
  - `tests/test_book_metadata_module.py`
  - `tests/test_safe_json.py`
  - `tests/test_prompt_generator_module.py`
  - `tests/test_gdrive_sync_module.py`
- Added post-audit hardening iteration for `src/cover_analyzer.py` edge + CLI paths and raised module coverage to full.
- Expanded `tests/test_cover_analyzer_module.py` for template fallback, missing-file/no-JPG errors, rectangle overlays, and CLI/main entrypoint flow.
- Added rollback/error-path regression coverage for `src/database.py` schema initialization.
- Expanded `tests/test_database_repository_module.py` with initialize rollback assertion path.
- Added Amazon export edge-path regression coverage (`font fallback`, `KDP resize bounds`, `missing winner`, and per-book export error aggregation).
- Expanded `tests/test_export_modules.py` and raised `src/export_amazon.py` to full coverage.
- Added Ingram export edge-path regression coverage (`missing reportlab`, `missing winner`, and catalog-level error aggregation).
- Expanded `tests/test_export_modules.py` and raised `src/export_ingram.py` to full coverage.
- Added security helper edge-path coverage for empty-path, range checks, required catalog IDs, and empty API key masking.
- Expanded `tests/test_security_module.py` and raised `src/security.py` to full coverage.
- Added catalog-scoped runtime path helpers in `src/config.py` for `cover_regions`, intelligent prompt artifacts, and winner selections.
- Removed fixed 99-entry validation in `scripts/validate_config.py`; catalog size validation is now dynamic per active catalog config.
- Wired iterate/jobs UIs to backend variant limits (removed hardcoded 20 cap) via `/api/iterate-data` and `/api/jobs` limit metadata.
- Added compatibility fallback for runtime stubs without `catalog_id` in generation/similarity/quality paths.
- Added regression coverage:
  - `tests/test_validate_config_script.py`
  - `tests/test_config_module.py` (catalog-scoped path helpers)
  - `tests/test_quality_review_utils.py` (iterate-data limit + catalog-scoped data paths)
- Normalized catalog-scoped winner/archive path defaults across CLI scripts and utilities:
  - `scripts/export_winners.py`
  - `scripts/archive_non_winners.py`
  - `scripts/generate_catalog.py`
  - `scripts/migrate_to_sqlite.py`
  - `scripts/auto_select_winners.py`
  - `scripts/prepare_print_delivery.py`
  - `src/gdrive_sync.py`
  - `src/mockup_generator.py`
  - `src/social_card_generator.py`
- Updated catalog import flow to write regions directly to catalog-specific path (no default-file overwrite side effect) in `scripts/import_catalog.py`.
- Added regression coverage for catalog-scoped CLI defaults and import behavior in `tests/test_script_catalog_path_defaults.py`.
- Added catalog-aware regeneration wiring:
  - `scripts/regenerate_weak.py` now accepts `--catalog` and configures runtime paths from active catalog.
  - `scripts/quality_review.py` now forwards active catalog id when invoking regeneration subprocess.

### Test and Release Snapshot
- `512` tests passing.
- `97.01%` total `src/` coverage (`--cov-fail-under=85` passes).
- Docker build + runtime health checks pass.

## [1.0.0] - 2026-02-21

### Phase 1: Foundation (Prompts 1A-3B)
- Implemented cover-analysis, prompt-generation, image-generation, quality-gate, compositing, and export core modules.
- Established 3784x2777 / 300 DPI format-preservation path for generated variants.
- Added baseline configuration plumbing and pipeline primitives.

### Phase 2: Orchestration and QA (Prompts 4A-5)
- Added end-to-end orchestration flow and run-state tracking.
- Added review tooling foundation with iteration/review web flows.
- Added visual QA support and quality-score handling for comparison workflows.

### Phase 3: Real Generation and Initial Scale (Prompts 6A-7B)
- Fixed blocking generation issues and prepared real-provider execution paths.
- Ran first real-generation workflow and integrated deployment/runtime setup.
- Scaled to 20-title initial scope and wired Drive sync pathways.

### Phase 4: Scale and Advanced Workflow (Prompts 8A-11D)
- Added scaling controls and workflow support for larger catalogs.
- Added winner-selection and archive/export automation scripts.
- Added intelligent prompting, similarity analysis, and mockup generation modules.
- Expanded web app with history, dashboard, similarity, and mockup pages plus supporting APIs.

### Phase 5: UI polish, hardening, performance, testing (Prompts 12-15)
- Unified UI system and page styles.
- Added API validation/response normalization and cache/error tracking.
- Expanded test suite and CI coverage gate.

### Phase 6: Final Release Hardening (Prompt 16)
- Completed 99-title region coverage and startup health checks.
- Added `/catalogs` page and PDF generation UX.
- Hardened shutdown behavior and Docker runtime defaults.
