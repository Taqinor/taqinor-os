"""Scanner statique des endpoints publics (AllowAny) — durcissement (YRBAC9, ASEC17).

Relève par AST toute vue (fonction ``@api_view`` ou classe) déclarée
``AllowAny`` et indique si elle porte un ``throttle_classes`` non vide
(anti-brute-force jeton). Le test associé exige un throttle sur chaque endpoint
public, sauf ceux d'une allowlist justifiée (ratchet — ne peut que se réduire).

ASEC17 — le scanner voit TOUTE forme de déclaration, dans TOUT fichier d'``apps/``,
``core/`` et ``authentication/`` (plus seulement ``views.py``) :

* ``permission_classes = [AllowAny]`` / ``(AllowAny,)`` / ``[permissions.AllowAny]``
  (liste, tuple, attribut, référence qualifiée) ;
* ``@permission_classes([AllowAny])`` sur une fonction ``@api_view`` ;
* ``@action(..., permission_classes=[AllowAny])`` sur une méthode de viewset ;
* ``get_permissions()`` qui rend ``AllowAny`` (même conditionnel : la vue a au
  moins un chemin public).

Un throttle = ``throttle_classes`` non vide (attribut de classe, décorateur,
argument d'``@action``) ou une méthode ``get_throttles``.

``core`` reste FONDATION : lecture AST de fichiers, aucun import d'app métier.
"""
from __future__ import annotations

import ast
from pathlib import Path

DJANGO_CORE_ROOT = Path(__file__).resolve().parents[1]
APPS_ROOT = DJANGO_CORE_ROOT / "apps"
#: Racines balayées. ``apps`` garde ses identifiants relatifs à ``apps/``
#: (compatibilité des allowlists YRBAC9) ; ``core``/``authentication`` sont
#: relatifs à la racine Django.
_ROOTS = (
    (APPS_ROOT, APPS_ROOT),
    (DJANGO_CORE_ROOT / "core", DJANGO_CORE_ROOT),
    (DJANGO_CORE_ROOT / "authentication", DJANGO_CORE_ROOT),
)
_SKIP_PARTS = {"migrations", "tests", "test", "__pycache__", "management"}
_SELF = Path(__file__).resolve()


def _is_source_file(path: Path) -> bool:
    if path.suffix != ".py" or path.resolve() == _SELF:
        return False
    if any(part in _SKIP_PARTS for part in path.parts):
        return False
    return not path.name.startswith(("test_", "tests_")) and path.name not in (
        "tests.py", "conftest.py")


def _deco_name(deco: ast.expr) -> str | None:
    node = deco.func if isinstance(deco, ast.Call) else deco
    return getattr(node, "id", None) or getattr(node, "attr", None)


def _mentions_allowany(value: ast.AST | None) -> bool:
    """Vrai si l'expression référence ``AllowAny`` (nom nu OU ``x.AllowAny``)."""
    if value is None:
        return False
    for sub in ast.walk(value):
        if getattr(sub, "id", None) == "AllowAny":
            return True
        if isinstance(sub, ast.Attribute) and sub.attr == "AllowAny":
            return True
    return False


def _nonempty_list(value: ast.expr) -> bool:
    return isinstance(value, (ast.List, ast.Tuple)) and bool(value.elts)


def _func_flags(node) -> tuple[bool, bool]:
    """(public, throttlé) d'une FONCTION ``@api_view`` ou d'une méthode ``@action``."""
    allow_any = throttled = False
    for deco in node.decorator_list:
        if not isinstance(deco, ast.Call):
            continue
        name = _deco_name(deco)
        if name == "permission_classes":
            allow_any = allow_any or any(_mentions_allowany(a) for a in deco.args)
        elif name == "throttle_classes":
            throttled = throttled or any(_nonempty_list(a) for a in deco.args)
        elif name == "action":
            for kw in deco.keywords:
                if kw.arg == "permission_classes":
                    allow_any = allow_any or _mentions_allowany(kw.value)
                elif kw.arg == "throttle_classes":
                    throttled = throttled or _nonempty_list(kw.value)
    return allow_any, throttled


