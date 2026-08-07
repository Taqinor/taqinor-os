#!/usr/bin/env python3
"""Garde permanente : un test frontend ne peut plus INVENTER la forme d'une reponse.

POURQUOI CETTE GARDE EXISTE — INCIDENT DU 03/08/2026
----------------------------------------------------
L'ecran « Appels d'offres > Tableau de bord » a plante en production alors que
sa route existait et que ses tests etaient VERTS des deux cotes.

  - ``apps/ao/selectors.py`` renvoie ``echeances_dues`` = ``len(...)``, un
    ENTIER ; l'ecran faisait ``.map()`` dessus -> TypeError.
  - il renvoie ``marches_en_execution`` = un OBJET ; l'ecran l'affichait comme
    enfant React -> « objects are not valid as a React child ».
  - l'ecran lisait 4 champs qui n'existent nulle part (``ao_en_cours``,
    ``taux_reussite``, ``cautions_immobilisees``, ``capacite_vs_engagement`` ;
    le serveur sert ``en_cours``, ``reussite``, ``cautions``, ``capacite``).
    6 lectures sur 6 etaient fausses.

LA CAUSE RACINE EST LE MOCK, PAS L'ECRAN. ``DashboardPage.test.jsx`` declare a
la main ``PAYLOAD = { ao_en_cours: 7, ..., echeances_dues: [ ... ] }`` —
l'INVERSE EXACT de ce que le backend renvoie — et le test passe au vert : il
verifie l'ecran contre l'hypothese de l'ecran. En face,
``apps/ao/tests/test_kpis_ao.py`` affirme ``echeances_dues == 1``. Les deux
suites sont vertes et se contredisent. Un mock ecrit a la main est une
DEUXIEME source de verite : c'est elle qu'il faut supprimer.

Cette garde compare le mock au contrat REEL derive du code serveur. Un test ne
peut plus se mentir a lui-meme.

POURQUOI PAS LE SCHEMA OPENAPI (mesure, pas opinion)
-----------------------------------------------------
La voie « comparer le front au schema OpenAPI » a ete essayee et INVALIDEE :

  1. ``docs/openapi-schema.yml`` ne contient AUCUNE forme de reponse — c'est un
     inventaire d'operations ; le mot ``properties:`` y apparait 0 fois.
  2. Le schema COMPLET regenere ne sauve rien la ou ca compte :
     ``GET /ao/tableau-marches/`` y est documente ``type: object`` SANS AUCUNE
     propriete, parce que la vue declare ``responses={200:
     OpenApiResponse(response=dict)}`` (apps/ao/kpis.py). Un controle fonde sur
     l'OpenAPI serait passe AU VERT sur l'ecran qui a plante.
  3. Pire, il MENT sur d'autres agregats : ``/flotte/vehicules/tableau-bord/``
     est documente avec le ``VehiculeSerializer`` alors que la vue renvoie
     ``{vehicules, engins, echeances, ...}``. Un controle naif y produirait des
     ROUGES sur du code CORRECT.
  4. La generation emet 406 avertissements « unable to guess serializer » — soit
     exactement les vues-fonctions et les @action agregees, c'est-a-dire la
     classe de code qui plante.

Le contrat est donc derive du CODE SERVEUR (le dictionnaire reellement
renvoye), pas du schema. Rendre l'OpenAPI utilisable reste souhaitable
(interdire ``response=dict`` sur un agregat) mais c'est un chantier de
centaines de vues, pas un prealable a fermer le robinet aujourd'hui.

CE QU'ELLE FAIT (analyse statique pure, sans base de donnees, sans dependance)
-----------------------------------------------------------------------------
1. Reprend le resolveur de ``check_api_contract.py`` pour savoir QUELLE vue
   sert quel chemin, puis lit le dictionnaire renvoye par cette vue (litteral,
   ou fonction de ``selectors.py``/``services.py`` resolue de proche en
   proche). Resultat : cle -> nature (objet / liste / nombre / texte /
   booleen / inconnu).
2. Relie chaque fonction d'un client ``frontend/src/api/*.js`` a son chemin.
3. Lit les mocks des tests frontend (``X.maFonction.mockResolvedValue({data:
   ...})``) et ECHOUE si le mock nomme une cle que le serveur ne renvoie pas,
   ou lui donne une nature incompatible.
3 bis. PACT9 — ECHOUE AUSSI sur un ECRAN qui lit un champ fantome, MEME SANS
   TEST. Controler les mocks laisse invisible l'ecran qui n'en a pas : les
   4 tuiles muettes de ``features/rh/Recrutement.jsx`` et les 4 lignes vides de
   ``features/flotte/VehiculeDetail.jsx`` n'affichent AUCUNE erreur, juste des
   tirets pour toujours. La condition de fiabilite est ecrite et mesuree :
   **apparier par ENDPOINT, jamais par nom de champ** (le second tombe sous
   10 % de precision des qu'il y a homonymie). Voir la section 3 bis du code.
4. ``--write`` fige le contrat lisible dans ``docs/api-contracts.md`` : le
   dictionnaire d'un agregat devient un fichier VERSIONNE, donc un changement
   de forme apparait dans le diff de la PR au lieu de casser un ecran.

PRINCIPE ANTI-FAUX-POSITIF : un doute ne rougit JAMAIS. Une vue dont la forme
n'est pas certaine statiquement est absente du contrat, donc ses mocks ne sont
pas controles. Un appariement par NOM DE CHAMP global est PROSCRIT (mesure :
moins de 10 % de precision) ; ici tout passe par le chemin.

BASE DE REFERENCE — ELLE NE PEUT QUE RETRECIR (memes regles que
scripts/api_contract_allow.txt ; voir scripts/api_shapes_allow.txt).

Usage :
    python scripts/check_api_shapes.py                 # garde CI
    python scripts/check_api_shapes.py --write         # regenere le contrat
    python scripts/check_api_shapes.py --write-baseline
"""
from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

