#!/usr/bin/env python
"""Garde « service sans appelant » : une fonction de service doit etre APPELEE.

POURQUOI CETTE GARDE EXISTE (CALX57)
-------------------------------------
Aucun script de ``scripts/`` ne mesurait les services Python orphelins. C'est
ainsi que ``apps/calepinage/services/`` a pu accumuler des milliers de lignes
qu'AUCUN consommateur n'appelle pendant tout un groupe de taches : du code
ecrit, teste, revu, merge — et jamais execute en production. Le symptome est
exactement celui du 03/08/2026 cote ecrans (68 ecrans livres, 7 atteignables) ;
le remede est le meme : une garde qui rend l'invisible visible, une base de
reference qui gele le passif sans l'effacer, et un sens de variation unique —
la dette ne peut que RETRECIR.

CE QU'ELLE MESURE, EXACTEMENT
-------------------------------
Pour chaque module de ``apps/<app>/services/`` : ses fonctions PUBLIQUES de
premier niveau (un nom prefixe de ``_`` est prive par convention, il ne promet
rien a personne). Une fonction est JUSTIFIEE des qu'un fichier ``.py`` non-test
du backend, AUTRE que le module qui la definit, la nomme reellement — appel
``f(...)``, attribut ``services.f``, passage en reference (``connect(f)``,
table de routage). Sinon, elle est signalee.

TROIS REGLES QUI EVITENT LE CRI AU LOUP
----------------------------------------
* **La facade paresseuse ne compte pas.** ``services/__init__.py`` reexporte
  tout : s'il comptait comme appelant, chaque fonction se justifierait
  elle-meme et la garde ne verrait jamais rien. Elle est donc IGNOREE comme
  appelant (la tache le demande explicitement).
* **Le module qui definit ne compte pas comme son propre appelant.** La
  question posee est « qui CONSOMME ce service ? » : un usage interne au
  fichier n'y repond pas — c'est le signe d'un helper qui devrait porter un
  ``_``.
* **Les tests ne comptent pas.** Un service appele UNIQUEMENT par ses tests
  est precisement la maladie mesuree : le test prouve qu'il marche, personne
  ne prouve qu'il sert.

CE QU'ELLE NE FAIT PAS
-----------------------
Aucun build, aucune base de donnees, aucun import du projet : ``ast`` seul,
sur le texte des fichiers. Un fichier illisible (syntaxe d'une version
future, encodage casse) est IGNORE, jamais accuse : le principe
anti-faux-positif prime toujours sur l'exhaustivite.

BASE DE REFERENCE — ELLE NE PEUT QUE RETRECIR
-----------------------------------------------
``scripts/services_appeles_allow.txt`` gele l'etat du jour : la garde empeche
la RECIDIVE, elle ne repare pas le passif. ``--write-baseline`` ne sait
qu'en RETIRER des lignes (celles qui ont trouve un appelant) ; ajouter une
dette exige ``--autoriser-croissance``, drapeau reserve au fondateur et
visible en revue.

Usage :
    python scripts/check_services_appeles.py                 # garde CI
    python scripts/check_services_appeles.py --stats         # inventaire
    python scripts/check_services_appeles.py --write-baseline
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO = ROOT / "backend" / "django_core"
BASELINE_PATH = ROOT / "scripts" / "services_appeles_allow.txt"

# Les apps dont les services sont surveilles. En ajouter une = une chaine de
# plus ici (ou `--app <nom>`) : la garde ne connait aucun nom de fonction, et
# n'encode donc jamais l'etendue de la maladie qu'elle mesure.
APPS_SURVEILLEES = ("calepinage",)


# ===========================================================================
# 1. Lecture
# ===========================================================================

def est_test(path: Path) -> bool:
    """Tests et fixtures : ni definitions surveillees, ni appelants valides."""
    parties = set(path.parts)
    return (
        path.name.startswith("test_")
        or path.name == "conftest.py"
        or "tests" in parties
        or "testing" in parties
    )


def _arbre(path: Path):
    """L'AST du fichier, ou ``None`` — jamais une accusation sur un illisible."""
    try:
        texte = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    try:
        return ast.parse(texte)
    except SyntaxError:
        return None


