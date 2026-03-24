# Alexandria Cover Designer - Release Summary

Version: `2.1.1`  
Date: `2026-03-01`

## Current Production-Track State
- New-design UI shell is hard-locked via `?v=20260302-designlock` + `Cache-Control: no-store`.
- Shared CSS now includes a non-overridable design-lock block (`!important`) to prevent legacy page CSS from reverting to old top navigation.
- Medallion compositing enforces conservative opening geometry so generated art stays behind ornaments.
- Prompt/generation guardrails are hardened against text/banner/frame artifacts.
- Dashboard latest cards resolve persisted paths robustly and backfill from output files when needed.
- Gemini image models are included in iterate model payloads (OpenRouter + direct Google IDs).

## What Was Finalized In This Pass
1. Prompt assembly hardening
- removed duplicated provider/model signature noise (`openrouter/openrouter/...`),
- removed malformed residual prompt artifacts (e.g. `", no,"`),
- kept guardrail directives explicit without unnecessary duplication.

2. Verification rerun
- focused suites passed (image generator, prompts, compositor, quality review),
- full `pytest` passed after changes,
- local endpoint checks passed (`/api/health`, `/api/iterate-data`, `/api/dashboard-data`).

3. Documentation refresh
- Updated project state docs, deploy runbook, QA checklist, and changelog to match current verified behavior.

## Verified Snapshot (Local)
- `GET /api/health` -> `{"status": "ok", ...}`
- `GET /api/iterate-data?catalog=classics` -> 12 models, includes all configured Gemini image IDs.
- `GET /api/dashboard-data?catalog=classics` -> populated `recent_results`.

## Visual Proof Paths
- `tmp/proof-local-iterate-ui-20260301-v211.png`
- `tmp/proof-local-dashboard-ui-20260301-v211.png`

## Honest Constraint
Fresh live-provider generations were not re-run in this exact local validation because provider credentials/Drive auth were not active in this runtime. Deployment-side visual QA is still required before claiming final production visual signoff.

## Mandatory Delivery Contract
Every delivery message must contain:
1. direct deployed webapp URL,
2. visual proof report artifact path(s).
3. updated `VISUAL-PROOF-REPORT.md`.