import check_api_contract as contract
from check_api_contract import (HOLE, ROOT, FRONT_SRC, RouteTrie, scan_js,
                                resolve_template, normalise_call)

BASELINE_PATH = ROOT / "scripts" / "api_shapes_allow.txt"
CONTRACT_PATH = ROOT / "docs" / "api-contracts.md"

# Natures comparables entre un dictionnaire Python et un litteral JS.
OBJET, LISTE, NOMBRE, TEXTE, BOOLEEN, INCONNU = (
    "objet", "liste", "nombre", "texte", "booleen", "inconnu")

MAX_DEPTH = 4


# ===========================================================================
# 1. Forme renvoyee par une vue (lecture du code serveur)
# ===========================================================================

class ShapeReader:
    def __init__(self, backend: contract.BackendRoutes):
        self.backend = backend
        self._cache: dict[tuple, dict | None] = {}

    # -- utilitaires de resolution ---------------------------------------
    def _module_tree(self, module: str):
        return self.backend._module(module)[1]

    def _find_function(self, module: str, name: str, depth: int = 0):
        """(module, FunctionDef) en suivant les imports, ou None."""
        if depth > MAX_DEPTH:
            return None
        tree = self._module_tree(module)
        if tree is None:
            return None
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                return (module, node)
        source = self.backend._imports_of(module).get(name)
        if source and not source.startswith(contract.FRAMEWORK_ROOTS):
            return self._find_function(source, name, depth + 1)
        return None

    def _find_method(self, module: str, class_name: str, method: str):
        resolved = self.backend._resolve_class(class_name, module)
        if resolved is None:
            return None
        owner, node = resolved
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method:
                return (owner, item)
        for base in node.bases:
            if isinstance(base, ast.Name):
                found = self._find_method(owner, base.id, method)
                if found:
                    return found
        return None

    # -- lecture d'une expression ----------------------------------------
    def kind_of(self, node, module: str, depth: int) -> str:
        if isinstance(node, ast.Dict):
            return OBJET
        if isinstance(node, (ast.List, ast.ListComp, ast.Tuple)):
            return LISTE
        if isinstance(node, ast.Constant):
            value = node.value
            if isinstance(value, bool):
                return BOOLEEN
            if isinstance(value, str):
                return TEXTE
            if isinstance(value, (int, float)):
                return NOMBRE
            return INCONNU
        if isinstance(node, ast.JoinedStr):
            return TEXTE
        if isinstance(node, ast.Compare) or (
                isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not)):
            return BOOLEEN
        if isinstance(node, ast.Call):
            name = contract._call_name(node)
            if name in ("len", "count", "int", "round", "sum", "float", "Decimal"):
                return NOMBRE
            if name in ("exists", "bool"):
                return BOOLEEN
            if name in ("str", "isoformat", "strftime"):
                return TEXTE
            if name in ("list", "values", "values_list"):
                return LISTE
            if name == "dict":
                return OBJET
            if isinstance(node.func, ast.Name) and depth < MAX_DEPTH:
                shape = self.shape_of_function(module, node.func.id, depth + 1)
                if shape is not None:
                    return OBJET
        if isinstance(node, ast.IfExp) and depth < MAX_DEPTH:
            left = self.kind_of(node.body, module, depth + 1)
            right = self.kind_of(node.orelse, module, depth + 1)
            return left if left == right else INCONNU
        if isinstance(node, ast.BoolOp) and depth < MAX_DEPTH:
            kinds = {self.kind_of(v, module, depth + 1) for v in node.values}
            kinds.discard(INCONNU)
            return kinds.pop() if len(kinds) == 1 else INCONNU
        if isinstance(node, ast.BinOp):
            return NOMBRE if isinstance(node.op, (ast.Sub, ast.Mult, ast.Div)) else INCONNU
        return INCONNU

    def dict_shape(self, node: ast.Dict, module: str, depth: int):
        shape = {}
        for key, value in zip(node.keys, node.values):
            if key is None:                      # `**autre` : forme incertaine
                return None
            literal = contract._const_str(key)
            if literal is None:
                return None
            shape[literal] = self.kind_of(value, module, depth)
        return shape

    # -- lecture d'une fonction / methode ---------------------------------
    def shape_of_function(self, module: str, name: str, depth: int = 0):
        key = ("f", module, name)
        if key in self._cache:
            return self._cache[key]
        self._cache[key] = None                  # anti-recursion
        found = self._find_function(module, name)
        result = self._shape_of_node(found, depth) if found else None
        self._cache[key] = result
        return result

    def shape_of_route(self, route: tuple, verb: str):
        """Forme renvoyee pour CE chemin ET CE verbe HTTP.

        Le verbe n'est pas un detail : `EngagementAudienceView` renvoie
        `{presets}` en GET et le resultat d'une creation en POST. Confondre les
        deux produisait de vrais faux positifs sur du code correct.
        """
        key = (route, verb)
        if key in self._cache:
            return self._cache[key]
        self._cache[key] = None
        view = self.backend.views.get(route)
        result = None
        if view:
            module, reference = view
            if reference:
                target = reference[0]
                if target == "fonction":
                    found = self._find_function(module, reference[1])
                    result = self._shape_of_node(found, 0) if found else None
                elif target == "classe":
                    found = self._find_method(module, reference[1], verb)
                    result = self._shape_of_node(found, 0) if found else None
                elif target == "action":
                    found = self._find_method(module, reference[1], reference[2])
                    result = self._shape_of_node(found, 0) if found else None
        self._cache[key] = result
        return result

    def _shape_of_node(self, found, depth: int):
        """Union des dictionnaires renvoyes par TOUS les `return` d'une vue.

        L'union est le sens SUR : une cle en trop rend le contrat plus
        permissif (aucun faux rouge), une cle manquante en produirait.
        Si UN SEUL `return` n'est pas lisible, la forme entiere est declaree
        incertaine et l'endpoint sort du contrat.
        """
        module, node = found
        assignments = _local_dicts(node)
        merged: dict[str, str] = {}
        seen = False
        for statement in ast.walk(node):
            if not isinstance(statement, ast.Return) or statement.value is None:
                continue
            expression = statement.value
            if isinstance(expression, ast.Call) and contract._call_name(expression) == "Response":
                if not expression.args:
                    continue                       # Response(status=204)
                expression = expression.args[0]
            shape = self._shape_of_expression(expression, module, assignments, depth)
            if shape is None:
                return None
            seen = True
            for field, kind in shape.items():
                if field in merged and merged[field] != kind:
                    merged[field] = INCONNU
                else:
                    merged.setdefault(field, kind)
        return merged if seen and merged else None

    def _shape_of_expression(self, expression, module, assignments, depth):
        if isinstance(expression, ast.Dict):
            return self.dict_shape(expression, module, depth)
        if isinstance(expression, ast.Name) and expression.id in assignments:
            return self.dict_shape(assignments[expression.id], module, depth)
        if isinstance(expression, ast.Call) and isinstance(expression.func, ast.Name) \
                and depth < MAX_DEPTH:
            return self.shape_of_function(module, expression.func.id, depth + 1)
        return None


