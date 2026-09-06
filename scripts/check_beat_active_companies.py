"""AUD415 — un fan-out beat balaie les sociétés ACTIVES, jamais toutes.

``authentication.selectors.active_companies()`` (SCA19) est la source UNIQUE
des sociétés balayables par une tâche périodique : elle exclut les tenants
``actif=False`` (suspendus, en fermeture — pont bool↔statut SCA18). L'audit
AUD415 a compté **10 sites** de fan-out beat qui itéraient encore
``Company.objects.all()`` en dur, dont un DESTRUCTIF (purge de corbeille GED,
02:30 quotidien avec ``GED_PURGE_AUTO_APPLY=1``) : un tenant suspendu
continuait de recevoir alertes crédit, séquences marketing, réappro stock,
prévisions SCM et relève IMAP réelle. Ils ont convergé ; cette garde empêche
le 11e — et gèle aussi le filtre recopié ``Company.objects.filter(actif=True)``,
qui a la bonne sémantique mais duplique la source unique (elle dérivera le jour
où la définition de « société balayable » bougera).

DB-free, AST-only (mêmes conventions que ``check_mouvement_stock_service.py`` /
``check_tenant_isolation.py`` : pas de Django, pas de base, tourne dans le job
CI rapide ``backend-lint-fast``).

CE QUI EST SCANNÉ
-----------------
Les modules de tâches périodiques UNIQUEMENT : ``apps/*/tasks.py``,
``apps/*/scheduled.py``, ``apps/*/beat_tasks.py`` (y compris en sous-paquet).
Le reste du dépôt est hors périmètre : une vue ou un service admin a le droit
de lister TOUTES les sociétés.

CE QUI EST REFUSÉ
-----------------
``Company.objects.all()`` et ``Company.objects.filter(actif=True)`` (ainsi que
``.filter(actif = True)`` écrit autrement — la comparaison est faite sur l'AST,
pas sur le texte).

ALLOWLIST (``scripts/beat_active_companies_allow.txt``)
-------------------------------------------------------
Une ligne ``chemin/relatif.py`` par exception ASSUMÉE, justifiée en
commentaire. Elle contient les deux exceptions déjà actées par SCA19 (compta,
chat) et les fichiers qui filtrent DÉJÀ ``actif=True`` à la main. Ajouter une
ligne est un choix explicite, revu comme du code.

Usage :
    python scripts/check_beat_active_companies.py           # check (CI)
    python scripts/check_beat_active_companies.py --list    # tous les sites
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
ALLOWLIST_PATH = ROOT / "scripts" / "beat_active_companies_allow.txt"

#: Le modèle dont le balayage périodique est réservé au sélecteur.
MODEL_NAME = "Company"

#: Le sélecteur qui EST la source unique (SCA19).
SELECTEUR = "authentication.selectors.active_companies()"

#: Noms de fichiers considérés comme des modules de tâches périodiques.
FICHIERS_BEAT = ("tasks.py", "scheduled.py", "beat_tasks.py")

#: Racine scannée : les apps métier (les fan-outs beat vivent tous là).
SCAN_ROOT = DJANGO_CORE / "apps"


def _is_test_path(path: Path) -> bool:
    parts = path.parts
    if any(p in ("tests", "migrations") for p in parts):
        return True
    name = path.name
    return (name.startswith("test_") or name.startswith("tests_")
            or name == "tests.py")


def _iter_source_files():
    if not SCAN_ROOT.is_dir():
        return
    for path in sorted(SCAN_ROOT.rglob("*.py")):
        if path.name not in FICHIERS_BEAT or _is_test_path(path):
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


def _est_filtre_actif_vrai(node: ast.Call) -> bool:
    """Vrai pour ``…filter(actif=True)`` (le filtre recopié à la main)."""
    for kw in node.keywords:
        if kw.arg != "actif":
            continue
        valeur = kw.value
        if isinstance(valeur, ast.Constant) and valeur.value is True:
            return True
    return False


def check_file(path: Path):
    """Renvoie [(ligne, expression)] des balayages non scopés trouvés."""
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
        reste = segments[segments.index(MODEL_NAME) + 1:]
        if reste[:1] != ["objects"] or len(reste) < 2:
            continue
        if reste[1] == "all":
            findings.append((node.lineno, f"{name}()"))
        elif reste[1] == "filter" and _est_filtre_actif_vrai(node):
            findings.append((node.lineno, f"{name}(actif=True)"))
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
        print("check_beat_active_companies : fan-out beat qui balaie des "
              "sociétés NON actives :")
        for line in offenders:
            print(f"  - {line}")
        print(
            f"\nItérez sur {SELECTEUR} (SCA19) : un tenant suspendu ou en "
            "fermeture ne doit plus être facturé, relancé ni balayé — et pour "
            "la GED, sa corbeille ne doit surtout pas être purgée "
            "DÉFINITIVEMENT (AUD415, 10 sites corrigés). Un "
            "Company.objects.filter(actif=True) recopié à la main est refusé "
            "pour la même raison : il duplique la source unique et dérivera. "
            "Exception assumée : ajouter le chemin à "
            "scripts/beat_active_companies_allow.txt avec sa justification."
        )
        return 1

    print("check_beat_active_companies : OK — tout fan-out beat passe par "
          "active_companies() (allowlist respectée).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
