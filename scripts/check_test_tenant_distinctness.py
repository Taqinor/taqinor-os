"""CI guard: a test that claims to build a SECOND tenant must really build one.

The bug this exists to stop (found 2026-07-31 in ``apps/chat/tests/test_chat.py``)
is the worst kind: a test that makes multi-tenancy look verified when it is not.

A test module typically ships a helper like::

    def make_company(slug='chat-co', nom='Chat Co'):
        company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
        return company

``authentication.Company.slug`` is UNIQUE and ``Company.save()`` derives it from
``slugify(nom)`` when blank, so a SECOND call landing on the same effective slug
returns the row that already exists. A test doing::

    def setUp(self):
        self.company = make_company()

    def test_no_cross_tenant_leak(self):
        other_company = make_company()          # <-- SAME ROW
        Thing.objects.create(company=other_company, ...)
        self.assertNotIn(thing.id, response_ids)

never exercises isolation at all: the "other company's" row lands in its own
company. The identical trap exists on the authenticated user — helpers doing
``User.objects.get_or_create(username=..., defaults={'company': company})`` on a
fixed default username hand back the FIRST user (still in the FIRST company),
so the request is not cross-tenant either.

This guard is a DB-free AST sweep (same shape as ``check_test_determinism.py``).
For every test method it resolves the effective UNIQUE KEY (Company.slug /
User.username) of every tenant-root creation reachable from that method and its
class's ``setUp``/``setUpTestData``/``setUpClass`` (base classes included), then
fails when two creations that the test treats as distinct collapse onto one row.

Helpers that uniquify (``itertools.count``/``uuid``/``factory.Sequence``…) are
safe by construction and are never flagged — that IS the recommended fix::

    _seq = itertools.count(1)

    def make_company(slug=None, nom=None):
        n = next(_seq)
        company, _ = Company.objects.get_or_create(
            slug=slug or f'chat-co-{n}', defaults={'nom': nom or f'Chat Co {n}'})
        return company

Usage:
    python scripts/check_test_tenant_distinctness.py           # check (CI)
    python scripts/check_test_tenant_distinctness.py --list-risky
        # advisory: every helper whose DEFAULT arguments resolve to a fixed key
"""
from __future__ import annotations

import ast
import os
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = ROOT / "backend" / "django_core"

SKIPPED_PARTS = {".git", "node_modules", "migrations", "dist", "build",
                 "__pycache__"}

# Scoping roots and the field that is UNIQUE on them. ``Company.nom`` is the
# fallback because ``Company.save()`` slugifies it when ``slug`` is blank.
TARGETS: dict[str, tuple[str, str | None]] = {
    "Company": ("slug", "nom"),
    "CustomUser": ("username", None),
    "User": ("username", None),
}

CREATE_METHODS = {"get_or_create", "update_or_create", "create", "create_user"}
SILENT_METHODS = {"get_or_create", "update_or_create"}

# A helper body containing any of these builds a fresh identifier every call.
UNIQUIFIER_RE = re.compile(
    r"next\(|uuid|\.count\(\)|randint|random\.|time\(\)|Sequence\(|token_hex"
    r"|itertools")

SETUP_NAMES = {"setUp", "setUpTestData", "setUpClass"}


class Unresolved(Exception):
    """The identifier depends on something this AST sweep cannot see."""


def slugify(value: object) -> str:
    """Mirror of ``django.utils.text.slugify`` (no Django import here).

    ``Company.save()`` calls it to derive a blank ``slug`` from ``nom``, so two
    ``Company.objects.create(nom=...)`` with the same name collide on the
    UNIQUE slug — this must transliterate accents exactly like Django does.
    """
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "-", text).strip("-_")


