#!/usr/bin/env python
"""Generateur de clauses CALCULEES des taches d'audit (AMET80-82, C-AMET-021).

Mesure du 09/10/2026 : ≈ 20 taches d'audit sur 48 affirmaient des Appelants /
Jumeaux / Listes figees FAUX, ecrits de memoire (ATOT2 : « 0 ecran » alors que
DevisRow.jsx lit la cle ; ATOT9 : le PUT de FactureForm passe par un thunk
Redux). Ce script les CALCULE sur l'arbre reel ; la tache colle sa sortie
(texte pret a coller, ou `--json`).

    appelants <fichier::symbole>   appelants Python `fichier::fonction`, references
                                   chaine (beat, settings, mock), et pour une vue :
                                   route -> wrapper `frontend/src/api` -> ecrans
                                   (hooks, thunks Redux, composants intermediaires)
    lecteurs-front <cle>           fichiers front qui lisent une cle servie
    ecrivains <Modele.champ>       sites qui ECRIVENT un champ (affectation, kwargs
                                   ORM, setattr litteral ou via liste, update_fields)
    index [--narrow MOTIF]         construit / rechauffe l'index (chronometre)

Index (API exportee `audit_tache.index`, reutilisee par check_forme_code.py) :
AST de `backend/**.py` + `scripts/*.py` hors migrations — definitions
qualifiees, lignes, empreinte du corps. `--narrow` : `git grep` AVANT l'AST, et
les references au motif sont indexees. Cache pickle par (HEAD, fichiers de code
modifies) dans le dossier temporaire. Mesure 09/10 (8 717 fichiers) : froid
47,6 s, chaud 1,3 s (budgets : 10 min / 3 min).
Reutilise `check_api_contract` (routes DRF, `FrontendCalls`, `scan_js`),
`check_services_appeles` (`est_test`, `_noms_utilises`), `check_taches_cablage`
(`est_ecran`) — aucune seconde implementation.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import pickle
import re
import subprocess
import sys
import tempfile
import time
from collections import namedtuple
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_api_contract as cac  # noqa: E402
import check_services_appeles as csa  # noqa: E402
import check_taches_cablage as ctc  # noqa: E402

DJANGO_REL = "backend/django_core"
PATHSPECS_PY = ("backend/*.py", "scripts/*.py")
FRONT_SRC = "frontend/src"
PATHSPECS_FRONT = tuple(f"{FRONT_SRC}/*{e}" for e in (".js", ".jsx", ".mjs", ".ts", ".tsx"))
CACHE_DIR = Path(tempfile.gettempdir()) / "audit_tache"
CHRONO: dict = {}

Def = namedtuple("Def", "qualname kind debut fin empreinte")

# Methodes de vue appelees par DRF : leurs « appelants » sont les ROUTES.
VERBES_PAR_HOOK = {"list": {"GET"}, "retrieve": {"GET"}, "create": {"POST"}, "perform_create": {"POST"},
                   "update": {"PUT"}, "partial_update": {"PATCH"}, "perform_update": {"PUT", "PATCH"},
                   "destroy": {"DELETE"}, "perform_destroy": {"DELETE"}}
HOOKS_DETAIL = {"retrieve", "update", "partial_update", "destroy", "perform_update", "perform_destroy"}
HOOKS_TRANSVERSES = {"get_permissions", "get_queryset", "get_serializer_class", "get_serializer", "get_object",
                     "initial", "dispatch", "check_permissions", "filter_queryset"}
APPELS_ECRITURE = {"create", "update", "update_or_create", "get_or_create", "bulk_create"}


# --- 1. git ---

def git(*args, racine=None) -> str:
    sortie = subprocess.run(["git", *args], cwd=str(racine or ROOT), capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    if sortie.returncode not in (0, 1):
        raise RuntimeError(f"git {' '.join(args[:2])} : {sortie.stderr.strip()}")
    return sortie.stdout


def git_grep(motif: str, pathspecs, racine=None, *, fixe=False, mot=False, liste=False) -> list:
    """[(rel, ligne, texte)] — ou [rel] si `liste` — sur l'arbre de travail suivi."""
    options = ["grep", "-I", "--no-color", "-l" if liste else "-n", "-F" if fixe else "-E"] + (["-w"] if mot else [])
    for un_motif in ([motif] if isinstance(motif, str) else motif):
        options += ["-e", un_motif]
    lignes = git(*options, "--", *pathspecs, racine=racine).splitlines()
    if liste:
        return [ligne for ligne in lignes if ligne]
    decoupees = (ligne.split(":", 2) for ligne in lignes)
    return [(rel, int(numero), texte) for rel, numero, texte in (d for d in decoupees if len(d) == 3)
            if numero.isdigit()]


