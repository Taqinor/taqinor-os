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
import check_duplicats_litteraux as cdl  # noqa: E402
import check_ownership as cown  # noqa: E402
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
    racine, rels, motif, fixe = lot
    filtre = re.compile(re.escape(motif) if fixe else motif) if motif else None
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


def fichiers_py(racine=None, narrow=None, fixe=False) -> list:
    if narrow:
        rels = git_grep(narrow, PATHSPECS_PY, racine, liste=True, fixe=fixe)
    else:
        rels = git("ls-files", "--", *PATHSPECS_PY, racine=racine).split()
    return sorted(r for r in rels if "/migrations/" not in r and r.endswith(".py"))


def index(narrow=None, racine=None, *, fixe=False, cache=True, cache_dir=None) -> dict:
    """{rel: {'defs': [Def], 'lignes': n, ('refs', 'noms_utilises' si narrow)}}."""
    racine = Path(racine or ROOT)
    debut = time.perf_counter()

    def calcul():
        rels = fichiers_py(racine, narrow, fixe)
        lots = [(str(racine), rels[i:i + 200], narrow, fixe) for i in range(0, len(rels), 200)]
        if len(lots) > 2:
            with ProcessPoolExecutor() as pool:
                resultats = list(pool.map(_analyser, lots))
        else:
            resultats = [_analyser(lot) for lot in lots]
        return {rel: entree for lot in resultats for rel, entree in lot}
    valeur = _memo_disque("index", racine, (narrow, fixe), cache_dir, calcul) if cache else calcul()
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
        backend = cac.BackendRoutes(ROOT / DJANGO_REL)  # ROOT lu A L'APPEL (depots jetables des tests)
        backend.build()
        vues = {}
        for route, (module, ref) in backend.views.items():
            source = backend._imports_of(module).get(ref[1]) if ref else None
            vues[route] = (module, ref, source)
        appels = cac.FrontendCalls(cac.frontend_files()).collect()
        fastapi = cac.fastapi_routes(ROOT / "backend" / "fastapi_ia")
        return {"routes": set(backend.routes) | fastapi, "vues": vues, "appels": appels}
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
    if (ROOT, rel) not in memo:
        memo[(ROOT, rel)] = (ROOT / rel).read_text(encoding="utf-8", errors="replace").splitlines()
    return memo[(ROOT, rel)]


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
    if (ROOT, rel) not in memo:
        memo[(ROOT, rel)] = cac.scan_js((ROOT / rel).read_text(encoding="utf-8", errors="replace"))[2].splitlines()
    return memo[(ROOT, rel)]


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
    else:  # « 0 écran » toujours EXPLICITE (METHODE §C.2, clause Appelants)
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


# --- 6. Lot 2 (AMET81) : assertions existantes, lecteurs d'un sample, listes figees ---

PROPRES = ("scripts/tests/golden/audit_tache/", "scripts/tests/test_audit_tache.py", "scripts/audit_tache.py")
PATHSPECS_TESTS = ("backend", "frontend/src", "frontend/e2e", "scripts/tests", "apps/web/src")
_CODE_HTTP = re.compile(r"(?:status_code\s*(?:,|==|!=)\s*|HTTP_|assert\w*\(\s*)(\d{3})\b")
_ROLE = re.compile(r"""\brole\w*\s*=\s*['"]([\w-]+)['"]|\bRole\.([A-Z_]+)|(is_superuser)\s*=\s*True""")
_VERBE_TEST = re.compile(r"\.(get|post|put|patch|delete)\(")
_NOM_TEST_JS = re.compile(r"""\b(?:it|test|describe)\s*\(\s*(['"`])(.+?)\1""")
_TYPE_DE_CLE = re.compile(r"""(?m)^TYPE_DE_CLE\s*=\s*['"](par_ligne|par_symbole)['"]""")


def categorie(rel: str) -> str | None:
    """test-py | test-front | e2e | contract_sample | golden | None (pas une assertion ;
    les goldens et le test de CET outil citent les symboles par construction)."""
    if rel.startswith(PROPRES):
        return None
    if rel.endswith(".json"):
        return "contract_sample" if "/contract_samples/" in rel else "golden" if "golden" in rel else None
    if rel.startswith("frontend/e2e/"):
        return "e2e"
    if rel.endswith(".py"):
        return "test-py" if csa.est_test(Path(rel)) else None
    return "test-front" if ctc.est_test(rel) else None


