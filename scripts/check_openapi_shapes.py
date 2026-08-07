#!/usr/bin/env python3
"""PACT7 — un endpoint AGREGE doit declarer sa FORME, jamais « un objet ».

POURQUOI CETTE GARDE EXISTE — LE CONSTAT QUI DISQUALIFIE LA SOLUTION EVIDENTE
-----------------------------------------------------------------------------
Apres l'incident du 03/08/2026 (l'ecran « Appels d'offres — Tableau de bord »
plante : zero cle sur six ne concordait), le reflexe est « qu'on s'appuie sur
le schema OpenAPI ». **Le schema n'aurait rien vu.**

``GET /ao/tableau-marches/`` y etait documente « type: object » SANS AUCUNE
PROPRIETE, parce que la vue declarait ``responses={200: OpenApiResponse(
response=dict)}`` (``apps/ao/kpis.py``). Une forme vide ne contredit rien :
elle valide tout, donc elle ne protege rien.

Pire, le schema **ment** sur certains agregats. ``/flotte/vehicules/
tableau-bord/`` etait documente avec le ``VehiculeSerializer`` — le
``serializer_class`` du ViewSet — alors que la vue renvoie
``{vehicules, engins, echeances, couts, entretien, pool}``. Idem pour
``/litiges/reclamations/tableau-bord/`` documente en ``ReclamationSerializer``.
Un garde-fou naif qui comparerait l'ecran au schema produirait donc des ROUGES
sur du code CORRECT : il faut d'abord que le schema cesse de mentir.

La generation emet 2 241 avertissements dont **406 « unable to guess
serializer »**, et ce sont exactement les vues-fonctions et les ``@action``
agregees — c'est-a-dire les tableaux de bord, c'est-a-dire la classe qui a
plante.

CE QUE CETTE GARDE FAIT — TROIS REGLES, ZERO BASE DE DONNEES, ZERO DEPENDANCE
-----------------------------------------------------------------------------
R1. **Interdiction dure : plus aucune forme VIDE.** ``response=dict``,
    ``response=list``, ``OpenApiTypes.OBJECT`` et ``OpenApiTypes.ANY`` dans un
    ``@extend_schema``/``OpenApiResponse`` sont refuses. Aucune base de
    reference : le depot en compte ZERO apres PACT7, il doit en compter zero
    demain. Declarer un serialiseur reel, ou un ``inline_serializer(...)``.

R2. **Cliquet sur « unable to guess serializer ».** Le compteur de ces
    signatures dans ``scripts/openapi_schema_allow.txt`` (fichier deja
    versionne, produit par ``check_openapi_schema.py --write-baseline``) est
    GELE puis DECROISSANT. Il ne peut jamais remonter.

R3. **Cliquet sur les endpoints agreges sans forme declaree.** Tout endpoint
    dont le chemin dit qu'il agrege (``tableau-bord``, ``kpi``, ``synthese``,
    ``statistiques``, ``cockpit``, ``analyse-*``, ``*-360``...) doit porter un
    ``@extend_schema(responses=...)``. La dette existante est figee dans
    ``scripts/openapi_shapes_allow.txt`` ; la liste NE PEUT QUE RETRECIR.

C'EST LE SEUL GESTE QUI PROTEGE AUSSI LES FONCTIONNALITES FUTURES : une fois la
forme declaree, lire un champ fantome devient impossible a ECRIRE — le
generateur publie la liste exacte des cles, et les gardes front<->back
(check_api_contract.py, check_api_shapes.py) ont enfin un document sur lequel
s'appuyer.

PRINCIPE ANTI-FAUX-POSITIF
--------------------------
La detection d'un endpoint agrege se fait sur son CHEMIN (vocabulaire de
tableau de bord), jamais en devinant la forme de son ``return`` : deviner la
forme est exactement ce qui produirait des rouges sur du code correct. Et tout
ce qui existe aujourd'hui est fige : seul un endpoint NOUVEAU rougit.

Usage :
    python scripts/check_openapi_shapes.py
    python scripts/check_openapi_shapes.py --stats
    python scripts/check_openapi_shapes.py --write-baseline
"""
from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_ROOT = ROOT / "backend" / "django_core"
BASELINE_PATH = ROOT / "scripts" / "openapi_shapes_allow.txt"
SCHEMA_BASELINE_PATH = ROOT / "scripts" / "openapi_schema_allow.txt"

SKIP_DIRS = {"migrations", "__pycache__", "node_modules", ".git", "tests"}

# --- R1 : formes VIDES interdites -------------------------------------------
# `response=dict` documente « type: object » SANS AUCUNE PROPRIETE : une forme
# qui valide tout ne protege rien. C'est litteralement ce que declarait
# `/ao/tableau-marches/` le jour ou l'ecran a plante.
FORMES_VIDES = {"dict", "list", "Dict", "List", "object", "Any"}
TYPES_VIDES = {"OBJECT", "ANY", "NONE"}