_ETATS: dict = {}


def etat_git(racine=None) -> str:
    """HEAD + fichiers de CODE modifies/non suivis (taille, mtime). Memoisee par process."""
    racine = Path(racine or ROOT).resolve()
    if racine not in _ETATS:
        brut = [git("rev-parse", "HEAD", racine=racine)]
        sale = git("status", "--porcelain", "--", "backend", "scripts", FRONT_SRC, racine=racine)
        for ligne in sorted(sale.splitlines()):
            chemin = racine / ligne[3:].strip().strip('"')
            if chemin.suffix in (".py", ".js", ".jsx", ".mjs", ".ts", ".tsx") and chemin.is_file():
                stat = chemin.stat()
                brut.append(f"{ligne}|{stat.st_size}|{stat.st_mtime_ns}")
        _ETATS[racine] = hashlib.sha1("\n".join(brut).encode("utf-8")).hexdigest()[:12]
    return _ETATS[racine]


def _memo_disque(nom: str, racine, parties, cache_dir, calcul):
    """Cache pickle `<nom>-<etat>-<parties>` ; un etat perime est purge."""
    dossier = Path(cache_dir or CACHE_DIR)
    etat = etat_git(racine)
    suffixe = hashlib.sha1(f"{Path(racine).resolve()}\x00{parties}".encode("utf-8")).hexdigest()[:10]
    chemin = dossier / f"{nom}-{etat}-{suffixe}.pickle"
    if chemin.is_file():
        try:
            return pickle.loads(chemin.read_bytes())
        except (OSError, pickle.PickleError, EOFError, AttributeError, ImportError):
            pass
    valeur = calcul()
    dossier.mkdir(parents=True, exist_ok=True)
    for ancien in dossier.glob(f"{nom}-*-{suffixe}.pickle"):
        ancien.unlink(missing_ok=True)
    chemin.write_bytes(pickle.dumps(valeur, protocol=pickle.HIGHEST_PROTOCOL))
    return valeur


# --- 2. Index AST (exporte : check_forme_code.py --inspecter le reutilise) ---

def empreinte_corps(noeud) -> str:
    """sha1 de l'AST du corps sans docstring ni positions (reformatage neutre)."""
    corps = noeud.body[1:] if ast.get_docstring(noeud, clean=False) is not None else noeud.body
    return hashlib.sha1(ast.dump(ast.Module(body=corps, type_ignores=[])).encode("utf-8")).hexdigest()


def definitions(arbre) -> list:
    trouvees = []

    def visiter(noeud, prefixe):
        for enfant in ast.iter_child_nodes(noeud):
            if isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qual = prefixe + enfant.name
                kind = "classe" if isinstance(enfant, ast.ClassDef) else "fonction"
                trouvees.append(Def(qual, kind, enfant.lineno, enfant.end_lineno, empreinte_corps(enfant)))
                visiter(enfant, qual + ".")
            else:
                visiter(enfant, prefixe)
    visiter(arbre, "")
    return trouvees


def englobant(defs, ligne: int) -> str:
    """La definition la plus interne qui contient `ligne`, sinon `<module>`."""
    meilleur = None
    for d in defs:
        if d.debut <= ligne <= d.fin and (meilleur is None or d.fin - d.debut < meilleur.fin - meilleur.debut):
            meilleur = d
    return meilleur.qualname if meilleur else "<module>"


