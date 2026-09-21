# -*- coding: utf-8 -*-
"""CALX168 — étape « mismatch d'ombrage » : l'effondrement I-V d'une chaîne.

LE CONSTAT
----------
``services/ombrage_chaines.py`` possède déjà la partition RÉELLE — la table
``affectation`` de ``services/chaines.py`` croisée avec l'accès solaire par
module — et publie par chaîne ``acces_min``, ``acces_max``, ``ecart_interne``
et le module le plus ombré. Son propre docstring s'interdit d'en tirer un
kWh (« AUCUN kWh, aucune perte : ce service publie de la géométrie »), et
aucun appelant n'existait hors de ses tests. Cette étape est ce consommateur :
elle lit cette géométrie et n'en réécrit pas une ligne.

CE QUE CETTE ÉTAPE MESURE — ET CE QU'ELLE NE MESURE PAS
---------------------------------------------------------
``acces_module`` (CALX158) a déjà retiré la perte LINÉAIRE d'irradiance :
chaque module perd ce que son ombre lui retire. Mais les modules d'une chaîne
sont en SÉRIE : le courant de la chaîne est celui de son module le moins
éclairé, si bien que l'ombre d'UN module coûte à TOUTE la chaîne. Cette étape
ne mesure QUE cet excédent électrique, au-delà de la perte linéaire déjà
appliquée — jamais l'ombre elle-même, qui serait alors comptée deux fois.

Parité :

* PV*SOL — « selon le nombre de brins ombrés, la caractéristique du module
  s'effondre »
  (https://help.valentin-software.com/pvsol/en/calculation/pv-modules/shading-due-to-nearby-objects/) ;
* HelioScope modélise la variabilité du champ par « IV curve mismatch »
  (https://help-center.helioscope.com/hc/en-us/articles/13804165205395-Modeling-101).

UNE FOURCHETTE, PAS UN CHIFFRE UNIQUE
---------------------------------------
Sans modèle à une diode (CALX198), aucune valeur INTERMÉDIAIRE ne se défend.
L'étape publie donc DEUX bornes, et elles encadrent la vérité :

* la borne **BASSE** — « module dérivé » : un module dont l'accès solaire
  passe sous un seuil SAISI est mis hors de la chaîne ; sa tension est
  perdue, le courant de la chaîne ne s'effondre pas. C'est la valeur RETENUE
  dans la cascade (``entree.modele``). Une diode de dérivation ne conduit que
  lorsqu'elle fait gagner : le point de fonctionnement retenu est donc le
  MEILLEUR des deux, jamais un point que l'électronique refuserait ;
* la borne **HAUTE** — « courant série » : le courant de la chaîne est borné
  par son module le moins éclairé. C'est l'hypothèse SANS diode de
  dérivation, donc la plus pessimiste.

L'écart entre les deux bornes est publié tel quel, avec les deux pages citées.

AUCUNE NOTION DE DIODE DANS LE DÉPÔT — ET C'EST DIT
-----------------------------------------------------
Le dépôt ne porte aujourd'hui aucun nombre de brins protégés (ni au stock, ni
au calepinage, ni au noyau) : la contrainte s'applique donc au MODULE ENTIER,
et ``entree.granularite`` le dit mot pour mot. Si une fiche publie un jour ce
nombre — lu ICI sans migration, par simple lecture défensive du champ —, la
granularité devient le BRIN et l'entrée le publie. Aurora journalise
l'hypothèse symétrique de son côté (« each bypass diode in the design has a
voltage drop of approximately 0.7 V », « approximately 2.1 V » pour trois
diodes en série,
https://help.aurorasolar.com/hc/en-us/articles/220132468-Aurora-Simulation-Engine).

CE QUI FAIT S'OMETTRE L'ÉTAPE — JAMAIS UNE APPROXIMATION
-----------------------------------------------------------
Pas de table d'affectation, pas de document de toiture, pas d'accès solaire,
aucune chaîne mesurable, ou pas de seuil de dérivation saisi : l'étape est
OMISE en nommant le champ qui manque. Aucun facteur forfaitaire
d'atténuation d'ombrage n'existe dans ce module — ni celui d'un logiciel du
marché, ni aucun autre : quand l'accès par module est indisponible, l'étape
est OMISE, elle n'est jamais approchée (D-CALX 7).

Micro-onduleur ou optimiseur déclaré : la chaîne n'impose plus son courant à
ses modules, et les deux bornes valent alors la perte linéaire — donc un
excédent nul, avec sa raison publiée.

Module PUR : aucune base, aucun réseau, aucun appel PVGIS.
"""
from __future__ import annotations

