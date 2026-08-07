#!/usr/bin/env python3
"""Garde permanente : tout chemin appele par le frontend DOIT exister au backend.

POURQUOI CETTE GARDE EXISTE — INCIDENT DU 03/08/2026
----------------------------------------------------
L'ecran « Appels d'offres > Bibliotheque » a plante en production : il appelait
``/ao/bibliotheque/``, une route que le backend n'a JAMAIS enregistree. Le meme
module appelait 8 autres ressources inexistantes (``zones``, ``chaines`` alors
que le serveur sert ``chaines-cotes``, ``variantes`` contre
``variantes-calepinage``, ``series-qr`` contre ``series-questions``...).

Aucun test ne l'a vu, et ce n'est pas un oubli : l'en-tete de
``frontend/src/api/aoApi.js`` declare noir sur blanc que ce fichier « PUBLIE le
contrat d'API que le backend enregistre ensuite ». La moitie frontend a donc
INVENTE le contrat et l'a designe comme obligation pour une lane backend qui
tournait en parallele dans un autre worktree et ne l'a jamais recu. Les deux
moities n'ont jamais eu le meme document sous les yeux, et rien — ni CI, ni
test, ni revue — ne les rapprochait.

Ce n'est pas la premiere fois : quatre campagnes de rattrapage front<->back en
un mois (Round 2 « cablage », docs/FRONTEND_GAP_PLAN.md, groupe WIR, puis cet
incident). Chacune a vide un stock ; aucune n'a ferme le robinet. Cette garde
EST le robinet. Elle rend mecaniquement impossible de livrer un appel frontend
vers une route qui n'existe pas.

NE LA DESACTIVEZ PAS. Si elle rougit, c'est qu'un ecran est deja mort en
production ou le sera au prochain deploiement.

CE QU'ELLE FAIT (analyse statique pure, sans base de donnees, sans dependance)
-----------------------------------------------------------------------------
1. Resout l'inventaire REEL des routes backend en partant de
   ``erp_agentique/urls.py`` : chaque ``include()`` est suivi, chaque
   ``router.register()`` est developpe en route de liste + de detail, et chaque
   ``@action(url_path=...)`` du ViewSet enregistre devient une sous-route. Le
   ``url_path`` par defaut d'une ``@action`` est le nom de la methode TEL QUEL
   (``grand_livre``, avec un souligne) — c'est exactement le piege qui a tue
   l'onglet « Grand-livre » de la compta, appele avec un tiret.
   Les routes FastAPI (``/api/fastapi/...``) sont resolues de la meme facon
   depuis ``backend/fastapi_ia/app/main.py``.
2. Extrait les chemins appeles par TOUT ``frontend/src`` (PACT5), en resolvant
   les cinq mecanismes qui rendaient les mesures naives fausses :
   constantes de base (``const P = '/gestion-projet'``), fabriques partagees
   (``makeResourceFactory(api, '/ao')`` puis ``crud('appels-offres')``),
   fabriques locales (``function crud(slug) { `/qhse/${slug}/` }``),
   litteraux gabarits, et ternaires de suffixe HISSES dans une variable
   (``const mode = x ? '?mode=overwrite' : ''``). Les COMMENTAIRES sont retires
   avant analyse : sans cela une simple mention d'une route d'ECRAN dans un
   commentaire devient un faux positif (mesure : c'etait le cas de
   ``/reporting/quote-to-cash``).

   PERIMETRE — POURQUOI TOUT ``frontend/src`` (PACT5, 03/08/2026)
   Jusqu'ici la garde ne lisait que les clients API (``frontend/src/api/*.js``
   plus les cinq ``*Api.js`` vivant dans ``features/``). Un ``api.get(...)``
   ecrit DANS le corps d'un composant lui echappait entierement — et c'est
   exactement la forme du bouton « Export Excel » de la valorisation du stock,
   qui appelait ``/stock/valorisation-xlsx/`` alors que l'action vit sur le
   ViewSet des produits (``/stock/produits/valorisation-xlsx/``) : mort en
   silence, invisible a la garde. L'elargissement a coute UN mecanisme de
   resolution (le ternaire hisse ci-dessus) et zero ligne d'exception.
   Les fichiers de test sont exclus : un test ne joint pas le serveur, sa
   forme est l'affaire de ``check_api_shapes.py``.
3. Echoue sur tout chemin appele qui ne correspond a aucune route enregistree.

PRINCIPE ANTI-FAUX-POSITIF (assume, delibere)
---------------------------------------------
Un doute ne rougit JAMAIS. Un segment dynamique cote frontend (``${id}``) est
un joker : il matche n'importe quel segment backend. Un sous-arbre que le
resolveur ne sait pas developper entierement (``include()`` introuvable,
ViewSet dont la classe ou les classes de base ne sont pas resolues, route
construite dynamiquement) est declare OPAQUE : tout appel dessous est ignore.
Cette garde sous-detecte volontairement — elle ne doit jamais crier au loup,
sinon elle finira desactivee, et le defaut recidivera une cinquieme fois.

BASE DE REFERENCE — ELLE NE PEUT QUE RETRECIR
---------------------------------------------
La dette historique est figee dans ``scripts/api_contract_allow.txt``. Seule
une occurrence NOUVELLE echoue. ``--write-baseline`` REFUSE d'ajouter une
ligne : il ne sait qu'en retirer (celles qui sont corrigees). Ajouter une
dette exige ``--autoriser-croissance``, un drapeau reserve au fondateur, dont
la presence dans un commit est visible en revue.

Usage :
    python scripts/check_api_contract.py                 # garde CI
    python scripts/check_api_contract.py --stats         # + inventaire chiffre
    python scripts/check_api_contract.py --write-baseline
"""
from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_ROOT = ROOT / "backend" / "django_core"
FASTAPI_ROOT = ROOT / "backend" / "fastapi_ia"
FRONT_SRC = ROOT / "frontend" / "src"
BASELINE_PATH = ROOT / "scripts" / "api_contract_allow.txt"

