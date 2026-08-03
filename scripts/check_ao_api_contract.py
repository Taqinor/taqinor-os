#!/usr/bin/env python3
"""Garde CI anti-recidive : le client d'API `ao` ne doit appeler QUE des routes
qui existent vraiment cote serveur.

POURQUOI CE SCRIPT EXISTE — INCIDENT DU 03/08/2026, EN PRODUCTION
-----------------------------------------------------------------------------
Le module « Appels d'offres » a ete construit par deux lanes en parallele
(`frontend/ao` et `backend/ao`) avec des CONTRATS DIFFERENTS. Personne ne s'en
est apercu avant la mise en production, ou :

  * l'ecran Bibliotheque appelait ``GET /ao/bibliotheque/`` — route JAMAIS
    enregistree dans ``apps/ao/urls.py`` : **404** ;
  * l'ecran Tableau de bord lisait des cles absentes de la reponse reelle de
    ``/ao/tableau-marches/`` et faisait ``.map()`` sur un ENTIER :
    **TypeError -> « Une erreur est survenue »**.

Les tests vitest n'ont RIEN vu : ils MOCKENT l'API avec la forme SUPPOSEE par
le front. Un test qui invente lui-meme la reponse du serveur ne prouve rien sur
le contrat reel — il prouve seulement que le front sait lire ce qu'il a ecrit.

Ce script est la garde qui MANQUAIT. Il compare les chemins reellement appeles
par ``frontend/src/api/aoApi.js`` aux routes reellement enregistrees par
``backend/django_core/apps/ao/urls.py`` (routeurs DRF + ``path()`` explicites +
``include()`` suivis, actions ``@action`` comprises, heritage resolu). Un
chemin appele qui n'existe pas cote serveur = ECHEC, en CI, AVANT la
production.

NE PAS LE DESACTIVER. Si une route disparait cote serveur, c'est le FRONT qu'il
faut corriger (ou la route qu'il faut creer) — pas cette garde. Une exception
reellement justifiee s'ajoute dans ``ALLOWLIST`` ci-dessous, avec motif ET
date.

Portee : existence des CHEMINS uniquement. La forme des REPONSES (le second
symptome du 03/08) reste du ressort des tests d'ecran, dont les mocks doivent
reproduire le serializer/selector reel — jamais une forme inventee.

Analyse 100 % STATIQUE (texte + AST) : aucun import Django, aucune base de
donnees. Tourne sur n'importe quel hote, comme les autres ``scripts/check_*``.

Usage :  python scripts/check_ao_api_contract.py
Sortie :  0 si chaque appel du front a une route serveur, 1 sinon.
"""
from __future__ import annotations

import ast
import difflib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend" / "django_core"

#: Client d'API du module et prefixe qu'il adresse (``api/axios`` ajoute
#: ``/api/django``, transverse et donc hors sujet ici).
FRONTEND_CLIENT = ROOT / "frontend" / "src" / "api" / "aoApi.js"
URLCONF = BACKEND / "apps" / "ao" / "urls.py"
API_PREFIX = "/ao/"

#: Bases DRF qui apportent les routes de collection / de detail.
LIST_BASES = {"ModelViewSet", "ReadOnlyModelViewSet", "ListModelMixin",
              "CreateModelMixin"}
DETAIL_BASES = {"ModelViewSet", "ReadOnlyModelViewSet", "RetrieveModelMixin",
                "UpdateModelMixin", "DestroyModelMixin"}
#: Bases qui ne routent QUE les ``@action`` (aucun CRUD implicite).
ACTION_ONLY_BASES = {"GenericViewSet", "ViewSet", "ViewSetMixin", "object"}

#: Allowlist VOLONTAIREMENT VIDE. Toute entree = un chemin front sans route
#: serveur, donc un 404 assume : justifier en commentaire ET dater.
ALLOWLIST: set[str] = set()

RE_PLACEHOLDER = re.compile(r"\$\{[^}]*\}|<[^>]*>|\{[^}]*\}")


def _normalise(path: str) -> str:
    """Ramene un chemin a sa signature comparable.

    Les interpolations front (``${id}``) et les convertisseurs Django
    (``<int:job_id>``) designent la meme chose : un segment variable.
    """
    path = RE_PLACEHOLDER.sub("<id>", path.strip())
    path = path.split("?", 1)[0]
    return "/".join(seg for seg in path.split("/") if seg)


# ───────────────────────────── cote serveur ──────────────────────────────

def _iter_backend_sources():
    """Fichiers Python du backend susceptibles de definir une vue (index des
    classes de base : ``CompanyScopedModelViewSet``, mixins de chatter…)."""
    for path in BACKEND.rglob("*.py"):
        parts = path.parts
        if "migrations" in parts or "node_modules" in parts:
            continue
        yield path


