#!/usr/bin/env python3
"""AMET98 (C-AMET-025) — garde statique GLOBALE des tables de parcours (job stage-names).

    python scripts/check_parcours.py            # exit 1 = ÉCHEC, sortie en français

Chaque `backend/django_core/apps/<pilote>/parcours/PA*.json` (METHODE §D.1) : chaque étape a
1 déclencheur, 1 fonction d'entrée, 1 checkpoint, ≥ 1 règle aval, symboles résolus (résolveur
`core/parcours.py` puis l'index AST d'AMET80) ; `portes[]` non vide (dette gelée qui ne fait que
rétrécir) ; une étape « manquante » est rapportée, jamais résolue ni rejouée. Même règle que les
gardes par pilote (AMET8/10/11/13/15/18/24), exécutée une seconde fois, globalement.

Point d'entrée seulement : la règle vit dans `scripts/parcours_tables.py`, la MÊME que
`rejouer_parcours.py` applique avant tout rejeu — aucune seconde implémentation.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import parcours_tables  # noqa: E402 — après sys.path/setup() (D-ENF22)


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--racine", default=str(parcours_tables.ROOT), help="racine du dépôt (tests)")
    a = a.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    return parcours_tables.verifier_tout(racine=Path(a.racine))


if __name__ == "__main__":
    sys.exit(main())