def _analyser(lot):
    """Worker (process pool) : [(rel, entree)] pour un lot de fichiers."""
    racine, rels, motif = lot
    filtre = re.compile(motif) if motif else None
    sortie = []
    for rel in rels:
        try:
            texte = (Path(racine) / rel).read_text(encoding="utf-8", errors="replace")
            arbre = ast.parse(texte)
        except (OSError, SyntaxError, ValueError):
            continue
        entree = {"defs": definitions(arbre), "lignes": texte.count("\n") + 1}
        if filtre is not None:
            refs = []
            for n in ast.walk(arbre):
                kind, valeur = (("nom", n.id) if isinstance(n, ast.Name) else ("attr", n.attr)
                                if isinstance(n, ast.Attribute) else ("chaine", n.value)
                                if isinstance(n, ast.Constant) and isinstance(n.value, str) else (None, ""))
                if kind and len(valeur) < 300 and filtre.search(valeur):
                    refs.append((kind, valeur, n.lineno))
            entree["refs"] = refs
            entree["noms_utilises"] = csa._noms_utilises(arbre) & {v for k, v, _ in refs if k != "chaine"}
        sortie.append((rel, entree))
    return sortie


def fichiers_py(racine=None, narrow=None) -> list:
    if narrow:
        rels = git_grep(narrow, PATHSPECS_PY, racine, liste=True)
    else:
        rels = git("ls-files", "--", *PATHSPECS_PY, racine=racine).split()
    return sorted(r for r in rels if "/migrations/" not in r and r.endswith(".py"))


def index(narrow=None, racine=None, *, cache=True, cache_dir=None) -> dict:
    """{rel: {'defs': [Def], 'lignes': n, ('refs', 'noms_utilises' si narrow)}}."""
    racine = Path(racine or ROOT)
    debut = time.perf_counter()

    def calcul():
        rels = fichiers_py(racine, narrow)
        lots = [(str(racine), rels[i:i + 200], narrow) for i in range(0, len(rels), 200)]
        if len(lots) > 2:
            with ProcessPoolExecutor() as pool:
                resultats = list(pool.map(_analyser, lots))
        else:
            resultats = [_analyser(lot) for lot in lots]
        return {rel: entree for lot in resultats for rel, entree in lot}
    valeur = _memo_disque("index", racine, narrow, cache_dir, calcul) if cache else calcul()
    CHRONO[f"index {narrow or 'complet'}"] = (len(valeur), round(time.perf_counter() - debut, 1))
    return valeur


# --- 3. Cibles `fichier::symbole` ---

def resoudre(cible: str, racine=None) -> tuple:
    """(rel, qualname, Def) — le fichier accepte aussi `apps/...` (django_core)."""
    racine = Path(racine or ROOT)
    fichier, sep, symbole = cible.partition("::")
    if not sep or not symbole:
        raise SystemExit(f"cible invalide « {cible} » : attendu fichier::symbole")
    rel = next((r for r in (fichier, f"{DJANGO_REL}/{fichier}") if (racine / r).is_file()), None)
    if rel is None:
        raise SystemExit(f"fichier introuvable : {fichier}")
    arbre = ast.parse((racine / rel).read_text(encoding="utf-8", errors="replace"))
    trouvee = next((d for d in definitions(arbre) if d.qualname == symbole), None)
    if trouvee is None:
        raise SystemExit(f"{rel} : symbole « {symbole} » introuvable")
    return Path(rel).as_posix(), symbole, trouvee


def _dotted(rel: str) -> str:
    rel = rel[len(DJANGO_REL) + 1:] if rel.startswith(DJANGO_REL + "/") else rel
    dotted = rel[:-3].replace("/", ".")
    return dotted[: -len(".__init__")] if dotted.endswith(".__init__") else dotted


# --- 4. Routes DRF et appels front (caches par SHA : la resolution coute ~1 min) ---