ROOT_URLCONF = "erp_agentique.urls"
FASTAPI_MOUNT = "api/fastapi"

# Marqueur interne d'un fragment dynamique (`${id}`) dans un litteral gabarit.
HOLE = "\x00"
# Segment normalise « n'importe quoi » (parametre d'URL des deux cotes).
ANY = "<>"

# Bases de classes qui ne peuvent apporter aucune @action : celles du
# framework. Une base venue d'ailleurs et non resolue rend le ViewSet OPAQUE.
FRAMEWORK_ROOTS = (
    "rest_framework", "django", "django_filters", "drf_spectacular",
    "rest_framework_simplejwt", "django_celery_beat",
)

# Modules du backend a NE PAS indexer (aucune vue, volume enorme).
SKIP_DIRS = {"migrations", "__pycache__", "node_modules", ".git", "tests"}


# ===========================================================================
# 1. Inventaire des routes backend (Django)
# ===========================================================================

def _iter_python_files(root: Path):
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        # Les suites de tests ne definissent aucun ViewSet route : les lire
        # doublerait le temps d'analyse pour rien.
        if path.name.startswith(("test_", "tests_")) or path.name == "tests.py":
            continue
        yield path


def _parse(path: Path):
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="replace"),
                         filename=str(path))
    except (OSError, SyntaxError):
        return None


def _import_map(tree: ast.AST, module_dotted: str) -> dict:
    """nom local -> module dotted d'ou il vient (imports absolus ET relatifs)."""
    package = module_dotted.rsplit(".", 1)[0] if "." in module_dotted else ""
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                # level=1 -> le paquet courant ; level=2 -> son parent, etc.
                base = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                source = ".".join([p for p in base if p] + ([node.module] if node.module else []))
            else:
                source = node.module or ""
            for alias in node.names:
                out[alias.asname or alias.name] = source
        elif isinstance(node, ast.Import):
            for alias in node.names:
                out[alias.asname or alias.name.split(".")[0]] = alias.name
    return out


