#!/usr/bin/env python3
"""GARDE CI (stage-names) — ACAL348 : chaque route GET du calepinage est sous contrat.

CLASSE C-ACAL-017 : la LISTE des calepinages n'avait aucun échantillon de
contrat avant ACAL11 (l'écran mockait une forme que le serveur ne produisait
jamais), et `check_api_shapes.py` s'ABSTIENT sur les ViewSets. Cette garde
énumère les routes GET du module — `CalepinageViewSet` (liste + détail),
`@action` GET (méthodes ET fonctions greffées par `views/rattachements.py` /
`_attacher`), vues `APIView` de `urls.py` (`parametres/`, `moteur/`…) — et
échoue en nommant chaque route dont AUCUN `contract_samples/*.json` ne cite
l'endpoint (champ `endpoint`, verbe facultatif = GET).

Les routes qui servent un FICHIER (pdf, svg, dxf, xlsx, csv, png, `fichier/`)
sont exemptées par leur extension/suffixe (EXTENSIONS_FICHIER).
Passif gelé : `scripts/routes_sous_contrat_allow.txt` (une route par ligne,
`GET calepinages/<>/…`), ne peut que RÉTRÉCIR (`--write-baseline` refuse
d'ajouter) ; une clé morte fait échouer la garde.

Usage :
    python scripts/check_calepinage_routes_sous_contrat.py [--stats] [--write-baseline]
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
TYPE_DE_CLE = "par_symbole"  # AMET100 — cle de contenu `fichier::symbole` (jamais un numero de ligne)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _cliquet  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP = Path("backend") / "django_core" / "apps" / "calepinage"
BASELINE = ROOT / "scripts" / "routes_sous_contrat_allow.txt"
EXTENSIONS_FICHIER = (".pdf", ".svg", ".dxf", ".xlsx", ".csv", ".png")
SUFFIXES_FICHIER = ("fichier",)
VIEWSETS_RACINE = {"CalepinageViewSet": "calepinages",
                   "GabaritDossierViewSet": "gabarits-dossiers"}
ENTETE = (
    "# Base de reference de check_calepinage_routes_sous_contrat.py (ACAL348).\n"
    "# Une ligne = une route GET du module calepinage qu'AUCUN contract_samples\n"
    "# ne cite. DETTE : ne peut que RETRECIR (--write-baseline refuse d'ajouter).\n"
)
_PREFIXE_API = re.compile(r"^/?api/django/calepinage/")
_GROUPE = re.compile(r"\(\?P<[^>]+>[^)]*\)|<[^>]+>|\{[^}]*\}")


def normaliser(chemin: str) -> str:
    """Forme canonique d'un chemin : sans préfixe d'API, identifiants -> <>."""
    chemin = chemin.replace(chr(92), "")
    chemin = _PREFIXE_API.sub("", chemin.strip())
    chemin = _GROUPE.sub("<>", chemin)
    segments = [("<>" if re.fullmatch(r"\d+", s) else s)
                for s in chemin.split("/") if s]
    return "/".join(segments)


def est_fichier(chemin_normalise: str) -> bool:
    dernier = chemin_normalise.rsplit("/", 1)[-1]
    return dernier.endswith(EXTENSIONS_FICHIER) or dernier in SUFFIXES_FICHIER


def _methodes(deco: ast.Call) -> list:
    for kw in deco.keywords:
        if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
            return [e.value.lower() for e in kw.value.elts
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return ["get"]


def _actions(fonction) -> list:
    """[(detail, url_path, methodes)] des @action d'une fonction."""
    out = []
    for deco in fonction.decorator_list:
        if not (isinstance(deco, ast.Call) and (
                (isinstance(deco.func, ast.Name) and deco.func.id == "action")
                or (isinstance(deco.func, ast.Attribute) and deco.func.attr == "action"))):
            continue
        detail, url_path = False, fonction.name
        for kw in deco.keywords:
            if kw.arg == "detail" and isinstance(kw.value, ast.Constant):
                detail = bool(kw.value.value)
            elif kw.arg == "url_path" and isinstance(kw.value, ast.Constant):
                url_path = str(kw.value.value)
        out.append((detail, url_path, _methodes(deco)))
    return out


def _fichiers_vues(root: Path) -> list:
    dossier = root / APP / "views"
    return [p for p in sorted(dossier.glob("*.py")) if p.name != "__init__.py"
            and not p.name.startswith(("test_", "tests_"))] if dossier.is_dir() else []


