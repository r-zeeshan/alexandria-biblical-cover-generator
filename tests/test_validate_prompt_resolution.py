from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_validate_prompt_resolution_script_passes_specific_rows(tmp_path: Path):
    payload = [
        {
            "number": 2,
            "title": "Moby Dick",
            "enrichment": {
                "protagonist": "Captain Ahab",
                "iconic_scenes": ["Ahab sights the whale", "The whale breaches beside the Pequod", "Ahab in the final chase"],
                "visual_motifs": ["whale", "harpoon", "storm sea"],
            },
        },
        {
            "number": 3,
            "title": "Gulliver's Travels",
            "enrichment": {
                "protagonist": "Lemuel Gulliver",
                "iconic_scenes": ["Gulliver bound by tiny ropes in Lilliput", "Gulliver at the Lilliputian court", "Gulliver towing the fleet"],
                "visual_motifs": ["Gulliver", "Lilliput", "miniature soldiers"],
            },
        },
        {
            "number": 52,
            "title": "Dracula",
            "enrichment": {
                "protagonist": "Count Dracula",
                "iconic_scenes": ["Dracula in his castle", "The carriage to Transylvania", "The final crypt confrontation"],
                "visual_motifs": ["castle", "coffin", "moonlight"],
            },
        },
        {
            "number": 27,
            "title": "Pride and Prejudice",
            "enrichment": {
                "protagonist": "Elizabeth Bennet",
                "iconic_scenes": ["Elizabeth at the assembly rooms with Darcy", "Elizabeth reading Darcy's letter", "Elizabeth walking the grounds of Pemberley"],
                "visual_motifs": ["Elizabeth", "Darcy", "letter"],
            },
        },
        {
            "number": 5,
            "title": "Frankenstein",
            "enrichment": {
                "protagonist": "Victor Frankenstein",
                "iconic_scenes": ["The creature awakens in the laboratory", "The monster on the glacier", "The Arctic pursuit"],
                "visual_motifs": ["creature", "monster", "lightning"],
            },
        },
    ]
    input_path = tmp_path / "enriched.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "scripts/validate_prompt_resolution.py", "--input", str(input_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASSED" in proc.stdout