class BackendRoutes:
    """Resout l'arbre d'URL Django par lecture statique (aucun import Django)."""

    def __init__(self, django_root: Path = DJANGO_ROOT):
        self.root = django_root
        self.routes: set[tuple] = set()
        self.opaque: set[tuple] = set()
        # route -> (module, ('fonction'|'classe'|'action', ...)) : QUI sert la
        # route. Inutilise par cette garde ; c'est le chainon dont
        # check_api_shapes.py a besoin pour remonter du chemin appele jusqu'au
        # dictionnaire reellement renvoye.
        self.views: dict[tuple, tuple] = {}
        self._modules: dict[str, tuple] = {}      # dotted -> (path, tree)
        self._classes: dict[str, list] = {}       # nom simple -> [(dotted, node)]
        self._class_by_module: dict[str, dict] = {}
        self._action_cache: dict[str, tuple] = {}
        self._seen_includes: set[str] = set()
        self._constants: dict[str, dict] = {}
        self._imports: dict[str, dict] = {}
        self.unknown_routes = 0
        self.stats = {"registres": 0, "vues": 0, "opaques": 0}

    def _imports_of(self, module: str) -> dict:
        """Table d'imports d'un module, MEMOISEE.

        Sans ce cache, `_import_map` re-parcourait l'AST entier d'un `views.py`
        de 4 000 lignes a chaque base de chaque ViewSet : 61 s de resolution
        au lieu de 4 s.
        """
        if module not in self._imports:
            _, tree = self._module(module)
            self._imports[module] = _import_map(tree, module) if tree is not None else {}
        return self._imports[module]

    def _string_constants(self, module: str) -> dict:
        """Constantes de module utilisables comme chaine de route."""
        if module in self._constants:
            return self._constants[module]
        _, tree = self._module(module)
        out = {}
        if tree is not None:
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    value = _const_str(node.value)
                    if value is None and isinstance(node.value, ast.Call) \
                            and _call_name(node.value) == "get" and len(node.value.args) > 1:
                        # os.environ.get('X', 'defaut/') -> la valeur par defaut
                        value = _const_str(node.value.args[1])
                    if value is not None:
                        out[target.id] = value
        self._constants[module] = out
        return out

    # -- chargement -------------------------------------------------------
    def _module_path(self, dotted: str) -> Path | None:
        candidate = self.root.joinpath(*dotted.split(".")).with_suffix(".py")
        if candidate.is_file():
            return candidate
        pkg = self.root.joinpath(*dotted.split(".")) / "__init__.py"
        return pkg if pkg.is_file() else None

    def _module(self, dotted: str):
        if dotted in self._modules:
            return self._modules[dotted]
        path = self._module_path(dotted)
        tree = _parse(path) if path else None
        self._modules[dotted] = (path, tree)
        return self._modules[dotted]

    def index_classes(self):
        """Index global des classes du backend (pour resoudre les ViewSets)."""
        for path in _iter_python_files(self.root):
            tree = _parse(path)
            if tree is None:
                continue
            dotted = ".".join(path.relative_to(self.root).with_suffix("").parts)
            if dotted.endswith(".__init__"):
                dotted = dotted[: -len(".__init__")]
            per_module = {}
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    per_module[node.name] = node
                    self._classes.setdefault(node.name, []).append((dotted, node))
            if per_module:
                self._class_by_module[dotted] = per_module
                self._modules.setdefault(dotted, (path, tree))

    # -- @action d'un ViewSet ---------------------------------------------
    def _resolve_class(self, name: str, from_module: str):
        """(dotted, ClassDef) ou None. Resolution par import d'abord."""
        _, tree = self._module(from_module)
        if tree is not None:
            imports = self._imports_of(from_module)
            source = imports.get(name)
            if source:
                node = self._class_by_module.get(source, {}).get(name)
                if node is not None:
                    return (source, node)
                # module non indexe (hors backend) -> inconnu
                if not any(source.startswith(r) for r in FRAMEWORK_ROOTS):
                    hits = self._classes.get(name, [])
                    if len(hits) == 1:
                        return hits[0]
                return None
            node = self._class_by_module.get(from_module, {}).get(name)
            if node is not None:
                return (from_module, node)
        hits = self._classes.get(name, [])
        return hits[0] if len(hits) == 1 else None

    def _base_is_framework(self, base: ast.AST, module: str) -> bool:
        root = base
        while isinstance(root, ast.Attribute):
            root = root.value
        if not isinstance(root, ast.Name):
            return False
        _, tree = self._module(module)
        if tree is None:
            return False
        source = self._imports_of(module).get(root.id, "")
        return any(source.startswith(r) or source == r for r in FRAMEWORK_ROOTS)

    def actions_of(self, viewset: str, from_module: str) -> tuple:
        """((detail, url_path), ...) et un drapeau « liste complete »."""
        key = f"{from_module}::{viewset}"
        if key in self._action_cache:
            return self._action_cache[key]
        self._action_cache[key] = ((), False)   # anti-recursion
        resolved = self._resolve_class(viewset, from_module)
        if resolved is None:
            return ((), False)
        module, node = resolved
        actions, complete = [], True
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for deco in item.decorator_list:
                if not (isinstance(deco, ast.Call) and _call_name(deco) == "action"):
                    continue
                detail = False
                url_path = item.name   # DRF : url_path par defaut = NOM DE LA METHODE
                known = True
                for kw in deco.keywords:
                    if kw.arg == "detail":
                        if isinstance(kw.value, ast.Constant):
                            detail = bool(kw.value.value)
                        else:
                            known = False
                    elif kw.arg == "url_path":
                        if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                            url_path = kw.value.value
                        else:
                            known = False
                if known:
                    actions.append((detail, url_path, module, item.name))
                else:
                    complete = False
        for base in node.bases:
            if self._base_is_framework(base, module):
                continue
            if isinstance(base, ast.Name):
                inherited, ok = self.actions_of(base.id, module)
                actions.extend(inherited)
                complete = complete and ok
            else:
                complete = False
        result = (tuple(actions), complete)
        self._action_cache[key] = result
        return result

    # -- parcours de l'URLconf --------------------------------------------
    def build(self):
        self.index_classes()
        self._walk_module(ROOT_URLCONF, ())

    def _routers(self, tree: ast.AST) -> dict:
        """nom de variable -> [(prefixe, nom du ViewSet)]"""
        routers: dict[str, list] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (isinstance(target, ast.Name) and isinstance(node.value, ast.Call)
                            and _call_name(node.value).endswith("Router")):
                        routers.setdefault(target.id, [])
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "register" and isinstance(node.func.value, ast.Name):
                var = node.func.value.id
                if not node.args:
                    continue
                prefix = _const_str(node.args[0])
                viewset = None
                if len(node.args) > 1:
                    target = node.args[1]
                    if isinstance(target, ast.Name):
                        viewset = target.id
                    elif isinstance(target, ast.Attribute):
                        viewset = target.attr
                routers.setdefault(var, []).append((prefix, viewset))
        return routers

    def _lists(self, tree: ast.AST) -> dict:
        out = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, (ast.List, ast.Tuple)):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        out[target.id] = list(node.value.elts)
        return out

    def _urlpatterns(self, tree: ast.AST) -> list:
        entries = []
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "urlpatterns":
                        entries.extend(_flatten(node.value, self._lists(tree)))
            elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) \
                    and node.target.id == "urlpatterns":
                entries.extend(_flatten(node.value, self._lists(tree)))
            elif isinstance(node, ast.If):
                for sub in node.body:
                    if isinstance(sub, ast.AugAssign) and isinstance(sub.target, ast.Name) \
                            and sub.target.id == "urlpatterns":
                        entries.extend(_flatten(sub.value, self._lists(tree)))
        return entries

    def _walk_module(self, dotted: str, prefix: tuple):
        path, tree = self._module(dotted)
        if tree is None:
            self._mark_opaque(prefix)
            return
        routers = self._routers(tree)
        lists = self._lists(tree)
        self._walk_entries(self._urlpatterns(tree), prefix, dotted, routers, lists)

    def _walk_entries(self, entries, prefix, module, routers, lists):
        constants = self._string_constants(module)
        for entry in entries:
            if isinstance(entry, RouterRef):
                self._expand_router(routers.get(entry.variable, []), prefix, module)
                continue
            if not (isinstance(entry, ast.Call) and _call_name(entry) in ("path", "re_path")):
                continue
            if not entry.args:
                continue
            raw = _const_str(entry.args[0])
            if raw is None:
                raw = _resolve_name(entry.args[0], constants)
            if raw is None:
                # Litteral non resolvable : on ignore ce SEUL sous-arbre, sans
                # jamais poser de joker a la racine (il rendrait toute la
                # garde muette). Compte affiche par --stats.
                self.unknown_routes += 1
                if prefix:
                    self._mark_opaque(prefix + (ANY,))
                continue
            is_regex = _call_name(entry) == "re_path"
            segments, opaque = normalise_route(raw, regex=is_regex)
            here = prefix + tuple(segments)
            if opaque:
                self._mark_opaque(here)
                continue
            view = entry.args[1] if len(entry.args) > 1 else None
            if isinstance(view, ast.Call) and _call_name(view) == "include":
                self._walk_include(view, here, module, routers, lists)
            else:
                self.routes.add(here)
                self.views[here] = (module, _view_reference(view))
                self.stats["vues"] += 1

    def _walk_include(self, call, prefix, module, routers, lists):
        if not call.args:
            self._mark_opaque(prefix)
            return
        target = call.args[0]
        if isinstance(target, ast.Tuple) and target.elts:
            target = target.elts[0]
        if isinstance(target, ast.Constant) and isinstance(target.value, str):
            dotted = target.value
            key = f"{dotted}|{prefix}"
            if key in self._seen_includes:
                return
            self._seen_includes.add(key)
            self._walk_module(dotted, prefix)
            return
        if isinstance(target, ast.Attribute) and target.attr == "urls" \
                and isinstance(target.value, ast.Name):
            self._expand_router(routers.get(target.value.id, []), prefix, module)
            return
        if isinstance(target, ast.Name) and target.id in lists:
            self._walk_entries(lists[target.id], prefix, module, routers, lists)
            return
        if isinstance(target, (ast.List, ast.Tuple)):
            self._walk_entries(_flatten(target, lists), prefix, module, routers, lists)
            return
        self._mark_opaque(prefix)

    def _expand_router(self, registered, prefix, module):
        for raw, viewset in registered:
            if raw is None:
                self._mark_opaque(prefix)
                continue
            segments, opaque = normalise_route(raw)
            base = prefix + tuple(segments)
            if opaque:
                self._mark_opaque(base)
                continue
            self.stats["registres"] += 1
            self.routes.add(base)
            self.routes.add(base + (ANY,))
            if viewset is None:
                self._mark_opaque(base)
                continue
            actions, complete = self.actions_of(viewset, module)
            for detail, url_path, owner, method in actions:
                sub, sub_opaque = normalise_route(url_path)
                target = base + ((ANY,) if detail else ()) + tuple(sub)
                if sub_opaque:
                    self._mark_opaque(target)
                else:
                    self.routes.add(target)
                    self.views[target] = (owner, ("action", viewset, method))
            if not complete:
                self._mark_opaque(base)

    def _mark_opaque(self, prefix):
        if not prefix:
            # Un prefixe vide rendrait TOUT opaque : la garde serait muette.
            self.unknown_routes += 1
            return
        self.opaque.add(tuple(prefix))
        self.stats["opaques"] += 1


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _view_reference(view):
    """('fonction', nom) / ('classe', nom) / None — QUI sert cette route."""
    if isinstance(view, ast.Name):
        return ("fonction", view.id)
    if isinstance(view, ast.Call) and isinstance(view.func, ast.Attribute) \
            and view.func.attr == "as_view":
        target = view.func.value
        if isinstance(target, ast.Name):
            return ("classe", target.id)
        if isinstance(target, ast.Attribute):
            return ("classe", target.attr)
    return None