def _literal(node: ast.AST, env: dict | None = None) -> object:
    """Constant value of ``node``; ``env`` resolves enclosing parameter names."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name) and env and env.get(node.id) is not None:
        return env[node.id]
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                parts.append(str(_literal(value.value, env)))
            else:
                raise Unresolved()
        return "".join(parts)
    raise Unresolved()


def _target_of(call: ast.Call) -> tuple[str, str] | None:
    """``Model.objects.<create-ish>(...)`` -> (model name, method name)."""
    func = call.func
    if not isinstance(func, ast.Attribute) or func.attr not in CREATE_METHODS:
        return None
    owner = func.value
    if not (isinstance(owner, ast.Attribute) and owner.attr == "objects"):
        return None
    if not isinstance(owner.value, ast.Name):
        return None
    if owner.value.id not in TARGETS:
        return None
    return owner.value.id, func.attr


def _key_source(call: ast.Call, model: str) -> tuple[ast.AST | None, bool]:
    """Return (node holding the unique key, whether it must be slugified)."""
    key_field, fallback_field = TARGETS[model]
    kwargs = {kw.arg: kw.value for kw in call.keywords if kw.arg}
    node = kwargs.get(key_field)
    fallback = kwargs.get(fallback_field) if fallback_field else None
    defaults = kwargs.get("defaults")
    if isinstance(defaults, ast.Dict):
        for key, value in zip(defaults.keys, defaults.values):
            if not isinstance(key, ast.Constant):
                continue
            if key.value == key_field and node is None:
                node = value
            elif fallback_field and key.value == fallback_field \
                    and fallback is None:
                fallback = value
    if node is None and call.args:
        # positional ``create_user('bob', ...)``
        node = call.args[0]
    if node is not None:
        return node, False
    return fallback, True


def _make_resolver(call: ast.Call, model: str):
    """Build ``resolver(argmap) -> unique key`` for one creation call."""
    source, needs_slugify = _key_source(call, model)
    if source is None:
        return None

    def resolve(node: ast.AST, argmap: dict) -> object:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            value = argmap.get(node.id)
            if value is None:
                raise Unresolved()
            return value
        if isinstance(node, ast.JoinedStr):
            parts = []
            for value in node.values:
                if isinstance(value, ast.Constant):
                    parts.append(str(value.value))
                elif isinstance(value, ast.FormattedValue):
                    parts.append(str(resolve(value.value, argmap)))
                else:
                    raise Unresolved()
            return "".join(parts)
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            # ``slug or f'co-{n}'`` — the argument wins when truthy
            left = resolve(node.values[0], argmap)
            return left if left else resolve(node.values[1], argmap)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return str(resolve(node.left, argmap)) + \
                str(resolve(node.right, argmap))
        raise Unresolved()

    def resolver(argmap: dict) -> str:
        value = resolve(source, argmap)
        return slugify(value) if needs_slugify else str(value)

    return resolver


class _HelperCollector(ast.NodeVisitor):
    """Index every function that persists a Company/User."""

    def __init__(self, lines: list[str]) -> None:
        self.lines = lines
        self.helpers: dict[str, dict] = {}
        self.functions: dict[str, ast.FunctionDef] = {}

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self.functions.setdefault(node.name, node)
        creation = None
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                target = _target_of(child)
                if target:
                    creation = (target[0], target[1], child)
                    break
        if creation is not None:
            model, method, call = creation
            body = "\n".join(self.lines[node.lineno - 1:node.end_lineno or 0])
            params, defaults = _signature(node)
            self.helpers[node.name] = {
                "model": model,
                "silent": method in SILENT_METHODS,
                "uniquified": bool(UNIQUIFIER_RE.search(body)),
                "params": params,
                "defaults": defaults,
                "lineno": node.lineno,
                "resolver": _make_resolver(call, model),
            }
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]


def _signature(node: ast.FunctionDef) -> tuple[list[str], list[object]]:
    params = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
    total = len(node.args.args)
    defaults: list[object] = [None] * (total - len(node.args.defaults))
    for default in node.args.defaults:
        try:
            defaults.append(_literal(default))
        except Unresolved:
            defaults.append(None)
    return params, defaults[total - len(params):]


def _wrapper_resolver(inner: dict, call: ast.Call):
    """Resolver for a function that delegates to an already-known helper.

    ``make_tenant()`` calling ``make_company()`` inherits the inner helper's
    fixed key — without this, a wrapper would hide the collision from the sweep.
    """
    def resolver(argmap: dict) -> str:
        inner_args: dict = {}
        for index, arg in enumerate(call.args):
            if index >= len(inner["params"]):
                continue
            try:
                inner_args[inner["params"][index]] = _literal(arg, argmap)
            except Unresolved:
                inner_args[inner["params"][index]] = None
        for keyword in call.keywords:
            if keyword.arg is None:
                raise Unresolved()
            try:
                inner_args[keyword.arg] = _literal(keyword.value, argmap)
            except Unresolved:
                inner_args[keyword.arg] = None
        for param, default in zip(inner["params"], inner["defaults"]):
            inner_args.setdefault(param, default)
        return inner["resolver"](inner_args)

    return resolver


def _add_wrapper_helpers(collector: _HelperCollector) -> None:
    """Fixpoint: register functions that create a tenant INDIRECTLY."""
    for _ in range(4):                      # depth cap; chains are shallow
        added = False
        for name, node in collector.functions.items():
            if name in collector.helpers:
                continue
            for child in ast.walk(node):
                if not isinstance(child, ast.Call) or \
                        not isinstance(child.func, ast.Name):
                    continue
                inner = collector.helpers.get(child.func.id)
                if inner is None or inner["resolver"] is None:
                    continue
                params, defaults = _signature(node)
                collector.helpers[name] = {
                    "model": inner["model"],
                    "silent": inner["silent"],
                    "uniquified": inner["uniquified"],
                    "params": params,
                    "defaults": defaults,
                    "lineno": node.lineno,
                    "resolver": _wrapper_resolver(inner, child),
                }
                added = True
                break
        if not added:
            return


def _argmap(helper: dict, call: ast.Call) -> dict | None:
    argmap: dict = {}
    for index, arg in enumerate(call.args):
        if index >= len(helper["params"]):
            continue
        try:
            argmap[helper["params"][index]] = _literal(arg)
        except Unresolved:
            argmap[helper["params"][index]] = None
    for keyword in call.keywords:
        if keyword.arg is None:
            return None            # ``**kwargs`` splat: unresolvable
        try:
            argmap[keyword.arg] = _literal(keyword.value)
        except Unresolved:
            argmap[keyword.arg] = None
    for param, default in zip(helper["params"], helper["defaults"]):
        argmap.setdefault(param, default)
    return argmap


def _creations_in(node: ast.AST, scope: dict) -> list[tuple]:
    """(model, key, silent, lineno, label) for each tenant-root creation."""
    found = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        name = None
        if isinstance(func, ast.Name):
            name = func.id
        elif (isinstance(func, ast.Attribute)
              and isinstance(func.value, ast.Name)
              and func.value.id in ("self", "cls")):
            name = func.attr
        if name in scope:
            helper = scope[name]
            if helper["uniquified"] or helper["resolver"] is None:
                continue
            argmap = _argmap(helper, child)
            if argmap is None:
                continue
            try:
                key = helper["resolver"](argmap)
            except Unresolved:
                continue
            found.append((helper["model"], key, helper["silent"],
                          child.lineno, f"{name}()"))
            continue
        target = _target_of(child)
        if target is None:
            continue
        model, method = target
        resolver = _make_resolver(child, model)
        if resolver is None:
            continue
        try:
            key = resolver({})
        except Unresolved:
            continue
        found.append((model, key, method in SILENT_METHODS, child.lineno,
                      f"{model}.objects.{method}()"))
    return found


def _module_name(path: Path) -> str:
    rel = path.relative_to(BACKEND_ROOT).as_posix()
    return rel[:-3].replace("/", ".")


def _iter_python_files():
    if not BACKEND_ROOT.exists():
        return
    for path in sorted(BACKEND_ROOT.rglob("*.py")):
        if any(part in SKIPPED_PARTS for part in path.parts):
            continue
        yield path


def is_test_file(path: Path) -> bool:
    """Same definition as ``scripts/check_test_determinism.py``."""
    name = path.name
    return (name.startswith("test_") or name.startswith("tests_")
            or name.endswith("_test.py") or name == "tests.py"
            or "tests" in path.parts)


# A module can only create a tenant root by naming one of TARGETS on a manager.
# ``CustomUser.objects`` contains ``User.objects``, so two probes cover all three.
CREATION_TOKENS = ("Company.objects", "User.objects")
IMPORT_RE = re.compile(r"^\s*from\s+([\w.]+)\s+import\b", re.MULTILINE)


def build_registry(files) -> tuple[dict, dict]:
    """(module -> {helper name: helper}, path -> parsed tree).

    Only files that can possibly matter are parsed: those naming a tenant-root
    manager, plus test files importing from a module that turned out to define
    a helper. A full ``ast.parse`` of the whole tree costs ~60 s; this is ~15 s.
    """
    registry: dict[str, dict] = {}
    trees: dict[Path, ast.Module] = {}
    deferred: list[tuple[Path, str]] = []

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not any(token in text for token in CREATION_TOKENS):
            if is_test_file(path):
                deferred.append((path, text))
            continue
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            continue
        trees[path] = tree
        collector = _HelperCollector(text.splitlines())
        collector.visit(tree)
        if collector.helpers:
            _add_wrapper_helpers(collector)
            registry[_module_name(path)] = collector.helpers

    # A test file with no manager call of its own still matters when it imports
    # a helper from one that has them (the shared ``tests/helpers.py`` pattern).
    # Relative imports (``from .helpers import ...``) are matched on suffix.
    suffixes: set[str] = set()
    for module in registry:
        parts = module.split(".")
        for index in range(len(parts)):
            suffixes.add(".".join(parts[index:]))
    for path, text in deferred:
        imported = {module.lstrip(".") for module in IMPORT_RE.findall(text)}
        if not (imported & suffixes):
            continue
        try:
            trees[path] = ast.parse(text)
        except (SyntaxError, ValueError):
            continue
    return registry, trees


def _scope_for(tree: ast.Module, module: str, registry: dict) -> dict:
    scope = dict(registry.get(module, {}))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        base = node.module or ""
        if node.level:
            package = module.rsplit(".", node.level)[0]
            base = f"{package}.{base}" if base else package
        source = registry.get(base)
        if not source:
            continue
        for alias in node.names:
            if alias.name in source:
                scope[alias.asname or alias.name] = source[alias.name]
    return scope


def violations_for(tree: ast.Module, module: str, registry: dict,
                   rel: str) -> list[str]:
    scope = _scope_for(tree, module, registry)
    if not scope:
        return []
    classes = {node.name: node for node in ast.walk(tree)
               if isinstance(node, ast.ClassDef)}

    def setup_creations(cls: ast.ClassDef, seen: tuple = ()) -> list[tuple]:
        acc: list[tuple] = []
        for base in cls.bases:
            name = base.id if isinstance(base, ast.Name) else (
                base.attr if isinstance(base, ast.Attribute) else None)
            if name and name in classes and name not in seen:
                acc += setup_creations(classes[name], seen + (cls.name,))
        for item in cls.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if item.name in SETUP_NAMES:
                    acc += _creations_in(item, scope)
            else:
                acc += _creations_in(item, scope)
        return acc

    failures: list[str] = []
    for cls in classes.values():
        shared = setup_creations(cls)
        methods = [item for item in cls.body
                   if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and item.name not in SETUP_NAMES]
        for method in methods:
            buckets: dict[tuple, list] = defaultdict(list)
            for model, key, silent, lineno, label in \
                    shared + _creations_in(method, scope):
                buckets[(model, key)].append((silent, lineno, label))
            for (model, key), entries in buckets.items():
                if len(entries) < 2 or not any(e[0] for e in entries):
                    continue
                where = ", ".join(f"line {e[1]} {e[2]}" for e in entries)
                field = TARGETS[model][0]
                failures.append(
                    f"{rel}:{entries[-1][1]}: {cls.name}.{method.name} builds "
                    f"{len(entries)} {model} rows that all resolve to "
                    f"{field}={key!r} ({where}) — get_or_create hands back the "
                    f"SAME row. If a SECOND tenant was intended, the isolation "
                    f"assertion proves nothing: pass an explicit distinct "
                    f"{field}, or give the helper a counter (itertools.count) "
                    f"so every call is a new tenant. If the SAME tenant was "
                    f"intended, assign it once to a variable and reuse it."
                )
    return failures


def risky_helpers(registry: dict) -> list[str]:
    """Advisory: helpers whose DEFAULT arguments resolve to a fixed key.

    These are safe only for as long as every call site that wants a second
    tenant passes its own identifier — the check above is what makes the
    failure mode impossible to ship silently.
    """
    out = []
    for module, helpers in sorted(registry.items()):
        for name, helper in sorted(helpers.items()):
            if not helper["silent"] or helper["uniquified"]:
                continue
            if helper["resolver"] is None:
                continue
            if name in SETUP_NAMES or name.startswith("test"):
                continue           # a test method, not a reusable helper
            if not any(p in ("slug", "nom", "name", "username", "code")
                       for p in helper["params"]):
                out.append(f"{module}:{helper['lineno']} {name}() -> "
                           f"{helper['model']} FIXED, no identifier parameter")
                continue
            try:
                key = helper["resolver"](
                    dict(zip(helper["params"], helper["defaults"])))
            except Unresolved:
                continue
            if key:
                out.append(f"{module}:{helper['lineno']} {name}() -> "
                           f"{helper['model']} key={key!r}")
    return out


def main() -> int:
    files = list(_iter_python_files())
    registry, trees = build_registry(files)

    if "--list-risky" in sys.argv:
        rows = risky_helpers(registry)
        print(f"{len(rows)} helper(s) whose defaults resolve to a fixed "
              f"tenant key (safe only while every call site passes its own):")
        for row in rows:
            print(f"  - {row}")
        return 0

    # The registry spans every module (a test may import a shared helper from a
    # non-test module); only TEST files are checked for the vacuous pattern.
    failures: list[str] = []
    for path, tree in trees.items():
        if not is_test_file(path):
            continue
        rel = path.relative_to(BACKEND_ROOT).as_posix()
        failures += violations_for(tree, _module_name(path), registry, rel)

    if failures:
        print("Vacuous multi-tenant isolation detected:")
        for failure in sorted(failures):
            print(f"  - {failure}")
        return 1

    print("Tenant-distinctness guard: every test that builds a second tenant "
          "really builds one.")
    return 0


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.exit(main())
