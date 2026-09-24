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

# -- Racines (globales MUTABLES, relues a l'appel : un test les monkeypatch,
#    exactement comme test_check_api_contract.py fait pour `cac.ROOT`). ------
ROOT = Path(__file__).resolve().parent.parent
DJANGO_ROOT = ROOT / "backend" / "django_core"
VIEWS_SUBPATH = ("apps", "calepinage", "views")
VIEWS_MODULE_PREFIX = "apps.calepinage.views"
FRONTEND_SRC = ROOT / "frontend" / "src"
BASELINE_PATH = ROOT / "scripts" / "calepinage_actions_allow.txt"


def _module_dotted(chemin: Path) -> str:
    rel = chemin.relative_to(DJANGO_ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _fonctions(corps) -> list:
    return [n for n in corps if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def inventaire_actions_declarees() -> list:
    """[{fichier, ligne, module, fonction, url_path}, ...] — une entree par
    ``@action`` reellement posee dans ``apps/calepinage/views/*.py``.

    Lecture AST DIRECTE (jamais via BackendRoutes) : c'est la seule facon
    d'avoir la ligne exacte de la declaration. La resolution de route reste,
    elle, entierement a BackendRoutes (voir `routes_par_action`).
    """
    views_root = DJANGO_ROOT.joinpath(*VIEWS_SUBPATH)
    trouvees = []
    if not views_root.is_dir():
        return trouvees
    for chemin in sorted(views_root.glob("*.py")):
        if chemin.name == "__init__.py" or chemin.name.startswith(("test_", "tests_")):
            continue
        try:
            source = chemin.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            tree = ast.parse(source, filename=str(chemin))
        except SyntaxError:
            continue
        module = _module_dotted(chemin)
        fichier_relatif = chemin.relative_to(ROOT).as_posix() if chemin.is_relative_to(ROOT) \
            else chemin.as_posix()

        candidats = _fonctions(tree.body)
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                candidats.extend(_fonctions(node.body))

        for fonction in candidats:
            for detail, url_path, known in contract._actions_du_decorateur(fonction):
                trouvees.append({
                    "fichier": fichier_relatif,
                    "ligne": fonction.lineno,
                    "module": module,
                    "fonction": fonction.name,
                    "url_path": url_path,
                    "detail": detail,
                    "known": known,
                })
    return trouvees


def routes_par_action(backend: "contract.BackendRoutes") -> dict:
    """{(module, fonction): [route complete, ...]} pour chaque ``@action``
    dont le proprietaire est un module de `apps.calepinage.views` — lu
    directement dans `backend.views`, rempli par
    `BackendRoutes._expand_router` pour CHAQUE action d'un ViewSet monte
    (methodes ET fonctions greffees CALX2). Sert a confirmer qu'une action
    declaree est reellement ROUTEE (routee, PAS forcement consommee) : une
    `@action` qui n'apparait jamais ici est du code mort, jamais atteignable,
    donc jamais consomme par construction.
    """
    out: dict = {}
    for route, (owner, ref) in backend.views.items():
        if not (isinstance(ref, tuple) and len(ref) == 3 and ref[0] == "action"):
            continue
        if owner != VIEWS_MODULE_PREFIX and not owner.startswith(VIEWS_MODULE_PREFIX + "."):
            continue
        out.setdefault((owner, ref[2]), []).append(route)
    return out


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
    """Segments non-vides d'un `url_path`, groupes de capture DRF retires."""
    sans_groupes = _GROUPE_CONVERTISSEUR.sub("", url_path)
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
            base[m.group("cle")] = m.group("url_path")
    return base


def ecrire_base(constats: list, path: Path | None = None):
    path = path or BASELINE_PATH
    corps = "\n".join(
        f"{c['fichier']}:{c['ligne']}  {c['url_path']}  "
        f"# non consommee au 23/09/2026 (CALX381)"
        for c in sorted(constats, key=lambda c: (c["fichier"], c["ligne"]))
    )
    path.write_text(
        ENTETE_BASE + (corps + "\n" if corps else ""),
        encoding="utf-8", newline="\n",
    )


# ===========================================================================
# Analyse
# ===========================================================================

def analyse() -> tuple:
    """(constats_non_consommes, stats) — constats = liste des actions
    declarees non consommees (avant filtrage par le passif)."""
    backend = contract.BackendRoutes(DJANGO_ROOT)
    backend.build()
    routes = routes_par_action(backend)
    texte = texte_frontend()
    declarees = inventaire_actions_declarees()

    constats = []
    for item in declarees:
        routee = bool(routes.get((item["module"], item["fonction"])))
        if routee and action_consommee(item["url_path"], texte):
            continue
        constats.append(item)

    stats = {
        "actions": len(declarees),
        "non_consommees": len(constats),
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
        print(f"@action inventoriees dans apps/calepinage/views/ : {stats['actions']}")
        print(f"  dont sans consommateur (avant passif) : {stats['non_consommees']}")

    if stats["actions"] == 0:
        print("\nECHEC : aucune @action trouvee dans apps/calepinage/views/. "
              "Soit le chemin analyse a bouge, soit la lecture a cesse de "
              "fonctionner — dans les deux cas la garde a cesse de garder.")
        return 1

    cles_constats = {f"{c['fichier']}:{c['ligne']}" for c in constats}
    base = charger_base()

    if args.write_baseline:
        ajouts = cles_constats - set(base)
        amorce = not BASELINE_PATH.is_file()
        if ajouts and not (args.autoriser_croissance or amorce):
            print("REFUS : --write-baseline ne peut que RETRECIR la base.")
            print(f"{len(ajouts)} nouvelle(s) dette(s) voudraient y entrer :")
            for cle in sorted(ajouts)[:20]:
                print(f"  + {cle}")
            print("Branchez l'action sur un vrai consommateur, supprimez-la, ou "
                  "assumez la dette avec --autoriser-croissance.")
            return 1
        ecrire_base(constats)
        print(f"Base de reference reecrite : {BASELINE_PATH} "
              f"({len(constats)} entree(s), "
              f"{len(set(base) - cles_constats)} retiree(s)).")
        return 0

    nouveaux = [c for c in constats if f"{c['fichier']}:{c['ligne']}" not in base]
    corriges = set(base) - cles_constats

    if nouveaux:
        print(f"\nECHEC : {len(nouveaux)} @action calepinage SANS consommateur "
              f"(hors base de reference).\n")
        for c in nouveaux:
            print(f"  {c['fichier']}:{c['ligne']}  url_path={c['url_path']!r} "
                  f"({c['module']}.{c['fonction']})")
        print("\nQUE FAIRE :")
        print("  - branchez-la sur `calepinageApi.js` (ou un `window.open`/`href` "
              "reel pour un PDF/DXF/XLSX) ;")
        print("  - ou supprimez-la si elle est morte ;")
        print("  - ou, dette assumee a drainer plus tard, "
              "`--write-baseline --autoriser-croissance` (fondateur).")
        return 1

    print(f"OK : {stats['actions']} @action lue(s), aucune NOUVELLE sans "
          f"consommateur ({len(base)} dette(s) historique(s) gelee(s), dont "
          f"{len(corriges)} desormais branchee(s)).")
    if corriges:
        print("Ces dettes corrigees peuvent quitter la base : "
              "python scripts/check_calepinage_actions_consommees.py --write-baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