def _tests_py(rel: str, lignes: set, racine) -> list:
    """[(Classe::test, debut, fin, setUp)] des fonctions de test qui contiennent
    une des lignes — ou, depuis une constante de module (`URL = '…'`), qui la nomment."""
    texte = (Path(racine) / rel).read_text(encoding="utf-8", errors="replace")
    arbre = ast.parse(texte)
    defs = definitions(arbre)
    constantes = {t.id for n in arbre.body if isinstance(n, ast.Assign) and n.lineno in lignes
                  for t in n.targets if isinstance(t, ast.Name)}
    trouves = []
    for d in defs:
        if d.kind != "fonction" or not d.qualname.split(".")[-1].startswith("test"):
            continue
        dedans = any(d.debut <= x <= d.fin for x in lignes)
        if not dedans and constantes:
            noeud = next(n for n in ast.walk(arbre) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                         and n.lineno <= d.debut <= n.end_lineno and n.name == d.qualname.split(".")[-1])
            dedans = any(isinstance(n, ast.Name) and n.id in constantes for n in ast.walk(noeud))
        if dedans:
            classe = d.qualname.rsplit(".", 1)[0] if "." in d.qualname else ""
            setup = next((x for x in defs if x.qualname == f"{classe}.setUp"), None)
            trouves.append((d.qualname.replace(".", "::"), d.debut, d.fin, setup))
    return trouves


def _affirme(rel: str, debut: int, fin: int, setup, racine) -> dict:
    """Codes HTTP, verbes et roles affirmes dans le corps (+ setUp pour les roles)."""
    lignes = (Path(racine) / rel).read_text(encoding="utf-8", errors="replace").splitlines()
    corps = "\n".join(lignes[debut - 1:fin])
    contexte = corps + ("\n".join(lignes[setup.debut - 1:setup.fin]) if setup else "")
    return {"codes": sorted({int(c) for c in _CODE_HTTP.findall(corps) if 100 <= int(c) < 600}),
            "verbes": sorted({v.upper() for v in _VERBE_TEST.findall(corps)}),
            "roles": sorted({next(g for g in m if g) for m in _ROLE.findall(contexte)})}


def _motif_route(route: tuple, carte: dict, hook: bool):
    """(litteral git grep, regex) d'une route dans un test, montage `/api/<x>/` libre.
    Hook de ViewSet : la base, sauf si suivie d'un segment frere litteral (`statistiques`)."""
    segs = route[2:]
    trou = r"[^/'\"\s]+"
    if not hook:
        corps = "/".join(trou if s in (cac.ANY, cac.PK) else re.escape(s) for s in segs)
        litteral = next(s for s in reversed(segs) if s not in (cac.ANY, cac.PK))
        return litteral, re.compile(r"(?<![\w-])" + corps + r"/?(?=['\"?#\s)]|$)")
    base = segs[:-1] if segs[-1] in (cac.ANY, cac.PK) else segs
    n = 2 + len(base)
    freres = {r[n] for r in carte["routes"] if r[2:n] == base and len(r) > n and r[n] not in (cac.ANY, cac.PK)}
    freres_detail = {r[n + 1] for r in carte["routes"] if r[2:n] == base and len(r) > n + 1
                     and r[n] in (cac.ANY, cac.PK) and r[n + 1] not in (cac.ANY, cac.PK)}
    motif = r"(?<![\w-])" + "/".join(map(re.escape, base)) + "/"
    if freres:
        motif += r"(?!(?:%s)(?:/|['\"?]))" % "|".join(map(re.escape, sorted(freres)))
    if freres_detail:
        motif += r"(?!%s/(?:%s)(?:/|['\"?]))" % (trou, "|".join(map(re.escape, sorted(freres_detail))))
    return "/".join(base) + "/", re.compile(motif)