from apps.calepinage.services import etapes
from apps.calepinage.services.ombrage_chaines import (
    MOTIF_SANS_ACCES, ombrage_des_chaines)

#: Le nom du poste — celui de ``chaine_pertes.ORDRE_ETAPES``.
POSTE = 'mismatch_ombrage'

#: La clé de réglage société lue ici (registre CALX145). Non saisie ⇒ étape
#: OMISE en la nommant : aucun seuil n'est deviné.
CLE_REGLAGE = 'seuil_derivation_acces'

#: Le nom des deux bornes. La borne BASSE est celle qui part dans la cascade.
MODELE_DERIVATION = 'derivation'
MODELE_COURANT_SERIE = 'courant_serie'

#: Les noms de champ sous lesquels une fiche module POURRAIT publier son
#: nombre de brins protégés par une diode de dérivation. Aucun n'existe dans
#: le dépôt aujourd'hui : la lecture est défensive, et son absence est DITE.
CHAMPS_BRINS = ('brins_proteges', 'diodes_bypass', 'nb_diodes_bypass',
                'nombre_diodes_bypass', 'substrings')

#: Les clés sous lesquelles une ligne d'affectation peut déclarer que son
#: module n'est plus contraint par le courant de sa chaîne.
CHAMPS_SANS_CONTRAINTE = ('micro_onduleur', 'microonduleur', 'optimiseur',
                          'optimiseur_produit')

MOTIF_SANS_AFFECTATION = (
    "Le contexte ne porte pas la table d'affectation des modules aux chaînes "
    '(« affectation », services/chaines.py) : sans elle, on ne sait pas '
    'QUELS modules sont en série, donc aucune contrainte de chaîne ne peut '
    "être mesurée. Rien n'est supposé.")

MOTIF_SANS_LAYOUT = (
    "Le contexte ne porte pas le document de toiture : l'accès solaire par "
    'module y est lu (roof_layout v2, zones[].geometry.solarAccess), et sans '
    "lui aucune dispersion I-V n'est mesurable.")

MOTIF_AUCUNE_CHAINE_MESURABLE = (
    "La table d'affectation et le document sont bien là, mais AUCUNE chaîne "
    "n'a d'accès solaire calculé sur ses modules : un module sans accès "
    "calculé n'est pas un module non ombré, et rien n'est complété.")

MOTIF_CHAINES_A_VIDE = (
    "Les chaînes mesurées ne portent aucune énergie de référence (tous les "
    "accès solaires calculés valent zéro) : l'excédent électrique au-delà de "
    'la perte linéaire ne se définit pas, il reste donc non publié.')

MOTIF_SEUIL_ABSENT = (
    "Aucun seuil d'accès solaire de dérivation n'est saisi pour cette "
    'société : la borne « module dérivé » ne se calcule pas sans lui, et '
    "aucune valeur n'est supposée à sa place (D-CALX 7).")

#: Ce qui est publié quand la granularité reste le module entier.
HYPOTHESE_MODULE = (
    'Le nombre de brins protégés par une diode de dérivation ne figure sur '
    'aucune fiche : la contrainte est appliquée au MODULE ENTIER, hypothèse '
    'la plus pessimiste pour la borne haute. La fourchette encadre la '
    "vérité, elle ne prétend pas la trancher.")

#: Ce qui est publié quand une fiche publie ce nombre.
HYPOTHESE_BRIN = (
    'La fiche module publie {brins} brin(s) protégé(s) par diode de '
    'dérivation : la contrainte porte sur le BRIN et non sur le module '
    "entier. L'accès solaire, lui, est lu PAR MODULE : le document ne "
    "localise pas l'ombre à l'intérieur du module, et aucune répartition "
    "entre brins n'est inventée ici.")

#: La raison publiée pour une chaîne qui n'impose plus son courant.
RAISON_SANS_CONTRAINTE = (
    'Un micro-onduleur ou un optimiseur est déclaré sur cette chaîne : '
    "chaque module y travaille à son propre point de puissance, la chaîne "
    "ne lui impose plus son courant. L'excédent de dispersion est donc nul "
    '— ce qui ne veut pas dire que le module n\'est pas ombré : sa perte '
    "linéaire reste comptée par l'étape « accès module ».")