def carte_routes(cache_dir=None) -> dict:
    debut = time.perf_counter()

    def calcul():
        backend = cac.BackendRoutes()
        backend.build()
        vues = {}
        for route, (module, ref) in backend.views.items():
            source = backend._imports_of(module).get(ref[1]) if ref else None
            vues[route] = (module, ref, source)
        appels = cac.FrontendCalls(cac.frontend_files()).collect()
        return {"routes": set(backend.routes) | cac.fastapi_routes(), "vues": vues, "appels": appels}
    valeur = _memo_disque("routes", ROOT, "routes", cache_dir, calcul)
    CHRONO["routes+appels front"] = (len(valeur["routes"]), round(time.perf_counter() - debut, 1))
    return valeur


def _route_texte(route: tuple) -> str:
    return "/" + "/".join("<id>" if s in (cac.ANY, cac.PK) else s for s in route) + "/"


def routes_du_symbole(rel: str, qual: str, carte: dict) -> list:
    """[(route, verbes|None, vue)] servies par ce symbole (ViewSet, @action, vue)."""
    parties = qual.split(".")
    classe, methode = (parties[0], parties[-1]) if len(parties) > 1 else (parties[0], None)
    dotted, app = _dotted(rel), ".".join(_dotted(rel).split(".")[:2])
    trouvees = []
    for route, (module, ref, source) in carte["vues"].items():
        if not ref or ref[1] != classe:
            continue
        if source and not (source == dotted or dotted.startswith(source + ".")):
            continue
        if not source and not module.startswith(app):
            continue
        kind = ref[0]
        if kind in ("fonction", "classe"):
            trouvees.append((route, None, f"{ref[1]}"))
            continue
        detail = route[-1] == cac.ANY
        if methode in VERBES_PAR_HOOK:
            if kind != "viewset" or detail != (methode in HOOKS_DETAIL):
                continue
        elif methode is not None and methode not in HOOKS_TRANSVERSES:
            if kind != "action" or ref[2] != methode:
                continue  # une @action : seule sa route ; un helper : aucune
        route = route[:-1] + (cac.PK,) if detail else route
        verbes = VERBES_PAR_HOOK.get(methode)
        trouvees.append((route, frozenset(verbes) if verbes else None, f"{classe}.{ref[2]}"))
    return sorted(set(trouvees), key=lambda t: t[0])


def _specificite(appel: tuple, route: tuple) -> int:
    """Segment litteral egal = 2, trou face a un trou = 1 : `/x/${id}/` va au
    detail `<pk>`, pas a une @action `/x/kpis/` ; `/x/statistiques/` va a la
    route litterale, pas au detail (le faux appelant MesEquipesCard)."""
    trous = (cac.ANY, cac.PK)
    return sum(2 if a == b and a not in trous else 1 if a in trous and b in trous else 0
               for a, b in zip(appel, route))


_MOTS_CLES = {"if", "for", "while", "switch", "catch", "return", "function", "await", "else"}
_VERBE = re.compile(r"\.(get|post|put|patch|delete)\s*\(")
_DECL_PROP = re.compile(r"^\s+(?:async\s+)?([A-Za-z_$][\w$]*)\s*(?::\s*(?:async\s*)?(?:\(|function|[\w$]+\s*=>)"
                        r"|\([^)]*\)\s*\{)")
_DECL_TOP = re.compile(r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function\s*\*?\s*([A-Za-z_$][\w$]*)"
                       r"|(?:const|let|var|class)\s+([A-Za-z_$][\w$]*))")


def _lignes(rel: str, memo={}) -> list:
    if rel not in memo:
        memo[rel] = (ROOT / rel).read_text(encoding="utf-8", errors="replace").splitlines()
    return memo[rel]


def _verbe(rel: str, ligne: int, brut: str) -> str:
    lignes = _lignes(rel)
    courante = lignes[ligne - 1]
    position = courante.find(brut.split(cac.HOLE)[0].split("${")[0])
    avant = "\n".join(lignes[max(0, ligne - 3):ligne - 1] + [courante[:position if position >= 0 else None]])
    trouves = _VERBE.findall(avant)
    return trouves[-1].upper() if trouves else "?"


