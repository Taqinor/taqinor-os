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
     garde est posée avant que le premier n'existe) ;
  3. (AFAC95, C-AFAC-053) un ``catch`` VIDE ou réduit à un commentaire
     (``catch { /* */ }`` passe ``no-empty`` d'ESLint : le 400 du serveur est
     avalé et l'écran ne dit rien) sous ``pages/`` ou ``features/``. Passif gelé
     dans ``scripts/frontend_catch_vide_allow.txt`` (``fichier::fonction  N``,
     N = nombre de catch vides de la fonction) : il ne peut que DÉCROÎTRE, une
     clé morte (moins de catch vides que la base) fait échouer la garde.
     Afficher l'erreur : ``utils/fetchAllPages`` pour les listes,
     ``hooks/useServerFieldErrors`` pour les formulaires.

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

# 3) catch vide ou réduit à des commentaires (le corps ne contient que des
#    espaces et des commentaires).
RE_CATCH_VIDE = re.compile(
    r"\bcatch\s*(?:\([^)]*\))?\s*\{(?:\s|/\*[\s\S]*?\*/|//[^\n]*)*\}")
CATCH_VIDE_ALLOW = ROOT / "scripts" / "frontend_catch_vide_allow.txt"
_DECLARATIONS = (
    re.compile(r"\bfunction\s*\*?\s*(\w+)\s*\("),
    re.compile(r"\b(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>"),
    re.compile(r"createAsyncThunk\(\s*['\"]([^'\"]+)['\"]"),
)
_MOTS_CLES = {"if", "for", "while", "switch", "catch", "return", "else", "try"}


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


def _fonction_de(texte: str, position: int) -> str:
    """Nom de la dernière déclaration reconnue AVANT ``position`` (clé de
    contenu, jamais un numéro de ligne)."""
    nom, dernier = "<module>", -1
    for rx in _DECLARATIONS:
        for m in rx.finditer(texte, 0, position):
            if m.group(1) not in _MOTS_CLES and m.start() > dernier:
                nom, dernier = m.group(1), m.start()
    return nom


def scan_catch_vide() -> dict:
    """{``fichier::fonction``: nombre de catch vides} sous pages/ et features/."""
    trouves: dict = {}
    for base in SCANNED_DIRS:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in SUFFIXES or any(m in path.name for m in TEST_MARKERS):
                continue
            rel = path.relative_to(ROOT).as_posix()
            texte = path.read_text(encoding="utf-8")
            if "catch" not in texte:
                continue
            # un `catch {}` CITÉ dans un commentaire de documentation /** */
            # n'est pas du code : on blanchit ces blocs (positions conservées).
            sans_doc = re.sub(r"/\*\*[\s\S]*?\*/",
                              lambda m: " " * len(m.group(0)), texte)
            for m in RE_CATCH_VIDE.finditer(sans_doc):
                cle = f"{rel}::{_fonction_de(sans_doc, m.start())}"
                trouves[cle] = trouves.get(cle, 0) + 1
    return trouves


def charger_catch_vide(chemin: Path | None = None) -> dict:
    chemin = chemin or CATCH_VIDE_ALLOW
    base: dict = {}
    if not chemin.is_file():
        return base
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.split("#", 1)[0].strip()
        if ligne:
            cle, _espace, n = ligne.rpartition(" ")
            base[cle.strip()] = int(n)
    return base


def ecrire_catch_vide(trouves: dict, chemin: Path | None = None) -> None:
    chemin = chemin or CATCH_VIDE_ALLOW
    entete = (
        "# AFAC95 - passif GELE de scripts/check_frontend_errors.py (regle 3) :\n"
        "# `catch` vides ou reduits a un commentaire sous frontend/src/{pages,features}.\n"
        "# Cle de CONTENU `fichier::fonction  N` (N = nombre de catch vides). Un site\n"
        "# liste ici est CONSTATE, pas approuve : afficher l'erreur (fetchAllPages /\n"
        "# useServerFieldErrors / frenchError) puis reduire la ligne. REGLE ABSOLUE :\n"
        "# cette liste ne peut que DECROITRE.\n")
    corps = "".join(f"{cle}  {n}\n" for cle, n in sorted(trouves.items()))
    chemin.write_text(entete + corps, encoding="utf-8", newline="\n")


def verifier_catch_vide(trouves: dict, base: dict) -> list:
    erreurs = []
    for cle, n in sorted(trouves.items()):
        if n > base.get(cle, 0):
            fichier, fonction = cle.split("::", 1)
            erreurs.append(
                f"{fichier} — {fonction} : catch vide ou réduit à un commentaire "
                "(l'erreur du serveur est avalée) — afficher l'erreur "
                "(utils/fetchAllPages, hooks/useServerFieldErrors, lib/frenchError.js)")
    for cle, n in sorted(base.items()):
        if trouves.get(cle, 0) < n:
            erreurs.append(f"entrée MORTE de frontend_catch_vide_allow.txt : {cle} "
                           f"({n} -> {trouves.get(cle, 0)}) — réduisez/retirez la ligne")
    return erreurs


def main() -> int:
    offenders = scan() + verifier_catch_vide(scan_catch_vide(), charger_catch_vide())
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