def assertions_existantes(cible: str, anciens=(), racine=None) -> dict:
    racine = Path(racine or ROOT)
    rel, qual, _ = resoudre(cible, racine)
    sites: dict = {}   # rel -> {ligne: via}
    if racine.resolve() == ROOT.resolve():
        carte = carte_routes()
        for route, verbes, vue in routes_du_symbole(rel, qual, carte):
            litteral, motif = _motif_route(route, carte, hook=vue.endswith((".list", ".retrieve")))
            for f, ligne, texte in git_grep(litteral, PATHSPECS_TESTS, racine, fixe=True):
                if categorie(f) and motif.search(texte):
                    sites.setdefault(f, {})[ligne] = (f"route {_route_texte(route)}", verbes)
    nom = qual.split(".")[-1]
    if not re.search(r"(ViewSet|View)$", qual.split(".")[0]):
        for f, ligne, _ in git_grep(nom, PATHSPECS_TESTS, racine, fixe=True, mot=True):
            if categorie(f) and f != rel:
                sites.setdefault(f, {}).setdefault(ligne, (f"nomme `{nom}`", None))
    for ancien in anciens:
        for f, ligne, _ in git_grep(ancien, PATHSPECS_TESTS, racine, fixe=True):
            if categorie(f):
                sites.setdefault(f, {})[ligne] = (f"littéral « {ancien} »", None)
    assertions = []
    for f, par_ligne in sorted(sites.items()):
        cat = categorie(f)
        if cat == "test-py":
            for test, debut, fin, setup in _tests_py(f, set(par_ligne), racine):
                lignes = [x for x in par_ligne if debut <= x <= fin] or sorted(par_ligne)
                via = sorted({par_ligne[x][0] for x in lignes})
                affirme = _affirme(f, debut, fin, setup, racine)
                attendus = set().union(*[par_ligne[x][1] or set() for x in lignes])
                if attendus and affirme["verbes"] and not attendus & set(affirme["verbes"]) \
                        and not any(v.startswith("littéral") for v in via):
                    continue  # la route est appelee, mais pas avec un verbe que sert le symbole
                assertions.append({"test": f"{f}::{test}", "categorie": cat, "via": via, **affirme, "verdict": ""})
        else:
            noms = {_nom_test_js(f, x, racine) for x in par_ligne} if cat in ("test-front", "e2e") else {None}
            for nom_test in sorted(noms, key=str):
                assertions.append({"test": f"{f}::{nom_test}" if nom_test else f, "categorie": cat,
                                   "via": sorted({v for v, _ in par_ligne.values()}), "codes": [], "verbes": [],
                                   "roles": [], "verdict": ""})
    resume = (f"`{a['test']}` ({', '.join(a['verbes'] + [str(c) for c in a['codes']] + a['roles']) or a['categorie']})"
              for a in assertions)
    texte = ("Assertions existantes : " + (" → ⟨verdict⟩ ; ".join(resume) or "aucune")
             + " — verdict à remplir : « reste vert » ou « réaligner » (alors dans `Files:`).")
    return {"cible": f"{rel}::{qual}", "anciens": list(anciens), "assertions": assertions, "texte": texte}


def _nom_test_js(rel: str, ligne: int, racine) -> str | None:
    lignes = (Path(racine) / rel).read_text(encoding="utf-8", errors="replace").splitlines()
    for numero in range(min(ligne, len(lignes)) - 1, -1, -1):
        m = _NOM_TEST_JS.search(lignes[numero])
        if m:
            return m.group(2)
    return None


