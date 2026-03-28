FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt && \
    /opt/venv/bin/pip install --no-cache-dir pytest-cov

FROM python:3.11-slim AS runtime

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8001

WORKDIR /app

# Runtime system dependencies for Pillow/OpenCV, PDF rendering, and health checks.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    curl \
    tini && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --create-home app

COPY --from=builder /opt/venv /opt/venv

COPY src/ src/
RUN mkdir -p config scripts data tmp "Output Covers" "Input Covers"

# Core scripts
COPY scripts/quality_review.py scripts/quality_review.py
COPY scripts/extract_frame_overlays.py scripts/extract_frame_overlays.py
COPY scripts/verify_composite.py scripts/verify_composite.py

# Catalog and config
COPY config/catalogs.json config/catalogs.json
COPY config/book_catalog.json config/book_catalog.json
COPY config/biblical_catalog_enriched.json config/biblical_catalog_enriched.json
COPY config/prompt_templates.json config/prompt_templates.json
COPY config/prompt_templates_biblical.json config/prompt_templates_biblical.json
COPY config/cover_templates.json config/cover_templates.json
COPY config/model_prompt_overrides.json config/model_prompt_overrides.json
COPY config/genre_presets.json config/genre_presets.json
COPY config/mockup_templates.json config/mockup_templates.json
COPY config/mockup_background_prompts.json config/mockup_background_prompts.json

# Biblical cover template and frame
COPY config/cover_template_full.png config/cover_template_full.png
COPY config/frame_overlay_template.png config/frame_overlay_template.png

# Fonts for text rendering
COPY config/fonts/ config/fonts/

# Ornaments (for template assembly)
COPY config/ornaments/ config/ornaments/

# Optional files — copy if they exist, create stubs if not
COPY config/cover_regions.json config/cover_regions.json
COPY .env.example .env.example

# Test catalog files (optional, may not exist in biblical fork)
COPY config/book_catalog_test-catalog.jso[n] config/
COPY config/book_prompts_test-catalog.jso[n] config/
COPY config/cover_regions_test-catalog.jso[n] config/

# Generate runtime files that aren't committed to repo
RUN python - <<'PY'
import json, sys
sys.path.insert(0, ".")

# Generate book_prompts.json from catalog + templates
from src.prompt_generator import generate_prompts_for_book
with open("config/book_catalog.json", encoding="utf-8") as f:
    books = json.load(f)
with open("config/prompt_templates_biblical.json", encoding="utf-8") as f:
    templates = json.load(f)
all_books = []
for b in books:
    prompts = generate_prompts_for_book(b, templates)
    variants = [p.to_dict() if hasattr(p, "to_dict") else {
        "variant_id": p.variant_id, "variant_key": p.variant_key,
        "variant_name": p.variant_name, "description": p.description,
        "prompt": p.prompt, "negative_prompt": p.negative_prompt,
        "style_reference": p.style_reference,
    } for p in prompts]
    all_books.append({"number": b["number"], "title": b["title"],
        "author": b.get("author", ""), "variants": variants})
with open("config/book_prompts.json", "w", encoding="utf-8") as f:
    json.dump({"book_count": len(all_books), "variant_count_per_book": 5,
        "total_prompts": len(all_books) * 5, "books": all_books}, f, ensure_ascii=False)
print(f"Generated prompts for {len(all_books)} books")

# Create empty prompt_library.json if missing
from pathlib import Path
if not Path("config/prompt_library.json").exists():
    with open("config/prompt_library.json", "w") as f:
        json.dump({"prompts": [], "version": 1}, f)
    print("Created empty prompt_library.json")

# Create empty frame_mask.png if missing
if not Path("config/frame_mask.png").exists():
    from PIL import Image
    Image.new("L", (100, 100), 0).save("config/frame_mask.png")
    print("Created placeholder frame_mask.png")

# Create favicon if missing
if not Path("favicon.ico").exists():
    from PIL import Image
    img = Image.new("RGB", (32, 32), (21, 32, 76))
    img.save("favicon.ico", format="ICO")
    print("Created placeholder favicon.ico")
PY

RUN chown -R app:app /app

USER app

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/api/health" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh", "-c", "exec python3 scripts/quality_review.py --serve --host ${HOST:-0.0.0.0} --port ${PORT:-8001} --output-dir \"Output Covers\""]
