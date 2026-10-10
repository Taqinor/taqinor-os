#!/usr/bin/env python3
"""GARDE CI (stage-names) — CALX381 : aucune ``@action`` du module calepinage
ne reste sans consommateur.

POURQUOI CETTE GARDE ET PAS `rapport_backend_sombre.py`
--------------------------------------------------------
`rapport_backend_sombre.py` travaille au niveau RESSOURCE et ecarte
EXPLICITEMENT les sous-routes (`@action`) de son perimetre (voir sa section 4 :
« on ecarte les sous-routes (@action) : une @action n'est pas une ressource,
elle suit l'ecran de sa ressource »). C'est correct pour un rapport mensuel non
bloquant, mais ca laisse un angle mort total sur les endpoints calepinage : au
23/09/2026, 71 `@action` existent dans `apps/calepinage/views/*.py`, et une
mesure ponctuelle en a trouve 21 sans aucun segment d'`url_path` correspondant
dans `frontend/src/api/calepinageApi.js` (`sorties.py`, `simulation.py`,
`io_layout.py`, `archivage.py`, `verrou.py`, `releve.py`, `export_csv.py`) —
`rapport_backend_sombre.py` en voit seulement 5 lignes calepinage au total,
parce que les sous-routes d'un routeur allume lui sont structurellement
invisibles.

CE QUE CETTE GARDE FAIT
------------------------
1. Inventorie chaque ``@action`` DECLAREE dans les fichiers de
   ``apps/calepinage/views/`` par lecture AST directe (methode d'un ViewSet ou
   fonction de module greffee, patron CALX2) — c'est la SEULE facon d'obtenir
   le fichier:ligne exact d'une declaration.
2. Reutilise ``check_api_contract.BackendRoutes`` (JAMAIS un second resolveur
   d'URLconf) pour confirmer que l'action est reellement ROUTEE — greffee sur
   un ViewSet qu'un routeur monte pour de vrai dans l'URLconf ; une action
   jamais retrouvee dans `backend.views` est du code mort, jamais atteignable,
   donc jamais consommee par construction.
3. Declare une action ROUTEE consommee si ses segments statiques (`url_path`,
   groupes de capture DRF retires) apparaissent tous, en texte, quelque part
   dans `frontend/src/**/*.{js,jsx}` — que ce soit un appel `calepinageApi.js`
   ORDINAIRE, un appel compose via une fabrique (`` `${pivot(id)}masse-lestage/`
   `` : NON resolu par ``check_api_contract.FrontendCalls``, mesure sur ce
   depot le 23/09/2026 — l'extracteur d'appels du contrat front<->back ne sert
   qu'a la question « ce chemin appele existe-t-il ? », jamais a la question
   inverse posee ici, donc une recherche TEXTUELLE des segments litteraux est
   le moyen fiable, pas un second resolveur de routes), ou un
   `window.open(...)`/`href=...` direct (la famille PDF/DXF/XLSX n'a
   structurellement aucun appel axios — sous-detection ASSUMEE, meme principe
   que PACT27 pour `rapport_backend_sombre.py`).
4. Sinon, elle figure dans le passif fige `scripts/calepinage_actions_allow.txt`
   — ou refuse toute action NEUVE non consommee ; le passif ne peut que
   RETRECIR (``--write-baseline``, meme regle que
   ``check_services_appeles.py`` / ``check_ecrans_atteignables.py`` : refuse
   d'ajouter une dette sauf ``--autoriser-croissance``, reserve au fondateur).

ASTK232 — LA MEME GARDE, PARAMETREE PAR MODULE (aucune seconde garde copiee) :
la table ``profil()`` couvre ``calepinage`` (comportement historique inchange),
``stock`` (``apps/stock/views/*.py``) et ``achats`` (``apps/achats/views.py``).
Pour stock/achats, la garde inventorie en plus les RESSOURCES routees
(``router.register`` / ``path`` vers une classe de vue du module) : une
ressource ou une ``@action`` ROUTEE, absente du passif, sans segment trouve
dans ``frontend/src`` et sans marqueur ``# headless: <raison>`` (raison
obligatoire, meme regex que ``rapport_backend_sombre.py``) rougit en nommant
fichier:ligne. Passifs : ``calepinage_actions_allow.txt`` (calepinage) et
``stock_actions_allow.txt`` (stock + achats) — tous deux decroissants.

Usage
-----
    python scripts/check_calepinage_actions_consommees.py
    python scripts/check_calepinage_actions_consommees.py --write-baseline
    python scripts/check_calepinage_actions_consommees.py --stats
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

import check_api_contract as contract
TYPE_DE_CLE = "par_symbole"  # AMET100 — cle de contenu `fichier::symbole` (jamais un numero de ligne)

# -- Racines (globales MUTABLES, relues a l'appel : un test les monkeypatch,
#    exactement comme test_check_api_contract.py fait pour `cac.ROOT`). ------
ROOT = Path(__file__).resolve().parent.parent
DJANGO_ROOT = ROOT / "backend" / "django_core"
VIEWS_SUBPATH = ("apps", "calepinage", "views")
VIEWS_MODULE_PREFIX = "apps.calepinage.views"
FRONTEND_SRC = ROOT / "frontend" / "src"
BASELINE_PATH = ROOT / "scripts" / "calepinage_actions_allow.txt"
#: ASTK232 — passif de stock + achats (decroissant, comme celui de calepinage).
#: ``None`` = ``ROOT/scripts/stock_actions_allow.txt`` calcule A L'APPEL (un test
#: qui deplace ``ROOT`` ne doit jamais ecrire dans le vrai depot).
STOCK_BASELINE_PATH = None


def _stock_baseline() -> Path:
    return STOCK_BASELINE_PATH or ROOT / "scripts" / "stock_actions_allow.txt"


#: Meme regex que scripts/rapport_backend_sombre.py (MARQUEUR) : la raison est
#: obligatoire (au moins RAISON_MINIMALE caracteres) — un marqueur nu est refuse.
MARQUEUR = re.compile(r"#\s*headless\s*:\s*(?P<raison>.*)$")
RAISON_MINIMALE = 3
MODULES = ("calepinage", "stock", "achats")


def profil(nom: str) -> dict:
    """Parametres d'un module garde (relus A L'APPEL : les tests
    monkeypatchent les globales ci-dessus)."""
    if nom == "calepinage":
        return {
            "nom": nom,
            "fichiers": lambda: _fichiers_dossier(
                DJANGO_ROOT.joinpath(*VIEWS_SUBPATH)),
            "prefix": VIEWS_MODULE_PREFIX,
            "baseline": BASELINE_PATH,
            "ressources": False,
        }
    if nom == "stock":
        return {
            "nom": nom,
            "fichiers": lambda: _fichiers_dossier(
                DJANGO_ROOT / "apps" / "stock" / "views"),
            "prefix": "apps.stock.views",
            "baseline": _stock_baseline(),
            "ressources": True,
        }
    if nom == "achats":
        return {
            "nom": nom,
            "fichiers": lambda: [DJANGO_ROOT / "apps" / "achats" / "views.py"],
            "prefix": "apps.achats.views",
            "baseline": _stock_baseline(),
            "ressources": True,
        }
    raise ValueError(nom)


def _fichiers_dossier(dossier: Path) -> list:
    if not dossier.is_dir():
        return []
    return [c for c in sorted(dossier.glob("*.py"))
            if c.name != "__init__.py"
            and not c.name.startswith(("test_", "tests_"))]


def _relatif(chemin: Path) -> str:
    return (chemin.relative_to(ROOT).as_posix() if chemin.is_relative_to(ROOT)
            else chemin.as_posix())


def marqueur_headless(lignes: list, debut: int, fin: int):
    """``None`` (pas de marqueur), ``''`` (marqueur SANS raison suffisante) ou
    la raison. Cherche de la ligne au-dessus de ``debut`` jusqu'a ``fin``
    (numeros 1-bases, bornes comprises)."""
    for numero in range(max(debut - 1, 1), min(fin, len(lignes)) + 1):
        trouve = MARQUEUR.search(lignes[numero - 1])
        if trouve:
            raison = trouve.group("raison").strip()
            return raison if len(raison) >= RAISON_MINIMALE else ""
    return None


def _module_dotted(chemin: Path) -> str:
    rel = chemin.relative_to(DJANGO_ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _fonctions(corps) -> list:
    return [n for n in corps if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def inventaire_actions_declarees(module: str = "calepinage") -> list:
    """[{fichier, ligne, module, fonction, url_path, headless, ...}, ...] —
    une entree par ``@action`` reellement posee dans les vues du module.

    Lecture AST DIRECTE (jamais via BackendRoutes) : c'est la seule facon
    d'avoir la ligne exacte de la declaration. La resolution de route reste,
    elle, entierement a BackendRoutes (voir `routes_par_action`).
    """
    trouvees = []
    for chemin in profil(module)["fichiers"]():
        try:
            source = chemin.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            tree = ast.parse(source, filename=str(chemin))
        except SyntaxError:
            continue
        lignes = source.splitlines()
        dotted = _module_dotted(chemin)
        fichier_relatif = _relatif(chemin)

        candidats = [(None, f) for f in _fonctions(tree.body)]
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                candidats.extend((node.name, f) for f in _fonctions(node.body))

        for classe, fonction in candidats:
            debut = min([fonction.lineno] + [d.lineno
                                             for d in fonction.decorator_list])
            for detail, url_path, known in contract._actions_du_decorateur(fonction):
                trouvees.append({
                    "fichier": fichier_relatif,
                    "ligne": fonction.lineno,
                    "module": dotted,
                    "fonction": fonction.name,
                    "classe": classe,
                    "url_path": url_path,
                    "detail": detail,
                    "known": known,
                    "domaine": module,
                    "genre": "action",
                    "headless": marqueur_headless(lignes, debut, fonction.lineno),
                })
    return trouvees


def inventaire_ressources(backend: "contract.BackendRoutes", module: str) -> list:
    """Ressources ROUTEES (``router.register`` / ``path`` vers une classe) dont
    la classe de vue vit dans les fichiers du module (ASTK232). Une entree par
    route : {fichier, ligne, url_path ('ressource/<segment>'), segment, ...}.
    Les vues-fonctions et les classes hors du module sont hors perimetre."""
    prof = profil(module)
    if not prof["ressources"]:
        return []
    fichiers = {_relatif(c): c for c in prof["fichiers"]()}
    trouvees, vues = [], set()
    for route, (_owner, ref) in backend.views.items():
        if not isinstance(ref, tuple) or len(ref) < 2:
            continue
        if ref[0] == "viewset" and len(ref) == 3 and ref[2] == "list":
            nom = ref[1]
        elif ref[0] == "classe":
            nom = ref[1]
        else:
            continue
        statiques = [seg for seg in route
                     if isinstance(seg, str) and seg not in (contract.ANY, contract.PK)]
        if not statiques:
            continue
        segment = statiques[-1]
        for dotted, node in backend._classes.get(nom, []):
            chemin = backend._modules.get(dotted, (None, None))[0]
            if chemin is None:
                continue
            rel = _relatif(chemin)
            if rel not in fichiers or (rel, node.lineno, segment) in vues:
                continue
            vues.add((rel, node.lineno, segment))
            lignes = fichiers[rel].read_text(
                encoding="utf-8", errors="replace").splitlines()
            debut = min([node.lineno] + [d.lineno for d in node.decorator_list])
            trouvees.append({
                "fichier": rel, "ligne": node.lineno, "module": dotted,
                "fonction": node.name, "classe": node.name,
                "url_path": f"ressource/{segment}", "segment": segment,
                "detail": False, "known": True, "domaine": module,
                "genre": "ressource",
                "headless": marqueur_headless(lignes, debut, node.lineno),
            })
    return trouvees


def routes_par_action(backend: "contract.BackendRoutes",
                      prefix: str | None = None) -> dict:
    """{(module, fonction): [route complete, ...]} pour chaque ``@action``
    dont le proprietaire est un module de `apps.calepinage.views` — lu
    directement dans `backend.views`, rempli par
    `BackendRoutes._expand_router` pour CHAQUE action d'un ViewSet monte
    (methodes ET fonctions greffees CALX2). Sert a confirmer qu'une action
    declaree est reellement ROUTEE (routee, PAS forcement consommee) : une
    `@action` qui n'apparait jamais ici est du code mort, jamais atteignable,
    donc jamais consomme par construction.
    """
    prefix = VIEWS_MODULE_PREFIX if prefix is None else prefix
    out: dict = {}
    for route, (owner, ref) in backend.views.items():
        if not (isinstance(ref, tuple) and len(ref) == 3 and ref[0] == "action"):
            continue
        # ACAL293 — une methode qui SURCHARGE une action heritee (ex.
        # ``chatter_noter`` du mixin records, reecrite sur CalepinageViewSet)
        # est attribuee par BackendRoutes au module du mixin : on indexe donc
        # aussi chaque action par (classe du ViewSet, fonction), cle que
        # `analyse` consulte pour une methode declaree dans une classe.
        out.setdefault(("classe", ref[1], ref[2]), []).append(route)
        if owner != prefix and not owner.startswith(prefix + "."):
            continue
        out.setdefault((owner, ref[2]), []).append(route)
    return out


def actions_rattachees(module: str = "calepinage") -> set:
    """ACAL338 — {(module pointe, fonction)} des ``@action`` MONTEES par un
    assistant de rattachement (``_attacher(viewset_classe)`` /
    ``rattacher(viewset)``) appele au niveau du module avec un ViewSet :
    ``viewset_classe.archiver = archiver`` y pose l'action sur la classe, mais
    ``BackendRoutes`` ne lit que l'affectation DIRECTE ``CalepinageViewSet.x =
    f`` — ces actions-la etaient donc signalees « non routees » a tort
    (archivage.py, io_layout.py). ``BackendRoutes`` n'est PAS modifie (utilise
    par d'autres gardes) : l'extension vit ici."""
    trouvees = set()
    for chemin in profil(module)["fichiers"]():
        try:
            tree = ast.parse(chemin.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        assistants = {}
        for node in tree.body:
            if (isinstance(node, ast.FunctionDef) and node.args.args
                    and ("attacher" in node.name or "rattacher" in node.name)):
                parametre = node.args.args[0].arg
                assistants[node.name] = [
                    cible.attr for sub in ast.walk(node)
                    if isinstance(sub, ast.Assign) for cible in sub.targets
                    if isinstance(cible, ast.Attribute)
                    and isinstance(cible.value, ast.Name)
                    and cible.value.id == parametre
                    and isinstance(sub.value, ast.Name)]
        appeles = {
            n.value.func.id for n in tree.body
            if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
            and isinstance(n.value.func, ast.Name) and n.value.args
            and isinstance(n.value.args[0], ast.Name)
            and n.value.args[0].id.endswith("ViewSet")}
        dotted = _module_dotted(chemin)
        for nom in appeles & set(assistants):
            for node in ast.walk(tree):
                if not (isinstance(node, ast.FunctionDef)
                        and node.name == nom):
                    continue
                for sub in ast.walk(node):
                    if (isinstance(sub, ast.Assign)
                            and isinstance(sub.value, ast.Name)):
                        trouvees.add((dotted, sub.value.id))
    return trouvees


def servie_par_inventaire(url_path: str, endpoints: set, texte: str) -> bool:
    """Vrai si ``url_path`` (point echappe retire) est un endpoint de
    l'inventaire documents ET que le front le telecharge via ``.endpoint``."""
    return (url_path.replace(chr(92), "").strip("/") in endpoints
            and ".endpoint" in texte)