def lecteurs_sample(sample: str, racine=None) -> dict:
    """Fichiers de CODE qui chargent le sample (chaine hors commentaire / docstring)."""
    racine = Path(racine or ROOT)
    nom = Path(sample).name
    trouves = {}
    for f, ligne, _ in git_grep(nom, PATHSPECS_TESTS, racine, fixe=True):
        if f.endswith(".md") or f.endswith(nom) or f.startswith(PROPRES):
            continue
        texte = (racine / f).read_text(encoding="utf-8", errors="replace")
        if f.endswith(".py"):
            arbre = ast.parse(texte)
            docs = {id(n.value) for n in ast.walk(arbre) if isinstance(n, ast.Expr)}
            charge = any(isinstance(n, ast.Constant) and isinstance(n.value, str) and nom in n.value
                         and id(n) not in docs for n in ast.walk(arbre))
        else:
            charge = nom in "".join(t[3] for t in cac.scan_js(texte)[1])
        if charge:
            trouves.setdefault(f, []).append(ligne)
    lecteurs = [{"fichier": f, "lignes": lg, "categorie": categorie(f) or ("front" if f.startswith("frontend")
                 else "code")} for f, lg in sorted(trouves.items())]
    par_cat: dict = {}
    for x in lecteurs:
        par_cat[x["categorie"]] = par_cat.get(x["categorie"], 0) + 1
    texte = (f"Contrat partagé : `{nom}` chargé par {len(lecteurs)} fichier(s) ("
             + ", ".join(f"{k} {v}" for k, v in sorted(par_cat.items())) + ") — "
             + ", ".join(f"`{x['fichier']}`" for x in lecteurs) + ".")
    return {"sample": nom, "lecteurs": lecteurs, "texte": texte}


def listes_figees(fichier: str, racine=None) -> dict:
    """Baselines / allowlists / registres (scripts/, docs/ racine, api-contracts,
    OpenAPI) qui citent le fichier ou une route qu'il sert ; garde proprietaire,
    type de cle (declare `TYPE_DE_CLE` ou deduit) et commande de regeneration."""
    racine = Path(racine or ROOT)
    rel = fichier if (racine / fichier).is_file() else f"{DJANGO_REL}/{fichier}"
    court = rel[len(DJANGO_REL) + 1:] if rel.startswith(DJANGO_REL + "/") else rel
    cites = {}
    for f, ligne, texte in git_grep(court, ("scripts/*", "docs/*.md", "docs/*.yml"), racine, fixe=True):
        if "/" not in f.split("/", 1)[1] and "PLAN" not in f and Path(f).name not in ("audit_tache.py", "ci_guards.py"):
            cites.setdefault(f, []).append((ligne, texte))
    if racine.resolve() == ROOT.resolve():
        arbre = ast.parse((racine / rel).read_text(encoding="utf-8", errors="replace"))
        carte = carte_routes()
        for classe in (n.name for n in arbre.body if isinstance(n, ast.ClassDef)):
            for route, _, _ in routes_du_symbole(rel, classe, carte):
                motif = re.compile(re.escape("/" + "/".join(route)).replace(re.escape(cac.PK), r"(?:<[^>]*>|\{[^}]*\})")
                                   + r"/?(?=[\s\[]|$)")
                for f in (x for x in ("docs/api-contracts.md", "docs/openapi-schema.yml") if (racine / x).is_file()):
                    for ligne, texte in enumerate((racine / f).read_text(encoding="utf-8").splitlines(), 1):
                        if motif.search(texte):
                            cites.setdefault(f, []).append((ligne, texte))
    gardes = []
    for liste, lignes in sorted(cites.items()):
        proprietaires = [liste] if liste.endswith(".py") else sorted(
            g for g in git_grep(Path(liste).name, ("scripts/check_*.py",), racine, fixe=True, liste=True))
        if not proprietaires and liste.startswith("docs/"):
            continue  # un document qu'aucune garde ne lit n'est pas une liste figee
        for garde in proprietaires or ["(aucune garde ne la lit)"]:
            source = (racine / garde).read_text(encoding="utf-8", errors="replace") if garde.endswith(".py") else ""
            declare = _TYPE_DE_CLE.search(source)
            ecriture = re.search(r"--write[\w-]*", source)
            par_ligne = any(re.search(re.escape(court) + r"[:#]\d+", t) for _, t in lignes)
            deduit = "par_ligne" if par_ligne else "par_symbole"
            gardes.append({"garde": garde, "liste": liste, "citations": len(lignes),
                           "type_de_cle": declare.group(1) if declare else deduit, "declare": bool(declare),
                           "regeneration": f"python {garde} {ecriture.group(0)}" if ecriture else "à la main"})
    texte = "Listes figées : " + (" ; ".join(
        f"`{g['liste']}` ({g['citations']} citation(s)) ← `{Path(g['garde']).name}` ("
        + (g["type_de_cle"] if g["declare"] else f"TYPE_DE_CLE absent (déduit : {g['type_de_cle']})")
        + f") → régénérer : `{g['regeneration']}`" for g in gardes)
        or f"aucune (grep `{court}` dans scripts/ et docs/ : 0)") + "."
    return {"fichier": rel, "gardes": gardes, "texte": texte}


