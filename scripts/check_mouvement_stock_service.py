"""AUD223 — garde sémantique : UN SEUL endroit crée un ``MouvementStock``.

``apps.stock.services.record_stock_movement`` prétendait depuis toujours être
« le SEUL endroit du dépôt qui crée un MouvementStock » — c'est lui qui émet
``core.events.mouvement_stock_enregistre`` (miroir comptable d'inventaire
permanent, ``compta/receivers.py``) et qui déclenche l'alerte seuil-bas.
L'audit R2 a compté **22 sites de production** qui en créaient un EN DIRECT et
échappaient donc aux deux. Ils ont convergé ; cette garde empêche le 23e.

DB-free, AST-only (mêmes conventions que ``scripts/check_get_or_create.py`` et
``scripts/check_read_modify_write.py`` : pas de Django, pas de base, tourne
dans le job CI rapide ``stage-names``).

CE QUI EST REFUSÉ
-----------------
Tout ``MouvementStock.objects.create(...)`` (ou ``MouvementStock(...)`` suivi
d'un ``.save()`` — même chose écrite autrement) dans du code de PRODUCTION.

CE QUI EST HORS PÉRIMÈTRE (jamais scanné)
-----------------------------------------
  * les tests (``tests.py``, ``tests_*.py``, ``test_*.py``, ``tests/``) : un
    test a le droit de fabriquer un historique de mouvements à la main ;
  * les migrations : elles manipulent des modèles HISTORIQUES, sur lesquels le
    service ne s'applique pas.

ALLOWLIST (``scripts/mouvement_stock_service_allow.txt``)
---------------------------------------------------------
Une ligne ``chemin/relatif.py`` par exception ASSUMÉE et justifiée en
commentaire. Elle contient le service lui-même et les seeders de DÉMO
(``seed_demo``), qui fabriquent un historique fictif hors de toute chaîne
réelle. Ajouter une ligne est un choix explicite, revu comme du code.

Usage :
    python scripts/check_mouvement_stock_service.py           # check (CI)
    python scripts/check_mouvement_stock_service.py --list    # tous les sites
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
ALLOWLIST_PATH = ROOT / "scripts" / "mouvement_stock_service_allow.txt"

#: Le modèle dont la création est réservée au service.
MODEL_NAME = "MouvementStock"

#: Racines scannées : tout le code Django de production.
SCAN_ROOTS = [
    DJANGO_CORE / "apps",
    DJANGO_CORE / "core",
    DJANGO_CORE / "authentication",
]


def _is_test_path(path: Path) -> bool:
    parts = path.parts
    if any(p in ("tests", "migrations") for p in parts):
        return True
    name = path.name
    return (name.startswith("test_") or name.startswith("tests_")
            or name == "tests.py")


def _iter_source_files():
    for root in SCAN_ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if _is_test_path(path):
                continue
            yield path


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _load_allowlist():
    if not ALLOWLIST_PATH.exists():
        return set()
    out = set()
    for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line)
    return out


def _callee_name(node: ast.Call):
    """Nom lisible de l'appelé : ``A.b.c(...)`` -> 'A.b.c', sinon None."""
    parts = []
    cur = node.func
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    else:
        return None
    return ".".join(reversed(parts))


def check_file(path: Path):
    """Renvoie [(ligne, expression)] des créations directes trouvées."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _callee_name(node)
        if not name:
            continue
        segments = name.split(".")
        if MODEL_NAME not in segments:
            continue
        idx = segments.index(MODEL_NAME)
        reste = segments[idx + 1:]
        # MouvementStock.objects.create(...) / .bulk_create(...) / ...
        if reste[:1] == ["objects"] and len(reste) >= 2 and reste[1] in (
                "create", "bulk_create", "get_or_create", "update_or_create"):
            findings.append((node.lineno, f"{name}(...)"))
        # MouvementStock(...) — instanciation nue (suivie d'un .save()).
        elif not reste:
            findings.append((node.lineno, f"{MODEL_NAME}(...)"))
    return findings


def main(argv):
    list_mode = "--list" in argv
    allow = _load_allowlist()
    offenders, listed = [], []
    for path in _iter_source_files():
        rel = _rel(path)
        for lineno, expr in check_file(path):
            listed.append(f"{rel}:{lineno}  {expr}")
            if rel not in allow:
                offenders.append(f"{rel}:{lineno}  {expr}")

    if list_mode:
        for line in listed:
            print(line)
        return 0

    if offenders:
        print("check_mouvement_stock_service : création directe d'un "
              "MouvementStock hors du service unique :")
        for line in offenders:
            print(f"  - {line}")
        print(
            "\nUtilisez apps.stock.services.record_stock_movement(...) : lui "
            "seul émet core.events.mouvement_stock_enregistre (miroir "
            "comptable d'inventaire permanent) et déclenche l'alerte "
            "seuil-bas. Un create direct est un mouvement invisible pour la "
            "comptabilité (AUD223, 22 sites corrigés). Exception assumée : "
            "ajouter le chemin à scripts/mouvement_stock_service_allow.txt "
            "avec sa justification."
        )
        return 1

    print("check_mouvement_stock_service : OK — aucune création directe de "
          "MouvementStock hors du service (allowlist respectée).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
