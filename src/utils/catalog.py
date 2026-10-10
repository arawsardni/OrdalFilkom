"""Document catalog (static/dataset/catalog.json): titles, scope and status of each PDF."""
import json
import os
from functools import lru_cache
from typing import Dict

from src.config.settings import Settings

CATALOG_PATH = os.path.join(Settings.DATASET_DIR, "catalog.json")


@lru_cache(maxsize=1)
def load_catalog() -> Dict[str, Dict]:
    if not os.path.exists(CATALOG_PATH):
        return {}
    with open(CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f).get("documents", {})


def document_info(file_name: str) -> Dict:
    """Catalog entry for a PDF, falling back to what the file name says
    ('2020_Pedoman_Akademik_FILKOM.pdf' -> title 'Pedoman Akademik FILKOM', year 2020)"""
    entry = load_catalog().get(file_name)
    if entry:
        return entry
    stem = file_name.rsplit(".", 1)[0]
    year, _, rest = stem.partition("_")
    if year.isdigit() and rest:
        return {"title": rest.replace("_", " "), "year": int(year)}
    return {"title": stem.replace("_", " "), "year": None}