def _declaration(rel: str, ligne: int, top_seulement: bool = False) -> tuple:
    """(nom, membre) : propriete indentee `getX: () =>` (membre) ou `export const x =`."""
    lignes = _lignes(rel)
    for numero in range(ligne - 1, max(-1, ligne - 40), -1):
        texte = lignes[numero]
        for motif, membre in ((_DECL_TOP, False),) + (() if top_seulement else ((_DECL_PROP, True),)):
            m = motif.match(texte)
            nom = next((g for g in m.groups() if g), None) if m else None
            if nom and nom not in _MOTS_CLES and (not membre or texte[:1].isspace()):
                return nom, membre
    return None, False


def wrappers_front(routes: list, carte: dict) -> list:
    """Appels front dont la route LA PLUS SPECIFIQUE est une des nôtres (MesEquipesCard)."""
    nos_routes = {r for r, _, _ in routes}
    verbes = {r: v for r, v, _ in routes}
    trouves = []
    for rel, ligne, brut, montage in carte["appels"]:
        appel = cac.normalise_call(brut, montage)
        if appel is None:
            continue
        if not any(cac.compatible(appel, r) for r in nos_routes):
            continue  # filtre bon marche avant de comparer aux ~5 000 routes
        candidates = [r for r in carte["routes"] if len(r) == len(appel) and cac.compatible(appel, r)]
        meilleure = max(_specificite(appel, r) for r in candidates)
        gagnantes = {r for r in candidates if _specificite(appel, r) == meilleure} & nos_routes
        if not gagnantes:
            continue
        verbe = _verbe(rel, ligne, brut)
        if all(verbes[r] and verbe not in verbes[r] for r in gagnantes):
            continue
        nom, membre = _declaration(rel, ligne)
        trouves.append({"fichier": rel, "ligne": ligne, "verbe": verbe, "nom": nom, "membre": membre,
                        "route": _route_texte(sorted(gagnantes)[0])})
    return trouves


def _code_front(rel: str, memo={}) -> list:
    """Lignes du code SANS commentaires ni contenu de chaine (`scan_js`)."""
    if rel not in memo:
        memo[rel] = cac.scan_js((ROOT / rel).read_text(encoding="utf-8", errors="replace"))[2].splitlines()
    return memo[rel]


def consommateurs_front(depart: list, profondeur: int = 3) -> tuple:
    """(ecrans, intermediaires, chemins) : qui importe le module du nom ET le nomme ; un
    non-ecran (thunk Redux, hook, composant) propage par SA declaration (ATOT9)."""
    chemins, intermediaires, vus = {}, set(), set()
    frontiere = [(w["fichier"], w["nom"], w.get("membre", False), f"{Path(w['fichier']).name}::{w['nom']}")
                 for w in depart if w["nom"]]
    for _ in range(profondeur):
        suivante = []
        frontiere = [f for f in frontiere if (f[0], f[1]) not in vus]
        vus.update((f[0], f[1]) for f in frontiere)
        lignes = git_grep(sorted({f[1] for f in frontiere}), PATHSPECS_FRONT, mot=True, fixe=True) \
            if frontiere else []
        for fichier, nom, membre, chaine in frontiere:
            importe = re.compile(r"""['"/]%s(?:\.\w+)?['"]""" % re.escape(Path(fichier).stem))
            usage = re.compile((r"\.\s*%s(?![\w$])" if membre else r"(?<![\w$.])%s(?![\w$])") % re.escape(nom))
            for rel, ligne, texte in lignes:
                if rel == fichier or nom not in texte or ctc.est_test(rel) \
                        or not importe.search(_texte_imports(rel)):
                    continue
                code = _code_front(rel)
                if ligne > len(code) or not usage.search(code[ligne - 1]) or code[ligne - 1].lstrip().startswith(
                        ("import", "export {")):
                    continue
                if ctc.est_ecran(rel) and rel.endswith((".jsx", ".tsx")):
                    chemins.setdefault(rel, chaine)
                    continue
                intermediaires.add(rel)
                declaration, _ = _declaration(rel, ligne, top_seulement=True)
                if declaration:
                    suivante.append((rel, declaration, False, f"{Path(rel).name}::{declaration} ← {chaine}"))
        frontiere = suivante
    return sorted(chemins), sorted(intermediaires), chemins


