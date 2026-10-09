#!/usr/bin/env python3
"""GARDE CI (stage-names) — ACAL317 : un seul écran réécrit le document entier.

CLASSE C-ACAL-044 : lecture-modification-écriture du DOCUMENT ENTIER
(`roof_layout`). Un écran (onglet, panneau) qui appelle
`enregistrerLayoutCalepinage(` réécrit tout le document à partir de sa copie
locale : la moindre copie périmée écrase le travail des autres onglets. Seul
l'atelier (`pages/ventes/ToitureDesign.jsx`, qui porte l'empreinte et le verrou
`If-Match`) a le droit d'écrire le document entier.

La garde lit `frontend/src` (hors tests, hors commentaires) et échoue en nommant
fichier:ligne pour tout APPEL `enregistrerLayoutCalepinage(` hors de l'atelier.
Une DÉFINITION (`enregistrerLayoutCalepinage: (`) n'est pas un appel ; le
variant `enregistrerLayoutCalepinageConditionnel(` est un autre nom.

Passif gelé : `ALLOWLIST` (fichier -> raison) ci-dessous — il ne peut que
RÉTRÉCIR, une entrée morte (le fichier n'appelle plus) fait échouer la garde.

Usage : python scripts/check_calepinage_ecrivains_layout.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ATELIER = "frontend/src/pages/ventes/ToitureDesign.jsx"
# Passif gelé (ne peut que rétrécir) : fichier -> raison.
ALLOWLIST = {
    "frontend/src/features/calepinage/PanneauAllees.jsx":
        "ACAL317 : PanneauAllees réécrit encore le document entier "
        "(à corriger par D01-T05/T12/T15/T19, hors périmètre de la garde).",
}

_APPEL = re.compile(r"(?<![\w$])(?:[\w$.]+\.)?enregistrerLayoutCalepinage\s*\(")


def _sans_commentaires(texte: str) -> str:
    """Retire /* */ et // en conservant les retours à la ligne (numéros stables)."""
    texte = re.sub(r"/\*[\s\S]*?\*/", lambda m: "\n" * m.group(0).count("\n"), texte)
    return re.sub(r"(?m)(?<![:'\"`])//.*$", "", texte)


def _est_test(path: Path) -> bool:
    return ".test." in path.name or "__tests__" in path.parts or "fixtures" in path.parts


def trouver_appels(root: Path = ROOT) -> dict:
    """{fichier relatif: [lignes]} des appels hors atelier."""
    src = root / "frontend" / "src"
    out: dict = {}
    if not src.is_dir():
        return out
    for path in sorted(src.rglob("*")):
        if path.suffix not in (".js", ".jsx", ".ts", ".tsx") or _est_test(path):
            continue
        rel = path.relative_to(root).as_posix()
        if rel == ATELIER:
            continue
        try:
            code = _sans_commentaires(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        lignes = [i + 1 for i, ligne in enumerate(code.splitlines())
                  if _APPEL.search(ligne)]
        if lignes:
            out[rel] = lignes
    return out


def verifier(root: Path = ROOT, allow: dict | None = None) -> list:
    allow = ALLOWLIST if allow is None else allow
    appels = trouver_appels(root)
    erreurs = []
    for rel, lignes in sorted(appels.items()):
        if rel not in allow:
            erreurs.append(
                f"{rel}:{lignes[0]} appelle enregistrerLayoutCalepinage( hors de "
                f"l'atelier ({ATELIER}) — réécriture du document entier "
                "(C-ACAL-044) ; passer par une route d'écriture ciblée.")
    for rel in sorted(set(allow) - set(appels)):
        erreurs.append(f"entrée MORTE de l'allowlist : {rel} n'appelle plus "
                       "enregistrerLayoutCalepinage( — retirez-la.")
    return erreurs


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    erreurs = verifier()
    if erreurs:
        print("check_calepinage_ecrivains_layout: ÉCHEC")
        for e in erreurs:
            print("  - " + e)
        return 1
    print("check_calepinage_ecrivains_layout: OK — seul l'atelier réécrit le "
          f"document entier ({len(ALLOWLIST)} passif(s) gelé(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