def relatif(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


# ===========================================================================
# 2. Les fonctions publiques des services
# ===========================================================================

def modules_services(app: str) -> list:
    """Les modules de ``apps/<app>/services/`` — hors facade et hors tests."""
    dossier = DJANGO / "apps" / app / "services"
    if not dossier.is_dir():
        return []
    modules = []
    for path in sorted(dossier.rglob("*.py")):
        if path.name == "__init__.py" or est_test(path):
            continue
        modules.append(path.resolve())
    return modules


def facades(apps) -> set:
    """``services/__init__.py`` de chaque app : reexporte, n'appelle pas."""
    return {
        (DJANGO / "apps" / app / "services" / "__init__.py").resolve()
        for app in apps
    }


def definitions(apps) -> list:
    """[(chemin du module, nom, ligne)] des fonctions PUBLIQUES de service."""
    trouvees = []
    for app in apps:
        for path in modules_services(app):
            arbre = _arbre(path)
            if arbre is None:
                continue
            for noeud in arbre.body:
                if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if noeud.name.startswith("_"):
                    continue
                trouvees.append((path, noeud.name, noeud.lineno))
    return trouvees


# ===========================================================================
# 3. Qui nomme quoi
# ===========================================================================

def _prefiltre(noms: set):
    """Un seul motif pour tous les noms, applique sur les OCTETS du fichier :
    la quasi-totalite des fichiers du backend ne mentionne aucun service et
    n'a alors ni a etre decodee ni a etre analysee (60 Mo de source)."""
    if not noms:
        return None
    alternative = "|".join(sorted(map(re.escape, noms)))
    return re.compile((r"\b(?:%s)\b" % alternative).encode("utf-8"))


def _noms_utilises(arbre) -> set:
    """Tout identifiant reellement REFERENCE : appel `f(...)`, attribut
    `services.f`, ou passage en reference (`connect(f)`, `{'a': f}`).

    Un `from x import f` seul n'en est PAS un : reexporter n'est pas
    consommer — c'est exactement ce qui rend la facade muette.
    """
    utilises = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Name):
            utilises.add(noeud.id)
        elif isinstance(noeud, ast.Attribute):
            utilises.add(noeud.attr)
    return utilises


def references(noms: set, ignores: set) -> dict:
    """{nom: {modules qui le nomment}} sur tout le backend, hors tests et
    hors `ignores` (les facades de services)."""
    motif = _prefiltre(noms)
    vues: dict = {}
    if motif is None:
        return vues
    for path in sorted(DJANGO.rglob("*.py")):
        resolu = path.resolve()
        if resolu in ignores or est_test(path) or "__pycache__" in path.parts:
            continue
        try:
            octets = path.read_bytes()
        except OSError:
            continue
        if not motif.search(octets):
            continue
        try:
            arbre = ast.parse(octets.decode("utf-8", errors="replace"))
        except SyntaxError:
            continue
        for nom in _noms_utilises(arbre) & noms:
            vues.setdefault(nom, set()).add(resolu)
    return vues


# ===========================================================================
# 4. Analyse
# ===========================================================================

def analyse(apps=None) -> tuple:
    """(constats, stats). Un constat = (signature, module, nom, ligne)."""
    apps = tuple(apps or APPS_SURVEILLEES)
    definies = definitions(apps)
    noms = {nom for _, nom, _ in definies}
    vues = references(noms, facades(apps))

    constats = []
    for path, nom, ligne in definies:
        appelants = vues.get(nom, set()) - {path}
        if appelants:
            continue
        constats.append((f"{relatif(path)}::{nom}", relatif(path), nom, ligne))

    stats = {
        "apps": len(apps),
        "modules": sum(len(modules_services(app)) for app in apps),
        "fonctions": len(definies),
        "sans_appelant": len(constats),
    }
    return sorted(constats), stats


# ===========================================================================
# 5. Base de reference + CLI
# ===========================================================================

ENTETE_BASE = """\
# Base de reference de check_services_appeles.py — DETTE HISTORIQUE, RIEN D'AUTRE.
#
# Chaque ligne est une fonction PUBLIQUE d'un module `services/` qu'aucun
# fichier .py non-test du backend n'appelle (la facade `services/__init__.py`
# et le module qui la definit ne comptent pas comme appelants). Cette liste
# gele l'etat du jour : la garde empeche la RECIDIVE, elle ne repare pas le
# passif — chaque ligne drainee est une fonction enfin branchee, ou supprimee.
#
# REGLE ABSOLUE : CETTE LISTE NE PEUT QUE RETRECIR.
#   - brancher (ou supprimer) une fonction puis `python
#     scripts/check_services_appeles.py --write-baseline` retire sa ligne ;
#   - `--write-baseline` REFUSE d'ajouter une ligne. Ajouter une dette exige
#     `--autoriser-croissance`, drapeau reserve au fondateur, visible en revue.
#
# La signature est `<module>::<fonction>`, jamais `fichier:ligne` : deplacer du
# code dans son fichier ne doit pas invalider la base.
"""