# --- 7. Lot 3 (AMET82) : jumeaux, emplacement, test canonique, tampon (API `inspecter`) ---

MUR = 2000

_TAMPON = re.compile(r"\(gen ([0-9a-f]{7,40}) ([^\s:()]+)::([\w.]+)#([0-9a-f]{8})\)")
_ID_TACHE = re.compile(r"(?:^|_)[a-z]+\d+[a-z]?(?=_)")


def _lignes_corps(rel: str, d, racine) -> list:
    lignes = (Path(racine) / rel).read_text(encoding="utf-8", errors="replace").splitlines()[d.debut - 1:d.fin]
    return [x.strip() for x in lignes[1:] if x.strip() and not x.strip().startswith(("#", '"', "'"))]


def jumeaux(cible: str, racine=None) -> dict:
    """Meme nom, corps AST identique (TOUS, jamais tronques), bloc litteral
    duplique, meme segment d'URL servi ailleurs, copies apps/web / PDF."""
    racine = Path(racine or ROOT)
    rel, qual, d = resoudre(cible, racine)
    nom = qual.split(".")[-1]
    corps = _lignes_corps(rel, d, racine)
    amorce = max(corps, key=len) if corps else None
    identiques = []
    candidats = index(narrow=amorce, fixe=True, racine=racine) if amorce else index(racine=racine)
    for f, e in sorted(candidats.items()):
        identiques += [{"symbole": f"{f}::{x.qualname}", "cible": f == rel and x.qualname == qual}
                       for x in e["defs"] if x.empreinte == d.empreinte and x.kind == d.kind]
    meme_nom = [f"{f}::{x.qualname}" for f, e in sorted(index(narrow=r"(def|class) +%s\b" % nom, racine=racine).items())
                for x in e["defs"] if x.qualname.split(".")[-1] == nom and x.empreinte != d.empreinte]
    blocs = []
    if racine.resolve() == ROOT.resolve():
        duplicats, _ = cdl.analyse(racine)
        for dup in duplicats:
            if any(b.fichier == rel and b.debut <= d.fin and b.fin >= d.debut for b in dup.blocs):
                blocs.append({"empreinte": dup.empreinte, "lignes": dup.nb_lignes,
                              "fichiers": [f for f in dup.fichiers if f != rel]})
    segments = []
    if racine.resolve() == ROOT.resolve() and re.search(r"(ViewSet|View)$", qual.split(".")[0]):
        carte = carte_routes()
        miens = routes_du_symbole(rel, qual, carte)
        derniers = {next(x for x in reversed(r) if x not in (cac.ANY, cac.PK)) for r, _, _ in miens}
        classe = qual.split(".")[0]
        for route, (module, ref, _) in sorted(carte["vues"].items()):
            if ref and ref[1] != classe and route[1] == "django" and route[-1] in derniers:
                segments.append(f"{_route_texte(route)} ({ref[1]})")
    copies = sorted({f for f, _, _ in git_grep(nom, ("apps/web/src", "backend/django_core/templates/pdf",
                                                     f"{DJANGO_REL}/apps/ventes/quote_engine"), racine,
                                               fixe=True, mot=True) if f != rel})
    par_fichier: dict = {}
    for j in identiques:
        f, q = j["symbole"].split("::", 1)
        par_fichier.setdefault(f, []).append(q)
    texte = (f"Jumeaux : corps identiques {len(identiques)} (cible comprise, liste complète) — "
             + " ; ".join(f"`{f}` : {', '.join(qs)}" for f, qs in par_fichier.items())
             + f" ; même nom, autre corps {len(meme_nom)}"
             + (f" ; blocs littéraux dupliqués {len(blocs)} (" + ", ".join(
                 f"{b['lignes']} l. avec {', '.join(f'`{x}`' for x in b['fichiers'])}" for b in blocs) + ")" if blocs
                else " ; blocs littéraux dupliqués 0")
             + (f" ; même segment d'URL servi ailleurs : {', '.join(f'`{x}`' for x in segments)}" if segments else "")
             + (f" ; copies apps/web / PDF : {', '.join(f'`{x}`' for x in copies)}" if copies else "")
             + " → verdict : « traité ici, survivant X » / « autre geste »." + "\n" + tampon(rel, qual, d, racine))
    return {"cible": f"{rel}::{qual}", "corps_identiques": identiques, "nb_corps_identiques": len(identiques),
            "meme_nom": meme_nom, "blocs_litteraux": blocs, "meme_segment_url": segments, "copies": copies,
            "texte": texte}


