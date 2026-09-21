#!/usr/bin/env python
"""CALX250 — Garde « aucun seuil électrique n'entre sans source ».

POURQUOI CETTE GARDE EXISTE
----------------------------
La discipline existe par endroits (``services/lestage.py`` restreint ses
littéraux par un auto-test, ``services/degagements.py`` publie « valeur
atelier actuelle, non sourcée », ``core/electrique/__init__.py`` promet que
« chaque constante NORMATIVE du moteur cite sa source en commentaire ») —
mais rien ne l'appliquait mécaniquement. ``core/electrique/types.py:130,132``
pose ``temp_coeff_voc_pct_c = -0.27`` et ``temp_coeff_pmax_pct_c = -0.35``
en défauts de dataclass sans aucune citation (CALX53 l'a NOMMÉ dans le
verdict aval, mais rien n'empêchait la prochaine tâche d'en ajouter un
troisième). Cette garde ferme la porte : un seuil électrique NEUF, non cité,
fait échouer la CI en donnant ``fichier:ligne`` — jamais un chiffre deviné.

CE QU'ELLE MESURE, EXACTEMENT
-------------------------------
Sur ``core/electrique/*.py`` et sur
``apps/calepinage/services/{electrique,chaines,cables,protections,terre,
norme,troncons,coffrets,raccordement,micro_onduleurs,polystring}.py``
(un fichier de cette liste qui n'existe pas encore — une autre lane du même
lot le construit — est simplement ignoré, jamais accusé) :

1. une **constante de MODULE** : ``NOM = <littéral>`` / ``NOM: T = <littéral>``
   au premier niveau du fichier (jamais dans une fonction ou une méthode) ;
2. un **défaut de champ de dataclass** : ``champ: T = <littéral>`` déclaré au
   premier niveau du corps d'une classe décorée ``@dataclass``.

Un « littéral » est un nombre (``int``/``float``) écrit en dur, signe compris
(``-0.27`` s'analyse comme ``UnaryOp(USub, Constant(0.27))`` en Python — géré
ici). ``field(default=...)`` / ``field(default_factory=...)`` et un défaut qui
RÉFÉRENCE une autre constante (``regime: str = REGIME_TT``) ne sont PAS des
littéraux : ce ne sont pas des nombres inventés sur place.

CE QU'ELLE NE MESURE PAS (délibérément, pour rester surgical et sans faux
positifs) : les arguments par défaut d'une fonction ordinaire, les nombres
littéraux À L'INTÉRIEUR d'un calcul (``* 1.25``), les tuples/listes de
barèmes (``CALIBRES_DISJONCTEUR_A = (6, 10, 16, …)``). C'est exactement le
périmètre écrit par la tâche CALX250 : « tout littéral numérique de module ou
tout défaut de dataclass » — ni plus, ni moins.

TRIVIAUX EXCLUS : ``0``, ``1``, ``-1``, ``2``, ``100`` (et leurs formes
flottantes) — ce sont des bornes de forme (borné à zéro, facteur unité,
exposant du carré, pourcentage plein), jamais un seuil électrique.

QU'EST-CE QU'UNE « SOURCE » ICI
---------------------------------
Un littéral est considéré SOURCÉ si le commentaire qui l'accompagne — sur sa
propre ligne (commentaire de fin de ligne), ou dans le bloc de commentaire/
code qui le précède SANS ligne vide entre les deux pour une constante de
module, ou dans le bloc de commentaire ``#`` qui le précède DIRECTEMENT pour
un champ de dataclass — cite une provenance reconnaissable : un texte
normatif (``NF C 15-100``, ``UTE C 15-712-1``, ``IEC``/``CEI``, ``EN xxxxx``),
une fiche produit/constructeur, une URL, une décision fondateur DATÉE, ou les
mots ``source``/``convention``/``registre``/« réglage société » (voir
``SOURCE_RE`` : ``référence``/``guide`` en sont délibérément absents, voir sa
docstring). Pour une constante de module, le bloc remonte jusqu'à la
première ligne VIDE (ça capture aussi bien « commentaire juste au-dessus »
que « un même commentaire d'en-tête introduit plusieurs constantes
consécutives », comme ``CHUTE_CIBLE_DC_PCT``/``CHUTE_MAX_DC_PCT`` dans
``core/electrique/cables.py``).

BASE DE RÉFÉRENCE — ELLE NE PEUT QUE RÉTRÉCIR
-------------------------------------------------
``scripts/seuils_electriques_exceptions.txt`` gèle le passif du jour : chaque
ligne ``fichier:ligne  # motif`` documente POURQUOI ce littéral existant reste
sans citation détectée. Un NOUVEAU littéral (absent de la base) fait échouer
la garde en nommant ``fichier:ligne``. ``--write-baseline`` ne sait que
RETIRER des lignes (celles qui ont trouvé une source, ou dont le littéral a
disparu) ; il REFUSE d'en ajouter sauf ``--autoriser-croissance`` (réservé au
fondateur).

Usage :
    python scripts/check_seuils_electriques.py                 # garde CI
    python scripts/check_seuils_electriques.py --stats          # inventaire
    python scripts/check_seuils_electriques.py --write-baseline
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO = ROOT / "backend" / "django_core"
CORE_ELECTRIQUE_DIR = DJANGO / "core" / "electrique"
SERVICES_DIR = DJANGO / "apps" / "calepinage" / "services"
BASELINE_PATH = ROOT / "scripts" / "seuils_electriques_exceptions.txt"

# Les modules de services surveillés — EXACTEMENT ceux nommés par la tâche
# CALX250. Certains n'existent pas encore (d'autres lanes du même lot les
# construisent) : `fichiers_analyses()` les ignore silencieusement plutôt que
# d'échouer — la garde ne doit jamais accuser un fichier absent.
SERVICES_SURVEILLES = (
    "electrique", "chaines", "cables", "protections", "terre", "norme",
    "troncons", "coffrets", "raccordement", "micro_onduleurs", "polystring",
)

# Valeurs de FORME, jamais des seuils électriques : bornes (0/1), facteur
# unité, exposant du carré, pourcentage plein. Les deux signes sont admis
# (un défaut de dataclass négatif comme `-1` resterait une borne de forme).
TRIVIAUX = frozenset({0, 1, -1, 2, 100, 0.0, 1.0, -1.0, 2.0, 100.0})

# Une provenance reconnaissable : texte normatif, fiche, URL, décision
# fondateur datée, ou un des mots qui annoncent une origine en français.
# DÉLIBÉRÉMENT SANS ``référence``/``guide`` : mesurés sur ce dépôt, les deux
# mots apparaissent aussi dans un sens qui N'EST PAS une citation (« la
# référence de tout le dessin » = le repère du schéma, ``core/electrique/
# schema.py``) — chaque cas de citation réelle observé ici matche déjà un
# motif plus spécifique (code de norme, ``fiche``, ``source``, ``convention``,
# décision fondateur datée) ; les retirer élimine ce faux négatif sans jamais
# désourcer une constante réellement citée (vérifié constante par constante).
SOURCE_RE = re.compile(
    r"(NF\s*C\s*\d|UTE\s*C\s*\d|\bIEC\s*\d|\bCEI\s*\d|\bEN\s*\d{3,5}\b|"
    r"https?://|"
    r"d[ée]cision\s+fondateur\s+\d{1,2}/\d{1,2}/\d{2,4}|"
    r"\bfiche\b|\bsource\b|\bconvention\b|"
    r"\bregistre\b|\br[ée]glages?\s+soci[ée]t[ée]\b)",
    re.IGNORECASE,
)


# ===========================================================================
# 1. Fichiers analysés
# ===========================================================================

def fichiers_analyses() -> list:
    """Les fichiers du périmètre CALX250, dans l'ordre — absents ignorés."""
    fichiers = []
    if CORE_ELECTRIQUE_DIR.is_dir():
        fichiers.extend(sorted(CORE_ELECTRIQUE_DIR.glob("*.py")))
    for nom in SERVICES_SURVEILLES:
        chemin = SERVICES_DIR / f"{nom}.py"
        if chemin.is_file():
            fichiers.append(chemin)
    return fichiers


