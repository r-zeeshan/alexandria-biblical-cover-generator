from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import textwrap

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run_style_diversifier_hook(*, title: str, author: str, style: dict) -> str:
    if shutil.which("node") is None:
        pytest.skip("node not installed")

    node_script = textwrap.dedent(
        f"""
        const fs = require('fs');
        const vm = require('vm');

        global.window = {{}};
        const source = fs.readFileSync('src/static/js/style-diversifier.js', 'utf8');
        vm.runInThisContext(source, {{ filename: 'style-diversifier.js' }});
        const result = window.StyleDiversifier.buildDiversifiedPrompt(
          {json.dumps(title)},
          {json.dumps(author)},
          {json.dumps(style)},
        );
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


def test_build_diversified_prompt_removes_duplicate_rendering_directives():
    result = _run_style_diversifier_hook(
        title="Emma",
        author="Jane Austen",
        style={
            "id": "art-nouveau-v2",
            "modifier": "Create in the expressive Art Nouveau color-and-line tradition of Alphonse Mucha.",
        },
    )

    lowered = result.lower()
    assert result.startswith('Book cover illustration')
    assert 'STYLE:' in result
    assert 'no text, no lettering' in lowered
    assert 'real traditional artwork' not in lowered
    assert 'not digital art, not ai-generated' not in lowered
    assert 'visible brushwork or pen strokes throughout' not in lowered
    assert 'the texture of a real physical artwork' not in lowered
    assert 'one dominant focal subject with layered depth' not in lowered
    assert 'the scene must be colorful and detailed' not in lowered
    assert len(result) < 600