# --- R2 : cliquet « unable to guess serializer » ------------------------------
SIGNATURE_NON_DEVINABLE = "unable to guess serializer"
# Plafond GELE au 03/08/2026, apres les corrections de PACT7. Il ne peut que
# BAISSER : chaque vue qui gagne un serialiseur reel le fait descendre, et
# c'est la seule direction autorisee. Baisser ce nombre est un progres a
# committer ; le remonter est un refus.
PLAFOND_NON_DEVINABLES = 406

# --- R3 : vocabulaire des endpoints AGREGES ----------------------------------
# Detection par le CHEMIN, jamais par la forme du `return` (cf. en-tete).
# Chaque motif correspond a une famille reellement presente dans ce depot.
MOTIFS_AGREGES = (
    r"tableau-bord", r"tableau-de-bord", r"tableau-marches", r"tableau-",
    r"dashboard", r"cockpit",
    r"^kpis?$", r"-kpis?$", r"^kpis?-", r"-kpis?-",
    r"statistiques", r"^stats$", r"-stats$",
    r"synthese", r"indicateurs", r"pilotage",
    r"^analyse-", r"-analyse$", r"^analyse$",
    r"-360$", r"^fiche-360", r"^vue-360",
)
_AGREGE = re.compile("|".join(MOTIFS_AGREGES))

_ACCENTS = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")


def normaliser_chemin(valeur: str) -> str:
    """`Tableau_Bord` -> `tableau-bord` (souligne, casse et accents effaces)."""
    return valeur.translate(_ACCENTS).lower().replace("_", "-")


def est_agrege(chemin: str) -> bool:
    return bool(_AGREGE.search(normaliser_chemin(chemin)))


# ===========================================================================
# Lecture statique du backend
# ===========================================================================

def _fichiers_python(root: Path = DJANGO_ROOT):
    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name.startswith(("test_", "tests_")) or path.name == "tests.py":
            continue
        yield path