def relatif(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _lire(path: Path):
    """(texte, lignes, arbre) ou ``None`` — jamais une accusation sur un
    fichier illisible ou syntaxiquement invalide (principe anti-faux-positif,
    même règle que ``check_services_appeles.py``)."""
    try:
        texte = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    try:
        arbre = ast.parse(texte, filename=str(path))
    except SyntaxError:
        return None
    return texte, texte.splitlines(), arbre


# ===========================================================================
# 2. Littéraux numériques : valeur, triviaux
# ===========================================================================

def _valeur_litterale(node):
    """Un ``int``/``float`` si ``node`` est un littéral numérique simple —
    ``Constant`` ou son opposé signé (``-X``/``+X``, un ``UnaryOp`` en AST
    Python) — sinon ``None``. Exclut les booléens (sous-type d'``int``)."""
    if isinstance(node, ast.UnaryOp) \
            and isinstance(node.op, (ast.USub, ast.UAdd)):
        interne = _valeur_litterale(node.operand)
        if interne is None:
            return None
        return -interne if isinstance(node.op, ast.USub) else interne
    if isinstance(node, ast.Constant) \
            and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return node.value
    return None


def _trivial(valeur) -> bool:
    return valeur in TRIVIAUX


# ===========================================================================
# 3. Ce que la garde surveille : constantes de module, défauts de dataclass
# ===========================================================================

def _constantes_module(arbre):
    """[(nom, ligne, valeur)] des assignations littérales au PREMIER niveau
    du module (jamais dans une fonction/classe)."""
    trouvees = []
    for noeud in arbre.body:
        if isinstance(noeud, ast.Assign):
            valeur = _valeur_litterale(noeud.value)
            if valeur is None or _trivial(valeur):
                continue
            for cible in noeud.targets:
                if isinstance(cible, ast.Name):
                    trouvees.append((cible.id, noeud.lineno, valeur))
        elif isinstance(noeud, ast.AnnAssign) and noeud.value is not None \
                and isinstance(noeud.target, ast.Name):
            valeur = _valeur_litterale(noeud.value)
            if valeur is None or _trivial(valeur):
                continue
            trouvees.append((noeud.target.id, noeud.lineno, valeur))
    return trouvees


def _decore_dataclass(classdef) -> bool:
    for dec in classdef.decorator_list:
        cible = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(cible, ast.Name) and cible.id == "dataclass":
            return True
        if isinstance(cible, ast.Attribute) and cible.attr == "dataclass":
            return True
    return False


def _defauts_dataclass(arbre):
    """[(classe, champ, ligne, valeur)] des champs de dataclass dont le
    DÉFAUT est un littéral numérique DIRECT — jamais ``field(...)``, jamais
    une référence à une autre constante (``= REGIME_TT`` n'est pas un
    ``Constant``, donc pas un littéral inventé sur place)."""
    trouvees = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.ClassDef) or not _decore_dataclass(noeud):
            continue
        for stmt in noeud.body:
            if not (isinstance(stmt, ast.AnnAssign) and stmt.value is not None
                    and isinstance(stmt.target, ast.Name)):
                continue
            valeur = _valeur_litterale(stmt.value)
            if valeur is None or _trivial(valeur):
                continue
            trouvees.append((noeud.name, stmt.target.id, stmt.lineno, valeur))
    return trouvees


