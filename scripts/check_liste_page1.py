#!/usr/bin/env python3
"""GARDE CI (stage-names) — ADOC38 : classe « liste lue sur la page 1 ».

Un écran de ``frontend/src/features/**`` qui lit ``.results`` d'un appel de
LISTE paginée DRF sans ``fetchAllPages`` (``utils/fetchAllPages``) ni lecture de
``next`` n'affiche que la PREMIÈRE page (le PAGE_SIZE du serveur) : au-delà, les
lignes manquent en silence (VX54 : StockList/DevisList/FactureList étaient faux
dès 101 enregistrements ; ADOC30-32 : GED et comptes portail).

CE QUI EST SIGNALÉ — par fonction (clé de contenu ``fichier::fonction``, JAMAIS
un numéro de ligne), une fonction qui, dans son corps, (1) lit
``data.results`` / ``data?.results``, (2) fait un appel asynchrone
(``.get(``, ``api.xxx(``, ``axios``, ``.then(``, ``await`` : un wrapper d'API
ne se voit pas), et (3) n'appelle ni ``fetchAllPages`` /
``chargerToutesLesPages``, ni ne lit ``next``.

CE QUI EST EXCLU
----------------
  * les tests (``*.test.*``) ;
  * un endpoint NON paginé : la liste des segments d'URL est DÉRIVÉE du code
    (classes backend ayant ``pagination_class = None`` + leurs
    ``router.register(r'<segment>', Classe)``), jamais écrite à la main ;
  * les fonctions listées dans ``scripts/liste_page1_allow.txt`` (passif gelé,
    ``fichier::fonction``) — il ne peut que DÉCROÎTRE : une clé morte (la
    fonction n'est plus signalée) fait échouer la garde.

Usage :
    python scripts/check_liste_page1.py           # check (CI)
    python scripts/check_liste_page1.py --list    # tous les sites signalés
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_FEATURES = ROOT / "frontend" / "src" / "features"
BACKEND = ROOT / "backend" / "django_core"
ALLOWLIST_PATH = ROOT / "scripts" / "liste_page1_allow.txt"

_RESULTS_RE = re.compile(r"\bdata\??\.results\b")
_HTTP_RE = re.compile(
    r"\.get\(|\bapi\.\w+\(|\baxios\b|\bapiGet\(|\.then\(|\bawait\b")
_PAGINE_RE = re.compile(
    r"fetchAllPages|chargerToutesLesPages|\.next\b|\bnext\s*[:=]|\bnext\?\.")

_MOTS_CLES = {"if", "for", "while", "switch", "catch", "function", "return",
              "else", "do", "try", "with", "await", "typeof", "new", "super"}
_DECL_RES = (
    re.compile(r"\bfunction\s*\*?\s*(\w+)\s*\("),
    re.compile(r"\b(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?"
               r"(?:\([^)]*\)|\w+)\s*=>"),
    re.compile(r"createAsyncThunk\(\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"^\s{0,4}(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{\s*$"),
)


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _iter_sources():
    if not FRONTEND_FEATURES.is_dir():
        return
    for path in sorted(FRONTEND_FEATURES.rglob("*")):
        if path.suffix not in (".js", ".jsx") or ".test." in path.name:
            continue
        yield path


def _declarations(lignes: list) -> list:
    """[(index_ligne, nom)] des déclarations de fonction reconnues, ordre fichier."""
    out = []
    for i, ligne in enumerate(lignes):
        for rx in _DECL_RES:
            m = rx.search(ligne)
            if m and m.group(1) not in _MOTS_CLES:
                out.append((i, m.group(1)))
                break
    return out


def segments_non_pagines() -> set:
    """Segments d'URL servis par une classe backend ``pagination_class = None``
    (dérivés du code : classes + ``router.register``), jamais listés à la main."""
    classes, registres = set(), []
    if not BACKEND.is_dir():
        return set()
    class_re = re.compile(r"^class\s+(\w+)\s*\(")
    reg_re = re.compile(r"register\(\s*r?['\"]([^'\"]+)['\"]\s*,\s*(\w+)")
    for path in sorted(BACKEND.rglob("*.py")):
        if any(p in ("migrations", "tests", "node_modules", "parked")
               for p in path.parts):
            continue
        try:
            texte = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "pagination_class" in texte:
            courante = None
            for ligne in texte.splitlines():
                m = class_re.match(ligne)
                if m:
                    courante = m.group(1)
                elif courante and re.match(
                        r"^\s+pagination_class\s*=\s*None\b", ligne):
                    classes.add(courante)
        if path.name.endswith("urls.py") and ".register(" in texte:
            registres.extend(reg_re.findall(texte))
    return {seg.strip("/").split("/")[-1] for seg, cls in registres
            if cls in classes}


def analyser() -> dict:
    """{cle 'fichier::fonction': ligne} des fonctions qui lisent la page 1."""
    non_pagines = segments_non_pagines()
    trouves: dict = {}
    for path in _iter_sources():
        try:
            lignes = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        decls = _declarations(lignes)
        bornes = [i for i, _ in decls] + [len(lignes)]
        for n, (debut, nom) in enumerate(decls):
            corps = "\n".join(lignes[debut:bornes[n + 1]])
            if not _RESULTS_RE.search(corps) or not _HTTP_RE.search(corps):
                continue
            if _PAGINE_RE.search(corps):
                continue
            if any(re.search(r"(?<![\w-])" + re.escape(seg) + r"/?['\"`?]",
                             corps) for seg in non_pagines):
                continue
            ligne = debut + 1
            for k in range(debut, bornes[n + 1]):
                if _RESULTS_RE.search(lignes[k]):
                    ligne = k + 1
                    break
            trouves.setdefault(f"{_rel(path)}::{nom}", ligne)
    return trouves


def _load_allowlist() -> set:
    if not ALLOWLIST_PATH.is_file():
        return set()
    out = set()
    for ligne in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        ligne = ligne.split("#", 1)[0].strip()
        if ligne:
            out.add(ligne)
    return out


def main(argv) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    trouves = analyser()
    if "--list" in argv:
        for cle, ligne in sorted(trouves.items()):
            print(f"{cle}  (ligne {ligne})")
        return 0
    allow = _load_allowlist()
    nouveaux = {k: v for k, v in trouves.items() if k not in allow}
    morts = sorted(allow - set(trouves))
    if nouveaux:
        print("check_liste_page1: liste paginée lue sur la page 1 "
              "(ni fetchAllPages, ni lecture de `next`) :")
        for cle, ligne in sorted(nouveaux.items()):
            fichier, fonction = cle.split("::", 1)
            print(f"  - {fichier}:{ligne}  {fonction} lit la page 1 d'une liste "
                  "paginée — utilisez utils/fetchAllPages")
    if morts:
        print("check_liste_page1: entrées MORTES de scripts/liste_page1_allow.txt "
              "(la fonction n'est plus signalée — retirez la ligne) :")
        for cle in morts:
            print(f"  - {cle}")
    if nouveaux or morts:
        return 1
    print(f"check_liste_page1: OK — {len(trouves)} site(s) historique(s) gelé(s), "
          "aucune nouvelle liste lue sur la page 1.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