def _resolve_name(node, constants: dict) -> str | None:
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    return None


def _const_str(node) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


class RouterRef:
    """Marqueur : `router.urls` epingle DANS une liste `urlpatterns`."""

    def __init__(self, variable):
        self.variable = variable


def _flatten(node, lists):
    """Developpe `router.urls + [...] + AUTRE_LISTE` en une liste d'elements."""
    if isinstance(node, (ast.List, ast.Tuple)):
        return list(node.elts)
    if isinstance(node, ast.Name):
        return list(lists.get(node.id, []))
    if isinstance(node, ast.Attribute) and node.attr == "urls" \
            and isinstance(node.value, ast.Name):
        # `urlpatterns = router.urls + [...]` — sans ce cas, TOUTES les
        # ressources du routeur disparaissaient de l'inventaire (et chaque
        # appel du frontend vers elles devenait un faux positif).
        return [RouterRef(node.value.id)]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _flatten(node.left, lists) + _flatten(node.right, lists)
    return []


_DJANGO_CONVERTER = re.compile(r"<[^>]+>")
_REGEX_GROUP = re.compile(r"\(\?P<[^>]+>[^)]*\)")


def normalise_route(raw: str, regex: bool = False):
    """('seg', '<>') + drapeau opaque (route non representable segment a segment)."""
    text = raw
    opaque = False
    if regex:
        text = text.lstrip("^").rstrip("$")
        text = _REGEX_GROUP.sub(ANY, text)
        if re.search(r"[\[\]()*+?{}\\|]", text):
            opaque = True
    if "path:" in text:                 # <path:x> avale plusieurs segments
        opaque = True
    # ORDRE IMPORTANT : le groupe nomme d'abord. `<[^>]+>` mange sinon le
    # `<downtime_id>` de `(?P<downtime_id>[^/.]+)` et laisse un segment
    # illisible — toutes les @action a parametre imbrique (sav, installations)
    # devenaient alors de faux positifs.
    text = _REGEX_GROUP.sub(ANY, text)
    text = _DJANGO_CONVERTER.sub(ANY, text)
    segments = []
    for segment in text.split("/"):
        if not segment:
            continue
        if segment != ANY and re.search(r"[\[\]()*+?^$\\|]", segment):
            opaque = True     # segment encore regex : on ne sait pas le lire
        segments.append(segment)
    return segments, opaque