# ===========================================================================
# 4. Une source est-elle citée ?
# ===========================================================================

def _bloc_module(lignes, ligne_no: int) -> str:
    """Le PARAGRAPHE qui porte ``ligne_no`` : on remonte tant que les lignes
    ne sont pas vides (commentaire OU code — un même commentaire d'en-tête
    introduit souvent plusieurs constantes consécutives, ex. ``CHUTE_CIBLE_
    DC_PCT``/``CHUTE_MAX_DC_PCT`` dans ``core/electrique/cables.py``),
    jusqu'à la première ligne vide ou le début du fichier."""
    i = ligne_no - 2  # index 0-based de la ligne juste AU-DESSUS de ligne_no
    while i >= 0 and lignes[i].strip() != "":
        i -= 1
    debut = i + 2  # 1-based : première ligne du paragraphe
    return "\n".join(lignes[debut - 1:ligne_no])


def _bloc_champ(lignes, ligne_no: int) -> str:
    """Le commentaire ``#`` qui précède DIRECTEMENT ``ligne_no`` (un champ de
    dataclass, jamais un paragraphe entier — deux champs voisins d'une même
    classe ne partagent pas forcément la même provenance) + sa propre ligne
    (commentaire de fin de ligne éventuel)."""
    i = ligne_no - 2
    while i >= 0 and lignes[i].strip().startswith("#"):
        i -= 1
    debut = i + 2
    return "\n".join(lignes[debut - 1:ligne_no])