def routes_get(root: Path = ROOT) -> set:
    """Ensemble des routes GET normalisées du module."""
    routes = set()
    classes_get = set()  # APIView avec une méthode get
    for chemin in _fichiers_vues(root):
        try:
            arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for noeud in arbre.body:
            if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # fonction greffée : par défaut sur le CalepinageViewSet
                for detail, url_path, methodes in _actions(noeud):
                    if "get" in methodes:
                        base = "calepinages/<>/" if detail else "calepinages/"
                        routes.add(normaliser(base + url_path))
            elif isinstance(noeud, ast.ClassDef):
                methodes_def = {n.name for n in noeud.body
                                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
                if "get" in methodes_def:
                    classes_get.add(noeud.name)
                racine = VIEWSETS_RACINE.get(noeud.name)
                if racine:
                    routes.add(normaliser(racine + "/"))
                    routes.add(normaliser(racine + "/<>/"))
                for n in noeud.body:
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for detail, url_path, methodes in _actions(n):
                            if "get" in methodes:
                                base = racine or "calepinages"
                                routes.add(normaliser(
                                    base + ("/<>/" if detail else "/") + url_path))
    urls = root / APP / "urls.py"
    if urls.is_file():
        try:
            arbre = ast.parse(urls.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            arbre = None
        for noeud in ast.walk(arbre) if arbre else []:
            if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
                    and noeud.func.id == "path" and len(noeud.args) >= 2
                    and isinstance(noeud.args[0], ast.Constant)
                    and isinstance(noeud.args[0].value, str)):
                vue = noeud.args[1]
                if (isinstance(vue, ast.Call) and isinstance(vue.func, ast.Attribute)
                        and vue.func.attr == "as_view"
                        and isinstance(vue.func.value, ast.Name)
                        and vue.func.value.id in classes_get):
                    routes.add(normaliser(noeud.args[0].value))
    return {r for r in routes if r}


def endpoints_contrats(root: Path = ROOT) -> set:
    """Tous les chemins cités par un champ `endpoint` (à tout niveau)."""
    trouves = set()

    def _marche(valeur):
        if isinstance(valeur, dict):
            for cle, sous in valeur.items():
                if cle == "endpoint" and isinstance(sous, str):
                    chemin = sous.split(None, 1)[-1] if " " in sous.strip() else sous
                    trouves.add(normaliser(chemin))
                else:
                    _marche(sous)
        elif isinstance(valeur, list):
            for sous in valeur:
                _marche(sous)

    for p in sorted((root / APP / "contract_samples").glob("*.json")):
        try:
            _marche(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return trouves


def dettes(root: Path = ROOT) -> set:
    cites = endpoints_contrats(root)
    return {f"GET {r}" for r in routes_get(root)
            if not est_fichier(r) and r not in cites}


def verifier(trouvees: set, base: set) -> list:
    return _cliquet.comparer(
        trouvees, base, nom_fichier="routes_sous_contrat_allow.txt",
        decrire=lambda c: (f"{c} : route GET du calepinage sans contract_samples/*.json "
                           "qui cite son endpoint — ajoutez l'échantillon."))


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--autoriser-croissance", action="store_true")
    args = ap.parse_args(argv)
    trouvees = dettes()
    routes = routes_get()
    if not routes:
        print("ÉCHEC : aucune route GET lue — la garde a cessé de garder.")
        return 1
    if args.stats:
        print(f"routes GET : {len(routes)} ; sans contrat (hors fichiers) : {len(trouvees)}")
        for r in sorted(trouvees):
            print("  " + r)
    if args.write_baseline:
        # Les chemins contiennent « <> » : séparateur de clé = ligne entière.
        try:
            _cliquet.ecrire(BASELINE, {c.replace(" ", "~") for c in trouvees}, ENTETE,
                            "ACAL348 route sans contrat",
                            autoriser_croissance=args.autoriser_croissance)
        except ValueError as exc:
            print("REFUS : " + str(exc))
            return 1
        print(f"Base réécrite ({len(trouvees)} entrée(s)).")
        return 0
    base = {c.replace("~", " ") for c in _cliquet.charger(BASELINE)}
    erreurs = verifier(trouvees, base)
    if erreurs:
        print("check_calepinage_routes_sous_contrat: ÉCHEC")
        for e in erreurs:
            print("  - " + e)
        return 1
    print(f"check_calepinage_routes_sous_contrat: OK — {len(routes)} route(s) GET, "
          f"{len(trouvees)} dette(s) gelée(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
