#!/usr/bin/env python3
"""GARDE CI (stage-names) — APAR65 : pas de `page_size` au-dessus du plafond serveur.

CLASSE C-APAR-056 « liste tronquée en silence au plafond serveur » : le serveur
borne `?page_size=` à `max_page_size` (200, `core/pagination.py`, LU ici et
jamais recopié). Un écran qui demande `page_size: 1000` et lit `results` sans
suivre `next` (ni `utils/fetchAllPages`) n'affiche que 200 lignes — avec 311
produits, 111 manquaient (sonde VC : « returned 200, count 309 »).

La garde lit `frontend/src` (hors tests, commentaires retirés) et signale, par
fonction (`fichier::fonction`), tout appel qui demande un `page_size` > plafond
ET lit `results` sans `fetchAllPages` / lecture de `next`. Dette gelée
(`DETTES`, une raison par entrée) : elle ne peut que DÉCROÎTRE — une entrée
corrigée sort de la base (« désormais branchée »), une entrée morte fait
échouer la garde.

Usage : python scripts/check_page_size_front.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGINATION = Path("backend") / "django_core" / "core" / "pagination.py"
FRONT = Path("frontend") / "src"
# Dette connue (cliquet) : 'fichier::fonction' -> raison. Corriger = sortir.
DETTES = {
    "frontend/src/pages/stock/BonsCommandeFournisseur.jsx::reloadSuggestions":
        "page_size: 1000 sur getProduits, lu sans fetchAllPages (stock : a corriger)",
    "frontend/src/pages/stock/FacturesFournisseur.jsx::reload":
        "page_size: 1000 sur getBonsCommandeFournisseur (stock : a corriger)",
    "frontend/src/pages/stock/ModelesBcf.jsx::reload":
        "page_size: 1000 sur getProduits (stock : a corriger)",
    "frontend/src/pages/stock/ReceptionsFournisseur.jsx::reload":
        "page_size: 1000 sur getBonsCommandeFournisseur (stock : a corriger)",
}
_RE_PAGE_SIZE = re.compile(r"""page_size['"]?\s*[:=]\s*(\d+)""")
_RE_RESULTS = re.compile(r"\bresults\b")
_RE_SUIT_NEXT = re.compile(r"fetchAllPages|chargerToutesLesPages|\.next\b|\bnext\s*[:=]|\bnext\?\.")
_DECL = (
    re.compile(r"\bfunction\s*\*?\s*(\w+)\s*\("),
    re.compile(r"\b(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>"),
    re.compile(r"createAsyncThunk\(\s*['\"]([^'\"]+)['\"]"),
)
_MOTS = {"if", "for", "while", "switch", "catch", "return", "else", "try"}


def plafond(root: Path = ROOT) -> int:
    """`max_page_size` LU dans core/pagination.py (la plus grande valeur)."""
    texte = (root / PAGINATION).read_text(encoding="utf-8")
    valeurs = [int(v) for v in re.findall(r"max_page_size\s*=\s*(\d+)", texte)]
    if not valeurs:
        raise SystemExit("check_page_size_front: max_page_size introuvable dans "
                         + PAGINATION.as_posix())
    return max(valeurs)


def _sans_commentaires(texte: str) -> str:
    texte = re.sub(r"/\*[\s\S]*?\*/", lambda m: chr(10) * m.group(0).count(chr(10)), texte)
    return re.sub(r"(?m)(?<![:'\"`])//.*$", "", texte)


def _declarations(lignes: list) -> list:
    sortie = []
    for i, ligne in enumerate(lignes):
        for rx in _DECL:
            m = rx.search(ligne)
            if m and m.group(1) not in _MOTS:
                sortie.append((i, m.group(1)))
                break
    return sortie


def analyser_source(source: str, max_ps: int) -> dict:
    """{fonction: ligne} des fonctions qui demandent trop et lisent results."""
    lignes = _sans_commentaires(source).splitlines()
    decls = _declarations(lignes)
    bornes = [i for i, _ in decls] + [len(lignes)]
    # portions : (nom, début, fin) ; le préambule avant la 1re déclaration = <module>
    portions = [("<module>", 0, bornes[0] if decls else len(lignes))]
    portions += [(nom, debut, bornes[k + 1]) for k, (debut, nom) in enumerate(decls)]
    trouves = {}
    for nom, debut, fin in portions:
        corps = chr(10).join(lignes[debut:fin])
        if not _RE_RESULTS.search(corps) or _RE_SUIT_NEXT.search(corps):
            continue
        for k in range(debut, fin):
            m = _RE_PAGE_SIZE.search(lignes[k])
            if m and int(m.group(1)) > max_ps:
                trouves.setdefault(nom, k + 1)
    return trouves


def analyser(root: Path = ROOT) -> dict:
    """{'fichier::fonction': ligne}."""
    max_ps = plafond(root)
    trouves = {}
    base = root / FRONT
    if not base.is_dir():
        return trouves
    for p in sorted(base.rglob("*")):
        if p.suffix not in (".js", ".jsx") or ".test." in p.name:
            continue
        try:
            source = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "page_size" not in source:
            continue
        for fonction, ligne in analyser_source(source, max_ps).items():
            trouves[f"{p.relative_to(root).as_posix()}::{fonction}"] = ligne
    return trouves


def verifier(trouves: dict, dettes: dict | None = None, max_ps: int = 200) -> list:
    dettes = DETTES if dettes is None else dettes
    erreurs = []
    for cle, ligne in sorted(trouves.items()):
        if cle not in dettes:
            fichier, fonction = cle.split("::", 1)
            erreurs.append(f"{fichier}:{ligne} ({fonction}) demande un page_size > {max_ps} "
                           "(plafond serveur) et lit `results` sans suivre `next` — "
                           "liste tronquée en silence ; utiliser utils/fetchAllPages.")
    for cle in sorted(set(dettes) - set(trouves)):
        erreurs.append(f"entrée MORTE de DETTES : {cle} est désormais branchée "
                       "(ou n'existe plus) — retirez-la de la base.")
    return erreurs


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    trouves = analyser()
    erreurs = verifier(trouves, max_ps=plafond())
    if erreurs:
        print("check_page_size_front: ÉCHEC")
        for e in erreurs:
            print("  - " + e)
        return 1
    print(f"check_page_size_front: OK — plafond serveur {plafond()}, "
          f"{len(trouves)} dette(s) gelée(s), aucune nouvelle.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