def _nom_appel(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _module_dotted(path: Path, root: Path) -> str:
    dotted = ".".join(path.relative_to(root).with_suffix("").parts)
    return dotted[: -len(".__init__")] if dotted.endswith(".__init__") else dotted


def _valeur_texte(node) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def formes_vides(tree: ast.AST, module: str) -> list[tuple[str, str]]:
    """R1 — occurrences de `response=dict` & co., NOMMEES par leur porteur.

    La signature porte le nom de la fonction/classe qui declare la forme vide,
    jamais seulement le module : trois occurrences dans un meme fichier
    doivent donner trois lignes a corriger, pas une.
    """
    trouvees = []

    def _formes(node, consommes: set):
        if not isinstance(node, ast.Call) or id(node) in consommes:
            return []
        if _nom_appel(node) not in ("OpenApiResponse", "extend_schema",
                                    "extend_schema_view"):
            return []
        formes = []
        for kw in node.keywords:
            if kw.arg not in ("response", "responses"):
                continue
            # `extend_schema(responses={200: OpenApiResponse(response=dict)})`
            # imbrique une declaration DANS une autre : sans ce marquage, le
            # parcours compte le meme defaut DEUX fois.
            for interne in ast.walk(kw.value):
                if isinstance(interne, ast.Call) \
                        and _nom_appel(interne) == "OpenApiResponse":
                    consommes.add(id(interne))
            for cible in _cibles_de_reponse(kw.value):
                if isinstance(cible, ast.Name) and cible.id in FORMES_VIDES:
                    formes.append(cible.id)
                elif isinstance(cible, ast.Attribute) and cible.attr in TYPES_VIDES \
                        and isinstance(cible.value, ast.Name) \
                        and cible.value.id.startswith("OpenApiTypes"):
                    formes.append(f"OpenApiTypes.{cible.attr}")
        return formes

    def _examiner(noeud, prefixe: str):
        for item in getattr(noeud, "body", []):
            if isinstance(item, ast.ClassDef):
                _examiner(item, f"{prefixe}{item.name}.")
                continue
            porteur = f"{prefixe}{item.name}" if isinstance(
                item, (ast.FunctionDef, ast.AsyncFunctionDef)) else prefixe or "<module>"
            consommes: set = set()
            # `ast.walk` est un parcours en LARGEUR : l'`extend_schema`
            # englobant est donc toujours vu AVANT l'`OpenApiResponse` qu'il
            # contient, et peut le marquer comme deja compte.
            for sous in ast.walk(item):
                for forme in _formes(sous, consommes):
                    trouvees.append((f"{module}:{porteur}", forme))

    _examiner(tree, "")
    return trouvees


def _cibles_de_reponse(node):
    """Deplie `{200: X}`, `[X]` et `X` en la liste des noeuds candidats."""
    if isinstance(node, ast.Dict):
        for value in node.values:
            yield from _cibles_de_reponse(value)
    elif isinstance(node, (ast.List, ast.Tuple)):
        for value in node.elts:
            yield from _cibles_de_reponse(value)
    elif isinstance(node, ast.Call):
        if _nom_appel(node) == "OpenApiResponse":
            for kw in node.keywords:
                if kw.arg == "response":
                    yield from _cibles_de_reponse(kw.value)
            if node.args:
                yield from _cibles_de_reponse(node.args[0])
    else:
        yield node


def _declare_une_reponse(decorators) -> bool:
    """La fonction porte-t-elle un `@extend_schema(responses=...)` ?"""
    for deco in decorators:
        if isinstance(deco, ast.Call) and _nom_appel(deco) == "extend_schema":
            if any(kw.arg == "responses" for kw in deco.keywords):
                return True
    return False


def _chemin_endpoint(deco: ast.Call, nom_methode: str) -> str | None:
    """Chemin d'une `@action` : `url_path`, sinon le NOM DE LA METHODE (DRF)."""
    for kw in deco.keywords:
        if kw.arg == "url_path":
            texte = _valeur_texte(kw.value)
            return texte if texte is not None else nom_methode
    return nom_methode


def endpoints_agreges_sans_forme(tree: ast.AST, module: str) -> list[str]:
    """R3 — signatures `module:Classe.methode` a corriger."""
    trouves = []

    def _examiner(noeud, prefixe: str):
        for item in noeud.body:
            if isinstance(item, ast.ClassDef):
                _examiner(item, f"{item.name}.")
                continue
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            chemins = []
            for deco in item.decorator_list:
                if not isinstance(deco, ast.Call):
                    continue
                nom = _nom_appel(deco)
                if nom == "action":
                    chemin = _chemin_endpoint(deco, item.name)
                    if chemin:
                        chemins.append(chemin)
                elif nom == "api_view":
                    chemins.append(item.name)
            if not chemins or not any(est_agrege(c) for c in chemins):
                continue
            if _declare_une_reponse(item.decorator_list):
                continue
            trouves.append(f"{module}:{prefixe}{item.name}")

    _examiner(tree, "")
    return trouves


def analyser(root: Path = DJANGO_ROOT):
    vides, agreges = [], []
    for path in _fichiers_python(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"),
                             filename=str(path))
        except (OSError, SyntaxError):
            continue
        module = _module_dotted(path, root)
        vides.extend(formes_vides(tree, module))
        agreges.extend(endpoints_agreges_sans_forme(tree, module))
    return sorted(set(vides)), sorted(set(agreges))


def compter_non_devinables(path: Path = SCHEMA_BASELINE_PATH) -> int:
    """R2 — signatures « unable to guess serializer » figees dans la base."""
    if not path.is_file():
        return 0
    return sum(
        1 for ligne in path.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.startswith("#")
        and SIGNATURE_NON_DEVINABLE in ligne)


# ===========================================================================
# Base de reference (elle ne peut que retrecir)
# ===========================================================================

ENTETE_BASE = """\
# PACT7 — base de reference de check_openapi_shapes.py : DETTE HISTORIQUE.
#
# Chaque ligne est un endpoint AGREGE (tableau de bord, KPI, synthese...) qui
# ne declare pas la forme de sa reponse : le schema OpenAPI publie donc pour
# lui soit rien, soit le serializer_class du ViewSet — c'est-a-dire un
# MENSONGE (`/flotte/vehicules/tableau-bord/` etait documente en
# VehiculeSerializer alors qu'il renvoie {vehicules, engins, echeances, ...}).
#
# REGLE ABSOLUE : CETTE LISTE NE PEUT QUE RETRECIR.
#   - declarer `@extend_schema(responses=inline_serializer(...))` sur la vue,
#     puis `python scripts/check_openapi_shapes.py --write-baseline` retire sa
#     ligne ;
#   - `--write-baseline` REFUSE d'ajouter une ligne. Assumer une nouvelle
#     dette exige `--autoriser-croissance`, drapeau reserve au fondateur,
#     visible en revue.
#
# La signature est `module:Classe.methode` — jamais `fichier:ligne`, qu'un
# simple decalage de lignes invaliderait (lecon du depot).
"""


def charger_base(path: Path = BASELINE_PATH) -> set[str]:
    if not path.is_file():
        return set()
    return {
        ligne.strip()
        for ligne in path.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.strip().startswith("#")
    }


def ecrire_base(entrees, path: Path = BASELINE_PATH):
    path.write_text(ENTETE_BASE + "\n".join(sorted(entrees)) + "\n",
                    encoding="utf-8", newline="\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="PACT7 — un endpoint agrege declare sa forme, jamais « un objet ».")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--autoriser-croissance", action="store_true",
                        help="FONDATEUR UNIQUEMENT : autorise l'ajout de dettes")
    args = parser.parse_args(argv)

    vides, agreges = analyser()
    non_devinables = compter_non_devinables()
    base = charger_base()

    if args.stats:
        print(f"Endpoints agreges detectes sans forme declaree : {len(agreges)} "
              f"({len(base)} en base de reference).")
        print(f"Formes vides (`response=dict` & co.) : {len(vides)}.")
        print(f"« unable to guess serializer » : {non_devinables} "
              f"(plafond gele : {PLAFOND_NON_DEVINABLES}).")

    if args.write_baseline:
        ajouts = set(agreges) - base
        amorce = not BASELINE_PATH.is_file()
        if ajouts and not (args.autoriser_croissance or amorce):
            print("REFUS : --write-baseline ne peut que RETRECIR la base.")
            for signature in sorted(ajouts)[:20]:
                print(f"  + {signature}")
            print("Declarez la forme (`@extend_schema(responses=...)`), ou "
                  "assumez la dette avec --autoriser-croissance.")
            return 1
        ecrire_base(agreges)
        print(f"Base de reference reecrite : {BASELINE_PATH.relative_to(ROOT)} "
              f"({len(agreges)} entree(s), {len(base - set(agreges))} retiree(s)).")
        return 0

    echec = False

    # R1 — interdiction dure, sans base de reference.
    if vides:
        echec = True
        print(f"\nECHEC (R1) : {len(vides)} declaration(s) de forme VIDE.\n")
        for porteur, forme in vides:
            print(f"  {porteur}  ->  response={forme}")
        print("\nUne forme vide documente « type: object » SANS AUCUNE PROPRIETE :")
        print("elle valide tout, donc elle ne protege rien. C'est exactement ce que")
        print("declarait /ao/tableau-marches/ le jour ou l'ecran a plante (03/08/2026).")
        print("\nCORRIGER : declarer un serialiseur REEL, ou le decrire en ligne :")
        print("    from drf_spectacular.utils import extend_schema, inline_serializer")
        print("    @extend_schema(responses=inline_serializer('MonAgregat', {")
        print("        'total': serializers.IntegerField(),")
        print("        ...")
        print("    }))")

    # R2 — cliquet : le compteur ne peut que baisser.
    if non_devinables > PLAFOND_NON_DEVINABLES:
        echec = True
        print(f"\nECHEC (R2) : {non_devinables} signature(s) « unable to guess "
              f"serializer » pour un plafond gele a {PLAFOND_NON_DEVINABLES}.\n")
        print("Ce compteur ne peut que DECROITRE. Une vue nouvelle sans serialiseur")
        print("resolvable est exactement la classe d'endpoint qui a plante le 03/08 :")
        print("declarez sa forme (serializer_class, @extend_schema(responses=...),")
        print("inline_serializer) au lieu de laisser le generateur deviner.")
    elif non_devinables < PLAFOND_NON_DEVINABLES:
        print(f"PROGRES : « unable to guess serializer » descendu a {non_devinables} "
              f"(plafond {PLAFOND_NON_DEVINABLES}). Abaissez PLAFOND_NON_DEVINABLES "
              f"a {non_devinables} dans scripts/check_openapi_shapes.py.")

    # R3 — cliquet sur les endpoints agreges sans forme declaree.
    nouveaux = sorted(set(agreges) - base)
    if nouveaux:
        echec = True
        print(f"\nECHEC (R3) : {len(nouveaux)} endpoint(s) AGREGE(s) sans forme "
              f"declaree, hors base de reference.\n")
        for signature in nouveaux:
            print(f"  {signature}")
        print("\nUn endpoint agrege qui ne declare pas sa forme est publie dans le")
        print("schema soit VIDE, soit avec le serializer_class du ViewSet — un")
        print("MENSONGE (/flotte/vehicules/tableau-bord/ etait documente en")
        print("VehiculeSerializer alors qu'il renvoie {vehicules, engins, ...}).")
        print("\nCORRIGER : @extend_schema(responses=inline_serializer('...', {...}))")
        print("sur la vue. Voir apps/flotte/views.py::VehiculeViewSet.tableau_bord.")

    if echec:
        return 1

    corrigees = len(base - set(agreges))
    print(f"OK : 0 forme vide, {non_devinables}/{PLAFOND_NON_DEVINABLES} "
          f"« unable to guess serializer », {len(agreges)} endpoint(s) agrege(s) "
          f"en dette (dont {corrigees} desormais corrige(s)).")
    if corrigees:
        print("Ces dettes corrigees peuvent quitter la base : "
              "python scripts/check_openapi_shapes.py --write-baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