def _texte_imports(rel: str) -> str:
    return "\n".join(ligne for ligne in _lignes(rel) if "import" in ligne or "from" in ligne)


# --- 5. Sous-commandes ---

def appelants(cible: str, racine=None) -> dict:
    rel, qual, _ = resoudre(cible, racine)
    nom = qual.split(".")[-1]
    classe = qual.split(".")[0] if "." in qual else None
    classe_vue = bool(classe and re.search(r"(ViewSet|View|APIView)$", classe))
    carte = carte_routes() if (classe_vue or not classe) else None
    routes = routes_du_symbole(rel, qual, carte) if carte else []
    est_vue = classe_vue and (bool(routes) or nom in VERBES_PAR_HOOK or nom in HOOKS_TRANSVERSES)
    python, chaines = [], []
    if not est_vue:
        idx = index(narrow=r"\b%s\b" % re.escape(nom), racine=racine)
        motif_classe = re.compile(r"\b%s\b" % re.escape(classe)) if classe else None
        for fichier, entree in sorted(idx.items()):
            if motif_classe and fichier != rel and not motif_classe.search(
                    (Path(racine or ROOT) / fichier).read_text(encoding="utf-8", errors="replace")):
                continue
            for kind, valeur, ligne in entree.get("refs", ()):
                if kind == "chaine" and (valeur == nom or valeur.endswith("." + nom)):
                    chaines.append({"symbole": f"{fichier}::{englobant(entree['defs'], ligne)}", "ligne": ligne,
                                    "valeur": valeur, "test": csa.est_test(Path(fichier))})
                elif kind != "chaine" and valeur == nom and nom in entree["noms_utilises"]:
                    ou = englobant(entree["defs"], ligne)
                    if fichier == rel and (ou == qual or ou.startswith(qual + ".")):
                        continue
                    python.append({"symbole": f"{fichier}::{ou}", "ligne": ligne,
                                   "test": csa.est_test(Path(fichier))})
    wrappers = wrappers_front(routes, carte) if routes else []
    ecrans, intermediaires, chemins = consommateurs_front(wrappers) if wrappers else ([], [], {})
    python = list({e["symbole"]: e for e in reversed(python)}.values())[::-1]  # 1 entree par symbole
    resultat = {"cible": f"{rel}::{qual}", "python": python, "chaines": chaines,
                "routes": [{"route": _route_texte(r), "verbes": sorted(v) if v else None, "vue": vue}
                           for r, v, vue in routes],
                "wrappers": wrappers, "intermediaires": intermediaires, "ecrans": ecrans, "chemins": chemins,
                "vue_drf": est_vue}
    resultat["texte"] = texte_appelants(resultat)
    return resultat


def texte_appelants(r: dict) -> str:
    prod = [e["symbole"] for e in r["python"] if not e["test"]]
    tests = [e for e in r["python"] if e["test"]]
    morceaux = []
    if r["vue_drf"]:
        morceaux.append("méthode de vue appelée par DRF (appelants = routes)")
    else:
        morceaux.append(f"Python {len(prod)} — " + (", ".join(f"`{s}`" for s in prod) or "aucun")
                        + (f" (+ {len(tests)} sites de test)" if tests else ""))
    if r["chaines"]:
        morceaux.append(f"références chaîne {len(r['chaines'])} — "
                        + ", ".join(f"`{c['symbole']}` (« {c['valeur']} »)" for c in r["chaines"]))
    if r["routes"]:
        noms = sorted({f"`{Path(w['fichier']).name}::{w['nom']}`" for w in r["wrappers"]})
        morceaux.append("routes " + ", ".join(f"{'/'.join(x['verbes'] or ['*'])} `{x['route']}`" for x in r["routes"])
                        + f" → wrappers front {len(noms)}" + (f" ({', '.join(noms)})" if noms else "")
                        + f" → {len(r['ecrans'])} écran(s)" + "".join(
                            f" ; `{Path(e).name}` ← {r['chemins'][e]}" for e in r["ecrans"]))
        morceaux[-1] = morceaux[-1].replace(" → 0 écran(s)", " → 0 écran")
    elif r["vue_drf"] or not r["python"]:
        morceaux.append("front : 0 écran (aucune route servie)")
    return "Appelants : " + " ; ".join(morceaux) + "."


