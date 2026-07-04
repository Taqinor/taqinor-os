"""Scanner statique des endpoints publics (AllowAny) — durcissement (YRBAC9).

Relève par AST toute vue (fonction ``@api_view`` ou classe) déclarée
``AllowAny`` et indique si elle porte un ``throttle_classes`` non vide
(anti-brute-force jeton). Le test associé exige un throttle sur chaque endpoint
public, sauf ceux d'une allowlist justifiée (ratchet — ne peut que se réduire).

``core`` reste FONDATION : lecture AST de fichiers, aucun import d'app métier.
"""
from __future__ import annotations

import ast
from pathlib import Path

DJANGO_CORE_ROOT = Path(__file__).resolve().parents[1]
APPS_ROOT = DJANGO_CORE_ROOT / "apps"


def _is_view_file(path: Path) -> bool:
    if "migrations" in path.parts or path.suffix != ".py":
        return False
    return (
        path.name == "views.py"
        or path.parent.name == "views"
        or path.name.endswith("_views.py")
        or path.name == "calendar.py"
    )


def _deco_name(deco: ast.expr) -> str | None:
    node = deco.func if isinstance(deco, ast.Call) else deco
    return getattr(node, "id", None) or getattr(node, "attr", None)


def _list_has_allowany(value: ast.expr) -> bool:
    if not isinstance(value, (ast.List, ast.Tuple)):
        return False
    return any(getattr(e, "id", None) == "AllowAny" for e in value.elts)


def _nonempty_list(value: ast.expr) -> bool:
    return isinstance(value, (ast.List, ast.Tuple)) and bool(value.elts)


def _func_flags(node) -> tuple[bool, bool]:
    allow_any = throttled = False
    for deco in node.decorator_list:
        if not isinstance(deco, ast.Call):
            continue
        name = _deco_name(deco)
        if name == "permission_classes":
            allow_any = allow_any or any(
                _list_has_allowany(a) for a in deco.args)
        elif name == "throttle_classes":
            throttled = throttled or any(_nonempty_list(a) for a in deco.args)
    return allow_any, throttled


def _class_flags(node: ast.ClassDef) -> tuple[bool, bool]:
    allow_any = throttled = False
    for stmt in node.body:
        if not isinstance(stmt, ast.Assign):
            continue
        targets = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
        if "permission_classes" in targets:
            allow_any = allow_any or _list_has_allowany(stmt.value)
        if "throttle_classes" in targets:
            throttled = throttled or _nonempty_list(stmt.value)
    return allow_any, throttled


def public_endpoints() -> list[dict]:
    """[{id, allow_any, throttled}] pour chaque vue AllowAny détectée.

    ``id`` = ``<app>/<fichier>::<vue>`` (stable, relatif à ``apps/``).
    """
    result: list[dict] = []
    for path in sorted(APPS_ROOT.rglob("*.py")):
        if not _is_view_file(path):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        rel = path.relative_to(APPS_ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                allow_any, throttled = _func_flags(node)
            elif isinstance(node, ast.ClassDef):
                allow_any, throttled = _class_flags(node)
            else:
                continue
            if allow_any:
                result.append({
                    "id": f"{rel}::{node.name}",
                    "throttled": throttled,
                })
    return result


def unthrottled_public_endpoints() -> list[str]:
    return [e["id"] for e in public_endpoints() if not e["throttled"]]
