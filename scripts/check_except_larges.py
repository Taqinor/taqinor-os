#!/usr/bin/env python3
"""GARDE CI (stage-names) — ENF22 / D-ENF22-BLE001 : « except large journalisant ».

Un ``except Exception`` / ``except BaseException`` / ``except:`` nu (avec ou sans
``# noqa: BLE001``) n'est toléré QUE si son corps JOURNALISE (``logger.*``, ``log.*``,
``logging.*``, ``capture_exception``, ``sentry_sdk``, ``warnings.warn``) ou RE-LÈVE.
Sinon le handler est SILENCIEUX : rouge, sauf s'il est gelé dans
``scripts/except_larges_allow.txt`` (passif décroissant : une entrée morte échoue).

Portée : ``backend/django_core/apps/**`` et ``backend/django_core/core/**`` hors
``migrations/`` et tests. Clé de contenu ``fichier::fonction`` (jamais un numéro de
ligne) ; un handler hors fonction porte ``<module>``.

Usage :
    python scripts/check_except_larges.py          # check (CI)
    python scripts/check_except_larges.py --list   # tous les sites silencieux
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

TYPE_DE_CLE = "par_symbole"  # AMET100 — cle de contenu `fichier::symbole`

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend" / "django_core"
RACINES = (BACKEND / "apps", BACKEND / "core")
ALLOWLIST_PATH = ROOT / "scripts" / "except_larges_allow.txt"

_LARGES = {"Exception", "BaseException"}
_RACINES_LOG = {"logger", "log", "logging", "_logger", "_log", "LOGGER", "LOG",
                "sentry_sdk", "warnings"}
_METHODES_LOG = {"debug", "info", "warning", "warn", "error", "exception",
                 "critical", "log", "capture_exception", "capture_message"}


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def est_large(handler: ast.ExceptHandler) -> bool:
    t = handler.type
    if t is None:
        return True
    noms = t.elts if isinstance(t, ast.Tuple) else [t]
    for n in noms:
        nom = n.id if isinstance(n, ast.Name) else getattr(n, "attr", None)
        if nom in _LARGES:
            return True
    return False


def _racine(node):
    while isinstance(node, ast.Attribute):
        node = node.value
    if isinstance(node, ast.Call):  # logging.getLogger(__name__).warning(...)
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == "getLogger":
            return _racine(f)
    nom = node.id if isinstance(node, ast.Name) else None
    if nom and nom.lower().strip("_").endswith(("logger", "log")):  # _appt_logger, _LOG...
        return "logger"
    return nom


def journalise(handler: ast.ExceptHandler) -> bool:
    for stmt in handler.body:
        for n in ast.walk(stmt):
            if isinstance(n, ast.Raise):
                return True
            if isinstance(n, ast.Call):
                f = n.func
                if isinstance(f, ast.Attribute):
                    if f.attr == "capture_exception" or (
                            f.attr in _METHODES_LOG and _racine(f) in _RACINES_LOG):
                        return True
                elif isinstance(f, ast.Name) and f.id == "capture_exception":
                    return True
    return False


def silencieux_dans(source: str) -> list:
    """Liste des noms de fonction (``<module>`` si hors fonction) des handlers silencieux."""
    arbre = ast.parse(source)
    out: list = []

    def visite(node, pile):
        for enfant in ast.iter_child_nodes(node):
            if isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                visite(enfant, pile + [enfant.name])
                continue
            if isinstance(enfant, ast.ExceptHandler) and est_large(enfant) \
                    and not journalise(enfant):
                fonctions = pile or ["<module>"]
                out.append(".".join(fonctions))
            visite(enfant, pile)

    visite(arbre, [])
    return out


def _sources():
    for racine in RACINES:
        if not racine.is_dir():
            continue
        for path in sorted(racine.rglob("*.py")):
            parts = path.relative_to(BACKEND).parts
            if "migrations" in parts or any(
                    p == "tests" or p.startswith("tests_") or p.startswith("test_")
                    or p in ("conftest.py",) for p in parts):
                continue
            yield path


def trouver() -> set:
    cles = set()
    for path in _sources():
        try:
            src = path.read_text(encoding="utf-8")
            noms = silencieux_dans(src)
        except (SyntaxError, UnicodeDecodeError):
            continue
        for nom in noms:
            cles.add(f"{_rel(path)}::{nom}")
    return cles


def _load_allowlist(chemin: Path = ALLOWLIST_PATH) -> set:
    if not chemin.is_file():
        return set()
    return {ligne.strip() for ligne in chemin.read_text(encoding="utf-8").splitlines()
            if ligne.strip() and not ligne.lstrip().startswith("#")}


def main(argv) -> int:
    trouves = trouver()
    if "--list" in argv:
        for k in sorted(trouves):
            print(k)
        return 0
    allow = _load_allowlist()
    nouveaux = sorted(trouves - allow)
    morts = sorted(allow - trouves)
    ok = True
    if nouveaux:
        ok = False
        print("check_except_larges: except large SILENCIEUX (ni log ni re-raise) — "
              "ajouter logger.warning/exception(...) ou resserrer l'exception :")
        for k in nouveaux:
            print(f"  {k}")
    if morts:
        ok = False
        print("check_except_larges: entrées MORTES de scripts/except_larges_allow.txt "
              "(retirer la ligne) :")
        for k in morts:
            print(f"  {k}")
    if ok:
        print(f"check_except_larges: OK ({len(trouves)} site(s) silencieux gelé(s)).")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