# ===========================================================================
# 2. Inventaire des routes FastAPI
# ===========================================================================

def fastapi_routes(root: Path = FASTAPI_ROOT) -> set[tuple]:
    main = root / "app" / "main.py"
    tree = _parse(main)
    routes: set[tuple] = set()
    if tree is None:
        return routes
    mount = tuple(FASTAPI_MOUNT.split("/"))

    def add(prefix: str, path_: str):
        segments = [s for s in f"{prefix}/{path_}".split("/") if s]
        segments = [ANY if s.startswith("{") else s for s in segments]
        routes.add(mount + tuple(segments))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for deco in node.decorator_list:
                if isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute) \
                        and isinstance(deco.func.value, ast.Name) and deco.func.value.id == "app" \
                        and deco.args:
                    literal = _const_str(deco.args[0])
                    if literal:
                        add("", literal)
        if isinstance(node, ast.Call) and _call_name(node) == "include_router" and node.args:
            module_name = None
            target = node.args[0]
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                module_name = target.value.id
            prefix = ""
            for kw in node.keywords:
                if kw.arg == "prefix":
                    prefix = _const_str(kw.value) or ""
            if not module_name:
                continue
            endpoint = root / "app" / "api" / "endpoints" / f"{module_name}.py"
            sub = _parse(endpoint)
            if sub is None:
                continue
            for item in ast.walk(sub):
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for deco in item.decorator_list:
                    if isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute) \
                            and isinstance(deco.func.value, ast.Name) \
                            and deco.func.value.id == "router" and deco.args:
                        literal = _const_str(deco.args[0])
                        if literal is not None:
                            add(prefix, literal)
    return routes


# ===========================================================================
# 3. Extraction des appels du frontend
# ===========================================================================

_ID_START = re.compile(r"[A-Za-z_$]")
_REGEX_PRECEDER = re.compile(r"[(,=:\[!&|?{};+\-*%~^<>]\s*$")
_REGEX_KEYWORD = re.compile(r"\b(return|typeof|instanceof|in|of|new|delete|void|case|do|else|yield|await)\s*$")


def scan_js(src: str):
    """(code sans commentaires, jetons de chaine, code masque).

    Le code garde la MEME longueur (commentaires remplaces par des espaces) :
    les decalages restent valables pour retrouver le numero de ligne. Les
    jetons sont (debut, fin, quote, contenu brut). Le code masque remplace le
    contenu des chaines par des espaces (comptage d'accolades sur).
    """
    out = list(src)
    masked = list(src)
    tokens = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        two = src[i:i + 2]
        if two == "//":
            j = src.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = masked[k] = " "
            i = j
            continue
        if two == "/*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if src[k] != "\n":
                    out[k] = masked[k] = " "
            i = j
            continue
        if c in "'\"`":
            start = i
            i += 1
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == c:
                    break
                i += 1
            end = min(i + 1, n)
            tokens.append((start, end, c, src[start + 1:end - 1]))
            for k in range(start + 1, end - 1):
                if src[k] != "\n":
                    masked[k] = " "
            i = end
            continue
        if c == "/":
            before = src[max(0, i - 40):i]
            if _REGEX_PRECEDER.search(before) or _REGEX_KEYWORD.search(before) or not before.strip():
                j = i + 1
                in_class = False
                while j < n and src[j] != "\n":
                    if src[j] == "\\":
                        j += 2
                        continue
                    if src[j] == "[":
                        in_class = True
                    elif src[j] == "]":
                        in_class = False
                    elif src[j] == "/" and not in_class:
                        break
                    j += 1
                if j < n and src[j] == "/":
                    for k in range(i + 1, j):
                        masked[k] = " "
                    i = j + 1
                    continue
        i += 1
    return "".join(out), tokens, "".join(masked)


_TEMPLATE_HOLE = re.compile(r"\$\{[^{}]*\}")
# `${flag ? '?cascade=1' : ''}` — un suffixe OPTIONNEL ou une chaine de
# requete, jamais un segment de chemin. Sans ce cas, `/x/desactiver/${...}`
# devenait `/x/desactiver/<>` : un faux positif sur du code correct.
_TERNARY_SUFFIX = re.compile(
    r"^[^?]+\?\s*(?P<a>'[^']*'|\"[^\"]*\")\s*:\s*(?P<b>'[^']*'|\"[^\"]*\")$")


def _est_suffixe_optionnel(valeur: str) -> bool:
    """Vrai si cette branche ne peut JAMAIS etre un segment de chemin."""
    return valeur == "" or valeur.startswith("?") or valeur.startswith("#")