def _source_citee(bloc: str) -> bool:
    return bool(SOURCE_RE.search(bloc))


# ===========================================================================
# 5. Analyse
# ===========================================================================

def analyse():
    """(constats, stats). Un constat = (signature, fichier, ligne,
    motif_ctx)."""
    constats = []
    n_fichiers = 0
    n_module = 0
    n_dataclass = 0
    for path in fichiers_analyses():
        lu = _lire(path)
        if lu is None:
            continue
        n_fichiers += 1
        _texte, lignes, arbre = lu
        rel = relatif(path)

        for nom, ligne, _valeur in _constantes_module(arbre):
            n_module += 1
            bloc = _bloc_module(lignes, ligne)
            if _source_citee(bloc):
                continue
            motif_ctx = f"constante de module « {nom} »"
            constats.append((f"{rel}:{ligne}", rel, ligne, motif_ctx))

        for classe, champ, ligne, _valeur in _defauts_dataclass(arbre):
            n_dataclass += 1
            bloc = _bloc_champ(lignes, ligne)
            if _source_citee(bloc):
                continue
            motif_ctx = f"défaut de dataclass « {classe}.{champ} »"
            constats.append((f"{rel}:{ligne}", rel, ligne, motif_ctx))

    stats = {
        "fichiers": n_fichiers,
        "constantes_module": n_module,
        "defauts_dataclass": n_dataclass,
        "sans_source": len(constats),
    }
    # Une ligne peut porter deux constats seulement si deux littéraux non
    # triviaux y vivent (rarissime : `X = 1.5; Y = 2.5` sur une ligne n'existe
    # pas dans du Python idiomatique) — trié pour un rapport déterministe.
    return sorted(constats, key=lambda c: (c[1], c[2])), stats


# ===========================================================================
# 6. Base de référence + CLI
# ===========================================================================

ENTETE_BASE = """\
# Base de reference de check_seuils_electriques.py (CALX250) — DETTE
# HISTORIQUE, RIEN D'AUTRE.
#
# Chaque ligne est un littéral numérique (constante de module ou défaut de
# champ de dataclass) de core/electrique/*.py ou des services electrique du
# lot CALX pour lequel le script n'a PAS détecté de commentaire de source
# reconnaissable (norme, fiche, URL, décision fondateur datée...) au moment
# où cette base a été écrite. Elle GÈLE le passif : la garde empêche la
# RÉCIDIVE (un littéral NEUF sans source fait échouer la CI), elle ne répare
# pas le passif — chaque ligne drainée est un littéral enfin sourcé (un
# commentaire de provenance ajouté), remplacé par une fiche/un réglage
# société, ou supprimé.
#
# REGLE ABSOLUE : CETTE LISTE NE PEUT QUE RETRECIR.
#   - sourcer (ou supprimer) un littéral puis `python
#     scripts/check_seuils_electriques.py --write-baseline` retire sa ligne ;
#   - `--write-baseline` REFUSE d'ajouter une ligne. Ajouter une dette exige
#     `--autoriser-croissance`, drapeau reserve au fondateur, visible en revue.
#
# Format : `<fichier>:<ligne>  # <motif>` — le motif dit POURQUOI ce littéral
# reste sans source détectée (revue humaine encore à faire, ou dette connue).
"""


def charger_base(path: Path | None = None) -> dict:
    # Résolu à L'APPEL, jamais en valeur par défaut (même piège documenté
    # dans check_services_appeles.py : une valeur par défaut figée à la
    # définition du module écrirait dans la VRAIE base même sous un test qui
    # réassigne BASELINE_PATH).
    path = path or BASELINE_PATH
    base = {}
    if not path.is_file():
        return base
    for ligne in path.read_text(encoding="utf-8").splitlines():
        contenu = ligne.strip()
        if not contenu or contenu.startswith("#"):
            continue
        cle, _, motif = contenu.partition("#")
        base[cle.strip()] = motif.strip()
    return base


