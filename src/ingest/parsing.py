"""PDF -> per-page markdown with pymupdf4llm (non-generative, unlike the LlamaParse it replaced).

Output is cached per PDF (keyed by the file's hash), so re-running the ingest only re-parses
files that changed. Needs the ingest dependency group: `uv sync --group ingest`.
"""
import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List

import pymupdf

PARSED_CACHE_DIR = Path("data/parsed_pymupdf")
MIN_TEXT_LAYER_CHARS = 50  # pages below this have no usable text layer (scans, covers)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_markdown(text: str) -> str:
    # Symbols whose glyphs don't map to text (e.g. ≥ in some fonts) come out as empty <sup>
    text = re.sub(r"<sup>\s*</sup>", " ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def parse_pdf(path: Path) -> List[Dict]:
    """[{page, text, has_text_layer}] for every page, from cache when the file is unchanged.

    Pages without a text layer are kept with empty text: the old LlamaParse "OCR" of these
    pages was mostly invented, and they are nearly all covers or blank pages.
    """
    import pymupdf4llm

    digest = file_hash(path)
    cache = PARSED_CACHE_DIR / f"{path.stem}.json"
    if cache.exists():
        cached = json.loads(cache.read_text(encoding="utf-8"))
        if cached.get("sha256") == digest:
            return cached["pages"]

    with pymupdf.open(path) as doc:
        text_layer = [len(page.get_text().strip()) >= MIN_TEXT_LAYER_CHARS for page in doc]
        chunks = pymupdf4llm.to_markdown(
            doc, page_chunks=True, header=False, footer=False, use_ocr=False, show_progress=False
        )
    if len(chunks) != len(text_layer):
        raise RuntimeError(f"{path.name}: got {len(chunks)} pages from pymupdf4llm, expected {len(text_layer)}")

    pages = [
        {"page": i + 1, "text": clean_markdown(chunk["text"]) if text_layer[i] else "", "has_text_layer": text_layer[i]}
        for i, chunk in enumerate(chunks)
    ]
    PARSED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"sha256": digest, "pages": pages}, ensure_ascii=False), encoding="utf-8")
    return pages
