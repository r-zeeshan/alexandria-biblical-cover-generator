# Alexandria Cover Designer

AI-powered book cover illustration generator for 25,000+ classic manuscripts.

## Quick Start

```bash
pip install -r requirements.txt
python -m src.pipeline
```

## Production

- Live app: https://web-production-900a7.up.railway.app/#iterate
- Current production code SHA: `c0c2404cb149e8a42a18699c97550fb5e300a2b2`
- Current public Railway service: `web`
- Important: the current live Railway deployment was last pushed via Railway CLI. A freelancer fork should not assume this exact Railway project is GitHub-linked; they should create or link their own Railway project for their fork.

## Freelancer Handoff

See [`FREELANCER-HANDOFF.md`](FREELANCER-HANDOFF.md) for the exact fork, clone, verification, environment, and Railway duplication steps for the current production version.

## Key Files

| File | Purpose |
|------|---------|
| `src/image_generator.py` | Backend prompt assembly and AI provider calls |
| `src/static/js/pages/iterate.js` | Frontend variant, scene, and style logic |
| `src/static/js/style-diversifier.js` | Style pool and diversified prompts |
| `config/prompt_library.json` | Base and wildcard prompt templates |
| `src/cover_compositor.py` | Circular crop and frame overlay pipeline |
| `scripts/regression_check.py` | Regression guardian; run before every deploy |

## Before Every Deploy

```bash
python scripts/regression_check.py
python scripts/regression_check.py --prod https://web-production-900a7.up.railway.app
```

Both commands must show 0 failures before deploying.

## Architecture

See `Codex Prompts/ARCHITECTURE-GUARDRAILS.md` for ownership rules and banned patterns.