def ecrire_base(entrees: dict, path: Path | None = None):
    path = path or BASELINE_PATH
    corps = "\n".join(
        f"{cle}  # {motif}" if motif else cle
        for cle, motif in sorted(entrees.items())
    )
    path.write_text(ENTETE_BASE + corps + "\n", encoding="utf-8", newline="\n")


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(
        description="Garde « aucun seuil électrique n'entre sans source » "
                    "(CALX250).")
    parser.add_argument("--stats", action="store_true",
                        help="inventaire chiffré")
    parser.add_argument("--write-baseline", action="store_true",
                        help="retire de la base les littéraux désormais "
                             "sourcés")
    parser.add_argument("--autoriser-croissance", action="store_true",
                        help="FONDATEUR UNIQUEMENT : autorise l'ajout de "
                             "dettes")
    args = parser.parse_args(argv)

    constats, stats = analyse()

    if args.stats:
        print(f"Fichiers lus : {stats['fichiers']}.")
        print(f"Constantes de module : {stats['constantes_module']} — "
              f"défauts de dataclass : {stats['defauts_dataclass']} — "
              f"{stats['sans_source']} sans source détectée.")

    # Le faux-vert le plus dangereux : la garde qui n'a plus rien analysé.
    if stats["fichiers"] == 0:
        print("\nECHEC : aucun fichier lu dans core/electrique/ ou "
              "apps/calepinage/services/ — le chemin analysé a bougé, ou la "
              "lecture a cessé de fonctionner : dans les deux cas la garde a "
              "cessé de garder.")
        return 1

    signatures = {c[0]: c[3] for c in constats}
    base = charger_base()

    if args.write_baseline:
        ajouts = set(signatures) - set(base)
        amorce = not BASELINE_PATH.is_file()
        if ajouts and not (args.autoriser_croissance or amorce):
            print("REFUS : --write-baseline ne peut que RETRECIR la base.")
            print(f"{len(ajouts)} nouvelle(s) dette(s) voudraient y entrer :")
            for entree in sorted(ajouts)[:20]:
                print(f"  + {entree}")
            print("Sourcez le littéral (commentaire de provenance), "
                  "supprimez-le, ou assumez la dette avec "
                  "--autoriser-croissance.")
            return 1
        # Conserve le motif déjà écrit pour les entrées qui restent ; les
        # entrées neuves de l'amorce prennent le motif calculé par l'analyse.
        entrees = {cle: base.get(cle, motif)
                   for cle, motif in signatures.items()}
        ecrire_base(entrees)
        retirees = len(set(base) - set(signatures))
        print(f"Base de référence réécrite : {relatif(BASELINE_PATH)} "
              f"({len(entrees)} entrée(s), {retirees} retirée(s)).")
        return 0

    nouveaux = [c for c in constats if c[0] not in base]

    if nouveaux:
        print(f"\nECHEC : {len(nouveaux)} seuil(s) électrique(s) NEUF(S) "
              f"sans source (hors base de référence).\n")
        for signature, fichier, ligne, motif_ctx in nouveaux:
            print(f"  {fichier}:{ligne}  ({motif_ctx})")
        print("\nQUE FAIRE :")
        print("  - ajoutez, sur la ligne ou juste au-dessus, un commentaire "
              "qui cite la provenance du chiffre (norme « NF C 15-100 »/"
              "« UTE C 15-712-1 »/« IEC »/« CEI », fiche produit, URL, ou "
              "« décision fondateur JJ/MM/AAAA ») ;")
        print("  - ou lisez la valeur depuis une fiche produit / un réglage "
              "société sourcé (registre `services/parametres_cles.py`) "
              "plutôt que de l'écrire en dur ;")
        print("  - ou, si c'est une valeur de FORME (borne, facteur unité), "
              "vérifiez qu'elle vaut bien 0/1/-1/2/100 — sinon ce n'est pas "
              "une valeur de forme et elle doit être sourcée.")
        print("\nCette garde existe parce qu'un coefficient de température "
              "(core/electrique/types.py) est resté un défaut de dataclass "
              "sans citation, invisible en aval jusqu'à ce que CALX53 le "
              "nomme explicitement dans le verdict. NE LA DÉSACTIVEZ PAS.")
        return 1

    corriges = set(base) - set(signatures)
    print(f"OK : {stats['constantes_module'] + stats['defauts_dataclass']} "
          f"littéral(aux) numérique(s) analysé(s) dans {stats['fichiers']} "
          f"fichier(s), aucun NOUVEAU sans source "
          f"({len(base)} dette(s) historique(s) gelée(s), dont "
          f"{len(corriges)} désormais sourcée(s) ou disparue(s)).")
    if corriges:
        print("Ces dettes corrigées peuvent quitter la base : "
              "python scripts/check_seuils_electriques.py --write-baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