def lecteurs_front(cle: str, racine=None) -> dict:
    par_fichier: dict = {}
    for rel, ligne, _ in git_grep(cle, PATHSPECS_FRONT, racine, mot=True, fixe=True):
        code = cac.scan_js((Path(racine or ROOT) / rel).read_text(encoding="utf-8", errors="replace"))[0]
        texte = code.splitlines()[ligne - 1] if ligne <= code.count("\n") + 1 else ""
        if re.search(r"(?<![\w$])%s(?![\w$])" % re.escape(cle), texte):
            par_fichier.setdefault(rel, []).append(ligne)
    lecteurs = [{"fichier": f, "lignes": l, "test": ctc.est_test(f)} for f, l in sorted(par_fichier.items())]
    prod = [x for x in lecteurs if not x["test"]]
    texte = (f"Appelants : lecteurs FRONT de `{cle}` {len(prod)} — "
             + (", ".join(f"`{Path(x['fichier']).name}:{','.join(map(str, x['lignes']))}`" for x in prod)
                or "0 écran")
             + (f" (+ {len(lecteurs) - len(prod)} test(s))" if len(lecteurs) > len(prod) else "") + ".")
    return {"cle": cle, "lecteurs": lecteurs, "texte": texte}


def ecrivains(cible: str, racine=None) -> dict:
    modele, sep, champ = cible.partition(".")
    if not sep:
        raise SystemExit(f"cible invalide « {cible} » : attendu Modele.champ")
    idx = index(narrow=r"\b%s\b" % re.escape(champ), racine=racine)
    trouves, champ_existe = [], False
    for rel, entree in sorted(idx.items()):
        if csa.est_test(Path(rel)) or not rel.startswith("backend/"):
            continue
        texte = (Path(racine or ROOT) / rel).read_text(encoding="utf-8", errors="replace")
        if not re.search(r"\b%s\b" % re.escape(modele), texte):
            continue
        arbre = ast.parse(texte)
        champ_existe = champ_existe or any(
            isinstance(n, ast.ClassDef) and n.name == modele and any(
                isinstance(a, ast.Assign) and any(getattr(t, "id", None) == champ for t in a.targets) for a in n.body)
            for n in arbre.body)
        for ligne, via in _sites_ecriture(arbre, champ, modele):
            ou = englobant(entree["defs"], ligne)
            if via == "clé de dict" and ou == "<module>":
                continue  # une table de module (`QUESTIONS['x'] = …`) n'ecrit aucun modele
            trouves.append({"symbole": f"{rel}::{ou}", "ligne": ligne, "via": via})
    texte = (f"Appelants : écrivains de `{cible}` {len({t['symbole'] for t in trouves})} — "
             + (", ".join(sorted({f"`{t['symbole']}` ({t['via']})" for t in trouves})) or "aucun")
             + ("" if champ_existe else f" ⚠ champ `{champ}` introuvable sur le modèle `{modele}`") + ".")
    return {"cible": cible, "ecrivains": trouves, "champ_existe": champ_existe, "texte": texte}