def _local_dicts(node):
    """nom -> Dict litteral, pour `resultat = {...}` puis `return resultat`."""
    out, banned = {}, set()
    for statement in ast.walk(node):
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1 \
                and isinstance(statement.targets[0], ast.Name):
            name = statement.targets[0].id
            if name in out:
                banned.add(name)               # reaffecte : trop incertain
            if isinstance(statement.value, ast.Dict):
                out[name] = statement.value
            else:
                banned.add(name)
    return {k: v for k, v in out.items() if k not in banned}


# ===========================================================================
# 2. Frontend : fonction du client API -> chemin
# ===========================================================================

_PROPERTY = re.compile(r"([A-Za-z_$][\w$]*)\s*:\s*(?:async\s*)?(?:\([^()]*\)|[A-Za-z_$][\w$]*)\s*=>")


class ApiFunctions(contract.FrontendCalls):
    """Comme FrontendCalls, mais retient le NOM de la fonction exportee."""

    def __init__(self, files):
        super().__init__(files)
        # (module frontend, nom de fonction) -> {(verbe, chemin)}
        self.functions: dict[tuple, set] = {}

    def _collect_file(self, path, src):
        code, tokens, masked = scan_js(src)
        token_at = {start: (end, quote, raw) for start, end, quote, raw in tokens}
        default_mount = contract.FASTAPI_MOUNT if "/api/fastapi" in code else "api/django"
        consts = self._constants(code, token_at, tokens)
        module = path.resolve()
        for match in re.finditer(r"([A-Za-z_$][\w$.]*)\.(%s)\s*\(" % "|".join(self.HTTP), masked):
            if not self.CLIENT_HINT.search(match.group(1)):
                continue
            verb = match.group(2)
            start, end = contract._first_argument(masked, match.end() - 1)
            if start is None:
                continue
            value = self._resolve_expression(code, token_at, consts, start, end)
            if not value or not value.startswith("/"):
                continue
            call = normalise_call(value, default_mount)
            if call is None:
                continue
            window = code[max(0, match.start() - 220):match.start()]
            labels = _PROPERTY.findall(window)
            if not labels:
                continue
            self.functions.setdefault((module, labels[-1]), set()).add((verb, call))


# ===========================================================================
# 3. Frontend : mocks des tests
# ===========================================================================

_MOCK = re.compile(r"([A-Za-z_$][\w$]*)\s*\.\s*mock(?:ResolvedValue|ReturnValue)"
                   r"(?:Once)?\s*\(")
