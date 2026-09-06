#!/usr/bin/env python3
"""NTPLT21 — Garde CI du manifeste de budgets de requêtes par endpoint.

Le manifeste ``docs/query-budgets.yml`` est le CONTRAT de perf par endpoint :
il associe chaque endpoint LISTE à fort trafic à un plafond de requêtes SQL.
Ce script échoue (exit 1) si une entrée ``enforced: true`` n'a PAS de test de
budget correspondant, c.-à-d. un fichier de test qui référence l'URL de
l'endpoint ET utilise ``assertMaxQueries`` ou ``assertNumQueries``.

But : rendre le manifeste opposable — on ne peut pas déclarer un budget sans
prouver qu'il est réellement testé (complète la sonde de parité YAPIC11).

AUD831 — ce script est un VRAI gate (peut rendre 1), pas un advisory, et est
maintenant branché dans le job CI ``stage-names`` (jamais gaté par le filtre
de chemins ``changes`` — il tourne sur CHAQUE push/PR, cf. ``ci.yml``). Avant
ce branchement, ``docs/query-budgets.yml`` affirmait au lecteur « job CI
stage-names / lint » alors que ``grep -rn query_budgets .github/`` rendait 0
occurrence : un endpoint déclaré ``enforced: true`` sans test de budget ne
faisait rougir AUCUN job CI.

Comportement :
- manifeste absent          -> notice + exit 0 (rien à garder) ;
- PyYAML absent             -> ÉCHEC EXPLICITE (exit 1, AUD831). Un
  environnement CI où PyYAML manque est une régression d'environnement, pas
  un cas légitime — un exit 0 silencieux serait exactement le faux-vert que
  ce garde existe pour abolir une fois branché ;
- manifeste illisible       -> exit 1 (drift à corriger).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "docs" / "query-budgets.yml"
BACKEND = ROOT / "backend" / "django_core"

BUDGET_ASSERTIONS = ("assertMaxQueries", "assertNumQueries")


def _iter_test_files():
    """Tous les fichiers de test du backend Django."""
    for path in BACKEND.rglob("*.py"):
        name = path.name
        if name.startswith("test") or "tests" in path.parts or "test" in name:
            if name.endswith(".py"):
                yield path


def _test_corpus():
    """Concatène (texte) les fichiers de test qui posent un budget de requêtes.

    Renvoie ``{path: text}`` uniquement pour les fichiers contenant au moins
    une assertion de budget — on ne cherche l'URL que là où un budget existe.
    """
    corpus = {}
    for path in _iter_test_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if any(a in text for a in BUDGET_ASSERTIONS):
            corpus[path] = text
    return corpus


def _has_budget_test(url: str, corpus: dict) -> bool:
    """True si un fichier à budget référence l'URL de l'endpoint."""
    return any(url in text for text in corpus.values())


def main() -> int:
    if not MANIFEST.exists():
        print("check_query_budgets: docs/query-budgets.yml absent — skip.")
        return 0
    try:
        import yaml
    except ImportError:
        # AUD831 — branché dans le job CI stage-names : PyYAML y est
        # désormais une dépendance requise (installée par le workflow), pas
        # une commodité de poste dev. Une absence ICI est une régression
        # d'environnement — l'ancien "notice + exit 0" aurait été le
        # faux-vert exact que ce garde existe pour abolir.
        print("check_query_budgets: PyYAML absent — impossible de valider "
              "le manifeste (dépendance requise une fois ce garde branché "
              "en CI ; jamais un faux-vert silencieux).", file=sys.stderr)
        return 1

    try:
        data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:  # noqa: BLE001 — drift = rouge explicite
        print(f"check_query_budgets: manifeste illisible: {exc}",
              file=sys.stderr)
        return 1

    endpoints = data.get("endpoints") or []
    if not isinstance(endpoints, list):
        print("check_query_budgets: 'endpoints' doit être une liste.",
              file=sys.stderr)
        return 1

    corpus = _test_corpus()
    missing = []
    checked = 0
    for entry in endpoints:
        if not isinstance(entry, dict):
            print("check_query_budgets: entrée non-dict ignorée.",
                  file=sys.stderr)
            return 1
        if not entry.get("enforced"):
            continue
        path = entry.get("path")
        if not path:
            print("check_query_budgets: entrée 'enforced' sans 'path'.",
                  file=sys.stderr)
            return 1
        checked += 1
        if not _has_budget_test(path, corpus):
            missing.append(path)

    if missing:
        print("check_query_budgets: endpoints 'enforced' SANS test de budget :",
              file=sys.stderr)
        for path in missing:
            print(f"  - {path}", file=sys.stderr)
        print("Écrire un test avec assertMaxQueries/assertNumQueries qui "
              "référence l'URL, ou passer l'entrée à enforced: false.",
              file=sys.stderr)
        return 1

    print(f"check_query_budgets: OK — {checked} endpoint(s) gardé(s) ont un "
          f"test de budget.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