def _sites_ecriture(arbre, champ: str, modele: str = "") -> list:
    """[(ligne, via)] : `x.champ =`, `d['champ'] =`, kwargs ORM, setattr (litteral ou
    en boucle sur une liste qui contient le champ), `update_fields` / `defaults`."""
    sequences = (ast.List, ast.Tuple, ast.Set)
    listes = {t.id for n in arbre.body if isinstance(n, ast.Assign) and isinstance(n.value, sequences)
              and any(isinstance(e, ast.Constant) and e.value == champ for e in n.value.elts)
              for t in n.targets if isinstance(t, ast.Name)}
    sites = []
    for n in ast.walk(arbre):
        if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            for cible in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                if isinstance(cible, ast.Attribute) and cible.attr == champ:
                    sites.append((n.lineno, "affectation"))
                elif isinstance(cible, ast.Subscript) and isinstance(cible.slice, ast.Constant) \
                        and cible.slice.value == champ:
                    sites.append((n.lineno, "clé de dict"))
        elif isinstance(n, ast.Call):
            nom = cac._call_name(n)
            if (nom in APPELS_ECRITURE or nom == modele) and any(k.arg == champ for k in n.keywords):
                sites.append((n.lineno, f"{nom}(…)"))
            if nom == "setattr" and len(n.args) > 1 and getattr(n.args[1], "value", None) == champ:
                sites.append((n.lineno, "setattr"))
            for k in n.keywords:
                if k.arg in ("update_fields", "defaults") and champ in {
                        getattr(e, "value", None) for e in getattr(k.value, "elts", getattr(k.value, "keys", []))}:
                    sites.append((n.lineno, k.arg))
        elif isinstance(n, ast.For):
            source = n.iter
            via = source.id if isinstance(source, ast.Name) and source.id in listes else None
            if via is None and isinstance(source, (ast.List, ast.Tuple)) and any(
                    isinstance(e, ast.Constant) and e.value == champ for e in source.elts):
                via = "liste littérale"
            if via and any(isinstance(c, ast.Call) and cac._call_name(c) == "setattr" for c in ast.walk(n)):
                sites.append((n.lineno, f"setattr dynamique via {via}"))
    return sites


COMMANDES = {"appelants": appelants, "lecteurs-front": lecteurs_front, "ecrivains": ecrivains}


def projection(commande: str, r: dict) -> dict:
    """Ce que fige un golden : symboles et fichiers, JAMAIS de numero de ligne."""
    if commande == "appelants":
        return {"python": sorted({e["symbole"] for e in r["python"]}),
                "chaines": sorted({c["symbole"] for c in r["chaines"]}),
                "routes": sorted(x["route"] for x in r["routes"]),
                "wrappers": sorted({f"{w['fichier']}::{w['nom']}" for w in r["wrappers"]}),
                "ecrans": r["ecrans"], "nb_ecrans": len(r["ecrans"])}
    if commande == "lecteurs-front":
        return {"lecteurs": [x["fichier"] for x in r["lecteurs"]]}
    if commande == "ecrivains":
        return {"ecrivains": sorted({e["symbole"] for e in r["ecrivains"]}), "champ_existe": r["champ_existe"]}
    return {k: v for k, v in r.items() if k != "texte"}


# --- 6. CLI ---

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Clauses calculées des tâches d'audit (AMET80-82).")
    parser.add_argument("commande", choices=sorted(COMMANDES) + ["index"])
    parser.add_argument("argument", nargs="?")
    parser.add_argument("--json", action="store_true", help="sortie JSON")
    parser.add_argument("--narrow", help="index : motif git grep -E appliqué avant l'AST")
    args = parser.parse_args(argv)
    for flux in (sys.stdout, sys.stderr):
        getattr(flux, "reconfigure", lambda **_: None)(encoding="utf-8")
    debut = time.perf_counter()
    if args.commande == "index":
        idx = index(narrow=args.narrow)
        print(f"index : {len(idx)} fichiers, {sum(len(e['defs']) for e in idx.values())} définitions")
    elif not args.argument:
        parser.error(f"{args.commande} : argument manquant")
    else:
        resultat = COMMANDES[args.commande](args.argument)
        print(json.dumps(resultat, ensure_ascii=False, indent=1) if args.json else resultat["texte"])
    for etape, (taille, secondes) in CHRONO.items():
        print(f"[chrono] {etape} : {taille} éléments en {secondes} s", file=sys.stderr)
    print(f"[chrono] total : {round(time.perf_counter() - debut, 1)} s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    import audit_tache  # un seul espace de noms : pickles et workers stables
    sys.exit(audit_tache.main())