def _spl_ouvertes(rel: str, nom: str) -> list:
    court = rel[len(DJANGO_REL) + 1:] if rel.startswith(DJANGO_REL + "/") else rel
    # Le symbole DEPLACE est dans le titre ou dans la liste `cible ← N symboles : a, b, nom ;`.
    deplace = re.compile(r"(?:^[^:]*|←[^;]*)\b%s\b" % re.escape(nom))
    return sorted(t.identifiant for t in ctc.lire_taches() if t.identifiant.startswith("SPL") and not t.close
                  and "deplac" in t.normalise.split(":", 1)[0] and deplace.search(t.texte)
                  and (court in t.texte or court.split("/", 1)[-1] in t.texte))


def emplacement(cible: str, racine=None) -> dict:
    racine = Path(racine or ROOT)
    rel, qual, d = resoudre(cible, racine)
    total = (racine / rel).read_text(encoding="utf-8", errors="replace").count("\n") + 1
    spl = _spl_ouvertes(rel, qual.split(".")[-1]) if racine.resolve() == ROOT.resolve() else []
    texte = (f"Emplacement : `{rel}::{qual}` ({total} l. ; symbole l. {d.debut}-{d.fin}, {d.fin - d.debut + 1} l."
             + (f" ; ≥ {MUR} l. = mur : point d'insertion après `{qual}` (l. {d.fin}) ou cible d'extraction"
                if total >= MUR else "")
             + (f" ; SPL ouvert(s) qui déplace(nt) le symbole : {', '.join(spl)} → `@after: {', '.join(spl)}`"
                if spl else "") + ").")
    return {"cible": f"{rel}::{qual}", "lignes": total, "debut": d.debut, "fin": d.fin, "mur": total >= MUR,
            "spl": spl, "texte": texte}


def test_canonique(cible: str, racine=None) -> dict:
    """Modules de test EXISTANTS classes : references au symbole, puis a ses
    appelants, puis au theme (nom des fichiers appelants) ; proprietaire de chacun."""
    racine = Path(racine or ROOT)
    rel, qual, _ = resoudre(cible, racine)
    nom = qual.split(".")[-1]
    app = "/".join(rel.split("/")[:4]) if rel.startswith(DJANGO_REL + "/apps/") else str(Path(rel).parent.as_posix())
    candidats = {f for f in git("ls-files", "--", app, racine=racine).split() if f.endswith(".py")
                 and csa.est_test(Path(f))}
    candidats |= {f for f, _, _ in git_grep(nom, ("backend",), racine, fixe=True, mot=True) if csa.est_test(Path(f))}
    idx = index(narrow=r"\b%s\b" % re.escape(nom), racine=racine)
    appelants_ = {englobant(e["defs"], ln).split(".")[0] for f, e in idx.items() if not csa.est_test(Path(f))
                  for k, v, ln in e.get("refs", ()) if k != "chaine" and v == nom} - {"<module>", qual.split(".")[0]}
    themes = {Path(f).stem for f, e in idx.items() if not csa.est_test(Path(f)) and f != rel} | {Path(rel).stem}
    themes -= {"services", "views", "models", "utils", "selectors", "__init__"}
    # Affinite d'identifiant : `tests_fg328_kitting.py` teste les vues « FG328 » qui appellent le symbole.
    entetes = [(racine / f).read_text(encoding="utf-8", errors="replace")[:3000] for f in idx if f != rel
               and not csa.est_test(Path(f))] + [_corps_texte(rel, qual, racine)]
    ids = {i.lower() for t in entetes for i in re.findall(r"\b([A-Z]{2,}\d+)\b", t)}
    registre = cown.charger_registre(racine / "docs" / "ownership.yml", racine=racine) \
        if (racine / "docs" / "ownership.yml").is_file() else None
    classes = []
    for f in sorted(candidats):
        texte = (racine / f).read_text(encoding="utf-8", errors="replace")
        score = (100 * len(re.findall(r"\b%s\b" % re.escape(nom), texte))
                 + 10 * sum(len(re.findall(r"\b%s\b" % re.escape(a), texte)) for a in appelants_)
                 + sum(5 for t in themes if t in Path(f).stem)
                 + 50 * len(ids & set(re.split(r"[_.]", Path(f).stem))))
        if score:
            classes.append({"module": f, "score": score, "id_de_tache": bool(_ID_TACHE.search(Path(f).stem)),
                            "proprietaire": cown.proprietaire(registre, f) if registre else None})
    classes.sort(key=lambda c: (-c["score"], c["module"]))
    texte = ("Test rouge d'abord : module EXISTANT proposé "
             + (f"`{classes[0]['module']}` (propriétaire {classes[0]['proprietaire']})" if classes else "aucun")
             + "".join(f" ; puis `{c['module']}`" for c in classes[1:5])
             + " — un nouveau fichier seulement avec « Nouveau fichier car : ».")
    return {"cible": f"{rel}::{qual}", "modules": classes, "texte": texte}


