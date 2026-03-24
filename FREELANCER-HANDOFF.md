# Freelancer Handoff

This file is the canonical handoff for duplicating the current production version of Alexandria Cover Designer.

## Source Of Truth

- GitHub repo: `https://github.com/ltvspot/alexandria-cover-designer`
- Clone URL: `https://github.com/ltvspot/alexandria-cover-designer.git`
- Default branch: `master`
- Current production code SHA: `c0c2404cb149e8a42a18699c97550fb5e300a2b2`
- Direct production webapp: `https://web-production-900a7.up.railway.app/#iterate`

## What To Fork

Fork the GitHub repo above and start from `master` at commit:

`c0c2404cb149e8a42a18699c97550fb5e300a2b2`

Do not start from an older local clone or an earlier SHA.

## Clone And Verify

```bash
git clone https://github.com/<your-github-username>/alexandria-cover-designer.git
cd alexandria-cover-designer
git fetch origin
git checkout master
git pull origin master
git rev-parse HEAD
```

The SHA printed by `git rev-parse HEAD` must be:

`c0c2404cb149e8a42a18699c97550fb5e300a2b2`

## Local Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m src.pipeline
```

Open the app locally and compare behavior against:

`https://web-production-900a7.up.railway.app/#iterate`

## Minimum Environment Variables

Use `.env.example` as the template. The important values a freelancer must fill in are:

- `OPENROUTER_API_KEY`
- `OPENAI_API_KEY`
- `GOOGLE_API_KEY`
- `FAL_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_CREDENTIALS_JSON` or `GOOGLE_CREDENTIALS_PATH`
- `GDRIVE_SOURCE_FOLDER_ID`
- `GDRIVE_OUTPUT_FOLDER_ID`

Do not reuse production secrets casually. Create freelancer-specific keys and a freelancer-specific Google service account if they need live generation or Drive access.

## Railway Duplication

The current live Railway app is the `web` service, but the latest production deployment was pushed via Railway CLI, not from a repo-linked source. That means a fork will not automatically recreate this exact deployment setup.

For a duplicate deployment, the freelancer should:

1. Create a new Railway project for their fork.
2. Link their forked repo or deploy from the local clone.
3. Reuse `railway.toml`.
4. Add the required environment variables from `.env.example`.
5. Confirm the healthcheck path is `/api/health`.

Current live Railway references:

- Project: `alexandria-cover-designer`
- Project ID: `ff92d325-72a5-480f-8ff7-856744b6b859`
- Public service name: `web`
- Public service ID: `3e03e783-724a-4999-8c55-c83db5a84b5e`
- Current public deployment ID: `03b0d76f-c3c3-4a8e-9634-0d4fd41fe7e3`

## Required Verification

Before claiming parity with production:

```bash
python3 scripts/regression_check.py
python3 scripts/regression_check.py --prod https://web-production-900a7.up.railway.app
```

The first command must pass locally. The second is the reference check against the current production app.

## Exact Message To Send A Freelancer

```text
Fork https://github.com/ltvspot/alexandria-cover-designer and start from master at commit c0c2404cb149e8a42a18699c97550fb5e300a2b2. The current live production reference is https://web-production-900a7.up.railway.app/#iterate. After cloning, run git rev-parse HEAD and confirm it prints c0c2404cb149e8a42a18699c97550fb5e300a2b2. Use .env.example as the environment template, and create your own Railway project or link your fork because the current live Railway deployment was last pushed via Railway CLI rather than coming from a repo-linked auto-deploy.
```