def ternaire_hisse(expression: str) -> str | None:
    """`cond ? '?mode=overwrite' : ''` -> `''`, sinon None (PACT5).

    Meme raisonnement que `_TERNARY_SUFFIX` dans `resolve_template`, mais pour
    un ternaire HISSE hors du gabarit, dans une variable :

        const mode = overwrite ? '?mode=overwrite' : ''
        api.post(`/parametres/config-import/${mode}`, bundle)

    Sans ce mecanisme, `${mode}` devient un trou, donc un segment joker, et la
    garde accuse `/parametres/config-import/<>` alors que la route reelle est
    `/parametres/config-import/` : un faux positif sur du code CORRECT. C'est
    le SEUL faux positif qu'a produit l'elargissement du perimetre a tout
    `frontend/src` (PACT5), et il est resolu par un mecanisme, jamais par une
    ligne d'exception.

    Regle deliberement STRICTE : on ne replie le ternaire que si AUCUNE de ses
    deux branches ne peut etre un segment de chemin (vide, `?requete`,
    `#ancre`). Un ternaire mixte (`x ? 'archive' : ''`) decrit un segment
    reellement optionnel : le replier masquerait un vrai appel, donc il reste
    non resolu — comportement identique a avant PACT5.
    """
    match = _TERNARY_SUFFIX.match(expression.strip())
    if not match:
        return None
    branches = [match.group("a")[1:-1], match.group("b")[1:-1]]
    return "" if all(_est_suffixe_optionnel(b) for b in branches) else None


def resolve_template(raw: str, quote: str, consts: dict) -> str | None:
    """Litteral -> chemin, `${X}` resolu par constante sinon marque HOLE."""
    if quote != "`":
        return raw

    def _sub(match):
        inner = match.group(0)[2:-1].strip()
        value = consts.get(inner)
        if isinstance(value, str):
            return value
        ternary = _TERNARY_SUFFIX.match(inner)
        if ternary:
            branches = [ternary.group("a")[1:-1], ternary.group("b")[1:-1]]
            if any(b == "" or b.startswith("?") for b in branches):
                return ""
        return HOLE
    previous = None
    text = raw
    while previous != text:
        previous = text
        text = _TEMPLATE_HOLE.sub(_sub, text)
    return text