def _corps_texte(rel: str, qual: str, racine) -> str:
    d = resoudre(f"{rel}::{qual}", racine)[2]
    return "\n".join((Path(racine) / rel).read_text(encoding="utf-8", errors="replace").splitlines()[d.debut - 1:d.fin])


def tampon(rel: str, qual: str, d, racine=None) -> str:
    sha = git("rev-parse", "--short=9", "HEAD", racine=racine).strip()
    return f"(gen {sha} {rel}::{qual}#{d.empreinte[:8]})"


def verifier(identifiant: str, racine=None) -> dict:
    """Fraicheur des tampons d'une tache : le symbole a-t-il change depuis ?"""
    tache = next((t for t in ctc.lire_taches() if t.identifiant == identifiant), None)
    if tache is None:
        raise SystemExit(f"tâche {identifiant} introuvable dans les plans")
    etats = []
    for sha, rel, qual, h8 in _TAMPON.findall(tache.texte):
        try:
            _, _, d = resoudre(f"{rel}::{qual}", racine)
            etat = "à jour" if d.empreinte.startswith(h8) else "périmée"
        except SystemExit:
            etat = "périmée"
        etats.append({"tampon": f"{rel}::{qual}#{h8}", "gen": sha, "etat": etat})
    perimee = any(e["etat"] == "périmée" for e in etats)
    texte = (f"{identifiant} : " + ("; ".join(f"{e['tampon']} (gen {e['gen']}) {e['etat']}" for e in etats)
                                    or "aucun tampon `(gen <sha> fichier::symbole#hash8)` (manuel : non vérifiable)"))
    return {"tache": identifiant, "tampons": etats, "perimee": perimee, "texte": texte}


def inspecter(cible: str, racine=None) -> dict:
    """API pour `check_forme_code.py --inspecter` (AMET85) : emplacement,
    jumeaux et test canonique d'un symbole, en une passe sur le meme index."""
    r = {"emplacement": emplacement(cible, racine), "jumeaux": jumeaux(cible, racine),
         "test_canonique": test_canonique(cible, racine)}
    r["texte"] = "\n".join(x["texte"] for x in r.values())
    return r


CLAUSES = {"appelants": "appelants", "assertions existantes": "assertions-existantes", "jumeaux": "jumeaux",
           "listes figees": "listes-figees", "emplacement": "emplacement",
           "test rouge d'abord": "test-canonique", "contrat partage": "lecteurs-sample"}


COMMANDES = {"appelants": appelants, "lecteurs-front": lecteurs_front, "ecrivains": ecrivains,
             "assertions-existantes": assertions_existantes, "lecteurs-sample": lecteurs_sample,
             "listes-figees": listes_figees, "jumeaux": jumeaux, "emplacement": emplacement,
             "test-canonique": test_canonique, "inspecter": inspecter}


