#!/usr/bin/env python3
"""
End-to-end smoke test for Alexandria Cover Designer.
Run after every deployment:

    python scripts/smoke_test.py
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import requests


PROD_URL = "https://web-production-900a7.up.railway.app"
REQUIRED_NEGATIVE_TERMS = [
    "vector",
    "airbrushed",
    "seamless",
    "uniform color",
    "visible circle outline",
    "wreath",
    "sunburst",
    "blank paper",
]
BANNED_CATALOG_STYLE_FRAGMENTS = [
    "gold outlines",
    "decorative elegance",
    "framing the scene",
    "spiralling decorative accents",
    "intricate marginalia patterns",
    "intricate geometric borders",
]
BANNED_PROMPT_FRAGMENTS = [
    "circular vignette illustration",
    "mandatory output rules",
    "no circular border",
    "no circular frame",
    "implied centered circle",
    "quiet outer corners",
]
REQUIRED_PROMPT_FRAGMENTS = [
    "victorian storybook color plate illustration",
    "colors specific to this story's setting and era",
]
MEDIUM_STARTS = [
    "Victorian storybook color plate illustration",
]
MAX_PROMPT_LENGTH = 1050


def _request_json(base_url: str, path: str, *, timeout: int = 15) -> Any:
    response = requests.get(f"{base_url.rstrip('/')}{path}", timeout=timeout)
    response.raise_for_status()
    return response.json()


def _load_prompt_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("prompts", [])
    else:
        rows = []
    return [row for row in rows if isinstance(row, dict)]


def _load_job_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("jobs", [])
    else:
        rows = []
    return [row for row in rows if isinstance(row, dict)]


def _result_rows(job: dict[str, Any]) -> list[dict[str, Any]]:
    result = job.get("result", {})
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            result = {}
    if not isinstance(result, dict):
        return []
    rows = result.get("results", [])
    return [row for row in rows if isinstance(row, dict)]


def check_prompt_catalog(base_url: str, catalog: str, *, min_entries: int = 5) -> tuple[bool, str]:
    payload = _request_json(base_url, f"/api/prompts?catalog={catalog}")
    prompts = _load_prompt_rows(payload)
    if len(prompts) < min_entries:
        return False, f"Prompt catalog too small: {len(prompts)} entries (need >= {min_entries})"
    for prompt in prompts:
        prompt_id = str(prompt.get("id", "")).strip()
        if not prompt_id.startswith("alexandria-"):
            continue
        template = str(prompt.get("prompt_template", "")).lower()
        negative_prompt = str(prompt.get("negative_prompt", "")).lower()
        for banned in BANNED_CATALOG_STYLE_FRAGMENTS:
            if banned in template:
                return False, f"{prompt_id}: prompt template contains banned style fragment '{banned}'"
        for term in REQUIRED_NEGATIVE_TERMS:
            if term not in negative_prompt:
                return False, f"{prompt_id}: prompt catalog negative_prompt missing '{term}'"
    return True, f"Prompt catalog: {len(prompts)} entries"


def check_recent_jobs(
    base_url: str,
    catalog: str,
    *,
    limit: int = 5,
    max_prompt_length: int = MAX_PROMPT_LENGTH,
) -> tuple[bool, list[str]]:
    payload = _request_json(base_url, f"/api/jobs?catalog={catalog}")
    jobs = _load_job_rows(payload)
    completed = [job for job in jobs if str(job.get("status", "")).strip().lower() == "completed"]
    completed.sort(key=lambda row: str(row.get("created_at", "")), reverse=True)
    if not completed:
        return False, ["No completed jobs available for smoke test."]

    failures: list[str] = []
    for job in completed[:limit]:
        token = str(job.get("id", ""))[:8] or "unknown"
        rows = _result_rows(job)
        result_row = rows[0] if rows else {}
        prompt = str(result_row.get("prompt") or job.get("prompt") or "").strip()
        negative_prompt = str(result_row.get("negative_prompt") or "").strip()

        if len(prompt) > max_prompt_length:
            failures.append(f"{token}: prompt too long ({len(prompt)} chars)")
        for banned in BANNED_PROMPT_FRAGMENTS:
            if banned in prompt.lower():
                failures.append(f"{token}: prompt contains banned fragment '{banned}'")
        if not any(prompt.startswith(prefix) for prefix in MEDIUM_STARTS):
            failures.append(f"{token}: prompt does not start with a medium opener")
        if "important rendering style" in prompt.lower():
            failures.append(f"{token}: old rendering prefix still present")
        if "dense saturated illustration filling every inch" not in prompt.lower():
            failures.append(f"{token}: texture closer missing from prompt")
        for required in REQUIRED_PROMPT_FRAGMENTS:
            if required not in prompt.lower():
                failures.append(f"{token}: prompt missing '{required}'")

        if not negative_prompt:
            failures.append(f"{token}: negative_prompt is empty")
            continue
        for term in REQUIRED_NEGATIVE_TERMS:
            if term not in negative_prompt.lower():
                failures.append(f"{token}: negative_prompt missing '{term}'")

    return not failures, failures or [f"Recent completed jobs checked: {min(limit, len(completed))}"]


def run_smoke_test(
    *,
    base_url: str = PROD_URL,
    catalog: str = "classics",
    limit: int = 5,
) -> int:
    print("Alexandria Smoke Test")
    print("=" * 40)

    ok = True

    print("\n1. Prompt Catalog:")
    try:
        catalog_ok, catalog_message = check_prompt_catalog(base_url, catalog)
        print(f"  {'✅' if catalog_ok else '❌'} {catalog_message}")
        ok = ok and catalog_ok
    except Exception as exc:
        print(f"  ❌ {exc}")
        ok = False

    print("\n2. Recent Jobs (prompt structure):")
    try:
        jobs_ok, job_messages = check_recent_jobs(base_url, catalog, limit=limit)
        marker = "✅" if jobs_ok else "❌"
        for message in job_messages:
            print(f"  {marker} {message}" if jobs_ok else f"  ❌ {message}")
        ok = ok and jobs_ok
    except Exception as exc:
        print(f"  ❌ {exc}")
        ok = False

    print("\n" + "=" * 40)
    if ok:
        print("✅ ALL CHECKS PASSED")
        return 0
    print("❌ SOME CHECKS FAILED")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Alexandria prompt-pipeline smoke checks.")
    parser.add_argument("--base-url", default=PROD_URL, help="Base Alexandria deployment URL.")
    parser.add_argument("--catalog", default="classics", help="Catalog id to inspect.")
    parser.add_argument("--limit", type=int, default=5, help="How many recent completed jobs to inspect.")
    args = parser.parse_args(argv)
    return run_smoke_test(base_url=args.base_url, catalog=args.catalog, limit=max(1, int(args.limit)))


if __name__ == "__main__":
    raise SystemExit(main())