_CONST_OBJECT = re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*\{")


def test_files():
    for pattern in ("**/*.test.jsx", "**/*.test.js", "**/*.test.mjs"):
        for path in sorted(FRONT_SRC.glob(pattern)):
            yield path


def _object_body(code: str, brace: int):
    """Texte entre l'accolade ouvrante et sa fermante."""
    depth = 0
    for index in range(brace, len(code)):
        char = code[index]
        if char in "{[(":
            depth += 1
        elif char in "}])":
            depth -= 1
            if depth == 0:
                return code[brace + 1:index]
    return None


def js_object_shape(code: str, masked: str, brace: int):
    """{cle: nature} d'un litteral objet JS (niveau 1 uniquement)."""
    body_masked = _object_body(masked, brace)
    if body_masked is None:
        return None
    body = code[brace + 1:brace + 1 + len(body_masked)]
    shape, depth, start = {}, 0, 0
    pieces = []
    for index, char in enumerate(body_masked):
        if char in "{[(":
            depth += 1
        elif char in "}])":
            depth -= 1
        elif char == "," and depth == 0:
            pieces.append(body[start:index])
            start = index + 1
    pieces.append(body[start:])
    for piece in pieces:
        match = re.match(r"\s*(?:'([^']+)'|\"([^\"]+)\"|([A-Za-z_$][\w$]*))\s*:", piece)
        if not match:
            continue
        name = match.group(1) or match.group(2) or match.group(3)
        value = piece[match.end():].strip()
        shape[name] = _js_kind(value)
    return shape


def _js_kind(value: str) -> str:
    if not value:
        return INCONNU
    head = value[0]
    if head == "{":
        return OBJET
    if head == "[":
        return LISTE
    if head in "'\"`":
        return TEXTE
    if head.isdigit() or (head == "-" and value[1:2].isdigit()):
        return NOMBRE
    if value.startswith(("true", "false")):
        return BOOLEEN
    return INCONNU


_VI_MOCK = re.compile(r"\bvi\s*\.\s*mock\s*\(\s*")


def mocked_modules(code: str, masked: str, token_at: dict, base: Path):
    """Modules frontend que ce test remplace par un mock (chemins resolus).

    Indispensable : `dryRun` existe dans importApi ET dans adsengineApi. Sans
    ce lien, la garde comparait le mock d'un module au contrat de l'autre —
    exactement l'appariement par NOM que l'audit a mesure a moins de 10 % de
    precision. On ne devine pas : on lit le `vi.mock('...')` du test.
    """
    modules = set()
    for match in _VI_MOCK.finditer(masked):
        start = match.end()
        if start not in token_at:
            continue
        _, quote, raw = token_at[start]
        target = resolve_template(raw, quote, {})
        if not target or HOLE in target:
            continue
        if target.startswith("."):
            candidate = (base.parent / target).resolve()
        elif target.startswith("/"):
            continue
        else:
            continue
        for suffix in ("", ".js", ".jsx", ".mjs"):
            probe = Path(str(candidate) + suffix)
            if probe.is_file():
                modules.add(probe)
                break
    return modules


def mocked_payloads(path: Path):
    """[(ligne, modules mockes, nom de fonction, {cle: nature})]."""
    src = path.read_text(encoding="utf-8", errors="replace")
    code, tokens, masked = scan_js(src)
    token_at = {start: (end, quote, raw) for start, end, quote, raw in tokens}
    modules = mocked_modules(code, masked, token_at, path)
    if not modules:
        return []
    objects = {}
    for match in _CONST_OBJECT.finditer(masked):
        shape = js_object_shape(code, masked, match.end() - 1)
        if shape is not None:
            objects[match.group(1)] = shape
    out = []
    for match in _MOCK.finditer(masked):
        name = match.group(1)
        start, end = contract._first_argument(masked, match.end() - 1)
        if start is None:
            continue
        argument = code[start:end].strip()
        shape = None
        if argument.startswith("{"):
            shape = js_object_shape(code, masked, start)
        elif re.fullmatch(r"[A-Za-z_$][\w$]*", argument):
            shape = objects.get(argument)
        if not shape:
            continue
        # La charge utile axios est `{ data: <payload> }` : on descend d'un cran.
        if set(shape) == {"data"} or (len(shape) <= 2 and "data" in shape):
            inner = _payload_of_data(code, masked, start, objects)
            if inner is None:
                continue
            shape = inner
        out.append((code.count("\n", 0, match.start()) + 1, modules, name, shape))
    return out


def _payload_of_data(code, masked, brace, objects):
    body_masked = _object_body(masked, brace)
    if body_masked is None:
        return None
    offset = brace + 1
    match = re.search(r"\bdata\s*:\s*", body_masked)
    if not match:
        return None
    value_at = offset + match.end()
    value = code[value_at:].lstrip()
    shift = len(code[value_at:]) - len(value)
    if value.startswith("{"):
        return js_object_shape(code, masked, value_at + shift)
    identifier = re.match(r"[A-Za-z_$][\w$]*", value)
    return objects.get(identifier.group(0)) if identifier else None


# ===========================================================================
# 3 bis. PACT9 — ECRAN -> ENDPOINT -> CHAMP (sans passer par un test)
# ===========================================================================
#
# POURQUOI. La garde ci-dessus controle les MOCKS : un ecran qui lit un champ
# inexistant et n'a AUCUN test lui reste invisible. C'est le cas de
# `features/rh/Recrutement.jsx` (4 tuiles KPI muettes) et de
# `features/flotte/VehiculeDetail.jsx` (4 lignes vides) : aucune erreur, aucune
# alerte, juste des tirets pour toujours.
#
# LA CONDITION MESUREE POUR QUE CETTE GARDE SOIT FIABLE. Un balayage a trouve
# 70 fichiers d'ecran sur 881 lisant au moins un champ `snake_case` absent du
# backend ; verification manuelle sur 10 tirages : 40 a 50 % de VRAIS defauts
# seulement. Ce taux INTERDIT d'en faire une garde en l'etat, et la raison est
# connue : apparier par NOM DE CHAMP tombe sous 10 % de precision des qu'il y a
# homonymie (`total` sur POS, sur la paie et sur la flotte n'est pas le meme
# champ). D'ou la regle absolue ci-dessous.
#
# ON APPARIE PAR ENDPOINT, JAMAIS PAR NOM DE CHAMP. La chaine complete est
# suivie : ecran -> fonction du client API -> URL -> vue -> dictionnaire. Un
# champ n'est accuse que si l'endpoint EXACT qui alimente la variable lue est
# identifie sans ambiguite ET que son contrat est certain. Tout maillon
# incertain fait ABANDONNER la variable entiere.
#
# DEUX LIENS SEULEMENT, les deux mecaniques et sans ambiguite :
#   A. `const { data } = useResource(() => client.fn(), …, {select: r => r.data})`
#      puis `data.champ` — la forme du tableau de bord AO qui a plante.
#   B. `const r = await client.fn(…)` puis `r.data.champ`.
# Les chaines a plus d'un relais (`Promise.all` -> `setState` -> etat lu
# ailleurs) sont DELIBEREMENT ignorees : les suivre statiquement demanderait de
# deviner, et une garde qui devine crie au loup, puis finit desactivee.

# Hooks du depot qui rendent `{ data, loading, error }`.
_HOOKS_RESSOURCE = ("useResource", "useApiQuery", "useQuery", "useFetch")

_DESTRUCTURATION = re.compile(
    r"\b(?:const|let)\s*\{([^{}]*)\}\s*=\s*(?:await\s+)?(%s)\s*\("
    % "|".join(_HOOKS_RESSOURCE))
# `select: (res) => res.data` — le marqueur qui prouve que la variable porte la
# CHARGE UTILE et non la reponse axios entiere. Sans lui, on n'apparie pas.
_SELECT_DATA = re.compile(
    r"select\s*:\s*\(?\s*([A-Za-z_$][\w$]*)\s*\)?\s*=>\s*\1\s*\??\.\s*data\b")
_AWAIT_APPEL = re.compile(
    r"\b(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*await\s+"
    r"([A-Za-z_$][\w$]*)\s*\.\s*([A-Za-z_$][\w$]*)\s*\(")
_APPEL_CLIENT = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\.\s*([A-Za-z_$][\w$]*)\s*\(")
_IMPORT_CLIENT = re.compile(
    r"\bimport\s+(?P<defaut>[A-Za-z_$][\w$]*)?\s*,?\s*(?:\{(?P<nommes>[^{}]*)\})?\s*"
    r"from\s*['\"](?P<cible>\.[^'\"]*)['\"]")

# Proprietes du langage / de la bibliotheque : jamais des champs de reponse.
_NON_CHAMPS = frozenset({
    "data", "length", "map", "filter", "forEach", "find", "findIndex", "reduce",
    "some", "every", "includes", "indexOf", "slice", "splice", "concat", "join",
    "sort", "reverse", "push", "pop", "shift", "unshift", "flat", "flatMap",
    "at", "keys", "values", "entries", "toString", "valueOf", "hasOwnProperty",
    "constructor", "then", "catch", "finally", "toFixed", "toLocaleString",
    "trim", "split", "replace", "padStart", "padEnd", "startsWith", "endsWith",
    "toLowerCase", "toUpperCase", "charAt", "repeat", "match", "test",
})


def screen_files():
    """Ecrans : tout `frontend/src` SAUF les clients API et les tests.

    Les clients (`src/api/`) sont deja l'affaire de la garde de contrat ; les
    tests, celle des mocks ci-dessus.
    """
    seen = {}
    for pattern in ("*.jsx", "*.js"):
        for path in sorted(FRONT_SRC.rglob(pattern)):
            if ".test." in path.name or ".spec." in path.name:
                continue
            if "node_modules" in path.parts:
                continue
            seen.setdefault(path, True)
    return list(seen)


def _clients_importes(code: str, path: Path, modules_connus: set) -> dict:
    """nom local -> chemin resolu du client API, pour CE fichier d'ecran.

    On ne devine JAMAIS a quel client appartient `xApi.fn()` : on lit l'import.
    C'est ce qui evite l'homonymie mesuree (`dryRun` existe dans `importApi`
    ET dans `adsengineApi`).
    """
    clients = {}
    for match in _IMPORT_CLIENT.finditer(code):
        candidat = (path.parent / match.group("cible")).resolve()
        sonde = None
        for suffixe in ("", ".js", ".jsx", ".mjs"):
            probe = Path(str(candidat) + suffixe)
            if probe.is_file() and probe in modules_connus:
                sonde = probe
                break
        if sonde is None:
            continue
        noms = []
        if match.group("defaut"):
            noms.append(match.group("defaut"))
        for specificateur in (match.group("nommes") or "").split(","):
            specificateur = specificateur.strip()
            if not specificateur:
                continue
            # `xApi as client` : c'est le nom LOCAL qui compte.
            noms.append(specificateur.split(" as ")[-1].strip())
        for nom in noms:
            if re.fullmatch(r"[A-Za-z_$][\w$]*", nom):
                clients[nom] = sonde
    return clients


def _liaisons(code: str, masked: str, clients: dict) -> list:
    """[(variable, prefixe de lecture, module, fonction)] — liens CERTAINS."""
    liaisons = []

    # LIEN A — hook de ressource avec `select: r => r.data`.
    for match in _DESTRUCTURATION.finditer(masked):
        fin = contract._first_argument(masked, match.end() - 1)[1]
        if fin is None:
            continue
        profondeur, borne = 0, match.end() - 1
        for index in range(match.end() - 1, len(masked)):
            if masked[index] in "([{":
                profondeur += 1
            elif masked[index] in ")]}":
                profondeur -= 1
                if profondeur == 0:
                    borne = index
                    break
        appel = code[match.end() - 1:borne + 1]
        if not _SELECT_DATA.search(appel):
            continue        # la variable porte peut-etre la reponse axios entiere
        variable = _variable_de_data(match.group(1))
        if variable is None:
            continue
        cible = _premier_appel_client(appel, clients)
        if cible is None:
            continue
        liaisons.append((variable, variable, cible[0], cible[1]))

    # LIEN B — `const r = await client.fn(…)` puis `r.data.champ`.
    for match in _AWAIT_APPEL.finditer(masked):
        variable, client, fonction = match.groups()
        if client not in clients:
            continue
        liaisons.append((variable, f"{variable}.data", clients[client], fonction))
    return liaisons


def _variable_de_data(destructuration: str):
    """`{ data: tableau, loading }` -> `tableau` ; `{ data }` -> `data`."""
    for morceau in destructuration.split(","):
        morceau = morceau.strip()
        if morceau == "data":
            return "data"
        alias = re.fullmatch(r"data\s*:\s*([A-Za-z_$][\w$]*)", morceau)
        if alias:
            return alias.group(1)
    return None


def _premier_appel_client(appel: str, clients: dict):
    for match in _APPEL_CLIENT.finditer(appel):
        nom, fonction = match.groups()
        if nom in clients:
            return (clients[nom], fonction)
    return None


def _lie_une_seule_fois(masked: str, variable: str) -> bool:
    """La variable n'est-elle liee QU'UNE fois dans ce fichier ?

    Deux liaisons du meme nom (deux `const data = …` dans deux composants d'un
    meme fichier) rendraient l'appariement incertain : on abandonne.
    """
    motif = re.compile(r"\b(?:const|let|var)\b[^=;\n]*\b%s\b[^=;\n]*="
                       % re.escape(variable))
    return len(motif.findall(masked)) == 1


def _jamais_un_parametre(masked: str, variable: str) -> bool:
    """Le nom sert-il AUSSI de parametre quelque part dans ce fichier ?

    LE piege mesure de PACT9, et il aurait suffi a rendre la garde bruyante
    donc morte. `const r = await gedApi.toggleFavoriDocument(…)` lie `r`, mais
    le MEME fichier ecrit ailleurs
    `gedApi.getAcls(…).then((r) => setEntries(r.data?.results ?? …))` : ce `r`
    est un AUTRE endpoint. Sans ce controle, la garde accusait `results` sur
    `toggleFavoriDocument` — cinq faux positifs sur cinq (ged, audit, ia,
    monitoring, ventes), tous sur du code CORRECT.

    Le nom d'une variable ne suffit donc pas a designer une portee : des qu'il
    est aussi un parametre, l'appariement redevient un appariement par NOM, et
    on abandonne. Sous-detecter est le comportement voulu.
    """
    nom = re.escape(variable)
    motifs = (
        # `r => …`
        r"(?<![\w$.])%s\s*=>" % nom,
        # `(r, i) => …` / `({ data }) => …`
        r"\(\s*[^()]*\b%s\b[^()]*\)\s*=>" % nom,
        # `function f(r) {` / `async function f(a, r) {`
        r"\bfunction\b[^(){}]*\(\s*[^()]*\b%s\b[^()]*\)" % nom,
    )
    return not any(re.search(motif, masked) for motif in motifs)


def _acces(prefixe: str) -> str:
    """Fragment d'expression reguliere pour `prefixe.champ` / `prefixe?.champ`."""
    return (r"(?<![\w$.])%s\s*\??\s*\.\s*"
            % re.escape(prefixe).replace(r"\.", r"\s*\??\s*\."))


def _champs_lus(code: str, prefixe: str) -> dict:
    """champ -> premiere ligne de lecture, pour `prefixe.champ` / `prefixe?.champ`."""
    motif = re.compile(_acces(prefixe) + r"([A-Za-z_$][\w$]*)")
    champs = {}
    for match in motif.finditer(code):
        champ = match.group(1)
        if champ in _NON_CHAMPS:
            continue
        champs.setdefault(champ, code.count("\n", 0, match.start()) + 1)
    return champs


# Les deux usages qui ont TUE l'ecran AO le 03/08/2026, et eux seuls : aucun
# autre n'est assez univoque pour accuser sans deviner.
#   * `.map(` sur un champ que le serveur renvoie en NOMBRE
#     -> « x.map is not a function » ;
#   * `{champ}` seul dans une accolade JSX alors que le serveur renvoie un OBJET
#     ou une LISTE -> « objects are not valid as a React child ».
_NATURES_NON_ITERABLES = frozenset({NOMBRE, TEXTE, BOOLEEN, OBJET})
_NATURES_NON_AFFICHABLES = frozenset({OBJET, LISTE})


def _usages_incompatibles(code: str, prefixe: str, forme: dict) -> list:
    """[(champ, ligne, motif)] — le champ existe mais l'ecran le MALTRAITE."""
    constats = []
    acces = _acces(prefixe)
    for champ, nature in sorted(forme.items()):
        if nature == INCONNU:
            continue
        borne = re.escape(champ) + r"(?![\w$])"
        if nature in _NATURES_NON_ITERABLES:
            itere = re.compile(acces + borne + r"\s*\??\s*\.\s*(?:map|forEach|filter)\s*\(")
            trouve = itere.search(code)
            if trouve:
                constats.append((
                    champ, code.count("\n", 0, trouve.start()) + 1,
                    f"l'ecran itere sur '{champ}' (.map/.forEach/.filter) alors "
                    f"que le serveur le renvoie en {nature} — c'est le "
                    f"« x.map is not a function » du 03/08/2026"))
        if nature in _NATURES_NON_AFFICHABLES:
            rendu = re.compile(r"\{\s*" + acces + borne + r"\s*\}")
            trouve = rendu.search(code)
            if trouve:
                constats.append((
                    champ, code.count("\n", 0, trouve.start()) + 1,
                    f"l'ecran rend '{champ}' tel quel dans le JSX alors que le "
                    f"serveur le renvoie en {nature} — c'est le « objects are "
                    f"not valid as a React child » du 03/08/2026"))
    return constats


def champs_fantomes(shapes):
    """[(fichier, ligne, fonction, chemin, champ, motif)] — ecrans fautifs."""
    par_module = {}
    for (module, nom), (route, forme) in shapes.items():
        par_module.setdefault(module, {})[nom] = (route, forme)
    if not par_module:
        return []

    constats = []
    for path in screen_files():
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        code, _, masked = scan_js(src)
        clients = _clients_importes(code, path, set(par_module))
        if not clients:
            continue
        relatif = path.relative_to(ROOT).as_posix()
        for variable, prefixe, module, fonction in _liaisons(code, masked, clients):
            contrat = par_module.get(module, {}).get(fonction)
            if contrat is None:
                continue            # forme incertaine : on n'accuse pas
            if not _lie_une_seule_fois(masked, variable):
                continue
            if not _jamais_un_parametre(masked, variable):
                continue
            route, forme = contrat
            for champ, ligne in sorted(_champs_lus(code, prefixe).items()):
                if champ in forme:
                    continue
                constats.append((
                    relatif, ligne, fonction, route, champ,
                    f"l'ecran lit '{champ}' sur la reponse de {fonction}() "
                    f"({route}), que le serveur ne renvoie PAS "
                    f"(il renvoie : {', '.join(sorted(forme))})"))
            for champ, ligne, motif in _usages_incompatibles(code, prefixe, forme):
                constats.append((relatif, ligne, fonction, route, champ, motif))
    return constats


# ===========================================================================
# 3 ter. PACT10 — L'EXEMPLE PARTAGE : `apps/<x>/contract_samples/*.json`
# ===========================================================================
#
# POURQUOI. `plan_lanes.py` force les lanes a etre disjointes en fichiers —
# c'est ce qui permet a 8 agents de travailler sans conflit. Or un contrat
# front<->back ne partage AUCUN fichier par construction (`urls.py` d'un cote,
# `frontend/src/api/*.js` de l'autre) : la regle qui protege des conflits de
# fusion garantit mecaniquement que les deux moities travaillent en aveugle.
# L'en-tete d'`aoApi.js` declarait « ce fichier PUBLIE le contrat que le backend
# enregistre ensuite » — une obligation adressee a une lane parallele qui ne l'a
# jamais recue. L'obligation n'avait aucun PORTEUR.
#
# `apps/<x>/contract_samples/<endpoint>.json` EST ce porteur : un exemple de
# reponse, versionne, que les deux moities lisent. Le backend affirme que sa
# vraie reponse egale l'exemple ; le frontend l'IMPORTE au lieu d'inventer son
# `PAYLOAD` (PACT13). Si le serveur change de forme, l'exemple change, et le
# test frontend casse tout seul — sans reunion, sans discipline humaine.
#
# La fonction ci-dessous est ce qui rend l'exemple DIGNE DE CONFIANCE : elle
# echoue si l'exemple et le dictionnaire reellement renvoye divergent (cle en
# trop, cle manquante, nature incompatible). Un exemple qui pourrit dans son
# coin serait pire que pas d'exemple du tout.

APPS_ROOT = ROOT / "backend" / "django_core" / "apps"
DOSSIER_ECHANTILLONS = "contract_samples"

_ENDPOINT = re.compile(r"^(?P<verbe>[A-Z]+)\s+(?P<chemin>/\S*)$")


def _nature_json(valeur) -> str:
    if isinstance(valeur, bool):
        return BOOLEEN
    if isinstance(valeur, dict):
        return OBJET
    if isinstance(valeur, list):
        return LISTE
    if isinstance(valeur, (int, float)):
        return NOMBRE
    if isinstance(valeur, str):
        return TEXTE
    return INCONNU          # `null` : le serveur peut le rendre en toute nature


def fichiers_echantillons(racine: Path = None):
    racine = APPS_ROOT if racine is None else racine
    if not racine.is_dir():
        return []
    return sorted(racine.glob(f"*/{DOSSIER_ECHANTILLONS}/*.json"))


def echantillons_de_contrat(shapes, racine: Path = None):
    """[(fichier, ligne, endpoint, chemin, champ, motif)] — exemples qui derivent."""
    import json

    par_route = {}
    for _, (route, forme) in shapes.items():
        par_route.setdefault(route, forme)

    constats = []
    for fichier in fichiers_echantillons(racine):
        relatif = fichier.relative_to(ROOT).as_posix() \
            if ROOT in fichier.parents or fichier.is_relative_to(ROOT) else fichier.name
        try:
            document = json.loads(fichier.read_text(encoding="utf-8"))
        except (OSError, ValueError) as erreur:
            constats.append((relatif, 1, fichier.stem, "?", "<fichier>",
                             f"JSON illisible : {erreur}"))
            continue
        endpoint = (document or {}).get("endpoint", "")
        exemple = (document or {}).get("exemple")
        entete = _ENDPOINT.match(str(endpoint).strip())
        if not entete or not isinstance(exemple, dict):
            constats.append((
                relatif, 1, fichier.stem, "?", "<fichier>",
                "l'echantillon doit porter `endpoint` (« GET /api/... ») et "
                "`exemple` (un objet). Voir apps/ao/contract_samples/README.md"))
            continue
        route = normalise_call(entete.group("chemin"), "api/django")
        chemin = "/" + "/".join(route) if route else entete.group("chemin")
        forme = par_route.get(chemin)
        if forme is None:
            # Endpoint hors contrat (forme non certaine statiquement) : un doute
            # ne rougit JAMAIS. L'exemple reste utile au frontend.
            continue
        for champ in sorted(set(exemple) - set(forme)):
            constats.append((
                relatif, 1, fichier.stem, chemin, champ,
                f"l'exemple declare '{champ}', que le serveur ne renvoie PAS "
                f"(il renvoie : {', '.join(sorted(forme))})"))
        for champ in sorted(set(forme) - set(exemple)):
            constats.append((
                relatif, 1, fichier.stem, chemin, champ,
                f"le serveur renvoie '{champ}' et l'exemple l'OMET : un "
                f"exemple incomplet laisse un champ hors contrat"))
        for champ in sorted(set(exemple) & set(forme)):
            attendue, trouvee = forme[champ], _nature_json(exemple[champ])
            if INCONNU in (attendue, trouvee) or attendue == trouvee:
                continue
            constats.append((
                relatif, 1, fichier.stem, chemin, champ,
                f"le serveur renvoie '{champ}' en {attendue}, l'exemple le "
                f"declare en {trouvee}"))
    return constats


# ===========================================================================
# 4. Rapprochement + contrat versionne
# ===========================================================================

def build_contract():
    backend = contract.BackendRoutes()
    backend.build()
    reader = ShapeReader(backend)

    api = ApiFunctions(contract.frontend_files())
    api.collect()

    known = RouteTrie()
    for route in backend.routes:
        known.add(route)

    shapes = {}          # (module frontend, fonction) -> (chemin, {cle: nature})
    for (module, name), calls in sorted(api.functions.items(), key=lambda item: str(item[0])):
        if len(calls) != 1:
            continue                       # plusieurs appels : on ne devine pas
        verb, route = next(iter(calls))
        if not known.matches(route):
            continue                       # rupture : c'est l'affaire de la garde 1
        shape = reader.shape_of_route(route, verb)
        if not shape:
            continue
        shapes[(module, name)] = ("/" + "/".join(route), shape)
    return shapes


def analyse(shapes=None):
    shapes = build_contract() if shapes is None else shapes
    findings = []
    for path in test_files():
        relative = path.relative_to(ROOT).as_posix()
        for line, modules, name, mock in mocked_payloads(path):
            candidates = [shapes[(module, name)] for module in modules
                          if (module, name) in shapes]
            if len(candidates) != 1:
                continue
            route, real = candidates[0]
            for field, kind in sorted(mock.items()):
                if field not in real:
                    findings.append((relative, line, name, route, field,
                                     f"le serveur ne renvoie AUCUN champ '{field}' "
                                     f"(il renvoie : {', '.join(sorted(real))})"))
                elif real[field] != INCONNU and kind != INCONNU and real[field] != kind:
                    findings.append((relative, line, name, route, field,
                                     f"le serveur renvoie '{field}' en {real[field]}, "
                                     f"le mock le declare en {kind}"))
    # PACT9 — meme forme de constat, meme signature `fonction|champ`, meme base
    # de reference : un ecran qui lit un champ fantome SANS avoir de test est
    # exactement le meme defaut qu'un mock qui ment, vu depuis l'autre bout.
    findings.extend(champs_fantomes(shapes))
    # PACT10 — l'exemple partage ne peut pas pourrir : il derive du serveur ou
    # il rougit. C'est ce qui le rend digne d'etre importe par les deux moities.
    findings.extend(echantillons_de_contrat(shapes))
    return findings, shapes


CONTRACT_HEADER = """\
# Contrat des reponses agregees — GENERE, ne pas editer a la main.
#
# Regenerer : `python scripts/check_api_shapes.py --write`
#
# Chaque ligne est la forme REELLE du dictionnaire renvoye par le serveur,
# lue dans le code (vue -> selecteur -> dictionnaire), pour un endpoint que le
# frontend appelle. C'est le document qui manquait le 03/08/2026 : la moitie
# frontend et la moitie backend d'une meme fonctionnalite n'avaient pas la
# meme forme sous les yeux, et le test de l'ecran mockait l'INVERSE EXACT de
# ce que le serveur renvoyait — les deux suites vertes, l'ecran mort.
#
# Un changement de forme cote serveur DOIT apparaitre ici, dans le diff de la
# PR. `scripts/check_api_shapes.py` echoue si un mock de test contredit cette
# liste (champ inexistant, ou nature incompatible).
"""


def render_contract(shapes) -> str:
    lines = [CONTRACT_HEADER, ""]
    rows = []
    for (module, name), (route, shape) in shapes.items():
        champs = ", ".join(f"{field}:{kind}" for field, kind in sorted(shape.items()))
        rows.append((Path(module).relative_to(ROOT).as_posix(), name, route, champs))
    for source, name, route, champs in sorted(rows):
        lines.append(f"- {source} :: {name} -> {route}")
        lines.append(f"    {champs}")
    return "\n".join(lines) + "\n"


BASELINE_HEADER = """\
# Base de reference de check_api_shapes.py — DETTE HISTORIQUE, RIEN D'AUTRE.
#
# Chaque ligne est un mock de test qui contredit la forme reellement renvoyee
# par le serveur. La garde n'echoue que sur une occurrence ABSENTE de cette
# liste.
#
# REGLE ABSOLUE : CETTE LISTE NE PEUT QUE RETRECIR. `--write-baseline` refuse
# d'ajouter une ligne ; il faut `--autoriser-croissance` (fondateur), visible
# en revue. La signature est `fonction|champ`, jamais `fichier:ligne` : un
# deplacement de ligne ne doit pas invalider la base.
"""


def signature(finding) -> str:
    _, _, name, _, field, _ = finding
    return f"{name}|{field}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Garde de forme : un mock de test ne peut pas contredire le serveur.")
    parser.add_argument("--write", action="store_true",
                        help="regenere docs/api-contracts.md")
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--autoriser-croissance", action="store_true",
                        help="FONDATEUR UNIQUEMENT : autorise l'ajout de dettes")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args(argv)

    findings, shapes = analyse()
    rendered = render_contract(shapes)

    if args.write:
        CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONTRACT_PATH.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"Contrat ecrit : {CONTRACT_PATH.relative_to(ROOT)} "
              f"({len(shapes)} endpoint(s) agrege(s)).")
        return 0

    if args.stats:
        print(f"Endpoints dont la forme est certaine statiquement : {len(shapes)}.")
        print(f"Mocks de test contredisant le serveur : {len(findings)}.")

    baseline = load_baseline()
    signatures = {signature(f) for f in findings}

    if args.write_baseline:
        added = signatures - baseline
        bootstrap = not BASELINE_PATH.is_file()
        if added and not (args.autoriser_croissance or bootstrap):
            print("REFUS : --write-baseline ne peut que RETRECIR la base.")
            for entry in sorted(added)[:20]:
                print(f"  + {entry}")
            return 1
        BASELINE_PATH.write_text(
            BASELINE_HEADER + "\n".join(sorted(signatures)) + "\n",
            encoding="utf-8", newline="\n")
        print(f"Base de reference reecrite : {BASELINE_PATH.relative_to(ROOT)} "
              f"({len(signatures)} entree(s)).")
        return 0

    drift = CONTRACT_PATH.is_file() and CONTRACT_PATH.read_text(encoding="utf-8") != rendered
    new = [f for f in findings if signature(f) not in baseline]

    if new:
        print(f"\nECHEC : {len(new)} mock(s) de test contredisent la reponse "
              f"REELLE du serveur.\n")
        for relative, line, name, route, field, reason in sorted(new):
            print(f"  {relative}:{line}  (mock de {name} -> {route})")
            print(f"      {reason}")
        print("\nUn mock ecrit a la main est une DEUXIEME source de verite : "
              "c'est exactement ce qui a laisse passer l'ecran AO Tableau de "
              "bord le 03/08/2026 (test vert, ecran mort). Aligner le mock sur "
              "docs/api-contracts.md, ou corriger le serveur si c'est LUI qui "
              "a tort. Ne desactivez pas cette garde.")
        return 1

    if drift:
        print(f"\nECHEC : {CONTRACT_PATH.relative_to(ROOT)} est en retard sur le code.")
        print("La forme d'une reponse a change sans que le contrat versionne bouge.")
        print("Regenerer (et relire le diff, c'est le but) : "
              "python scripts/check_api_shapes.py --write")
        return 1

    print(f"OK : {len(shapes)} endpoint(s) agrege(s) sous contrat, aucun mock de "
          f"test ne contredit le serveur ({len(baseline)} dette(s) historique(s)).")
    return 0


def load_baseline() -> set:
    if not BASELINE_PATH.is_file():
        return set()
    return {
        line.strip()
        for line in BASELINE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }


if __name__ == "__main__":
    raise SystemExit(main())
