# DEPLOY.md — Alexandria Cover Designer (Current)

Last updated: `2026-03-01`

## 1. Preconditions
- Python 3.11+
- virtualenv available (`.venv`)
- Railway CLI authenticated to target project/service
- environment values configured in Railway

Preferred environment variables:
- `OPENROUTER_API_KEY`
- `GOOGLE_API_KEY`
- `DRIVE_SOURCE_FOLDER_ID`
- `DRIVE_OUTPUT_FOLDER_ID`
- `BUDGET_LIMIT_USD`

Compatibility aliases still accepted:
- `GDRIVE_SOURCE_FOLDER_ID`
- `GDRIVE_OUTPUT_FOLDER_ID`
- `MAX_COST_USD`

## 2. Mandatory Local Validation
Run before every deploy:

```bash
.venv/bin/pytest
```

Optional compile sanity:

```bash
python3 -m compileall src scripts
```

## 3. Hard New-Design Lock Checks (Must Pass)

```bash
rg -n "20260302-designlock" src/static/*.html
curl -s -D - http://127.0.0.1:8080/iterate -o /dev/null | rg "Cache-Control: no-store"
curl -s -D - 'http://127.0.0.1:8080/src/static/iterate.css?v=20260302-designlock' -o /dev/null | rg "Cache-Control: no-store"
```

Expected:
- all static pages include `?v=20260302-designlock`
- HTML/CSS/JS routes return `Cache-Control: no-store`

## 4. Medallion Safety Checks (Must Pass)
Verify constants in `src/cover_compositor.py`:
- `DETECTION_OPENING_RATIO = 0.758`
- `MIN_OPENING_MARGIN_PX = 72`

Verify mask exists:
- `config/compositing_mask.png`

## 5. Prompt/Artifact Hardening Checks (Must Pass)
Verify in `src/image_generator.py`:
- strict scene guardrail includes no-text/no-frame constraints,
- prompt cleanup removes malformed fragments,
- model signature formatting does not duplicate provider prefixes,
- 429 retry uses `Retry-After` backoff.

## 6. Railway Deploy

```bash
railway up
```

If selection is required:

```bash
railway link
railway up
```

## 7. Post-Deploy Live Checks

```bash
curl -s https://<app-domain>/api/health
curl -s 'https://<app-domain>/api/iterate-data?catalog=classics' | jq '.models'
curl -s -D - https://<app-domain>/iterate -o /dev/null | rg 'Cache-Control: no-store'
```

Must pass:
- health status is ok,
- iterate-data contains expected Gemini model IDs,
- no-store headers present,
- iterate UI renders the new shell.

## 8. Visual Proof Requirement
Capture and retain under `tmp/` for every deployment:
- iterate page screenshot (new UI shell visible),
- dashboard screenshot (`Latest Generated Covers` visible),
- at least one composited cover proof with ornaments in front of generated art.

Mandatory release communication:
- Always send the direct deployed URL.
- Always send the visual proof report path(s).
- Never send a completion message without both.
- Always refresh `VISUAL-PROOF-REPORT.md` with current live checks + screenshot paths.

## 9. Rollback Rule
If any mandatory check fails:
1. stop rollout communication,
2. fix locally and re-run validation,
3. redeploy,
4. re-run live checks and visual proof capture before reporting success.