class FrontendCalls:
    """Extrait (fichier, ligne, chemin) de chaque appel HTTP litteral."""

    HTTP = ("get", "post", "put", "patch", "delete", "head", "options", "request")
    CLIENT_HINT = re.compile(r"(?i)(api|client|instance|axios|http)")

    def __init__(self, files):
        self.files = list(files)
        self.calls = []          # (path relatif, ligne, chemin brut, prefixe)
        self.unresolved = 0

    def collect(self):
        for path in self.files:
            try:
                src = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            self._collect_file(path, src)
        return self.calls

    def _collect_file(self, path: Path, src: str):
        code, tokens, masked = scan_js(src)
        token_at = {start: (end, quote, raw) for start, end, quote, raw in tokens}
        default_mount = FASTAPI_MOUNT if "/api/fastapi" in code else "api/django"
        consts = self._constants(code, token_at, tokens, masked)
        rel = path.relative_to(ROOT).as_posix()

        def record(offset, value):
            if not value or not value.startswith("/"):
                return
            self.calls.append((rel, code.count("\n", 0, offset) + 1, value, default_mount))

        # a) appels directs client.get('/x/y/')
        for match in re.finditer(r"([A-Za-z_$][\w$.]*)\.(%s)\s*\(" % "|".join(self.HTTP), masked):
            client = match.group(1)
            if not self.CLIENT_HINT.search(client):
                continue
            arg_start, arg_end = _first_argument(masked, match.end() - 1)
            if arg_start is None:
                continue
            value = self._resolve_expression(code, token_at, consts, arg_start, arg_end)
            if value is None:
                self.unresolved += 1
                continue
            record(arg_start, value)

        # b) fabriques de ressources -> crud('slug')
        for name, (prefix, suffix) in self._factories(code, token_at, tokens, consts).items():
            for match in re.finditer(r"(?<![\w$.])%s\s*\(\s*" % re.escape(name), masked):
                start = match.end()
                if start not in token_at:
                    continue
                end, quote, raw = token_at[start]
                if quote == "`":
                    continue
                record(start, f"{prefix}{raw}{suffix}")

    def _constants(self, code, token_at, tokens, masked=None):
        consts = {}
        for match in re.finditer(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*", code):
            start = match.end()
            if start not in token_at:
                # PACT5 — pas une chaine : peut-etre un ternaire de suffixe
                # hisse (`const mode = x ? '?mode=overwrite' : ''`).
                value = ternaire_hisse(code[start:_fin_instruction(masked or code, start)])
                if value is not None:
                    consts[match.group(1)] = value
                continue
            _, quote, raw = token_at[start]
            value = resolve_template(raw, quote, consts)
            if value is not None:
                consts[match.group(1)] = value
        return consts

    def _factories(self, code, token_at, tokens, consts):
        """nom -> (prefixe, suffixe) d'une fabrique de ressource REST."""
        factories = {}
        # makeResourceFactory(client, '/base')
        for match in re.finditer(
                r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*makeResourceFactory\s*\(", code):
            after = code.find(",", match.end())
            if after < 0:
                continue
            start = _next_token_start(code, after + 1)
            if start is None or start not in token_at:
                continue
            _, quote, raw = token_at[start]
            base = resolve_template(raw, quote, consts)
            if base and base.startswith("/"):
                factories[match.group(1)] = (base.rstrip("/") + "/", "/")
        # function crud(slug) { const base = `/qhse/${slug}/` ... }
        for match in re.finditer(
                r"(?:function\s+([A-Za-z_$][\w$]*)\s*\(\s*([A-Za-z_$][\w$]*)\s*\)"
                r"|\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*\(?\s*([A-Za-z_$][\w$]*)\s*\)?\s*=>)",
                code):
            name = match.group(1) or match.group(3)
            param = match.group(2) or match.group(4)
            if not name or name in factories:
                continue
            body_end = min(len(code), match.end() + 4000)
            needle = "${%s}" % param
            for start, end, quote, raw in tokens:
                if start < match.end() or start > body_end or quote != "`":
                    continue
                if needle not in raw:
                    continue
                head, _, tail = raw.partition(needle)
                head = resolve_template(head, "`", consts) or ""
                tail = resolve_template(tail, "`", consts) or ""
                if head.startswith("/") and HOLE not in head:
                    factories[name] = (head, tail)
                break
        return factories

    def _resolve_expression(self, code, token_at, consts, start, end):
        if start in token_at:
            token_end, quote, raw = token_at[start]
            if token_end >= end:
                return resolve_template(raw, quote, consts)
            return None
        name = code[start:end].strip()
        if re.fullmatch(r"[A-Za-z_$][\w$]*", name):
            return consts.get(name)
        return None


def _fin_instruction(masked, start):
    """Fin de l'instruction commencant a `start` (`;` ou fin de ligne).

    Le balayage se fait sur le code MASQUE (contenu des chaines efface) : un
    `;` ou un saut de ligne A L'INTERIEUR d'une chaine ne doit pas couper
    l'expression.
    """
    end = len(masked)
    for index in range(start, end):
        if masked[index] in ";\n":
            return index
    return end


def _next_token_start(code, index):
    while index < len(code) and code[index].isspace():
        index += 1
    return index if index < len(code) else None


def _first_argument(masked, open_paren):
    """(debut, fin) du premier argument d'un appel, ou (None, None)."""
    depth = 0
    i = open_paren
    n = len(masked)
    start = None
    while i < n:
        c = masked[i]
        if c in "([{":
            depth += 1
            if depth == 1:
                start = _next_token_start(masked, i + 1)
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return (start, i) if start is not None else (None, None)
        elif c == "," and depth == 1:
            return (start, i) if start is not None else (None, None)
        i += 1
    return (None, None)


# ===========================================================================
# 4. Rapprochement
# ===========================================================================

_SEGMENT_OK = re.compile(r"^[\w.\-~%:@" + re.escape(HOLE) + r"]+$")


def normalise_call(raw: str, default_mount: str):
    """Chemin frontend -> segments normalises, ou None si non verifiable."""
    path = raw.split("?", 1)[0].split("#", 1)[0]
    if not path.startswith("/"):
        return None
    if not path.startswith("/api/"):
        path = f"/{default_mount}{path}"
    segments = []
    for raw_segment in path.split("/"):
        if not raw_segment:
            continue
        if HOLE in raw_segment:
            segments.append(ANY)
            continue
        if not _SEGMENT_OK.match(raw_segment):
            return None
        segments.append(raw_segment)
    return tuple(segments) if segments else None


def compatible(call: tuple, route: tuple) -> bool:
    if len(call) != len(route):
        return False
    return all(a == b or a == ANY or b == ANY for a, b in zip(call, route))


class RouteTrie:
    """Arbre de segments. `<>` est un JOKER des DEUX cotes (cf. en-tete)."""

    TERMINAL = "\x01"

    def __init__(self):
        self.root = {}

    def add(self, segments):
        node = self.root
        for segment in segments:
            node = node.setdefault(segment, {})
        node[self.TERMINAL] = True

    def _walk(self, node, segments, stop_on_terminal):
        if stop_on_terminal and node.get(self.TERMINAL):
            return True
        if not segments:
            return bool(node.get(self.TERMINAL)) and not stop_on_terminal
        head, rest = segments[0], segments[1:]
        children = node.keys() if head == ANY else (head, ANY)
        for key in children:
            child = node.get(key)
            if key == self.TERMINAL or child is None:
                continue
            if self._walk(child, rest, stop_on_terminal):
                return True
        return False

    def matches(self, call) -> bool:
        return self._walk(self.root, tuple(call), stop_on_terminal=False)

    def covers_prefix_of(self, call) -> bool:
        """Vrai si un prefixe de `call` atteint une entree de l'arbre."""
        return self._walk(self.root, tuple(call), stop_on_terminal=True)


# PACT5 — perimetre : TOUT le source frontend, pas seulement les clients API.
FRONT_EXTENSIONS = ("*.js", "*.jsx", "*.mjs")
# Un test ne joint jamais le serveur : sa charge utile est mockee, donc son
# chemin n'est pas un contrat. La forme des mocks est l'affaire de
# check_api_shapes.py. Les inclure n'ajouterait que du bruit (mesure : 3
# appels, 0 constat).
FRONT_SKIP = (".test.", ".spec.")


def frontend_files():
    seen = {}
    for pattern in FRONT_EXTENSIONS:
        for path in sorted(FRONT_SRC.rglob(pattern)):
            if any(marker in path.name for marker in FRONT_SKIP):
                continue
            if "node_modules" in path.parts:
                continue
            seen.setdefault(path, True)
    return list(seen)


def analyse():
    backend = BackendRoutes()
    backend.build()
    routes = set(backend.routes) | fastapi_routes()
    known = RouteTrie()
    for route in routes:
        known.add(route)
    opaque = RouteTrie()
    for prefix in backend.opaque:
        opaque.add(prefix)

    extractor = FrontendCalls(frontend_files())
    extractor.collect()

    findings, checked, skipped = [], 0, 0
    seen = set()
    for rel, line, raw, mount in extractor.calls:
        call = normalise_call(raw, mount)
        if call is None:
            skipped += 1
            continue
        checked += 1
        if known.matches(call):
            continue
        if opaque.covers_prefix_of(call):
            skipped += 1
            continue
        key = (rel, line, raw)
        if key in seen:
            continue
        seen.add(key)
        findings.append((rel, line, raw, "/" + "/".join(call)))
    stats = {
        "routes": len(routes),
        "opaques": len(backend.opaque),
        "inconnues": backend.unknown_routes,
        "appels": checked,
        "ignores": skipped + extractor.unresolved,
        "registres": backend.stats["registres"],
        "vues": backend.stats["vues"],
    }
    return findings, stats


# ===========================================================================
# 5. Base de reference + CLI
# ===========================================================================

BASELINE_HEADER = """\
# Base de reference de check_api_contract.py — DETTE HISTORIQUE, RIEN D'AUTRE.
#
# Chaque ligne est un chemin normalise appele par le frontend et qui ne
# correspond a AUCUNE route backend enregistree : un ecran deja mort. La garde
# n'echoue que sur une occurrence ABSENTE de cette liste.
#
# REGLE ABSOLUE : CETTE LISTE NE PEUT QUE RETRECIR.
#   - corriger un appel puis `python scripts/check_api_contract.py
#     --write-baseline` retire sa ligne ;
#   - `--write-baseline` REFUSE d'ajouter une ligne. Ajouter une dette exige
#     `--autoriser-croissance`, drapeau reserve au fondateur, visible en revue.
#
# La signature est le CHEMIN, jamais `fichier:ligne` : un deplacement de ligne
# ne doit pas invalider la base (lecon du depot).
"""


def load_baseline(path: Path = BASELINE_PATH) -> set:
    if not path.is_file():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }


def write_baseline(entries: set, path: Path = BASELINE_PATH):
    path.write_text(BASELINE_HEADER + "\n".join(sorted(entries)) + "\n",
                    encoding="utf-8", newline="\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Garde front<->back : tout chemin appele existe-t-il au backend ?")
    parser.add_argument("--stats", action="store_true",
                        help="affiche l'inventaire chiffre resolu")
    parser.add_argument("--write-baseline", action="store_true",
                        help="retire de la base les dettes corrigees")
    parser.add_argument("--autoriser-croissance", action="store_true",
                        help="FONDATEUR UNIQUEMENT : autorise l'ajout de dettes")
    args = parser.parse_args(argv)

    findings, stats = analyse()
    if args.stats:
        print(f"Routes backend resolues : {stats['routes']} "
              f"({stats['registres']} ressources de routeur, {stats['vues']} vues) ; "
              f"{stats['opaques']} sous-arbre(s) opaque(s).")
        print(f"Appels frontend verifies : {stats['appels']} "
              f"({stats['ignores']} non verifiables, ignores).")

    signatures = {path for _, _, _, path in findings}
    baseline = load_baseline()

    if args.write_baseline:
        added = signatures - baseline
        bootstrap = not BASELINE_PATH.is_file()   # premiere ecriture : le gel
        if added and not (args.autoriser_croissance or bootstrap):
            print("REFUS : --write-baseline ne peut que RETRECIR la base.")
            print(f"{len(added)} nouvelle(s) dette(s) voudraient y entrer :")
            for signature in sorted(added)[:20]:
                print(f"  + {signature}")
            print("Corrigez l'appel (ou la route), ou assumez la dette avec "
                  "--autoriser-croissance.")
            return 1
        write_baseline(signatures)
        print(f"Base de reference reecrite : {BASELINE_PATH.relative_to(ROOT)} "
              f"({len(signatures)} entree(s), {len(baseline - signatures)} retiree(s)).")
        return 0

    new = [f for f in findings if f[3] not in baseline]
    fixed = baseline - signatures
    if new:
        print(f"\nECHEC : {len(new)} appel(s) frontend vers une route backend "
              f"INEXISTANTE (hors base de reference).\n")
        for rel, line, raw, path in sorted(new):
            print(f"  {rel}:{line}")
            print(f"      appelle  {raw.replace(HOLE, '{}')}")
            print(f"      resolu   {path}  ->  AUCUNE route backend ne correspond")
        print("\nCORRIGER, dans cet ordre de preference :")
        print("  1. le nom cote frontend, si le backend sert deja la ressource "
              "sous un autre nom (piege classique : `grand-livre` cote client "
              "contre `grand_livre` cote serveur, le `url_path` par defaut "
              "d'une @action etant le NOM DE LA METHODE, souligne compris) ;")
        print("  2. la route cote backend, si la fonctionnalite doit exister ;")
        print("  3. la suppression de l'appel, s'il est mort.")
        print("Cette garde existe a cause de l'incident du 03/08/2026 "
              "(ecran AO Bibliotheque en 404 en production) : voir l'en-tete "
              "de scripts/check_api_contract.py. Ne la desactivez pas.")
        return 1

    print(f"OK : {stats['appels']} appel(s) frontend verifies, tous resolus vers "
          f"une route backend reelle ({len(baseline)} dette(s) historique(s) "
          f"en base de reference, dont {len(fixed)} desormais corrigee(s)).")
    if fixed:
        print("Ces dettes corrigees peuvent quitter la base : "
              "python scripts/check_api_contract.py --write-baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
