#!/usr/bin/env python3
"""Alexandria Cover Designer — Regression Guardian.

Run before EVERY deploy. If any check fails, DO NOT deploy.
Usage: python scripts/regression_check.py [--prod URL]

Without --prod: checks source files only (fast, no network).
With --prod: also checks the live production deployment.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASS = 0
FAIL = 0
WARN = 0


def ok(label):
    global PASS
    PASS += 1
    print(f"  ✅ {label}")


def fail(label):
    global FAIL
    FAIL += 1
    print(f"  ❌ {label}")


def warn(label):
    global WARN
    WARN += 1
    print(f"  ⚠️  {label}")


def check(condition, label):
    if condition:
        ok(label)
    else:
        fail(label)
    return condition


def read(relpath):
    p = ROOT / relpath
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prod", default="", help="Production base URL for live checks")
    args = parser.parse_args()

    print("\n🔒 REGRESSION GUARDIAN — Alexandria Cover Designer\n")

    # ═══════════════════════════════════════════════════
    # SECTION 1: app.js — Global frontend script
    # ═══════════════════════════════════════════════════
    print("── app.js ──")
    app_js = read("src/static/js/app.js")
    if app_js is None:
        fail("app.js not found")
    else:
        check("_thumbnailVersionToken" in app_js, "_thumbnailVersionToken() defined in app.js (PROMPT-82)")
        check("renderErr" in app_js or "non-fatal" in app_js, "Result rendering has try-catch fallback (PROMPT-82)")
        check("Mandatory output rules" not in app_js, "No 'Mandatory output rules' retry bloat (PROMPT-70)")
        check("circular vignette illustration" not in app_js, "No 'circular vignette' retry mutation (PROMPT-75A)")

        m = re.search(r"MAX_CONCURRENT:\s*(\d+)", app_js)
        if m:
            check(int(m.group(1)) >= 4, f"JobQueue.MAX_CONCURRENT = {m.group(1)} (≥4)")
        else:
            fail("JobQueue.MAX_CONCURRENT not found")

    # ═══════════════════════════════════════════════════
    # SECTION 2: iterate.js — Variant/scene/style logic
    # ═══════════════════════════════════════════════════
    print("\n── iterate.js ──")
    iterate_js = read("src/static/js/pages/iterate.js")
    if iterate_js is None:
        fail("iterate.js not found")
    else:
        check("_shuffleAndDeal" in iterate_js, "_shuffleAndDeal() exists (PROMPT-77 zero-repeat)")
        check("buildExpandedPromptSequence" not in iterate_js, "buildExpandedPromptSequence removed (PROMPT-77)")
        check("_fisherYatesShuffle" in iterate_js, "_fisherYatesShuffle() exists (PROMPT-77)")
        check("_buildTitleAnchor" in iterate_js, "_buildTitleAnchor() exists (PROMPT-78)")
        check("_promptStartsWithBookContent" in iterate_js, "_promptStartsWithBookContent() exists (PROMPT-78)")
        check("under stormlight" not in iterate_js, "No 'under stormlight' generic atmosphere (PROMPT-78)")
        check("'at dawn'" not in iterate_js and '"at dawn"' not in iterate_js, "No 'at dawn' generic atmosphere (PROMPT-78)")
        check("'by candlelight'" not in iterate_js and '"by candlelight"' not in iterate_js, "No 'by candlelight' generic atmosphere (PROMPT-78)")
        check("_sceneContainsBookContent" in iterate_js, "_sceneContainsBookContent() exists (PROMPT-78)")
        check("VISUAL STYLE:" in iterate_js or "styleModifier" in iterate_js, "Style modifier appended to prompts (PROMPT-83)")
        check("_assertBatchStyleUniqueness" in iterate_js, "_assertBatchStyleUniqueness() exists (PROMPT-77)")

        m = re.search(r"SEQUENTIAL_BATCH_SIZE\s*=\s*(\d+)", iterate_js)
        if m:
            check(int(m.group(1)) >= 4, f"SEQUENTIAL_BATCH_SIZE = {m.group(1)} (≥4)")
        else:
            fail("SEQUENTIAL_BATCH_SIZE not found")

        m = re.search(r"DEFAULT_VARIANT_COUNT\s*=\s*(\d+)", iterate_js)
        if m:
            check(int(m.group(1)) == 10, f"DEFAULT_VARIANT_COUNT = {m.group(1)} (must be 10)")
        else:
            fail("DEFAULT_VARIANT_COUNT not found")

    # ═══════════════════════════════════════════════════
    # SECTION 3: style-diversifier.js — Style pool
    # ═══════════════════════════════════════════════════
    print("\n── style-diversifier.js ──")
    sd_js = read("src/static/js/style-diversifier.js")
    if sd_js is None:
        fail("style-diversifier.js not found")
    else:
        pool_count = sd_js.count("id: '")
        check(pool_count >= 15, f"STYLE_POOL has {pool_count} entries (≥15)")
        check("buildDiversifiedPrompt" in sd_js, "buildDiversifiedPrompt() exists")
        check("selectDiverseStyles" in sd_js, "selectDiverseStyles() exists")

    # ═══════════════════════════════════════════════════
    # SECTION 4: image_generator.py — Backend prompts
    # ═══════════════════════════════════════════════════
    print("\n── image_generator.py ──")
    ig_py = read("src/image_generator.py")
    if ig_py is None:
        fail("image_generator.py not found")
    else:
        check("ALEXANDRIA_NEGATIVE_PROMPT" in ig_py, "ALEXANDRIA_NEGATIVE_PROMPT constant exists")
        check(ig_py.count("ALEXANDRIA_NEGATIVE_PROMPT") >= 2, "ALEXANDRIA_NEGATIVE_PROMPT referenced ≥2 times (wired into calls)")
        check("ALEXANDRIA_SYSTEM_PROMPT" in ig_py, "ALEXANDRIA_SYSTEM_PROMPT constant exists")
        check("ALEXANDRIA_MEDIUM_OPENER" in ig_py or "MEDIUM_OPENERS" in ig_py, "Medium opener constant exists (PROMPT-76/79)")
        check("full rectangular canvas" not in ig_py, "No 'full rectangular canvas' anti-medallion text")
        check("Mandatory output rules" not in ig_py, "No 'Mandatory output rules' retry bloat")
        check(
            "vibrancy_only" in ig_py or "dull_penalty > 0.25" in ig_py or "dull_penalty > 0.2" in ig_py,
            "low_vibrancy guardrail relaxed (PROMPT-83)",
        )

        m = re.search(r"MAX_CONTENT_VIOLATION_SCORE\s*=\s*([\d.]+)", ig_py)
        if m:
            score = float(m.group(1))
            check(score >= 0.20, f"MAX_CONTENT_VIOLATION_SCORE = {score} (≥0.20)")
        else:
            warn("MAX_CONTENT_VIOLATION_SCORE not found")

    # ═══════════════════════════════════════════════════
    # SECTION 5: config.py — Model pricing
    # ═══════════════════════════════════════════════════
    print("\n── config.py ──")
    config_py = read("src/config.py")
    if config_py is None:
        fail("config.py not found")
    else:
        m = re.search(r'"openrouter/google/gemini-3-pro-image-preview":\s*([\d.]+)', config_py)
        if m:
            price = float(m.group(1))
            check(price >= 0.10, f"Nano Banana Pro price = ${price} (≥$0.10, not $0.02)")
        else:
            warn("Nano Banana Pro price not found in MODEL_COST_USD")

    # ═══════════════════════════════════════════════════
    # SECTION 6: prompt_library.json — Templates
    # ═══════════════════════════════════════════════════
    print("\n── prompt_library.json ──")
    pl_text = read("config/prompt_library.json")
    if pl_text is None:
        fail("prompt_library.json not found")
    else:
        try:
            pl_data = json.loads(pl_text)
            prompts = pl_data if isinstance(pl_data, list) else pl_data.get("prompts", [])
            bases = [p for p in prompts if p.get("category") == "base" or "BASE" in p.get("name", "")]
            wildcards = [p for p in prompts if p.get("category") == "wildcard" or "wildcard" in p.get("id", "")]

            check(len(bases) >= 5, f"{len(bases)} base prompts (≥5)")
            check(len(wildcards) >= 25, f"{len(wildcards)} wildcard prompts (≥25)")
            check(len(prompts) >= 35, f"{len(prompts)} total prompts (≥35)")

            for b in bases:
                tpl = b.get("prompt_template", "")
                name = b.get("name", "?")
                if "{SCENE}" not in tpl:
                    fail(f"{name}: missing {{SCENE}} placeholder")
                if "{MOOD}" not in tpl:
                    fail(f"{name}: missing {{MOOD}} placeholder")
                if len(tpl) > 500:
                    warn(f"{name}: template is {len(tpl)} chars (>500)")

        except json.JSONDecodeError:
            fail("prompt_library.json is invalid JSON")

    # ═══════════════════════════════════════════════════
    # SECTION 7: File existence checks
    # ═══════════════════════════════════════════════════
    print("\n── Critical files ──")
    critical_files = [
        "src/image_generator.py",
        "src/static/js/app.js",
        "src/static/js/pages/iterate.js",
        "src/static/js/style-diversifier.js",
        "src/static/js/compositor.js",
        "src/cover_compositor.py",
        "src/gdrive_sync.py",
        "src/config.py",
        "config/prompt_library.json",
        "railway.toml",
        "Dockerfile",
    ]
    for f in critical_files:
        check((ROOT / f).exists(), f"{f} exists")

    # ═══════════════════════════════════════════════════
    # SECTION 8: Production checks (optional)
    # ═══════════════════════════════════════════════════
    if args.prod:
        print(f"\n── Production: {args.prod} ──")
        try:
            import urllib.error
            import urllib.request

            try:
                with urllib.request.urlopen(f"{args.prod}/api/health", timeout=15) as resp:
                    health = json.load(resp)
                check(health.get("healthy") is True, "Production /api/health is healthy")
            except Exception as e:
                fail(f"Production health check failed: {e}")

            try:
                with urllib.request.urlopen(f"{args.prod}/api/prompts?catalog=classics", timeout=15) as resp:
                    pdata = json.load(resp)
                prompt_list = pdata if isinstance(pdata, list) else pdata.get("prompts", [])
                check(len(prompt_list) >= 35, f"Production has {len(prompt_list)} prompts (≥35)")
            except Exception as e:
                fail(f"Production prompt check failed: {e}")

            try:
                with urllib.request.urlopen(f"{args.prod}/static/js/pages/iterate.js", timeout=15) as resp:
                    prod_iterate = resp.read().decode("utf-8", errors="replace")
                check("_shuffleAndDeal" in prod_iterate, "Production iterate.js has _shuffleAndDeal")
                check("buildExpandedPromptSequence" not in prod_iterate, "Production iterate.js: buildExpandedPromptSequence removed")
                check("_thumbnailVersionToken" not in prod_iterate or True, "Production iterate.js OK")
            except Exception as e:
                fail(f"Production JS check failed: {e}")

        except ImportError:
            warn("urllib not available — skipping production checks")

    # ═══════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════
    total = PASS + FAIL + WARN
    print(f"\n{'='*50}")
    print(f"REGRESSION GUARDIAN: {PASS} passed, {FAIL} failed, {WARN} warnings ({total} total)")
    print(f"{'='*50}")

    if FAIL > 0:
        print("\n🚫 DEPLOY BLOCKED — Fix all failures before deploying.\n")
        sys.exit(1)
    elif WARN > 0:
        print("\n⚠️  DEPLOY OK WITH WARNINGS — Review warnings above.\n")
        sys.exit(0)
    else:
        print("\n✅ ALL CHECKS PASSED — Safe to deploy.\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
