"""Read-only product catalog helper — vendored data from RedaSolar/devis-simulator.

Only the auto-selection bits the OS lacks are lifted: picking a default battery
to build the "Avec batterie" (Option 2) column when an OS quote has none. The
simulator's file-writing / editing machinery (save_catalog, custom templates,
JSON storage) is intentionally NOT carried over.
"""
from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CATALOG_FILE = BASE_DIR / "catalog_data.json"


def load_catalog() -> dict:
    """Load the bundled brand catalog. Returns {} if unreadable."""
    try:
        with open(CATALOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def pick_default_battery() -> dict:
    """Return a sensible default battery line for the Avec-batterie option.

    Prefers a real named-brand 5 kWh battery from the catalog; falls back to the
    catalog __default__ price, then to a hard default. Shape matches the premium
    generator's item dicts: designation, marque, quantite, prix_unit_ttc.
    """
    catalog = load_catalog()
    batteries = catalog.get("Batterie", {})

    # Prefer a named brand with a 5 kWh entry (most common residential default).
    for brand, sizes in batteries.items():
        if brand == "__default__" or not isinstance(sizes, dict):
            continue
        entry = sizes.get("5")
        if isinstance(entry, dict) and entry.get("sell_ttc"):
            return {
                "designation": "Batterie 5 kWh",
                "marque": brand,
                "quantite": 1,
                "prix_unit_ttc": float(entry["sell_ttc"]),
            }

    # Fallback: catalog __default__ price.
    default = batteries.get("__default__", {})
    price = float(default.get("sell_ttc") or 16000)
    return {
        "designation": "Batterie 5 kWh",
        "marque": "Deye",
        "quantite": 1,
        "prix_unit_ttc": price,
    }