#: Les deux pages citées dans ``cascade[].reference``.
REFERENCE = (
    'PV*SOL — Shading due to nearby objects : « selon le nombre de brins '
    "ombrés, la caractéristique du module s'effondre » — "
    'https://help.valentin-software.com/pvsol/en/calculation/pv-modules/'
    'shading-due-to-nearby-objects/. HelioScope — Modeling 101 : la '
    'variabilité du champ est modélisée par « IV curve mismatch » — '
    'https://help-center.helioscope.com/hc/en-us/articles/'
    '13804165205395-Modeling-101. Lecture du dépôt : '
    'services/ombrage_chaines.py (accès solaire par chaîne) et '
    'services/chaines.py (affectation module → chaîne).')

__all__ = ['POSTE', 'CLE_REGLAGE', 'MODELE_DERIVATION',
           'MODELE_COURANT_SERIE', 'CHAMPS_BRINS', 'CHAMPS_SANS_CONTRAINTE',
           'MOTIF_SANS_AFFECTATION', 'MOTIF_SANS_LAYOUT',
           'MOTIF_AUCUNE_CHAINE_MESURABLE', 'MOTIF_CHAINES_A_VIDE',
           'MOTIF_SEUIL_ABSENT', 'HYPOTHESE_MODULE', 'HYPOTHESE_BRIN',
           'RAISON_SANS_CONTRAINTE', 'REFERENCE', 'appliquer']


def appliquer(serie, contexte):
    """``(serie, etape)`` — l'excédent I-V des chaînes ombrées, ou son silence.

    Fonction PURE : ni ``serie`` ni ses points ne sont modifiés sur place.
    """
    contexte = contexte if isinstance(contexte, dict) else {}
    libelle = _libelle()

    affectation = _affectation(contexte)
    if not affectation:
        return serie, etapes.etape_omise(libelle, MOTIF_SANS_AFFECTATION,
                                         champ='affectation')
    layout = _layout(contexte)
    if not layout:
        return serie, etapes.etape_omise(libelle, MOTIF_SANS_LAYOUT,
                                         champ='ombrage.layout')

    lecture = ombrage_des_chaines(layout, affectation)
    if not lecture['mesure']:
        return serie, etapes.etape_omise(libelle, MOTIF_SANS_ACCES,
                                         champ='ombrage.solarAccess')

    repere = _repere_du_pan(contexte)
    chaines = [chaine for chaine in lecture['chaines']
               if chaine['modules_mesures'] and (repere is None
                                                 or chaine['pan'] == repere)]
    if not chaines:
        return serie, etapes.etape_omise(libelle,
                                         MOTIF_AUCUNE_CHAINE_MESURABLE,
                                         champ='ombrage.solarAccess.values')

    seuil = etapes.reglage(contexte, CLE_REGLAGE)
    valeur_seuil = _nombre(seuil.get('valeur')) if seuil else None
    if valeur_seuil is None:
        return serie, etapes.etape_omise(
            libelle, MOTIF_SEUIL_ABSENT,
            champ='reglages_simulation.%s' % CLE_REGLAGE)

    brins = _brins_proteges(contexte)
    sans_contrainte = _chaines_sans_contrainte(contexte, affectation)
    mesures = [_mesurer_chaine(chaine, valeur_seuil, sans_contrainte)
               for chaine in chaines]

    lineaire = sum(mesure['lineaire'] for mesure in mesures)
    if lineaire <= 0.0:
        return serie, etapes.etape_omise(libelle, MOTIF_CHAINES_A_VIDE,
                                         champ='ombrage.solarAccess.values')
    basse = sum(mesure['derivation'] for mesure in mesures)
    haute = sum(mesure['courant_serie'] for mesure in mesures)
    nominal = sum(mesure['modules_mesures'] for mesure in mesures)

    facteur = basse / lineaire
    rendue = etapes.mettre_a_l_echelle(serie, facteur)
    entree = {
        'modele': MODELE_DERIVATION,
        'seuil_acces_derivation': {
            'valeur': valeur_seuil,
            'source': seuil.get('source'),
            'reference': seuil.get('reference'),
            'cle': CLE_REGLAGE,
        },
        'granularite': 'brin' if brins else 'module',
        'brins_proteges': brins,
        'hypothese': (HYPOTHESE_BRIN.format(brins=brins) if brins
                      else HYPOTHESE_MODULE),
        'bornes': {
            'basse': _borne(MODELE_DERIVATION, basse, lineaire, nominal),
            'haute': _borne(MODELE_COURANT_SERIE, haute, lineaire, nominal),
        },
        # L'écart des deux BORNES, en points de pourcentage : il se lit dans
        # le même sens que les pertes qu'elles publient, donc positif.
        'ecart_bornes_pct': _pourcentage(basse, haute, lineaire),
        'facteur_applique': round(facteur, 6),
        'perte_lineaire_deja_appliquee': bool((serie or {}).get(
            'acces_module')),
        'pan': repere,
        'chaines_mesurees': len(mesures),
        'modules_mesures': nominal,
        'modules_sans_acces': list(lecture['modules_sans_acces']),
        'chaines': [_publier_chaine(mesure) for mesure in mesures],
        'chaines_sans_contrainte': [
            {'chaine': mesure['chaine'], 'pan': mesure['pan'],
             'raison': RAISON_SANS_CONTRAINTE}
            for mesure in mesures if mesure['sans_contrainte']],
        'avertissements': list(lecture['avertissements']),
    }
    return rendue, etapes.etape_appliquee(
        libelle, source=seuil.get('source'), reference=REFERENCE,
        entree=entree)


