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

ASTK35 — deux autres chemins qui contournent le service sont refusés :

  * ``serializer.save()`` d'un ``ModelSerializer`` dont ``Meta.model`` est
    ``MouvementStock`` (instancié directement, ou obtenu par
    ``self.get_serializer()`` dans une vue dont ``serializer_class`` est ce
    sérialiseur) : ``ModelSerializer.create`` écrit la ligne sans passer par
    ``record_stock_movement`` ;
  * toute écriture DIRECTE de ``quantite_stock`` (``x.quantite_stock = …``,
    ``+=``, ``update_fields=['quantite_stock']``, ``.update(quantite_stock=…)``)
    hors de ``record_stock_movement`` : le stock ne bouge que par un mouvement.

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
TYPE_DE_CLE = "par_symbole"  # AMET100 — cle de contenu `fichier::symbole` (jamais un numero de ligne)

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


#: Fonction qui a le droit d'écrire ``quantite_stock`` (le point de passage).
SERVICE_FUNCTION = "record_stock_movement"
STOCK_FIELD = "quantite_stock"


def _mouvement_serializer_names(tree) -> set:
    """Noms des ``*ModelSerializer`` dont ``Meta.model`` est MouvementStock."""
    noms = set()
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        for stmt in cls.body:
            if not (isinstance(stmt, ast.ClassDef) and stmt.name == "Meta"):
                continue
            for sub in stmt.body:
                if (isinstance(sub, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == "model"
                                for t in sub.targets)):
                    val = sub.value
                    nom = (val.id if isinstance(val, ast.Name)
                           else val.attr if isinstance(val, ast.Attribute)
                           else None)
                    if nom == MODEL_NAME:
                        noms.add(cls.name)
    return noms


def _repo_serializer_names() -> set:
    """Sérialiseurs MouvementStock de tout le dépôt (balayage mis en cache)."""
    global _SER_CACHE
    if _SER_CACHE is None:
        noms = set()
        for path in _iter_source_files():
            try:
                texte = path.read_text(encoding="utf-8")
                if MODEL_NAME not in texte:
                    continue
                noms |= _mouvement_serializer_names(ast.parse(texte))
            except (SyntaxError, UnicodeDecodeError, OSError):
                continue
        _SER_CACHE = noms
    return _SER_CACHE


_SER_CACHE = None


def _short(node):
    """``Name`` ou ``mod.Name`` -> 'Name' (sinon None)."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _serializer_save_findings(tree, ser_names):
    """``serializer.save()`` d'un sérialiseur MouvementStock (ASTK35)."""
    if not ser_names:
        return []
    fonctions_de_vue = set()
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        if any(isinstance(st, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "serializer_class"
                       for t in st.targets)
               and _short(st.value) in ser_names for st in cls.body):
            fonctions_de_vue |= {
                n for n in ast.walk(cls)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    out = set()
    for fn in [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        vue = fn in fonctions_de_vue

        def est_serializer(appel):
            nom = _short(appel.func)
            return nom in ser_names or (vue and nom == "get_serializer")

        variables = set()
        for node in ast.walk(fn):
            if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                    and est_serializer(node.value)):
                variables |= {t.id for t in node.targets
                              if isinstance(t, ast.Name)}
        for node in ast.walk(fn):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "save"):
                continue
            cible = node.func.value
            if (isinstance(cible, ast.Call) and est_serializer(cible)) or (
                    isinstance(cible, ast.Name) and cible.id in variables):
                out.add((node.lineno, "serializer.save() (MouvementStock)"))
    return sorted(out)


def _stock_write_findings(tree):
    """Écritures directes de ``quantite_stock`` hors du service (ASTK35)."""
    out = []

    def visite(node, dans_service):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            dans_service = dans_service or node.name == SERVICE_FUNCTION
        if not dans_service:
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                cibles = (node.targets if isinstance(node, ast.Assign)
                          else [node.target])
                for t in cibles:
                    if isinstance(t, ast.Attribute) and t.attr == STOCK_FIELD:
                        out.append((node.lineno, f".{STOCK_FIELD} = ..."))
            elif isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg == "update_fields" and isinstance(
                            kw.value, (ast.List, ast.Tuple, ast.Set)):
                        if any(isinstance(e, ast.Constant)
                               and e.value == STOCK_FIELD
                               for e in kw.value.elts):
                            out.append((node.lineno,
                                        f"update_fields=['{STOCK_FIELD}']"))
                if (isinstance(node.func, ast.Attribute)
                        and node.func.attr == "update"
                        and any(kw.arg == STOCK_FIELD for kw in node.keywords)):
                    out.append((node.lineno, f".update({STOCK_FIELD}=...)"))
        for enfant in ast.iter_child_nodes(node):
            visite(enfant, dans_service)

    visite(tree, False)
    return out


def check_file(path: Path, serializer_names=None):
    """Renvoie [(ligne, expression)] des contournements du service trouvés."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []
    findings = []
    ser_names = set(_mouvement_serializer_names(tree))
    ser_names |= (set(serializer_names) if serializer_names is not None
                  else _repo_serializer_names())
    findings.extend(_serializer_save_findings(tree, ser_names))
    findings.extend(_stock_write_findings(tree))
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