def charger_base(path: Path | None = None) -> set:
    # Resolu A L'APPEL, jamais en valeur par defaut : une valeur par defaut est
    # figee a la definition du module, si bien qu'un test qui reassigne
    # BASELINE_PATH ecrirait quand meme dans la VRAIE base du depot.
    path = path or BASELINE_PATH
    if not path.is_file():
        return set()
    return {
        ligne.strip()
        for ligne in path.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.strip().startswith("#")
    }


def ecrire_base(signatures: set, path: Path | None = None):
    path = path or BASELINE_PATH
    path.write_text(ENTETE_BASE + "\n".join(sorted(signatures)) + "\n",
                    encoding="utf-8", newline="\n")


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(
        description="Garde « service sans appelant » : un service livre doit "
                    "etre appele par un vrai consommateur.")
    parser.add_argument("--app", action="append", default=None,
                        help="app a surveiller (par defaut : "
                             + ", ".join(APPS_SURVEILLEES) + ")")
    parser.add_argument("--stats", action="store_true",
                        help="inventaire chiffre")
    parser.add_argument("--write-baseline", action="store_true",
                        help="retire de la base les fonctions desormais appelees")
    parser.add_argument("--autoriser-croissance", action="store_true",
                        help="FONDATEUR UNIQUEMENT : autorise l'ajout de dettes")
    args = parser.parse_args(argv)

    constats, stats = analyse(args.app)

    if args.stats:
        print(f"Modules de services lus : {stats['modules']} "
              f"({stats['apps']} app(s) surveillee(s)).")
        print(f"Fonctions publiques : {stats['fonctions']} — "
              f"{stats['sans_appelant']} sans aucun appelant hors de leur "
              f"propre module.")

    # Une garde qui n'analyse plus rien conclut « OK : 0 » et rend 0 : c'est le
    # faux-vert le plus dangereux. Aucun nombre n'est epingle ici — seulement
    # l'exigence d'avoir VU quelque chose.
    if stats["fonctions"] == 0:
        print("\nECHEC : aucune fonction publique de service trouvee. Soit le "
              "chemin analyse a bouge (backend/django_core/apps/<app>/"
              "services/), soit la lecture a cesse de fonctionner — dans les "
              "deux cas la garde a cesse de garder.")
        return 1

    signatures = {c[0] for c in constats}
    base = charger_base()

    if args.write_baseline:
        ajouts = signatures - base
        amorce = not BASELINE_PATH.is_file()
        if ajouts and not (args.autoriser_croissance or amorce):
            print("REFUS : --write-baseline ne peut que RETRECIR la base.")
            print(f"{len(ajouts)} nouvelle(s) dette(s) voudraient y entrer :")
            for entree in sorted(ajouts)[:20]:
                print(f"  + {entree}")
            print("Branchez la fonction sur un vrai appelant, supprimez-la, ou "
                  "assumez la dette avec --autoriser-croissance.")
            return 1
        ecrire_base(signatures)
        print(f"Base de reference reecrite : {relatif(BASELINE_PATH)} "
              f"({len(signatures)} entree(s), "
              f"{len(base - signatures)} retiree(s)).")
        return 0

    nouveaux = [c for c in constats if c[0] not in base]
    corriges = base - signatures

    if nouveaux:
        print(f"\nECHEC : {len(nouveaux)} fonction(s) de service livree(s) "
              f"SANS aucun appelant (hors base de reference).\n")
        for signature, module, nom, ligne in nouveaux:
            print(f"  {module}:{ligne}  ({nom})")
            print("      aucun fichier .py non-test du backend n'appelle cette "
                  "fonction — ni une vue, ni une tache, ni un autre service "
                  "(sa propre facade `services/__init__.py` et son propre "
                  "module ne comptent pas)")
        print("\nQUE FAIRE :")
        print("  - branchez-la sur son vrai consommateur (vue, tache, "
              "serializer, autre service) — c'est le geste attendu ;")
        print("  - ou, si elle est un detail d'implementation, prefixez son "
              "nom d'un `_` : elle ne promet alors plus rien a personne ;")
        print("  - ou supprimez-la si elle est morte — mais ne la laissez pas "
              "livree-et-jamais-executee.")
        print("\nCette garde existe parce que des milliers de lignes de "
              "services ont ete ecrites, testees et fusionnees sans jamais "
              "etre appelees. Voir l'en-tete de "
              "scripts/check_services_appeles.py. NE LA DESACTIVEZ PAS.")
        return 1

    print(f"OK : {stats['fonctions']} fonction(s) publique(s) de service "
          f"lue(s) dans {stats['modules']} module(s), aucune NOUVELLE sans "
          f"appelant ({len(base)} dette(s) historique(s) gelee(s), dont "
          f"{len(corriges)} desormais branchee(s)).")
    if corriges:
        print("Ces dettes corrigees peuvent quitter la base : "
              "python scripts/check_services_appeles.py --write-baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