def endpoints_inventaire_documents() -> set:
    """ACAL338 — chemins servis par l'inventaire ``services/documents``
    (``_DEFINITIONS_DOCUMENTS`` : 4e champ de chaque ligne ; ``AUTRES_FORMATS``) :
    ``PanneauDocuments.jsx`` les telecharge via ``entree.endpoint`` — ils sont
    donc CONSOMMES sans que leur nom litteral figure dans ``frontend/src``."""
    chemin = (DJANGO_ROOT / "apps" / "calepinage" / "services" / "documents"
              / "__init__.py")
    try:
        tree = ast.parse(chemin.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return set()
    endpoints = set()
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            continue
        nom = node.targets[0].id
        if nom == "_DEFINITIONS_DOCUMENTS":
            for ligne in getattr(node.value, "elts", []):
                elts = getattr(ligne, "elts", [])
                if (len(elts) >= 4 and isinstance(elts[3], ast.Constant)
                        and isinstance(elts[3].value, str)):
                    endpoints.add(elts[3].value.strip("/"))
        elif nom == "AUTRES_FORMATS":
            for sub in ast.walk(node.value):
                if (isinstance(sub, ast.Tuple) and len(sub.elts) == 2
                        and isinstance(sub.elts[1], ast.Constant)
                        and isinstance(sub.elts[1].value, str)
                        and sub.elts[1].value.endswith("/")):
                    endpoints.add(sub.elts[1].value.strip("/"))
    return endpoints


# Un groupe nomme de convertisseur DRF (`(?P<id>[^/.]+)`) ne peut, par
# construction, apparaitre TEL QUEL dans une source JS : le retirer laisse les
# segments litteraux qui, eux, sont recopies mot pour mot cote client (avec ou
# sans le detour d'une fabrique `pivot(id)` — CALX381 : check_api_contract.
# FrontendCalls ne resout PAS `` `${pivot(id)}masse-lestage/` `` en route
# complete, verifie sur le vrai depot le 23/09/2026 (masse-lestage, variantes,
# comparer... tous rendus a tort « sans consommateur » par un matching de
# route strict) — la recherche TEXTUELLE des segments statiques est donc plus
# fiable ici que la resolution d'appel de check_api_contract, qui ne sert
# qu'a la moitie « ce chemin existe-t-il » du contrat, jamais a la question
# inverse posee par cette garde.
_GROUPE_CONVERTISSEUR = re.compile(r"\(\?P<[^>]+>[^)]*\)")


def segments_statiques(url_path: str) -> list:
    """Segments non-vides d'un `url_path`, groupes de capture DRF retires.

    ACAL229 — un point ECHAPPE (antislash-point, `r'export\\.csv'`) est un
    point litteral : le frontend ecrit `export.csv`, c'est donc `export.csv`
    qu'on y cherche (sinon chaque export echappe deviendrait une dette).
    """
    sans_groupes = _GROUPE_CONVERTISSEUR.sub("", url_path).replace("\\.", ".")
    return [s for s in sans_groupes.split("/") if s]


def texte_frontend() -> str:
    """Concatenation de tout `frontend/src/**/*.{js,jsx}` (hors tests) — une
    seule lecture, un seul passage ; la recherche de consommation est ensuite
    une simple sous-chaine, jamais une resolution d'appel."""
    if not FRONTEND_SRC.is_dir():
        return ""
    morceaux = []
    for chemin in FRONTEND_SRC.rglob("*"):
        if chemin.suffix not in (".js", ".jsx"):
            continue
        if ".test." in chemin.name:
            continue
        try:
            morceaux.append(chemin.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return "\n".join(morceaux)


def action_consommee(url_path: str, texte: str) -> bool:
    """Une action est CONSOMMEE si TOUS ses segments statiques (le nom de
    methode ou le libelle d'`url_path`, groupes DRF retires) apparaissent
    quelque part dans `frontend/src` — qu'ils soient touches par un vrai appel
    `calepinageApi.js` (le cas courant) ou par un `window.open`/`href` direct
    (la famille PDF/DXF/XLSX, sans aucun appel axios — sous-detection
    ASSUMEE, meme principe que PACT27). Un segment de moins de 3 caracteres
    est ignore (bruit, jamais distinctif)."""
    segments = [s for s in segments_statiques(url_path) if len(s) >= 3]
    if not segments:
        return url_path in texte
    return all(segment in texte for segment in segments)


# ===========================================================================
# Base de reference
# ===========================================================================

ENTETE_BASE = """\
# Base de reference de check_calepinage_actions_consommees.py — DETTE
# HISTORIQUE, RIEN D'AUTRE (CALX381).
#
# Chaque ligne est une `@action` de `apps/calepinage/views/*.py` qu'AUCUN
# appel axios de frontend/src ni aucun `window.open`/`href` ne consomme.
# Cette liste gele l'etat du jour : la garde empeche la RECIDIVE, elle ne
# repare pas le passif — chaque ligne drainee est une action enfin branchee,
# retiree du code, ou expliquee par un vrai consommateur non litteral.
#
# REGLE ABSOLUE : CETTE LISTE NE PEUT QUE RETRECIR.
#   - brancher (ou supprimer) une action puis `python
#     scripts/check_calepinage_actions_consommees.py --write-baseline` retire
#     sa ligne ;
#   - `--write-baseline` REFUSE d'ajouter une ligne. Ajouter une dette exige
#     `--autoriser-croissance`, drapeau reserve au fondateur, visible en revue.
#
# Format : `<fichier>:<ligne>  <url_path>  # <raison datee>`.
"""

_LIGNE_BASE = re.compile(r"^(?P<cle>\S+:\d+)\s+(?P<url_path>\S+)\s*(?:#.*)?$")


def cle_dette(fichier: str, url_path: str) -> str:
    """Cle de comparaison d'une dette : ``fichier`` + ``url_path`` normalise
    (antislashes d'echappement retires). JAMAIS le numero de ligne : une
    insertion de code au-dessus d'une action deja en dette la decalait et la
    faisait passer pour NEUVE (vague D ACAL, 05/10/2026 : 5 faux rouges dans
    ``views/documents.py``). La ligne reste ecrite dans la base, a titre de
    repere humain seulement."""
    return f"{fichier}::{url_path.replace(chr(92), '')}"


def _cle_constat(c: dict) -> str:
    return cle_dette(c["fichier"], c["url_path"])


def charger_base(path: Path | None = None) -> dict:
    path = path or BASELINE_PATH
    if not path.is_file():
        return {}
    base = {}
    for ligne in path.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#"):
            continue
        m = _LIGNE_BASE.match(ligne)
        if m:
            fichier = m.group("cle").rsplit(":", 1)[0]
            base[cle_dette(fichier, m.group("url_path"))] = m.group("cle")
    return base


ENTETE_BASE_STOCK = """\
# Base de reference de check_calepinage_actions_consommees.py pour STOCK et
# ACHATS — DETTE NOMMEE, RIEN D'AUTRE (ASTK232 ; ressources ET @action).
#
# Chaque ligne est une ressource routee ou une `@action` de apps/stock/views/
# ou apps/achats/views.py qu'AUCUN appel de frontend/src ne consomme et qui ne
# porte pas de marqueur `# headless: <raison>`. Le passif est amorce APRES les
# ecrans du groupe (il ne doit contenir que la dette nommee par ASTK233).
#
# REGLE ABSOLUE : CETTE LISTE NE PEUT QUE RETRECIR.
#   - brancher (ou supprimer, ou marquer `# headless:`) puis `python
#     scripts/check_calepinage_actions_consommees.py --write-baseline` retire
#     la ligne ;
#   - `--write-baseline` REFUSE d'ajouter une ligne ; ajouter une dette exige
#     `--autoriser-croissance`, drapeau reserve au fondateur.
#
# Format : `<fichier>:<ligne>  <url_path>  # <raison datee>`
# (`ressource/<segment>` pour une ressource, le url_path pour une @action).
"""


def ecrire_base(constats: list, path: Path | None = None,
                entete: str | None = None):
    path = path or BASELINE_PATH
    if entete is None:
        entete = ENTETE_BASE if path == BASELINE_PATH else ENTETE_BASE_STOCK
    corps = "\n".join(
        f"{c['fichier']}:{c['ligne']}  {c['url_path']}  "
        f"# non consommee au 23/09/2026 (CALX381)"
        if c.get("domaine", "calepinage") == "calepinage" else
        f"{c['fichier']}:{c['ligne']}  {c['url_path']}  "
        f"# sans consommateur au 07/10/2026 (ASTK232)"
        for c in sorted(constats, key=lambda c: (c["fichier"], c["ligne"]))
    )
    path.write_text(
        entete + (corps + "\n" if corps else ""),
        encoding="utf-8", newline="\n",
    )


# ===========================================================================
# Analyse
# ===========================================================================

def analyse() -> tuple:
    """(constats_non_consommes, stats) — constats = liste des actions et
    ressources declarees non consommees (avant filtrage par le passif), tous
    modules confondus ; ``stats['par_module']`` detaille, ``stats['invalides']``
    liste les marqueurs ``# headless:`` sans raison."""
    backend = contract.BackendRoutes(DJANGO_ROOT)
    backend.build()
    texte = texte_frontend()
    inventaire_docs = endpoints_inventaire_documents()

    constats, invalides, par_module = [], [], {}
    for nom in MODULES:
        prof = profil(nom)
        routes = routes_par_action(backend, prof["prefix"])
        declarees = inventaire_actions_declarees(nom)
        ressources = inventaire_ressources(backend, nom)
        rattachees = actions_rattachees(nom)
        compte = 0
        for item in declarees + ressources:
            if item["headless"] == "":
                invalides.append(item)
            if item["genre"] == "ressource":
                consommee = bool(re.search(
                    r"(?<![\w-])" + re.escape(item["segment"]) + r"(?![\w-])",
                    texte))
            else:
                routee = bool(routes.get((item["module"], item["fonction"]))) or bool(
                    item.get("classe")
                    and routes.get(("classe", item["classe"], item["fonction"])))
                routee = routee or (item["module"], item["fonction"]) in rattachees
                consommee = routee and (
                    action_consommee(item["url_path"], texte)
                    or (nom == "calepinage" and servie_par_inventaire(
                        item["url_path"], inventaire_docs, texte)))
            if consommee or item["headless"]:
                continue
            constats.append(item)
            compte += 1
        par_module[nom] = {"actions": len(declarees),
                           "ressources": len(ressources),
                           "non_consommees": compte}

    stats = {
        "actions": sum(m["actions"] for m in par_module.values()),
        "non_consommees": len(constats),
        "par_module": par_module,
        "invalides": invalides,
    }
    return constats, stats


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(
        description="Garde « action calepinage sans consommateur » (CALX381).")
    parser.add_argument("--stats", action="store_true", help="inventaire chiffre")
    parser.add_argument(
        "--write-baseline", action="store_true",
        help="retire de la base les actions desormais consommees",
    )
    parser.add_argument(
        "--autoriser-croissance", action="store_true",
        help="FONDATEUR UNIQUEMENT : autorise l'ajout de dettes",
    )
    args = parser.parse_args(argv)

    constats, stats = analyse()

    if args.stats:
        print(f"@action inventoriees dans apps/calepinage/views/ : "
              f"{stats['par_module']['calepinage']['actions']}")
        print(f"  dont sans consommateur (avant passif) : "
              f"{stats['par_module']['calepinage']['non_consommees']}")
        for nom in MODULES[1:]:
            m = stats["par_module"][nom]
            print(f"{nom} : {m['actions']} @action + {m['ressources']} "
                  f"ressource(s), {m['non_consommees']} sans consommateur "
                  f"(avant passif)")

    if stats["par_module"]["calepinage"]["actions"] == 0:
        print("\nECHEC : aucune @action trouvee dans apps/calepinage/views/. "
              "Soit le chemin analyse a bouge, soit la lecture a cesse de "
              "fonctionner — dans les deux cas la garde a cesse de garder.")
        return 1

    if stats["invalides"]:
        print(f"\nECHEC : {len(stats['invalides'])} marqueur(s) `# headless:` "
              "SANS raison (un marqueur nu est un interrupteur, pas une "
              "intention) :")
        for c in stats["invalides"]:
            print(f"  {c['fichier']}:{c['ligne']}  ({c['module']}.{c['fonction']})")
        return 1

    # Passifs : un fichier par groupe de modules (calepinage ; stock + achats).
    chemins = {}
    for nom in MODULES:
        chemins.setdefault(profil(nom)["baseline"], []).append(nom)
    bases = {chemin: charger_base(chemin) for chemin in chemins}

    def base_de(c):
        return bases[profil(c["domaine"])["baseline"]]

    if args.write_baseline:
        code = 0
        for chemin, noms in chemins.items():
            propres = [c for c in constats if c["domaine"] in noms]
            cles = {_cle_constat(c) for c in propres}
            base = bases[chemin]
            ajouts = cles - set(base)
            amorce = not chemin.is_file()
            if ajouts and not (args.autoriser_croissance or amorce):
                print(f"REFUS : --write-baseline ne peut que RETRECIR la base "
                      f"({chemin.name}).")
                print(f"{len(ajouts)} nouvelle(s) dette(s) voudraient y entrer :")
                for cle in sorted(ajouts)[:20]:
                    print(f"  + {cle}")
                print("Branchez l'action sur un vrai consommateur, supprimez-la, "
                      "marquez-la `# headless: <raison>`, ou assumez la dette "
                      "avec --autoriser-croissance.")
                code = 1
                continue
            ecrire_base(propres, chemin)
            print(f"Base de reference reecrite : {chemin} "
                  f"({len(propres)} entree(s), "
                  f"{len(set(base) - cles)} retiree(s)).")
        return code

    nouveaux = [c for c in constats if _cle_constat(c) not in base_de(c)]
    cles_constats = {_cle_constat(c) for c in constats}
    corriges = {cle for base in bases.values() for cle in base} - cles_constats

    if nouveaux:
        print(f"\nECHEC : {len(nouveaux)} @action/ressource SANS consommateur "
              f"(hors base de reference).\n")
        for c in nouveaux:
            print(f"  {c['fichier']}:{c['ligne']}  url_path={c['url_path']!r} "
                  f"({c['module']}.{c['fonction']})")
        print("\nQUE FAIRE :")
        print("  - branchez-la sur l'API du frontend (ou un `window.open`/`href` "
              "reel pour un PDF/DXF/XLSX) ;")
        print("  - ou supprimez-la si elle est morte ;")
        print("  - ou marquez-la `# headless: <raison>` si elle n'a PAS d'ecran "
              "par conception (portail public, webhook, tache...) ;")
        print("  - ou, dette assumee a drainer plus tard, "
              "`--write-baseline --autoriser-croissance` (fondateur).")
        return 1

    dettes = sum(len(b) for b in bases.values())
    print(f"OK : {stats['actions']} @action lue(s), aucune NOUVELLE sans "
          f"consommateur ({dettes} dette(s) historique(s) gelee(s), dont "
          f"{len(corriges)} desormais branchee(s)).")
    if corriges:
        print("Ces dettes corrigees peuvent quitter la base : "
              "python scripts/check_calepinage_actions_consommees.py --write-baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