def _class_flags(node: ast.ClassDef) -> tuple[bool, bool]:
    allow_any = throttled = False
    for stmt in node.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if stmt.name == "get_permissions" and _mentions_allowany(stmt):
                allow_any = True
            elif stmt.name == "get_throttles":
                throttled = True
            continue
        if isinstance(stmt, ast.Assign):
            targets = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
            value = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(
                stmt.target, ast.Name):
            targets, value = [stmt.target.id], stmt.value
        else:
            continue
        if "permission_classes" in targets:
            allow_any = allow_any or _mentions_allowany(value)
        if "throttle_classes" in targets and value is not None:
            throttled = throttled or _nonempty_list(value)
    return allow_any, throttled


_BODY_VERBS = {"post", "put", "patch"}


def _reads_body_unguarded(handlers) -> bool:
    """ASEC17 / C-ASEC-028 — le handler lit le corps comme un dict
    (``request.data.get(...)`` / ``request.data[...]``) SANS jamais vérifier que
    c'est un objet (``isinstance(request.data, dict)``) ni le faire valider par
    un sérialiseur : un corps JSON non-objet (``[]``, ``"x"``) lève alors une
    ``AttributeError``/``TypeError`` → 500 générique (sans fuite — handler DRF)."""
    for handler in handlers:
        texte = ast.unparse(handler)
        lit = ("request.data.get(" in texte or "request.data[" in texte)
        if not lit:
            continue
        if "isinstance(request.data" in texte or "Serializer(" in texte:
            continue
        return True
    return False


def _iter_files():
    seen = set()
    for scan_root, id_root in _ROOTS:
        if not scan_root.is_dir():
            continue
        for path in sorted(scan_root.rglob("*.py")):
            if path in seen or not _is_source_file(path):
                continue
            seen.add(path)
            yield path, id_root


def endpoints_of_source(source: str, rel: str) -> list[dict]:
    """[{id, throttled, body_unguarded}] des vues AllowAny d'UN source Python.

    Séparé de ``public_endpoints`` pour que le scanner soit éprouvé sur des
    sources synthétiques (une forme de déclaration oubliée = vue invisible)."""
    tree = ast.parse(source)
    result: list[dict] = []

    def visit(body, owner_throttled=False, owner=None):
        for node in body:
            if isinstance(node, ast.ClassDef):
                allow_any, throttled = _class_flags(node)
                if allow_any:
                    result.append({
                        "id": f"{rel}::{node.name}",
                        "throttled": throttled,
                        "body_unguarded": _reads_body_unguarded([
                            m for m in node.body
                            if isinstance(m, (ast.FunctionDef,
                                              ast.AsyncFunctionDef))
                            and m.name in _BODY_VERBS]),
                    })
                visit(node.body, throttled, node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                allow_any, throttled = _func_flags(node)
                if allow_any:
                    nom = f"{owner}.{node.name}" if owner else node.name
                    result.append({
                        "id": f"{rel}::{nom}",
                        "throttled": throttled or owner_throttled,
                        "body_unguarded": _reads_body_unguarded([node]),
                    })
                visit(node.body, False, None)
            elif isinstance(getattr(node, "body", None), list):
                visit(node.body, owner_throttled, owner)
                for extra in ("orelse", "finalbody"):
                    sub = getattr(node, extra, None)
                    if isinstance(sub, list):
                        visit(sub, owner_throttled, owner)

    visit(tree.body)
    return result


def public_endpoints() -> list[dict]:
    """[{id, throttled, body_unguarded}] pour chaque vue AllowAny détectée.

    ``id`` = ``<chemin>::<vue>`` (relatif à ``apps/`` pour les apps, à la racine
    Django pour ``core/`` et ``authentication/``). Une méthode ``@action``
    publique est ``<chemin>::<Classe>.<méthode>``.
    """
    result: list[dict] = []
    for path, id_root in _iter_files():
        try:
            source = path.read_text(encoding="utf-8")
            if "AllowAny" not in source:
                continue
            result.extend(endpoints_of_source(
                source, path.relative_to(id_root).as_posix()))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
    return result


def unthrottled_public_endpoints() -> list[str]:
    return [e["id"] for e in public_endpoints() if not e["throttled"]]


def body_unguarded_public_endpoints() -> list[str]:
    """Vues publiques qui lisent le corps comme un objet sans le garder
    (inventaire C-ASEC-028 : un corps JSON non-objet y donne un 500)."""
    return [e["id"] for e in public_endpoints() if e["body_unguarded"]]
