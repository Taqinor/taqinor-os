"""Scanner statique des ``get_object_or_404(<Model>, pk=…)`` non scopés
(YRBAC11).

Repère, dans les ``views.py``/``views/*.py``/``*_views.py`` des apps métier,
tout appel ``get_object_or_404(<Model>, pk=…)`` qui ne porte NI un mot-clé
``company=``/``company_id=`` NI un mot-clé de portée usuel (``owner=``,
``created_by=``…) — c'est la dette que ``core.selectors.get_company_object``
résorbe (YRBAC11). Un appel qui filtre déjà par société/portée n'est PAS de la
dette (ex. ``get_object_or_404(Modele, pk=modele_id, company=company)``).

Volontairement STATIQUE (AST, jamais d'exécution) et best-effort : un faux
négatif (scope appliqué autrement, ex. sur un queryset déjà filtré passé en 1er
argument) est acceptable — l'objectif est de lister la dette RESTANTE, pas de
prouver l'absence totale de bug. ``core`` reste FONDATION : aucun import
d'app métier, uniquement de la lecture AST de fichiers.
"""
from __future__ import annotations

import ast
from pathlib import Path

DJANGO_CORE_ROOT = Path(__file__).resolve().parents[1]
APPS_ROOT = DJANGO_CORE_ROOT / "apps"

# Mots-clés qui, s'ils apparaissent en keyword d'un get_object_or_404, prouvent
# un scoping explicite (société ou portée propriétaire) — pas de la dette.
_SCOPE_KEYWORDS = frozenset({
    "company", "company_id",
    "owner", "owner_id",
    "created_by", "created_by_id",
    "user", "user_id",
})

# Apps fondation/techniques exemptées (même esprit que
# ``core.permissions.EXEMPT_PREFIXES`` — ce ne sont pas des apps « métier »
# multi-tenant au sens business-core/satellite).
_EXEMPT_APPS = frozenset({
    "authentication", "roles", "parametres", "core", "records",
    "customfields", "audit", "reporting", "dataimport",
})


def _is_view_file(path: Path) -> bool:
    if "migrations" in path.parts or "tests" in path.parts:
        return False
    if path.suffix != ".py":
        return False
    return (
        path.name == "views.py"
        or path.parent.name == "views"
        or path.name.endswith("_views.py")
    )


def _first_arg_model_name(call: ast.Call) -> str | None:
    if not call.args:
        return None
    first = call.args[0]
    return getattr(first, "id", None) or getattr(first, "attr", None)


def _has_scope_keyword(call: ast.Call) -> bool:
    return any(kw.arg in _SCOPE_KEYWORDS for kw in call.keywords)


def _has_pk_keyword_or_second_positional(call: ast.Call) -> bool:
    if any(kw.arg == "pk" for kw in call.keywords):
        return True
    return len(call.args) >= 2


def unscoped_get_object_calls() -> dict[str, list[str]]:
    """{app -> [«fichier:ligne::Model», …]} des appels non scopés.

    Un appel compte comme dette s'il ressemble à
    ``get_object_or_404(Model, pk=…)`` (ou un 2e positionnel = le pk) SANS
    aucun mot-clé de ``_SCOPE_KEYWORDS``.
    """
    result: dict[str, list[str]] = {}
    for path in sorted(APPS_ROOT.rglob("*.py")):
        if not _is_view_file(path):
            continue
        app = path.relative_to(APPS_ROOT).parts[0]
        if app in _EXEMPT_APPS:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        rel = path.relative_to(DJANGO_CORE_ROOT)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func_name = (
                getattr(node.func, "id", None)
                or getattr(node.func, "attr", None)
            )
            if func_name != "get_object_or_404":
                continue
            model_name = _first_arg_model_name(node)
            if model_name is None:
                continue
            if not _has_pk_keyword_or_second_positional(node):
                continue
            if _has_scope_keyword(node):
                continue
            result.setdefault(app, []).append(
                f"{rel}:{node.lineno}::{model_name}")
    return result


def unscoped_counts() -> dict[str, int]:
    return {app: len(items) for app, items in unscoped_get_object_calls().items()}
