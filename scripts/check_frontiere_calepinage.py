#!/usr/bin/env python3
"""GARDE CI (stage-names) — CALX372 : la frontière du module calepinage
contre les couplages interdits, depuis une base MESURÉE.

CONSTAT. La décision D-CALX 2 (21/09/2026) interdit tout couplage NEUF de
`apps/calepinage` vers les appels d'offres (`apps.ao`) et la GED
(`apps.ged`) — l'existant reste tel quel jusqu'à son détachement — et le
lot 7 ajoute des lectures croisées vers les visites techniques, qui doivent
passer par `apps.visites.selectors`, jamais par `apps.visites.models`. Aucune
garde ne le tenait : `test_calx2_rattachements` ne greppe que
`views/rattachements.py`, et l'import-linter ne couvre que
`apps.calepinage.models`.

MESURE DU JOUR (24/09/2026, CETTE tâche, sur `dev-calx-m5`) : le constat de
la tâche PLAN2 (16 fichiers `apps.ao` + 4 `apps.ged`) est PÉRIMÉ — SOLMVP15 a
détaché le module d'appels d'offres. Il reste exactement QUATRE instructions
d'import de `apps.ged`, toutes fonction-locales, et ZÉRO de `apps.ao` ou de
`apps.visites.models` :
  services/pack_technique.py:224 et :351, services/reglementaire.py:604
  (`apps.ged.services` — dépôt et fusion PDF) ; services/terre.py:125
  (`apps.ged.selectors`). C'est la base écrite par `--write-baseline`.

CE QUE CETTE GARDE FAIT. AST sur chaque `.py` de `apps/calepinage/**` HORS
TESTS (un dossier `tests/`, un `test_*.py`/`tests_*.py` est ignoré : un test
a le droit de fabriquer une visite ou un document). Sont relevés :
  * `import apps.ao…` / `import apps.ged…` / `import apps.visites.models…` ;
  * `from apps.ao… import …`, `from apps.ged… import …`,
    `from apps.visites.models import …` — et `from apps import ged`,
    `from apps.visites import models`, qui visent les mêmes modules ;
  * `importlib.import_module('apps.ao…')` / `__import__('apps.ged…')` avec un
    nom LITTÉRAL (sinon la garde se contournerait en une ligne).
`apps.visites.selectors` est ADMIS sans base : c'est LA porte de lecture.

Chaque constat est `fichier:ligne:module` (fichier relatif au dépôt). Il doit
figurer dans `scripts/frontiere_calepinage_allow.txt` ; un import NEUF
rougit en citant `fichier:ligne`, et une ligne de base devenue INUTILE
(import retiré, ou déplacé) rougit aussi — la base ne ment jamais.

LA BASE NE PEUT QUE RÉTRÉCIR. `--write-baseline` réécrit la base depuis
l'état du jour, mais REFUSE toute croissance : pour chaque couple
(fichier, module), le nombre d'imports ne peut pas dépasser celui de la base
(un import simplement DÉPLACÉ de quelques lignes se ré-enregistre ; un
import NOUVEAU, non). Ajouter une dette exige `--autoriser-croissance`,
drapeau réservé au fondateur, visible en revue.

Usage
-----
    python scripts/check_frontiere_calepinage.py
    python scripts/check_frontiere_calepinage.py --write-baseline
    python scripts/check_frontiere_calepinage.py --stats
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from collections import Counter
from pathlib import Path

# -- Racines (globales MUTABLES, relues à l'appel : le test les remplace). --
ROOT = Path(__file__).resolve().parent.parent
CALEPINAGE_DIR = ROOT / "backend" / "django_core" / "apps" / "calepinage"
BASELINE_PATH = ROOT / "scripts" / "frontiere_calepinage_allow.txt"

#: Les modules dont un import NEUF est interdit (D-CALX 2, lot 7).
MODULES_INTERDITS = ("apps.ao", "apps.ged", "apps.visites.models")

#: La porte ADMISE sans base (documentaire : elle ne tombe sous aucun
#: préfixe interdit, ce tuple dit POURQUOI elle passe).
MODULES_ADMIS = ("apps.visites.selectors",)

_FONCTIONS_IMPORT = ("import_module", "__import__")


def interdit(module: str) -> bool:
    """Vrai si ``module`` est un module interdit ou l'un de ses sous-modules."""
    return any(module == prefixe or module.startswith(prefixe + ".")
               for prefixe in MODULES_INTERDITS)