def _index_classes() -> dict[str, tuple[Path, tuple[str, ...]]]:
    """Index ``nom de classe -> (fichier, noms des classes de base)``.

    Balayage textuel volontaire : indexer par AST tout le backend couterait
    bien plus cher pour le meme resultat, et une declaration multi-ligne non
    reconnue retombe simplement sur le comportement prudent (voir
    ``_resolve_bases``).
    """
    pattern = re.compile(r"^class\s+(\w+)\s*\(([^)]*)\)\s*:", re.M)
    index: dict[str, tuple[Path, tuple[str, ...]]] = {}
    for path in _iter_backend_sources():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in pattern.finditer(text):
            name, bases = match.group(1), match.group(2)
            if name in index:
                continue
            parsed = tuple(
                base.strip().split(".")[-1]
                for base in bases.split(",")
                if base.strip() and "=" not in base
            )
            index[name] = (path, parsed)
    return index


def _class_node(path: Path, name: str) -> ast.ClassDef | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def _action_routes(node: ast.ClassDef) -> list[tuple[bool, str]]:
    """``@action`` declarees par la classe -> ``[(detail, url_path), …]``.

    ``url_path`` par defaut = le nom de la methode tel quel (regle DRF).
    """
    routes: list[tuple[bool, str]] = []
    for item in node.body:
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for deco in item.decorator_list:
            if not isinstance(deco, ast.Call):
                continue
            func = deco.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name != "action":
                continue
            detail, url_path = False, item.name
            for kw in deco.keywords:
                if kw.arg == "detail" and isinstance(kw.value, ast.Constant):
                    detail = bool(kw.value.value)
                elif kw.arg == "url_path" and isinstance(kw.value, ast.Constant):
                    url_path = str(kw.value.value)
            routes.append((detail, url_path))
    return routes


def _resolve_bases(viewset: str, index) -> tuple[set[str], bool]:
    """Remonte la chaine d'heritage : ``(noms rencontres, chaine complete ?)``.

    Une base introuvable (definie hors du backend, p. ex. DRF lui-meme) rend la
    chaine incomplete — l'appelant retombe alors sur l'hypothese PRUDENTE
    « la vue expose le CRUD », pour ne JAMAIS signaler a tort une route
    manquante.
    """
    seen: set[str] = set()
    complete = True
    queue = [viewset]
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        entry = index.get(name)
        if entry is None:
            if name not in LIST_BASES | DETAIL_BASES | ACTION_ONLY_BASES:
                complete = False
            continue
        queue.extend(entry[1])
    return seen, complete


def _viewset_routes(prefix: str, viewset: str, index) -> set[str]:
    """Routes generees par ``router.register(prefix, viewset)``."""
    routes: set[str] = set()
    bases, complete = _resolve_bases(viewset, index)
    has_list = bool(bases & LIST_BASES) or not complete
    has_detail = bool(bases & DETAIL_BASES) or not complete
    if has_list:
        routes.add(_normalise(f"{prefix}/"))
    if has_detail:
        routes.add(_normalise(f"{prefix}/<id>/"))

    entry = index.get(viewset)
    chain = [viewset, *(entry[1] if entry else ())]
    for name in chain:
        target = index.get(name)
        if target is None:
            continue
        node = _class_node(target[0], name)
        if node is None:
            continue
        for detail, url_path in _action_routes(node):
            middle = "/<id>/" if detail else "/"
            routes.add(_normalise(f"{prefix}{middle}{url_path}/"))
    return routes


def _module_path(dotted: str) -> Path | None:
    candidate = BACKEND / Path(*dotted.split("."))
    candidate = candidate.with_suffix(".py")
    return candidate if candidate.exists() else None


def _collect_urlconf(path: Path, mount: str, index, seen: set[Path]) -> set[str]:
    """Routes reellement enregistrees par un module d'URLs (recursif)."""
    if path in seen or not path.exists():
        return set()
    seen.add(path)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return set()

    # Routeurs DRF du module : nom de variable -> routes deja developpees.
    routers: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "register"
                and isinstance(node.func.value, ast.Name)):
            continue
        if len(node.args) < 2 or not isinstance(node.args[0], ast.Constant):
            continue
        viewset = node.args[1]
        name = viewset.attr if isinstance(viewset, ast.Attribute) else getattr(viewset, "id", "")
        if not name:
            continue
        routers.setdefault(node.func.value.id, set()).update(
            _viewset_routes(str(node.args[0].value), name, index))

    routes: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "path" and node.args
                and isinstance(node.args[0], ast.Constant)):
            continue
        route = f"{mount}/{node.args[0].value}"
        target = node.args[1] if len(node.args) > 1 else None

        if isinstance(target, ast.Call) and getattr(target.func, "id", "") == "include":
            arg = target.args[0] if target.args else None
            # include('apps.ao.calepinage_urls') — on suit le module.
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                sub = _module_path(arg.value)
                if sub is not None:
                    routes |= _collect_urlconf(sub, route, index, seen)
            # include(router.urls) — on monte les routes du routeur.
            elif isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name):
                for sub_route in routers.get(arg.value.id, set()):
                    routes.add(_normalise(f"{route}/{sub_route}/"))
            continue

        routes.add(_normalise(route))
    return routes


