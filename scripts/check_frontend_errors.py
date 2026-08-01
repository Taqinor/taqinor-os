#!/usr/bin/env python3
"""EZ16 — Garde CI anti-jargon : plus jamais de JSON brut dans un message d'erreur.

L'audit des trajets quotidiens a trouvé HUIT sites (dans 7 fichiers) qui
sérialisaient l'objet d'erreur et le jetaient tel quel à l'utilisateur :

    const msg = err?.detail ?? err?.non_field_errors?.[0] ?? JSON.stringify(err)
    description={`Erreur : ${JSON.stringify(error)}`}

Résultat à l'écran : ``{"client":["Ce champ est obligatoire."]}``. Un employé ne
lit pas ça — il appelle quelqu'un.

Les huit sites sont purgés (patron ``lib/frenchError.js``) ; ce script est la
garde ANTI-RÉGRESSION. Il échoue si :

  1. ``JSON.stringify(err…)`` réapparaît sous ``frontend/src/pages/`` ou
     ``frontend/src/features/`` (hors tests) ;
  2. un ``toast.error(err)`` NU réapparaît (zéro occurrence aujourd'hui : la
     garde est posée avant que le premier n'existe).

Ce script N'ARBITRE PAS le contrat d'erreur unique (VX203, gaté) : il est
purement mécanique. Sérialiser une erreur pour un LOG (``console``) reste
permis — seul l'affichage utilisateur est visé.

Usage :  python scripts/check_frontend_errors.py
Sortie :  0 si propre, 1 sinon (liste des fichiers:lignes fautifs).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNED_DIRS = [
    ROOT / "frontend" / "src" / "pages",
    ROOT / "frontend" / "src" / "features",
]
SUFFIXES = {".js", ".jsx", ".mjs"}

# Un fichier de test a le droit de FABRIQUER un payload d'erreur.
TEST_MARKERS = (".test.", ".spec.")

# 1) Sérialisation d'une erreur destinée à l'écran.
RE_STRINGIFY = re.compile(r"JSON\.stringify\(\s*(err|error)\b")
# 2) Toast qui passe l'objet d'erreur BRUT (jamais un message).
RE_TOAST_RAW = re.compile(r"toast\.(error|warning)\(\s*(err|error)\s*[,)]")

# Allowlist VOLONTAIREMENT VIDE : le dernier site a été purgé par EZ16. Toute
# entrée ajoutée ici doit être justifiée en commentaire ET datée.
ALLOWLIST: set[str] = set()


def _strip_comments(text: str) -> str:
    """Retire commentaires de bloc et de ligne (un commentaire peut CITER le
    motif pour raconter le bug corrigé — ce n'est pas une régression)."""
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    return re.sub(r"^\s*//.*$", "", text, flags=re.M)


def scan() -> list[str]:
    offenders: list[str] = []
    for base in SCANNED_DIRS:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in SUFFIXES:
                continue
            name = path.name
            if any(marker in name for marker in TEST_MARKERS):
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel in ALLOWLIST:
                continue
            raw = path.read_text(encoding="utf-8")
            code = _strip_comments(raw)
            for lineno, line in enumerate(code.splitlines(), start=1):
                if RE_STRINGIFY.search(line):
                    offenders.append(
                        f"{rel}:{lineno} — JSON brut affiche a l'utilisateur "
                        f"(utiliser lib/frenchError.js)")
                if RE_TOAST_RAW.search(line):
                    offenders.append(
                        f"{rel}:{lineno} — toast.error(err) nu "
                        f"(utiliser lib/frenchError.js)")
    return offenders


def main() -> int:
    offenders = scan()
    if offenders:
        print("[check_frontend_errors] ECHEC - jargon technique montre a l'utilisateur :")
        for line in offenders:
            print(f"  - {line}")
        print()
        print("  Corriger avec `frenchError(err, 'Message francais.')` "
              "(frontend/src/lib/frenchError.js).")
        return 1
    scanned = sum(
        1
        for base in SCANNED_DIRS
        if base.exists()
        for p in base.rglob("*")
        if p.suffix in SUFFIXES and not any(m in p.name for m in TEST_MARKERS)
    )
    print(f"[check_frontend_errors] OK - {scanned} fichiers, aucun JSON brut "
          f"ni toast d'erreur nu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