# ── la mesure d'une chaîne ──────────────────────────────────────────────

def _mesurer_chaine(chaine, seuil, sans_contrainte):
    """Les trois puissances relatives d'une chaîne, en « modules pleins ».

    ``lineaire`` est ce que la perte d'irradiance seule laisserait (la somme
    des accès), ``courant_serie`` ce que la contrainte de série laisse sans
    aucune diode, et ``derivation`` ce que la même chaîne laisse quand les
    modules sous le seuil en sont sortis. Une diode ne conduit que
    lorsqu'elle fait gagner : la borne basse ne descend donc jamais sous la
    borne haute, par construction et non par correction après coup.
    """
    acces = [module['acces'] for module in chaine['modules']
             if module['acces'] is not None]
    mesures = len(acces)
    lineaire = sum(acces)
    exempte = (chaine['pan'], chaine['chaine']) in sans_contrainte
    if exempte:
        return {
            'chaine': chaine['chaine'], 'pan': chaine['pan'],
            'mppt': chaine['mppt'], 'modules_mesures': mesures,
            'acces_min': chaine['acces_min'], 'lineaire': lineaire,
            'courant_serie': lineaire, 'derivation': lineaire,
            'modules_derives': [], 'sans_contrainte': True,
        }
    courant_serie = mesures * min(acces)
    retenus = [valeur for valeur in acces if valeur >= seuil]
    derivation = max(sum(retenus), courant_serie)
    derives = [module['module'] for module in chaine['modules']
               if module['acces'] is not None and module['acces'] < seuil]
    return {
        'chaine': chaine['chaine'], 'pan': chaine['pan'],
        'mppt': chaine['mppt'], 'modules_mesures': mesures,
        'acces_min': chaine['acces_min'], 'lineaire': lineaire,
        'courant_serie': courant_serie, 'derivation': derivation,
        'modules_derives': derives, 'sans_contrainte': False,
    }


def _publier_chaine(mesure):
    """Ce qu'une chaîne publie — des parts relatives, jamais des kWh."""
    return {
        'chaine': mesure['chaine'],
        'pan': mesure['pan'],
        'mppt': mesure['mppt'],
        'modules_mesures': mesure['modules_mesures'],
        'acces_min': mesure['acces_min'],
        'modules_derives': list(mesure['modules_derives']),
        'sans_contrainte': mesure['sans_contrainte'],
        'excedent_basse_pct': _pourcentage(mesure['lineaire'],
                                           mesure['derivation'],
                                           mesure['lineaire']),
        'excedent_haute_pct': _pourcentage(mesure['lineaire'],
                                           mesure['courant_serie'],
                                           mesure['lineaire']),
    }