def projection(commande: str, r: dict) -> dict:
    """Ce que fige un golden : symboles et fichiers, JAMAIS de numero de ligne."""
    if commande == "appelants":
        return {"python": sorted({e["symbole"] for e in r["python"]}),
                "chaines": sorted({c["symbole"] for c in r["chaines"]}),
                "routes": sorted(x["route"] for x in r["routes"]),
                "wrappers": sorted({f"{w['fichier']}::{w['nom']}" for w in r["wrappers"]}),
                "ecrans": r["ecrans"], "nb_ecrans": len(r["ecrans"])}
    if commande in ("lecteurs-front", "lecteurs-sample"):
        return {"lecteurs": [x["fichier"] for x in r["lecteurs"]]}
    if commande == "ecrivains":
        return {"ecrivains": sorted({e["symbole"] for e in r["ecrivains"]}), "champ_existe": r["champ_existe"]}
    if commande == "assertions-existantes":
        return {"assertions": sorted({a["test"] for a in r["assertions"]})}
    if commande == "jumeaux":
        return {"corps_identiques": sorted(j["symbole"] for j in r["corps_identiques"]),
                "nb_corps_identiques": r["nb_corps_identiques"], "copies": r["copies"]}
    if commande == "emplacement":
        return {"mur": r["mur"], "spl": r["spl"]}
    if commande == "test-canonique":
        return {"modules": [m["module"] for m in r["modules"]][:1]}
    if commande == "listes-figees":
        return {"gardes": sorted({f"{g['liste']} <- {g['garde']} ({g['type_de_cle']})" for g in r["gardes"]})}
    return {k: v for k, v in r.items() if k != "texte"}


# --- 6. CLI ---

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Clauses calculées des tâches d'audit (AMET80-82).")
    parser.add_argument("elements", nargs="*", help="<commande> <argument> (avec --clause : <argument>)")
    parser.add_argument("--json", action="store_true", help="sortie JSON")
    parser.add_argument("--narrow", help="index : motif git grep -E appliqué avant l'AST")
    parser.add_argument("--anciens", nargs="*", default=[], help="assertions-existantes : anciens littéraux")
    parser.add_argument("--clause", help="libellé de clause (Appelants, Jumeaux, Emplacement…) : texte à coller")
    parser.add_argument("--verifier", metavar="ID", help="fraîcheur des tampons (gen …) d'une tâche ; 1 si périmée")
    parser.add_argument("--racine", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    for flux in (sys.stdout, sys.stderr):
        getattr(flux, "reconfigure", lambda **_: None)(encoding="utf-8")
    debut, racine = time.perf_counter(), args.racine
    if args.verifier:
        resultat = verifier(args.verifier, racine)
        print(resultat["texte"])
        return 1 if resultat["perimee"] else 0
    elements = ([CLAUSES.get(ctc.normaliser(args.clause).strip(), args.clause)] if args.clause else []) + args.elements
    if not elements or elements[0] not in list(COMMANDES) + ["index"]:
        parser.error(f"commande inconnue : {elements[:1]} (attendu : {', '.join(sorted(COMMANDES))}, index)")
    if elements[0] == "index":
        idx = index(narrow=args.narrow)
        print(f"index : {len(idx)} fichiers, {sum(len(e['defs']) for e in idx.values())} définitions")
    elif len(elements) < 2:
        parser.error(f"{elements[0]} : argument manquant")
    else:
        options = {"anciens": args.anciens} if elements[0] == "assertions-existantes" else {}
        resultat = COMMANDES[elements[0]](elements[1], racine=racine, **options)
        print(json.dumps(resultat, ensure_ascii=False, indent=1) if args.json else resultat["texte"])
    for etape, (taille, secondes) in CHRONO.items():
        print(f"[chrono] {etape} : {taille} éléments en {secondes} s", file=sys.stderr)
    print(f"[chrono] total : {round(time.perf_counter() - debut, 1)} s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    import audit_tache  # un seul espace de noms : pickles et workers stables
    sys.exit(audit_tache.main())
