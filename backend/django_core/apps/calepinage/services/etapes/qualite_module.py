"""CALX165 — l'étape « qualité module » : la tolérance de la fiche, la règle
de la société, ou rien.

CE QUE LE DÉPÔT AVAIT, ET POURQUOI ÇA NE SUFFISAIT PAS
--------------------------------------------------------
``services/pertes.py`` porte le poste ``qualite_module`` au catalogue sans
aucun calcul, et la fiche technique ne portait AUCUNE tolérance de puissance
(les seuls ``tolerance_*`` du dépôt sont des tolérances d'ACHAT, prix et
quantité). Un module trié « 0/+3 % » et un module trié « ±3 % » se
simulaient donc à l'identique. CALX60 a ouvert
``FicheTechnique.tolerance_pmax_min_pct`` / ``tolerance_pmax_max_pct`` ;
cette étape est leur lecteur.

LES DEUX ENTRÉES, ET AUCUNE TROISIÈME
---------------------------------------
1. **La tolérance publiée** par le constructeur, lue sur la fiche du module
   (``contexte['fiche_module']``). Absente ⇒ étape OMISE en nommant le champ.
2. **La règle de la société**, réglage sourcé
   ``parametres.simulation.regle_qualite_module`` (registre CALX145). Non
   saisie ⇒ étape OMISE en nommant le réglage. Une tolérance seule ne dit
   PAS ce qu'il faut en faire : retenir la borne basse, la moyenne ou le
   quart de PVsyst sont trois décisions différentes, et c'est la société qui
   la prend — pas ce module (D-CALX 7).

LE QUART DE PVsyst EST UNE RÈGLE CITÉE, PAS UNE CONSTANTE
-----------------------------------------------------------
PVsyst propose, pour cette perte, un quart de la différence entre les deux
bornes de tolérance du fabricant, et traite un tri positif seul (par exemple
0…+3 %) comme un GAIN et non comme une perte
(https://www.pvsyst.com/help/project-design/array-and-system-losses/module-quality-losses.html).
Ce quart n'est écrit NULLE PART comme valeur par défaut : il n'entre dans le
calcul que si la société a choisi la règle ``quart_pvsyst`` et l'a sourcée.
Tant qu'elle ne l'a pas fait, l'étape reste omise — un 0 % se lirait « les
modules sont exactement à leur puissance nominale », ce que personne n'a
vérifié.

LE SIGNE
---------
La variation est exprimée en % de la puissance nominale : POSITIVE quand les
modules sont en moyenne au-dessus du nominal (l'étape se déclare alors
``gain=True``, et la cascade publie une ``perte_pct`` négative), NÉGATIVE
quand ils sont en dessous.
"""
from __future__ import annotations

from apps.calepinage.services import etapes

#: Les deux champs de fiche lus, sous les noms que ``specs_for_produit``
#: (CALX60) publie.
CHAMP_MIN = 'tolerance_pmax_min_pct'
CHAMP_MAX = 'tolerance_pmax_max_pct'

#: Les champs tels qu'on les NOMME à l'écran quand ils manquent.
CHAMP_MIN_AFFICHE = f'FicheTechnique.{CHAMP_MIN}'
CHAMP_MAX_AFFICHE = f'FicheTechnique.{CHAMP_MAX}'

#: Le réglage société qui dit QUOI FAIRE de la tolérance (registre CALX145).
CLE_REGLAGE = 'regle_qualite_module'
REGLAGE_AFFICHE = f'parametres.simulation.{CLE_REGLAGE}'

#: La référence doctrinale citée par l'étape.
REFERENCE_PVSYST = (
    'PVsyst — Module quality losses : un quart de la différence entre les '
    'bornes de tolérance du fabricant est proposé, et un tri positif seul '
    'devient un gain '
    '(https://www.pvsyst.com/help/project-design/array-and-system-losses/'
    'module-quality-losses.html).')

#: LES RÈGLES ADMISES, chacune avec ce qu'elle lit et ce qu'elle dit d'elle.
#: ``aucune`` est une décision, pas une absence : la société déclare ne PAS
#: appliquer de perte de qualité, et l'étape le publie au lieu de se taire.
REGLES = {
    'quart_pvsyst': {
        'libelle': 'Un quart de la différence entre les deux bornes '
                   '(règle proposée par PVsyst)',
        'besoin_max': True,
    },
    'borne_basse': {
        'libelle': 'La borne BASSE de la tolérance, retenue telle quelle '
                   '(pire cas publié par le constructeur)',
        'besoin_max': False,
    },
    'moyenne': {
        'libelle': 'La moyenne des deux bornes de la tolérance',
        'besoin_max': True,
    },
    'aucune': {
        'libelle': "Aucune perte de qualité module n'est appliquée "
                   '(décision de la société)',
        'besoin_max': False,
    },
}