def _est_un_test(chemin: Path) -> bool:
    relatif = chemin.relative_to(CALEPINAGE_DIR)
    if "tests" in relatif.parts[:-1]:
        return True
    return chemin.name.startswith(("test_", "tests_")) or chemin.name == "tests.py"


def fichiers() -> list:
    """Les ``.py`` de ``apps/calepinage/**`` hors tests, dans un ordre stable."""
    if not CALEPINAGE_DIR.is_dir():
        return []
    return sorted(chemin for chemin in CALEPINAGE_DIR.rglob("*.py")
                  if not _est_un_test(chemin))


def _nom_de_fonction(appel: ast.Call) -> str:
    fonction = appel.func
    if isinstance(fonction, ast.Name):
        return fonction.id
    if isinstance(fonction, ast.Attribute):
        return fonction.attr
    return ""


def imports_interdits(source: str) -> list:
    """``[(ligne, module)]`` — chaque import interdit d'un texte Python.

    Un ``from X import a, b`` compte UNE fois (sa ligne, le module ``X``) ;
    ``from apps import ged`` / ``from apps.visites import models`` comptent
    sous le module réellement visé (``apps.ged``, ``apps.visites.models``).
    Un texte illisible (syntaxe future) rend ``[]`` : la garde n'accuse
    jamais ce qu'elle ne sait pas lire.
    """
    try:
        arbre = ast.parse(source)
    except SyntaxError:
        return []
    constats = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                if interdit(alias.name):
                    constats.append((noeud.lineno, alias.name))
        elif isinstance(noeud, ast.ImportFrom):
            if noeud.level or not noeud.module:
                continue  # import relatif : reste DANS le module
            if interdit(noeud.module):
                constats.append((noeud.lineno, noeud.module))
                continue
            for alias in noeud.names:
                complet = f"{noeud.module}.{alias.name}"
                if interdit(complet):
                    constats.append((noeud.lineno, complet))
        elif isinstance(noeud, ast.Call):
            if _nom_de_fonction(noeud) not in _FONCTIONS_IMPORT or not noeud.args:
                continue
            premier = noeud.args[0]
            if (isinstance(premier, ast.Constant)
                    and isinstance(premier.value, str)
                    and interdit(premier.value)):
                constats.append((noeud.lineno, premier.value))
    return sorted(set(constats))


def _relatif(chemin: Path) -> str:
    try:
        return chemin.relative_to(ROOT).as_posix()
    except ValueError:
        return chemin.as_posix()


def analyse() -> list:
    """``["fichier:ligne:module", …]`` — l'état du jour, trié."""
    constats = []
    for chemin in fichiers():
        try:
            source = chemin.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for ligne, module in imports_interdits(source):
            constats.append(f"{_relatif(chemin)}:{ligne}:{module}")
    return sorted(constats)


# ===========================================================================
# Base de référence
# ===========================================================================

ENTETE_BASE = """\
# Base de reference de check_frontiere_calepinage.py — DETTE HISTORIQUE,
# RIEN D'AUTRE (CALX372).
#
# Chaque ligne est un import de apps/calepinage/** (hors tests) vers un module
# INTERDIT par la decision D-CALX 2 (apps.ao, apps.ged) ou par le lot 7
# (apps.visites.models ; apps.visites.selectors est admis sans base). Mesure
# du 24/09/2026 : 4 imports apps.ged, tous fonction-locaux, ZERO apps.ao
# (SOLMVP15 a detache le module d'appels d'offres) et ZERO apps.visites.models.
#
# REGLE ABSOLUE : CETTE LISTE NE PEUT QUE RETRECIR.
#   - retirer un import puis `python scripts/check_frontiere_calepinage.py
#     --write-baseline` retire sa ligne ; un import simplement DEPLACE s'y
#     re-enregistre a sa nouvelle ligne ;
#   - `--write-baseline` REFUSE tout import NOUVEAU (plus d'imports d'un meme
#     module dans un meme fichier que la base n'en porte). Ajouter une dette
#     exige `--autoriser-croissance`, drapeau reserve au fondateur, visible en
#     revue.
#
# Format : `<fichier>:<ligne>:<module>`.
"""

_LIGNE_BASE = re.compile(r"^(?P<cle>\S+:\d+:[\w.]+)\s*(?:#.*)?$")


