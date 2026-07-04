"""Scanner statique des gardes de permission sur les ``@action`` DRF (YRBAC4).

Le pattern d'or (``apps/crm/views.py``) est : chaque ``@action`` custom déclare
sa propre ``permission_classes=[…]``, OU son viewset expose un ``get_permissions``
qui route la garde par nom d'action. Ce module parse les ``views`` de toutes les
apps et relève les ``@action`` NON gardées (ni ``permission_classes=`` ni
``get_permissions`` sur leur viewset) — c'est la dette que YRBAC3 résorbe.

Le test associé applique un RATCHET : il fige un baseline par app (l'état
courant de la dette) et échoue si une app DÉPASSE son baseline (nouvelle
``@action`` sans garde). Au fur et à mesure que YRBAC3 fine-graine les apps, le
baseline se réduit — jamais il n'augmente.

``core`` reste FONDATION : lecture AST de fichiers, aucun import d'app métier.
"""
from __future__ import annotations

import ast
from pathlib import Path

DJANGO_CORE_ROOT = Path(__file__).resolve().parents[1]
APPS_ROOT = DJANGO_CORE_ROOT / "apps"


def _is_view_file(path: Path) -> bool:
    if "migrations" in path.parts:
        return False
    if path.suffix != ".py":
        return False
    return (
        path.name == "views.py"
        or path.parent.name == "views"
        or path.name.endswith("_views.py")
    )


def _decorator_name(deco: ast.expr) -> str | None:
    node = deco.func if isinstance(deco, ast.Call) else deco
    return getattr(node, "id", None) or getattr(node, "attr", None)


def _action_has_permission_kw(deco: ast.expr) -> bool:
    if not isinstance(deco, ast.Call):
        return False
    return any(kw.arg == "permission_classes" for kw in deco.keywords)


def unguarded_actions() -> dict[str, list[str]]:
    """{app -> [«fichier::viewset.action», …]} des @action sans garde explicite.

    Une @action est GARDÉE si elle porte ``permission_classes=`` OU si son
    viewset déclare un ``get_permissions`` (qui route la garde par action).
    """
    result: dict[str, list[str]] = {}
    for path in sorted(APPS_ROOT.rglob("*.py")):
        if not _is_view_file(path):
            continue
        app = path.relative_to(APPS_ROOT).parts[0]
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        rel = path.relative_to(DJANGO_CORE_ROOT)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            has_get_perms = any(
                isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name == "get_permissions"
                for n in node.body
            )
            for member in node.body:
                if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for deco in member.decorator_list:
                    if _decorator_name(deco) != "action":
                        continue
                    guarded = _action_has_permission_kw(deco) or has_get_perms
                    if not guarded:
                        result.setdefault(app, []).append(
                            f"{rel}::{node.name}.{member.name}")
    return result


def unguarded_counts() -> dict[str, int]:
    return {app: len(items) for app, items in unguarded_actions().items()}
