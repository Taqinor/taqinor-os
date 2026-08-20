"""Read-only product catalog helper — vendored data from RedaSolar/devis-simulator.

The simulator's file-writing / editing machinery (save_catalog, custom
templates, JSON storage) is intentionally NOT carried over.

Z1 (ORDRE FONDATEUR, 20/08/2026) — ``pick_default_battery`` a été SUPPRIMÉE.
Elle fabriquait une « Batterie 5 kWh » de catalogue pour composer l'option
« Avec batterie » d'un devis hybride qui n'en portait aucune : un composant et
un prix INVENTÉS sur un document client. Aucun chiffre montré au client ne peut
venir d'ailleurs que d'une saisie réelle ou d'une dérivation traçable — ne
réintroduisez PAS de sélection par défaut ici.
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
