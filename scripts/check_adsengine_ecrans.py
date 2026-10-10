#!/usr/bin/env python3
"""GARDE CI (stage-names) — AACQ77 : écrans publicité (adsengine) et page des payloads.

Périmètre : ``frontend/src/features/adsengine/**/*.jsx`` et
``frontend/src/pages/crm/WebsiteLeadPayloadsPage.jsx`` (hors ``*.test.*``).

Deux règles, par site, en français avec fichier:ligne :

  (R1) « liste lue sur la page 1 » : une fonction qui lit ``.results`` d'un
       appel asynchrone sans ``fetchAllPages`` / ``readPaginated`` / ``page_size``
       / lecture de ``next``. Clé gelée : ``fichier::R1::fonction``.
  (R2) « échec de chargement avalé » : un ``.catch(...)`` qui remplace l'échec
       par une valeur vide (``[]``, ``{}``, ``null``, ``normalizeX(null)``,
       ``EMPTY_*``) SANS poser d'état d'erreur dans le même ``catch`` (un
       setter dont le nom contient err/fail/indispo). Clé gelée :
       ``fichier::R2::<corps du catch normalisé>``.

Jumeaux (périmètres distincts) : ``check_api_shapes.py`` (formes d'API) et
``check_liste_page1.py`` (ADOC38/ALEA20 : pagination des écrans CRM).

Dette gelée : ``scripts/adsengine_ecrans_allow.txt`` (mesurée au build). Elle ne
peut que DÉCROÎTRE : une entrée devenue conforme sans être retirée fait
échouer la garde.

Usage :
    python scripts/check_adsengine_ecrans.py           # check (CI)
    python scripts/check_adsengine_ecrans.py --list    # tous les sites signalés
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
TYPE_DE_CLE = "par_symbole"  # AMET100 — cle de contenu `fichier::symbole` (jamais un numero de ligne)

ROOT = Path(__file__).resolve().parent.parent
ADSENGINE = ROOT / "frontend" / "src" / "features" / "adsengine"
PAYLOADS = ROOT / "frontend" / "src" / "pages" / "crm" / "WebsiteLeadPayloadsPage.jsx"
ALLOWLIST_PATH = ROOT / "scripts" / "adsengine_ecrans_allow.txt"

_RESULTS_RE = re.compile(r"\b(?:data|raw|rawData|r|m|c)\??\.results\b")
_HTTP_RE = re.compile(
    r"\.get\(|\bapi\.\w+\(|\badsengineApi\.|\baxios\b|\.then\(|\bawait\b")
_PAGINE_RE = re.compile(
    r"fetchAllPages|readPaginated|page_size|chargerToutesLesPages|\.next\b"
    r"|\bnext\s*[:=]|\bnext\?\.")
_MOTS_CLES = {"if", "for", "while", "switch", "catch", "function", "return",
              "else", "do", "try", "with", "await", "typeof", "new", "super"}
_DECL_RES = (
    re.compile(r"\bfunction\s*\*?\s*(\w+)\s*\("),
    re.compile(r"\b(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?"
               r"(?:\([^)]*\)|\w+)\s*=>"),
    re.compile(r"^\s{0,4}(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{\s*$"),
)
_VIDE_SETTER_RE = re.compile(
    r"\bset\w*\(\s*(?:\[\s*\]|\{\s*\}|null|undefined|normalize\w*\(\s*null\s*\)"
    r"|EMPTY_\w+|\{[^{}]*:\s*\[\s*\][^{}]*\})\s*\)")
_VIDE_RETOUR_RE = re.compile(
    r"^\s*(?:\(\s*\)|\w+)?\s*=>\s*(?:\[\s*\]|null)\s*$")
_ETAT_ERREUR_RE = re.compile(r"\bset\w*(?:err|fail|indispo)\w*\(", re.IGNORECASE)


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _iter_sources():
    if ADSENGINE.is_dir():
        for path in sorted(ADSENGINE.rglob("*.jsx")):
            if ".test." not in path.name:
                yield path
    if PAYLOADS.is_file():
        yield PAYLOADS


def _declarations(lignes: list) -> list:
    out = []
    for i, ligne in enumerate(lignes):
        for rx in _DECL_RES:
            m = rx.search(ligne)
            if m and m.group(1) not in _MOTS_CLES:
                out.append((i, m.group(1)))
                break
    return out


def _corps_catch(texte: str, debut: int) -> str:
    """Contenu entre les parenthèses de ``.catch(`` (``debut`` = index après '(')."""
    profondeur = 1
    i = debut
    while i < len(texte) and profondeur:
        c = texte[i]
        if c == "(":
            profondeur += 1
        elif c == ")":
            profondeur -= 1
        i += 1
    return texte[debut:i - 1]


def _regle_r1(path: Path, lignes: list, trouves: dict) -> None:
    decls = _declarations(lignes)
    bornes = [i for i, _ in decls] + [len(lignes)]
    for n, (debut, nom) in enumerate(decls):
        corps = "\n".join(lignes[debut:bornes[n + 1]])
        if not _RESULTS_RE.search(corps) or not _HTTP_RE.search(corps):
            continue
        if _PAGINE_RE.search(corps):
            continue
        ligne = debut + 1
        for k in range(debut, bornes[n + 1]):
            if _RESULTS_RE.search(lignes[k]):
                ligne = k + 1
                break
        trouves.setdefault(
            f"{_rel(path)}::R1::{nom}",
            (ligne, "lit la page 1 d'une liste paginée — utilisez "
                    "fetchAllPages/readPaginated ou page_size"))


def _regle_r2(path: Path, texte: str, trouves: dict) -> None:
    for m in re.finditer(r"\.catch\(", texte):
        corps = _corps_catch(texte, m.end())
        vide = _VIDE_SETTER_RE.search(corps) or _VIDE_RETOUR_RE.match(corps)
        if not vide or _ETAT_ERREUR_RE.search(corps):
            continue
        ligne = texte.count("\n", 0, m.start()) + 1
        norm = re.sub(r"\s+", " ", corps).strip()[:90].rstrip()
        trouves.setdefault(
            f"{_rel(path)}::R2::{norm}",
            (ligne, "remplace un échec de chargement par une valeur vide sans "
                    "état d'erreur — posez un état d'erreur (patron loadError)"))


def analyser() -> dict:
    """{cle: (ligne, message)} de tous les sites signalés (R1 et R2)."""
    trouves: dict = {}
    for path in _iter_sources():
        try:
            texte = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        _regle_r1(path, texte.splitlines(), trouves)
        _regle_r2(path, texte, trouves)
    return trouves


def _load_allowlist() -> set:
    if not ALLOWLIST_PATH.is_file():
        return set()
    out = set()
    for ligne in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#"):
            out.add(ligne)
    return out


def main(argv) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    trouves = analyser()
    if "--list" in argv:
        for cle, (ligne, _msg) in sorted(trouves.items()):
            print(f"{cle}  (ligne {ligne})")
        return 0
    allow = _load_allowlist()
    nouveaux = {k: v for k, v in trouves.items() if k not in allow}
    morts = sorted(allow - set(trouves))
    if nouveaux:
        print("check_adsengine_ecrans: écran publicité non conforme (AACQ77) :")
        for cle, (ligne, msg) in sorted(nouveaux.items()):
            fichier = cle.split("::", 1)[0]
            print(f"  - {fichier}:{ligne}  {msg}")
    if morts:
        print("check_adsengine_ecrans: entrées MORTES de "
              "scripts/adsengine_ecrans_allow.txt (le site est devenu conforme "
              "— retirez la ligne) :")
        for cle in morts:
            print(f"  - {cle}")
    if nouveaux or morts:
        return 1
    print(f"check_adsengine_ecrans: OK — {len(trouves)} site(s) historique(s) "
          "gelé(s), aucun nouveau.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