# ────────────────────────────── cote client ──────────────────────────────

RE_FACTORY = re.compile(
    r"(?:const|let|var)\s+(\w+)\s*=\s*makeResourceFactory\(\s*\w+\s*,\s*"
    r"['\"]([^'\"]+)['\"]")
RE_CALL = re.compile(r"\b(?:api|client)\.(?:get|post|patch|put|delete)\("
                     r"\s*([`'\"])([^`'\"]+)\1")


def _strip_comments(text: str) -> str:
    """Neutralise les commentaires SANS deplacer les lignes.

    Un commentaire peut CITER un chemin pour raconter l'incident — ce n'est pas
    un appel reseau. Mais le contenu retire est remplace par autant de sauts de
    ligne : sinon les numeros de ligne signales ne designeraient plus le vrai
    appel, et le message enverrait le lecteur au mauvais endroit.
    """
    text = re.sub(r"/\*[\s\S]*?\*/",
                  lambda m: "\n" * m.group(0).count("\n"), text)
    # ``[^\S\n]*`` et non ``\s*`` : en mode MULTILINE, ``\s*`` avale les sauts
    # de ligne qui PRECEDENT le ``//`` et decale tous les numeros suivants.
    return re.sub(r"^[^\S\n]*//.*$", "", text, flags=re.M)


def _frontend_calls(path: Path) -> list[tuple[int, str]]:
    """Chemins appeles par le client, avec leur ligne : fabrique CRUD partagee
    (``makeResourceFactory``) developpee en collection + detail, plus chaque
    appel axios litteral."""
    text = _strip_comments(path.read_text(encoding="utf-8"))
    calls: list[tuple[int, str]] = []

    for match in RE_FACTORY.finditer(text):
        factory, base = match.group(1), match.group(2)
        if not base.rstrip("/").endswith(API_PREFIX.strip("/")):
            continue
        pattern = re.compile(rf"\b{re.escape(factory)}\(\s*['\"]([^'\"]+)['\"]\s*\)")
        for hit in pattern.finditer(text):
            lineno = text.count("\n", 0, hit.start()) + 1
            calls.append((lineno, _normalise(f"{hit.group(1)}/")))
            calls.append((lineno, _normalise(f"{hit.group(1)}/<id>/")))

    for match in RE_CALL.finditer(text):
        route = match.group(2)
        if not route.startswith(API_PREFIX):
            continue
        lineno = text.count("\n", 0, match.start()) + 1
        calls.append((lineno, _normalise(route[len(API_PREFIX):])))

    # Deduplique en gardant la premiere ligne citee (message plus utile).
    unique: dict[str, int] = {}
    for lineno, route in calls:
        unique.setdefault(route, lineno)
    return sorted((lineno, route) for route, lineno in unique.items())


# ──────────────────────────────── rapport ────────────────────────────────

def scan() -> tuple[list[str], int, int]:
    index = _index_classes()
    served = _collect_urlconf(URLCONF, "", index, set())
    called = _frontend_calls(FRONTEND_CLIENT)
    rel = FRONTEND_CLIENT.relative_to(ROOT).as_posix()

    offenders: list[str] = []
    for lineno, route in called:
        if route in served or route in ALLOWLIST:
            continue
        close = difflib.get_close_matches(route, sorted(served), n=1, cutoff=0.6)
        piste = f" (proche de {API_PREFIX}{close[0]}/)" if close else ""
        offenders.append(
            f"{rel}:{lineno} - {API_PREFIX}{route}/ appele par le front, "
            f"AUCUNE route serveur{piste}")
    return offenders, len(called), len(served)


def main() -> int:
    if not FRONTEND_CLIENT.exists() or not URLCONF.exists():
        print("[check_ao_api_contract] ECHEC - client d'API ou urls.py "
              "introuvable (chemins codes en tete du script).")
        return 1

    offenders, called, served = scan()
    if offenders:
        print("[check_ao_api_contract] ECHEC - le front appelle des routes "
              "qui n'existent pas cote serveur :")
        for line in offenders:
            print(f"  - {line}")
        print()
        print("  Incident du 03/08/2026 : c'est exactement ainsi que l'ecran "
              "Bibliotheque est parti en 404 en production.")
        print("  Corriger le CLIENT (frontend/src/api/aoApi.js) pour viser la "
              "route reelle, ou enregistrer la route manquante dans "
              "backend/django_core/apps/ao/urls.py.")
        print("  Un mock de test n'est PAS une preuve : il doit reproduire le "
              "serializer/selector reel.")
        return 1

    print(f"[check_ao_api_contract] OK - {called} chemins appeles, tous servis "
          f"par l'une des {served} routes enregistrees.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