MOTIF_TOLERANCE_ABSENTE = (
    "Aucune tolérance de puissance n'est publiée sur la fiche de {produit} : "
    "rien ne dit de combien la puissance réelle des modules s'écarte du "
    "nominal. L'étape est OMISE — aucun forfait n'est appliqué à sa place.")

MOTIF_REGLE_ABSENTE = (
    "La tolérance de puissance de {produit} est publiée, mais la société n'a "
    "pas choisi ce qu'il faut en faire : retenir la borne basse, la moyenne "
    'ou le quart proposé par PVsyst sont trois décisions différentes. '
    "L'étape est OMISE tant que la règle n'est pas saisie et sourcée.")

MOTIF_REGLE_INCONNUE = (
    'La règle de qualité module saisie par la société, « {valeur} », ne fait '
    'partie des règles connues ({connues}). Aucune règle n\'est devinée : '
    "l'étape est OMISE.")

MOTIF_REGLE_AUCUNE = (
    'La société a choisi de n\'appliquer AUCUNE perte de qualité module '
    '({source}) : l\'étape figure dans la cascade pour être VUE et reste '
    "sans effet. C'est une décision déclarée, pas une donnée manquante.")

MOTIF_BORNE_HAUTE_ABSENTE = (
    'La règle « {regle} » a besoin des DEUX bornes de tolérance, et la borne '
    "haute de {produit} n'est pas publiée. L'étape est OMISE plutôt que "
    'calculée sur une seule borne.')

MOTIF_BORNES_INCOHERENTES = (
    'La tolérance publiée de {produit} a une borne haute ({maximum} %) '
    'INFÉRIEURE à sa borne basse ({minimum} %) : la plage ne se lit pas. '
    "L'étape est OMISE plutôt que calculée sur une plage retournée.")

MOTIF_ENERGIE_ILLISIBLE = (
    "Aucune colonne d'énergie lisible dans la série ({colonnes}) : il n'y a "
    "rien à quoi appliquer la tolérance de {produit}. L'étape est OMISE.")

__all__ = ['CHAMP_MIN', 'CHAMP_MAX', 'CHAMP_MIN_AFFICHE',
           'CHAMP_MAX_AFFICHE', 'CLE_REGLAGE', 'REGLAGE_AFFICHE', 'REGLES',
           'REFERENCE_PVSYST', 'appliquer']


def appliquer(serie, contexte):
    """``(serie, etape)`` — le contrat de ``services/etapes/__init__.py``.

    Fonction PURE : la série reçue n'est jamais modifiée sur place, et
    l'étape omise la rend telle quelle.
    """
    contexte = contexte if isinstance(contexte, dict) else {}
    fiche_module = contexte.get('fiche_module') or {}
    produit = _produit_designe(contexte)
    libelle = _libelle()

    minimum = _nombre(_tolerance_min(fiche_module))
    if minimum is None:
        return serie, etapes.etape_omise(
            libelle, MOTIF_TOLERANCE_ABSENTE.format(produit=produit),
            champ=CHAMP_MIN_AFFICHE)

    saisie = etapes.reglage(contexte, CLE_REGLAGE)
    if saisie is None:
        return serie, etapes.etape_omise(
            libelle, MOTIF_REGLE_ABSENTE.format(produit=produit),
            champ=REGLAGE_AFFICHE)

    nom_regle = _nom_de_regle(saisie.get('valeur'))
    if nom_regle is None:
        return serie, etapes.etape_omise(
            libelle,
            MOTIF_REGLE_INCONNUE.format(valeur=saisie.get('valeur'),
                                        connues=', '.join(sorted(REGLES))),
            champ=REGLAGE_AFFICHE)

    if nom_regle == 'aucune':
        return serie, etapes.etape_omise(
            libelle,
            MOTIF_REGLE_AUCUNE.format(source=_provenance(saisie)))

    maximum = _nombre(_tolerance_max(fiche_module))
    if REGLES[nom_regle]['besoin_max'] and maximum is None:
        return serie, etapes.etape_omise(
            libelle,
            MOTIF_BORNE_HAUTE_ABSENTE.format(regle=nom_regle,
                                             produit=produit),
            champ=CHAMP_MAX_AFFICHE)
    if maximum is not None and maximum < minimum:
        return serie, etapes.etape_omise(
            libelle,
            MOTIF_BORNES_INCOHERENTES.format(produit=produit,
                                             minimum=minimum,
                                             maximum=maximum),
            champ=f'{CHAMP_MIN_AFFICHE} / {CHAMP_MAX_AFFICHE}')

    colonne = etapes.colonne_energie(serie)
    if colonne is None:
        return serie, etapes.etape_omise(
            libelle,
            MOTIF_ENERGIE_ILLISIBLE.format(
                produit=produit,
                colonnes=', '.join(etapes.ORDRE_COLONNES_ENERGIE)))

    variation = _variation_pct(nom_regle, minimum, maximum)
    suite = etapes.mettre_a_l_echelle(serie, 1.0 + variation / 100.0)
    return suite, etapes.etape_appliquee(
        libelle,
        source='fiche',
        entree=_entree(nom_regle),
        reference=_reference(produit, nom_regle, saisie, minimum, maximum,
                             variation),
        gain=variation > 0.0)


