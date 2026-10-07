#!/usr/bin/env python3
"""GARDE CI — ADOC79 : une seule primitive de lecture d'adresse IP.

QJR416 a posé ``core.throttling.ip_de_requete`` comme LA SEULE lecture d'adresse
IP du dépôt (dernier saut de confiance de ``X-Forwarded-For``, jamais le premier
saut choisi par l'appelant). Cette garde empêche la récidive : toute lecture de
``REMOTE_ADDR``, ``HTTP_X_FORWARDED_FOR`` ou ``HTTP_CF_CONNECTING_IP`` (littéral
de chaîne dans le code, docstrings et commentaires exclus) HORS de
``backend/django_core/core/throttling.py`` fait échouer la CI.

Les lecteurs encore présents sont gelés PAR FICHIER dans ``EXCEPTIONS`` (jamais
par numéro de ligne) ; la liste ne peut que DÉCROÎTRE : un fichier qui ne lit
plus ces clés doit être retiré de la liste (« exception morte »).

Hors périmètre : migrations, tests, ``parked``. Chaque exception est corrigée
chez son propriétaire (appeler ``ip_de_requete``), jamais ici.

Usage :
    python scripts/check_ip_primitive.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"

#: Clés WSGI qui portent une adresse IP.
CLES_IP = frozenset({"REMOTE_ADDR", "HTTP_X_FORWARDED_FOR",
                     "HTTP_CF_CONNECTING_IP"})

#: LA primitive : seul fichier autorisé à les lire.
PRIMITIVE = "backend/django_core/core/throttling.py"

#: Lecteurs historiques gelés PAR FICHIER (décroissant seulement).
EXCEPTIONS = {
    "backend/django_core/apps/crm/webhooks.py",
    "backend/django_core/apps/identity/middleware.py",
    "backend/django_core/apps/identity/views.py",
    "backend/django_core/apps/reporting/diffusion_views.py",
    "backend/django_core/authentication/views.py",
    "backend/django_core/core/views.py",
}

_PARTIES_EXCLUES = {"migrations", "tests", "test", "__pycache__", "parked",
                    "node_modules"}


def _est_test(path: Path) -> bool:
    nom = path.name
    return (nom.startswith(("test_", "tests_")) or nom in ("tests.py", "conftest.py")
            or any(p in _PARTIES_EXCLUES for p in path.parts))


def lectures(texte: str) -> list:
    """[(ligne, cle)] des littéraux de clé IP du code (docstrings exclues)."""
    try:
        tree = ast.parse(texte)
    except SyntaxError:
        return []
    docstrings = set()
    for noeud in ast.walk(tree):
        if isinstance(noeud, ast.Expr) and isinstance(noeud.value, ast.Constant) \
                and isinstance(noeud.value.value, str):
            docstrings.add(id(noeud.value))
    out = []
    for noeud in ast.walk(tree):
        if (isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
                and noeud.value in CLES_IP and id(noeud) not in docstrings):
            out.append((noeud.lineno, noeud.value))
    return sorted(out)


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def balayer() -> dict:
    """{fichier relatif: [(ligne, cle)]} hors primitive, tests et migrations."""
    trouves = {}
    if not DJANGO_CORE.is_dir():
        return trouves
    for path in sorted(DJANGO_CORE.rglob("*.py")):
        if _est_test(path.relative_to(DJANGO_CORE)):
            continue
        rel = _rel(path)
        if rel == PRIMITIVE:
            continue
        try:
            trouvees = lectures(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        if trouvees:
            trouves[rel] = trouvees
    return trouves


def verifier(trouves: dict | None = None, exceptions=None) -> list:
    """Messages d'échec (liste vide = vert)."""
    trouves = balayer() if trouves is None else trouves
    exceptions = EXCEPTIONS if exceptions is None else exceptions
    echecs = []
    for rel, lignes in sorted(trouves.items()):
        if rel in exceptions:
            continue
        for ligne, cle in lignes:
            echecs.append(
                f"{rel}:{ligne} lit {cle} — utilisez "
                "core.throttling.ip_de_requete (QJR416)")
    for rel in sorted(exceptions):
        if rel not in trouves:
            echecs.append(
                f"{rel}: exception morte — ce fichier ne lit plus d'adresse IP, "
                "retirez-le de EXCEPTIONS (décroissance seulement)")
    return echecs


def main() -> int:
    echecs = verifier()
    if echecs:
        print("check_ip_primitive : lecture d'adresse IP hors de la primitive :")
        for ligne in echecs:
            print(f"  - {ligne}")
        return 1
    print(f"check_ip_primitive : OK — aucune lecture d'IP hors de la primitive "
          f"({len(EXCEPTIONS)} lecteur(s) historique(s) gelé(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