def charger_base(path: Path | None = None) -> list:
    path = path or BASELINE_PATH
    if not path.is_file():
        return []
    base = []
    for ligne in path.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#"):
            continue
        m = _LIGNE_BASE.match(ligne)
        if m:
            base.append(m.group("cle"))
    return sorted(set(base))


def ecrire_base(constats: list, path: Path | None = None):
    path = path or BASELINE_PATH
    corps = "\n".join(sorted(constats))
    path.write_text(ENTETE_BASE + (corps + "\n" if corps else ""),
                    encoding="utf-8", newline="\n")


def _fichier_module(cle: str) -> tuple:
    fichier, _ligne, module = cle.rsplit(":", 2)
    return fichier, module


def croissances(constats: list, base: list) -> list:
    """Les couples (fichier, module) qui porteraient PLUS d'imports que la base."""
    actuel = Counter(_fichier_module(cle) for cle in constats)
    avant = Counter(_fichier_module(cle) for cle in base)
    return sorted(f"{fichier}:{module} ({avant[(fichier, module)]} -> {n})"
                  for (fichier, module), n in actuel.items()
                  if n > avant[(fichier, module)])


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(
        description="Garde « frontière du module calepinage » (CALX372).")
    parser.add_argument("--stats", action="store_true",
                        help="inventaire chiffré")
    parser.add_argument("--write-baseline", action="store_true",
                        help="réécrit la base depuis l'état du jour (jamais "
                             "plus grande)")
    parser.add_argument("--autoriser-croissance", action="store_true",
                        help="FONDATEUR UNIQUEMENT : autorise l'ajout de dettes")
    args = parser.parse_args(argv)

    lus = fichiers()
    if not lus:
        print("\nECHEC : aucun fichier Python trouvé dans apps/calepinage/. "
              "Soit le chemin analysé a bougé, soit la lecture a cessé de "
              "fonctionner — dans les deux cas la garde a cessé de garder.")
        return 1

    constats = analyse()
    base = charger_base()

    if args.stats:
        print(f"Fichiers lus (hors tests) : {len(lus)}")
        print(f"Imports interdits relevés : {len(constats)}")
        for cle in constats:
            print(f"  {cle}")

    if args.write_baseline:
        amorce = not BASELINE_PATH.is_file()
        trop = croissances(constats, base)
        if trop and not (args.autoriser_croissance or amorce):
            print("REFUS : --write-baseline ne peut que RETRECIR la base.")
            print(f"{len(trop)} import(s) NOUVEAU(X) voudrai(en)t y entrer :")
            for ligne in trop[:20]:
                print(f"  + {ligne}")
            print("Passez par apps.visites.selectors (visites), ou retirez "
                  "l'import ; dette assumée : --autoriser-croissance "
                  "(fondateur).")
            return 1
        ecrire_base(constats)
        print(f"Base de reference reecrite : {BASELINE_PATH} "
              f"({len(constats)} entree(s), "
              f"{len(set(base) - set(constats))} retiree(s)).")
        return 0

    nouveaux = sorted(set(constats) - set(base))
    perimes = sorted(set(base) - set(constats))
    echec = False

    if nouveaux:
        echec = True
        print(f"\nECHEC : {len(nouveaux)} import(s) INTERDIT(S) hors base "
              f"de référence (D-CALX 2 / lot 7) :")
        for cle in nouveaux:
            fichier, ligne, module = cle.rsplit(":", 2)
            print(f"  {fichier}:{ligne}  import {module}")
        print("\nQUE FAIRE :")
        print("  - une visite se lit par apps.visites.selectors, jamais "
              "apps.visites.models ;")
        print("  - aucun couplage NEUF vers apps.ao ni apps.ged (D-CALX 2) ;")
        print("  - un import existant simplement DÉPLACÉ : "
              "python scripts/check_frontiere_calepinage.py --write-baseline")

    if perimes:
        echec = True
        print(f"\nECHEC : {len(perimes)} ligne(s) de base DEVENUE(S) "
              f"INUTILE(S) (import retiré ou déplacé) — à retirer :")
        for cle in perimes:
            print(f"  {cle}")
        print("Réécrivez la base : "
              "python scripts/check_frontiere_calepinage.py --write-baseline")

    if echec:
        return 1

    print(f"OK : {len(lus)} fichier(s) de apps/calepinage/ lu(s) (hors tests), "
          f"aucun import interdit hors base ({len(base)} dette(s) "
          f"historique(s) gelée(s) ; {MODULES_ADMIS[0]} admis).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