# ── la règle, et ce qu'elle fait de la tolérance ────────────────────────

def _variation_pct(nom_regle, minimum, maximum):
    """L'écart à la puissance nominale, en % — POSITIF = au-dessus.

    Aucun coefficient n'est écrit ailleurs qu'ici, et aucun ne s'applique
    sans que la société ait nommé sa règle.
    """
    if nom_regle == 'borne_basse':
        return minimum
    if nom_regle == 'moyenne':
        return (minimum + maximum) / 2.0
    # quart_pvsyst : un quart de la LARGEUR de la plage, compté en gain
    # quand la plage ne descend jamais sous le nominal (tri positif seul).
    quart = (maximum - minimum) / 4.0
    return quart if minimum >= 0.0 else -quart


def _nom_de_regle(valeur):
    """Le nom canonique de la règle saisie, ou ``None`` si elle est inconnue.

    Casse et espaces sont tolérés — une règle inconnue ne l'est jamais.
    """
    if not isinstance(valeur, str):
        return None
    nom = valeur.strip().lower()
    return nom if nom in REGLES else None


def _entree(nom_regle):
    """Les champs de fiche que la règle a réellement lus."""
    if REGLES[nom_regle]['besoin_max']:
        return f'{CHAMP_MIN} + {CHAMP_MAX}'
    return CHAMP_MIN


def _reference(produit, nom_regle, saisie, minimum, maximum, variation):
    """D'où vient le chiffre : la fiche, la règle société, et la doctrine."""
    plage = (f'Tolérance publiée sur la fiche de {produit} : '
             f'{_texte(minimum)} % à '
             f'{_texte(maximum) if maximum is not None else "—"} %.')
    regle = (f'Règle de la société : « {nom_regle} » — '
             f'{REGLES[nom_regle]["libelle"]} ({_provenance(saisie)}).')
    effet = (f'Écart retenu : {_texte(variation)} % de la puissance '
             f'nominale ({"gain" if variation > 0 else "perte"}).')
    return f'{plage} {regle} {effet} {REFERENCE_PVSYST}'


def _provenance(saisie):
    """``source`` du réglage, et sa ``reference`` quand elle est saisie."""
    source = (saisie.get('source') or '').strip()
    reference = (saisie.get('reference') or '').strip()
    if reference:
        return f'source : {source} — {reference}'
    return f'source : {source}'


# ── la fiche : lue sous les noms que CALX60 publie ──────────────────────

def _tolerance_min(fiche_module):
    """La borne BASSE de tolérance publiée, ou ``None``.

    ``specs_for_produit`` rend un DICT de specs ; un double d'essai peut
    porter un objet. Les deux lectures nomment la même clé publiée.
    """
    if isinstance(fiche_module, dict):
        return fiche_module.get('tolerance_pmax_min_pct')
    return getattr(fiche_module, 'tolerance_pmax_min_pct', None)


def _tolerance_max(fiche_module):
    """La borne HAUTE de tolérance publiée, ou ``None``."""
    if isinstance(fiche_module, dict):
        return fiche_module.get('tolerance_pmax_max_pct')
    return getattr(fiche_module, 'tolerance_pmax_max_pct', None)


# ── les petites lectures ────────────────────────────────────────────────

def _produit_designe(contexte):
    """Le nom du module PV tel que le document le porte, ou un repli.

    ``designations`` est la table que ``services/electrique.py`` compose déjà
    pour nommer le matériel retenu ; absente, l'étape parle du « module
    retenu » plutôt que d'un produit qu'elle ne connaît pas.
    """
    designations = contexte.get('designations')
    if isinstance(designations, dict):
        nom = (designations.get('module') or '').strip()
        if nom:
            return nom
    return 'le module retenu'


def _libelle():
    from apps.calepinage.services.chaine_pertes import LIBELLES
    return LIBELLES['qualite_module']


def _nombre(valeur):
    """``float(valeur)`` quand c'est un nombre, sinon ``None``.

    Les Decimal des champs de fiche passent par ici ; un texte, un ``None``
    ou un booléen n'entrent jamais dans un calcul.
    """
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _texte(valeur):
    """Un nombre écrit court : ``3`` plutôt que ``3.0``."""
    entier = int(valeur)
    return str(entier) if float(entier) == float(valeur) else str(valeur)