def _borne(modele, puissance, lineaire, nominal):
    """Une borne publiée : son excédent, et la perte totale de la chaîne.

    ``excedent_pct`` est ce que CETTE étape retire (au-delà de la perte
    linéaire déjà appliquée) ; ``perte_chaine_pct`` est la perte de la chaîne
    face à des modules non ombrés — c'est le chiffre qui se lit à l'écran, et
    il ne sort JAMAIS de la cascade, où seul l'excédent compte.
    """
    return {
        'modele': modele,
        'excedent_pct': _pourcentage(lineaire, puissance, lineaire),
        'perte_chaine_pct': _pourcentage(nominal, puissance, nominal),
    }


def _pourcentage(depart, arrivee, base):
    """``100 × (depart − arrivee) / base``, arrondi — ou ``None`` sans base."""
    if not base:
        return None
    return round(100.0 * (depart - arrivee) / base, 3)


# ── les entrées, une par une ────────────────────────────────────────────

def _libelle():
    """Le libellé FRANÇAIS du poste, déclaré une seule fois (CALX148)."""
    from apps.calepinage.services.chaine_pertes import LIBELLES

    return LIBELLES[POSTE]


def _affectation(contexte):
    """La table module → chaîne, ou ``()``.

    Deux emplacements sont acceptés : la clé de contexte que CALX5 pose, et
    le bloc électrique du résultat quand c'est lui qui voyage.
    """
    lue = contexte.get('affectation')
    if not lue:
        electrique = contexte.get('electrique')
        lue = (electrique.get('affectation')
               if isinstance(electrique, dict) else None)
    if not isinstance(lue, (list, tuple)):
        return ()
    return tuple(ligne for ligne in lue if isinstance(ligne, dict))


def _layout(contexte):
    """Le document de toiture, lu là où l'ordonnanceur le pose."""
    ombrage = contexte.get('ombrage')
    layout = ombrage.get('layout') if isinstance(ombrage, dict) else None
    layout = layout or contexte.get('layout')
    return layout if isinstance(layout, dict) else None


def _repere_du_pan(contexte):
    """Le repère du pan que cette série décrit, ou ``None``.

    Même lecture que ``etapes/acces_module.py`` : quand le contexte nomme le
    pan, seules SES chaînes entrent dans la mesure.
    """
    plan = contexte.get('plan')
    if isinstance(plan, dict):
        for cle in ('cle', 'label', 'id'):
            if plan.get(cle):
                return str(plan[cle])
        return None
    return str(plan) if plan else None


def _brins_proteges(contexte):
    """Le nombre de brins protégés publié par la fiche module, ou ``None``.

    Lecture DÉFENSIVE : la fiche est un dict de specs aujourd'hui, et rien
    n'interdit qu'elle devienne un objet. Aucun champ n'existe dans le dépôt,
    donc aucune migration n'est demandée ici : l'absence est la règle, et
    elle est publiée.
    """
    fiche = contexte.get('fiche_module')
    if fiche is None:
        return None
    for champ in CHAMPS_BRINS:
        brut = (fiche.get(champ) if isinstance(fiche, dict)
                else getattr(fiche, champ, None))
        nombre = _nombre(brut)
        if nombre is not None and nombre >= 1:
            return int(nombre)
    return None


def _chaines_sans_contrainte(contexte, affectation):
    """``{(pan, chaîne)}`` — les chaînes qui n'imposent plus leur courant.

    Deux déclarations sont lues : la ligne d'affectation elle-même (un
    module sous micro-onduleur ou optimiseur), et l'optimiseur déclaré pour
    tout le document. Rien n'est déduit d'une fiche onduleur : un onduleur
    de chaîne n'est pas un micro-onduleur, et le deviner au nom serait une
    invention.
    """
    global_ = _optimiseur_du_document(contexte)
    exemptes = set()
    for ligne in affectation:
        chaine = ligne.get('chaine')
        if chaine is None:
            continue
        declare = global_ or any(ligne.get(champ)
                                 for champ in CHAMPS_SANS_CONTRAINTE)
        if declare:
            exemptes.add((str(ligne.get('pan') or ''), chaine))
    return exemptes


def _optimiseur_du_document(contexte):
    """Un optimiseur ou micro-onduleur est-il déclaré pour tout le document ?"""
    if contexte.get('fiche_optimiseur'):
        return True
    electrique = contexte.get('electrique')
    if isinstance(electrique, dict):
        return bool(electrique.get('optimiseur_produit')
                    or electrique.get('optimiseur'))
    return False


def _nombre(valeur):
    """Un flottant lisible, ou ``None`` — jamais une valeur de remplacement."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return None if nombre != nombre else nombre
