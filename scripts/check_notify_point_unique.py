#!/usr/bin/env python3
"""GARDE CI (stage-names) — APAR63 : un SEUL point d'écriture des notifications.

Classe gardée (C-APAR-031) : une notification écrite hors de ``notify()`` /
``notify_many()`` échappe au report nocturne (N1), aux préférences et au
filtrage par module. Tout ``Notification.objects.create`` / ``bulk_create`` /
``get_or_create`` / ``update_or_create`` et tout ``Notification(...)`` du backend
doit donc vivre dans ``backend/django_core/apps/notifications/services.py``
(où se trouvent ``notify``, ``notify_many`` et ``notify_security_change``).

Exclus : les tests (``tests/``, ``test_*.py``, ``tests*.py``, ``conftest.py``),
les migrations, ``services.py`` lui-même et la liste blanche NOMMÉE ci-dessous
(``seed_demo_company.py`` : données de démo).

Dette gelée : ``scripts/notify_point_unique_allow.txt`` — lignes
``chemin::fonction  # justification``. Une entrée SANS justification est
refusée ; une entrée devenue conforme sans être retirée fait échouer la garde ;
la liste ne peut que DÉCROÎTRE.

Usage :
    python scripts/check_notify_point_unique.py           # check (CI)
    python scripts/check_notify_point_unique.py --list    # tous les sites
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
TYPE_DE_CLE = "par_symbole"  # AMET100 — cle de contenu `fichier::symbole` (jamais un numero de ligne)

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend" / "django_core"
ALLOWLIST_PATH = ROOT / "scripts" / "notify_point_unique_allow.txt"

# Seul fichier autorisé à écrire une Notification (notify, notify_many,
# notify_security_change y vivent).
POINT_UNIQUE = "backend/django_core/apps/notifications/services.py"
# Liste blanche NOMMÉE (fichiers entiers, justification obligatoire).
LISTE_BLANCHE_NOMMEE = {
    "backend/django_core/authentication/management/commands/seed_demo_company.py":
        "données de démonstration (seed), jamais un flux métier",
}
_ECRITURES = {"create", "bulk_create", "get_or_create", "update_or_create"}
_SKIP_DIRS = {"migrations", "tests", "node_modules", "parked", "__pycache__"}
MESSAGE = "passer par notify()/notify_many() (report N1, préférences, module)"


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _est_exclu(path: Path) -> bool:
    rel = path.relative_to(BACKEND)
    if any(p in _SKIP_DIRS for p in rel.parts[:-1]):
        return True
    nom = path.name
    return (nom == "conftest.py" or nom.startswith("test_")
            or nom.startswith("tests"))


def _nom_notification(noeud) -> bool:
    if isinstance(noeud, ast.Name):
        return noeud.id == "Notification"
    if isinstance(noeud, ast.Attribute):
        return noeud.attr == "Notification"
    return False


def _est_ecriture(appel: ast.Call) -> bool:
    f = appel.func
    if _nom_notification(f):  # Notification(...)
        return True
    # Notification.objects.create(...)
    return (isinstance(f, ast.Attribute) and f.attr in _ECRITURES
            and isinstance(f.value, ast.Attribute) and f.value.attr == "objects"
            and _nom_notification(f.value.value))


class _Visiteur(ast.NodeVisitor):
    def __init__(self):
        self.pile = []
        self.sites = []  # (ligne, fonction)

    def _fonction(self, noeud):
        self.pile.append(noeud.name)
        self.generic_visit(noeud)
        self.pile.pop()

    visit_FunctionDef = _fonction
    visit_AsyncFunctionDef = _fonction
    visit_ClassDef = _fonction

    def visit_Call(self, noeud):
        if _est_ecriture(noeud):
            self.sites.append((noeud.lineno, ".".join(self.pile) or "<module>"))
        self.generic_visit(noeud)


def sites_du_source(source: str) -> list:
    """[(ligne, fonction)] des écritures de Notification dans ``source``."""
    try:
        arbre = ast.parse(source)
    except SyntaxError:
        return []
    v = _Visiteur()
    v.visit(arbre)
    return v.sites


def analyser() -> dict:
    """{cle 'chemin::fonction': ligne} des écritures hors point unique."""
    trouves: dict = {}
    if not BACKEND.is_dir():
        return trouves
    for path in sorted(BACKEND.rglob("*.py")):
        if _est_exclu(path):
            continue
        rel = _rel(path)
        if rel == POINT_UNIQUE or rel in LISTE_BLANCHE_NOMMEE:
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "Notification" not in source:
            continue
        for ligne, fonction in sites_du_source(source):
            trouves.setdefault(f"{rel}::{fonction}", ligne)
    return trouves


def _load_allowlist():
    """(cles, entrées sans justification)."""
    cles, sans_justif = set(), []
    if not ALLOWLIST_PATH.is_file():
        return cles, sans_justif
    for brut in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        if not brut.strip() or brut.lstrip().startswith("#"):
            continue
        cle, _, justif = brut.partition("#")
        cle = cle.strip()
        cles.add(cle)
        if not justif.strip():
            sans_justif.append(cle)
    return cles, sans_justif


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
    allow, sans_justif = _load_allowlist()
    nouveaux = {k: v for k, v in trouves.items() if k not in allow}
    morts = sorted(allow - set(trouves))
    if nouveaux:
        print("check_notify_point_unique: Notification écrite hors de "
              "apps/notifications/services.py :")
        for cle, ligne in sorted(nouveaux.items()):
            fichier, fonction = cle.split("::", 1)
            print(f"  - {fichier}:{ligne}  {fonction} — {MESSAGE}")
    if sans_justif:
        print("check_notify_point_unique: entrées de liste blanche SANS "
              "justification (ajoutez « # raison ») :")
        for cle in sans_justif:
            print(f"  - {cle}")
    if morts:
        print("check_notify_point_unique: entrées MORTES de "
              "scripts/notify_point_unique_allow.txt (retirez la ligne) :")
        for cle in morts:
            print(f"  - {cle}")
    if nouveaux or sans_justif or morts:
        return 1
    print(f"check_notify_point_unique: OK — {len(trouves)} site(s) historique(s) "
          "gelé(s), aucune nouvelle écriture hors notify().")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
