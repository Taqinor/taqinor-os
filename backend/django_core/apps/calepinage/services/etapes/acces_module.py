# -*- coding: utf-8 -*-
"""CALX158 — étape « accès module » : ``solarAccess`` LU MODULE PAR MODULE.

LE CONSTAT
----------
``services/ombrage_chaines.py`` sait déjà lire ``zones[].geometry.
solarAccess.values`` module par module — mais son propre docstring le dit :
« AUCUN kWh, aucune perte : ce service publie de la géométrie ». Aucun
consommateur n'existait hors de ses tests. Ce module est ce consommateur :
il réutilise :func:`~apps.calepinage.services.ombrage_chaines.acces_par_module`
et transforme cette géométrie en une perte, sans rien réécrire.

Parité : HelioScope modélise la performance de CHAQUE module, à chaque
heure, là où un outil qui « simule un module et met le résultat à l'échelle »
ne le peut pas
(https://help-center.helioscope.com/hc/en-us/articles/8537729072019-Maximum-Allowable-Design-Size).

CE QUE LE DOCUMENT DOIT DÉCLARER — SINON L'ÉTAPE S'OMET
---------------------------------------------------------
``solarAccess.method`` n'est pas décoratif : deux jeux de valeurs issus de
deux tracés différents ne sont pas comparables. La méthode doit dire

* ``horizon`` — l'accès inclut-il le masque LOINTAIN ? Il doit valoir
  ``False`` : l'horizon reste un poste séparé (CALX156), et une lecture qui
  l'inclut le compterait deux fois ;
* ``rangees`` — l'auto-ombrage entre rangées est-il déjà compté ? La réponse
  ne change rien ICI (elle pilote l'exclusivité de ``inter_rangees`` chez
  l'ordonnanceur), mais une méthode qui ne la dit pas laisse la question
  ouverte : l'étape s'omet en nommant la clé.

UN MODULE ``null`` N'EST PAS UN MODULE À 100 %
-----------------------------------------------
Le contrat v2 l'interdit explicitement : ``null`` = module NON calculé. Ces
modules sont publiés dans ``entree.modules_sans_acces`` et EXCLUS de la
moyenne — jamais complétés à 1, ce qui remonterait artificiellement l'accès
du champ.

LA RÉSOLUTION EST DITE, JAMAIS SURJOUÉE
-----------------------------------------
``values`` porte UN facteur par module, pas une courbe horaire : l'étape
applique donc un facteur CONSTANT au direct de chaque heure et le DIT
(``entree.resolution``, ``entree.application``, ``entree.avertissement``)
plutôt que de prétendre à une lecture heure par heure qu'elle n'a pas. La
simulation module par module (CALX182) s'appuiera sur
``serie['acces_module']``, que cette étape pose sur la série rendue.
"""
from __future__ import annotations

from apps.calepinage.services import etapes
from apps.calepinage.services.ombrage_chaines import (
    MOTIF_SANS_ACCES, acces_par_module)
from apps.calepinage.services.pvgis_serie import MOTIF_COMPOSANTES_ABSENTES

#: Le nom du poste — celui de ``chaine_pertes.ORDRE_ETAPES``.
POSTE = 'acces_module'

#: Les deux clés que ``solarAccess.method`` DOIT déclarer, et ce que
#: l'absence de chacune empêche de trancher.
CLES_METHODE = {
    'horizon': (
        "la méthode ne dit pas si l'accès solaire inclut le masque LOINTAIN "
        "(« horizon »). L'horizon est un poste séparé (CALX156) : sans cette "
        'réponse, il serait compté une fois ici et une fois là.'),
    'rangees': (
        "la méthode ne dit pas si l'auto-ombrage entre RANGÉES est déjà "
        "compté (« rangees ») : sans cette réponse, l'ombre des rangées "
        "serait comptée deux fois avec l'étape « inter_rangees »."),
}

#: Le motif publié quand la méthode déclare inclure l'horizon lointain.
MOTIF_HORIZON_INCLUS = (
    "La méthode d'accès solaire déclare inclure le masque LOINTAIN "
    '(« horizon: true ») : l\'horizon a son propre poste dans la cascade '
    "(CALX156) et l'appliquer aussi ici le compterait deux fois. Reprenez la "
    "lecture d'accès solaire sans l'horizon, ou laissez l'horizon seul.")

#: Le motif publié quand aucun module du plan n'a d'accès calculé.
MOTIF_AUCUN_MODULE_CALCULE = (
    "Le document porte bien une lecture d'accès solaire, mais AUCUN module "
    "n'y est calculé (toutes les entrées valent « null »). Un module sans "
    "accès calculé n'est pas un module non ombré : rien n'est supposé.")

#: L'avertissement publié quand la lecture n'est pas horaire.
AVERTISSEMENT_ANNUEL = (
    "Le document ne porte qu'UN facteur d'accès par module, pas une courbe "
    'horaire : le facteur est appliqué CONSTANT à toutes les heures. La '
    'perte publiée est donc une perte de résolution ANNUELLE, pas une '
    "lecture heure par heure.")

#: La référence publiée dans ``cascade[].reference``.
REFERENCE = (
    'HelioScope — Maximum Allowable Design Size : la performance de chaque '
    'module est modélisée, plutôt qu’un module simulé puis mis à l’échelle — '
    'https://help-center.helioscope.com/hc/en-us/articles/'
    '8537729072019-Maximum-Allowable-Design-Size. Lecture du document : '
    'roof_layout v2, zones[].geometry.solarAccess (CAL248).')

__all__ = ['POSTE', 'CLES_METHODE', 'MOTIF_HORIZON_INCLUS',
           'MOTIF_AUCUN_MODULE_CALCULE', 'AVERTISSEMENT_ANNUEL', 'REFERENCE',
           'appliquer']


def appliquer(serie, contexte):
    """``(serie, etape)`` — le direct dératé par l'accès solaire des modules.

    Fonction PURE : ni ``serie`` ni ses points ne sont modifiés sur place.
    """
    contexte = contexte if isinstance(contexte, dict) else {}
    libelle = _libelle()
    ombrage = contexte.get('ombrage') or {}

    acces = _lecture_acces(ombrage)
    if acces is None:
        return serie, etapes.etape_omise(libelle, MOTIF_SANS_ACCES,
                                         champ='ombrage.solarAccess')

    methode = _methode(acces)
    for cle, motif in CLES_METHODE.items():
        if not isinstance(methode.get(cle), bool):
            return serie, etapes.etape_omise(
                libelle, f"L'accès solaire est lu, mais {motif}",
                champ=f'ombrage.solarAccess.method.{cle}')
    if methode['horizon']:
        return serie, etapes.etape_omise(libelle, MOTIF_HORIZON_INCLUS)

    valeurs = _valeurs(contexte, ombrage, acces)
    if valeurs is None:
        return serie, etapes.etape_omise(libelle, MOTIF_SANS_ACCES,
                                         champ='ombrage.solarAccess.values')
    mesures = [valeur for valeur in valeurs if valeur is not None]
    if not mesures:
        return serie, etapes.etape_omise(libelle, MOTIF_AUCUN_MODULE_CALCULE,
                                         champ='ombrage.solarAccess.values')

    points = (serie or {}).get('points') or []
    if not points:
        return serie, etapes.etape_omise(
            libelle, "La série horaire est vide : aucun accès solaire ne "
            "peut y être appliqué.", champ='serie.points')
    if any(point.get('gb_i_w_m2') is None for point in points):
        return serie, etapes.etape_omise(libelle, MOTIF_COMPOSANTES_ABSENTES)

    # La moyenne ne porte QUE sur les modules calculés : un « null » complété
    # à 1 remonterait l'accès du champ (contrat v2, CAL248).
    facteur = sum(mesures) / len(mesures)
    sans_acces = [rang for rang, valeur in enumerate(valeurs)
                  if valeur is None]
    resolution = _resolution(methode)

    suite = _derater(serie, points, facteur)
    suite['acces_module'] = {
        'facteurs': list(valeurs),
        'facteur_moyen': round(facteur, 6),
        'modules_calcules': len(mesures),
        'modules_sans_acces': sans_acces,
        'resolution': resolution,
    }
    entree = {
        'acces_par_module': list(valeurs),
        'facteur_moyen': round(facteur, 6),
        'facteur_minimal': round(min(mesures), 6),
        'modules_calcules': len(mesures),
        'modules_lus': len(valeurs),
        'modules_sans_acces': sans_acces,
        'methode': dict(methode),
        'resolution': resolution,
        'application': 'facteur constant par heure, moyenne des modules '
                       'CALCULÉS',
        'composantes_touchees': 'gb_i_w_m2 seule (le diffus et le réfléchi '
                                'ne sont pas masqués)',
    }
    if resolution != 'horaire':
        entree['avertissement'] = AVERTISSEMENT_ANNUEL
    return suite, etapes.etape_appliquee(
        libelle, source='document', reference=REFERENCE, entree=entree)


# ── les entrées, une par une ────────────────────────────────────────────

def _libelle():
    """Le libellé FRANÇAIS du poste, déclaré une seule fois (CALX148)."""
    from apps.calepinage.services.chaine_pertes import LIBELLES

    return LIBELLES[POSTE]


def _lecture_acces(ombrage):
    """Le bloc ``solarAccess`` du contexte, ou ``None``.

    Les deux écritures sont acceptées — celle du document (``solarAccess``)
    et sa forme francisée —, exactement comme l'ordonnanceur les lit pour
    son exclusivité.
    """
    acces = ombrage.get('solar_access') or ombrage.get('solarAccess')
    return acces if isinstance(acces, dict) and acces else None


def _methode(acces):
    """La méthode déclarée, en dict — une chaîne ne déclare rien."""
    methode = acces.get('method')
    if not isinstance(methode, dict):
        methode = acces.get('methode')
    return methode if isinstance(methode, dict) else {}


def _resolution(methode):
    """La résolution que le document DÉCLARE, sans la surjouer."""
    declaree = methode.get('resolution')
    if isinstance(declaree, str) and declaree.strip():
        return declaree.strip()
    return 'horaire' if methode.get('horaire') is True else 'annuelle'


def _valeurs(contexte, ombrage, acces):
    """Les facteurs d'accès, module par module, ou ``None``.

    Trois lectures, dans l'ordre : la liste ``values`` du bloc lui-même, la
    table ``par_pan`` qu'un contexte peut porter, et enfin le document de
    toiture — relu par ``ombrage_chaines.acces_par_module``, le service qui
    connaît déjà l'ordre des modules d'un pan.
    """
    lues = _liste(acces.get('values'))
    if lues is not None:
        return lues

    par_pan = acces.get('par_pan')
    if not isinstance(par_pan, dict):
        layout = ombrage.get('layout') or contexte.get('layout')
        par_pan = acces_par_module(layout) if layout else {}
    if not par_pan:
        return None

    repere = _repere_du_pan(contexte)
    if repere is not None and repere in par_pan:
        return _liste(par_pan[repere])
    assemblees = []
    for cle in sorted(par_pan):
        liste = _liste(par_pan[cle])
        if liste:
            assemblees.extend(liste)
    return assemblees or None


def _repere_du_pan(contexte):
    """Le repère du pan que cette série décrit, ou ``None``.

    La chaîne s'applique à la série d'UN pan ; quand le contexte le nomme,
    seuls SES modules entrent dans la moyenne. Sans nom, tous les modules
    lus sont pris — et ``entree.modules_lus`` le dit.
    """
    plan = contexte.get('plan')
    if isinstance(plan, dict):
        for cle in ('cle', 'label', 'id'):
            if plan.get(cle):
                return str(plan[cle])
        return None
    return str(plan) if plan else None


def _liste(valeurs):
    """``[facteur ou None]`` lus dans une liste, ou ``None`` si ce n'en est
    pas une. Un facteur hors de [0, 1] est traité comme NON calculé : le
    contrat v2 borne ces valeurs, et les rogner en inventerait."""
    if not isinstance(valeurs, (list, tuple)):
        return None
    lues = []
    for valeur in valeurs:
        nombre = _nombre(valeur)
        lues.append(nombre if nombre is not None and 0.0 <= nombre <= 1.0
                    else None)
    return lues


# ── le dératage ─────────────────────────────────────────────────────────

def _derater(serie, points, facteur):
    """Une COPIE de la série dont le direct porte le facteur d'accès."""
    suite = []
    for point in points:
        copie = dict(point)
        copie['gb_i_w_m2'] = (_nombre(point.get('gb_i_w_m2')) or 0.0) * facteur
        _reporter(point, copie)
        suite.append(copie)
    rendue = dict(serie)
    rendue['points'] = suite
    return rendue


def _reporter(avant, apres):
    """Recompose ``gi_w_m2`` et met l'énergie à l'échelle du même rapport.

    ``G(i)`` est la SOMME des trois composantes sous ``components=1``
    (vérifié sur les réponses PVGIS réelles par
    ``tests/test_calx152_composantes.py``). Une colonne de puissance déjà
    présente suit le MÊME rapport, heure par heure.
    """
    diffuse = _nombre(avant.get('gd_i_w_m2')) or 0.0
    reflechie = _nombre(avant.get('gr_i_w_m2')) or 0.0
    globale_avant = _nombre(avant.get('gi_w_m2'))
    globale_apres = apres['gb_i_w_m2'] + diffuse + reflechie
    apres['gi_w_m2'] = globale_apres
    if not globale_avant:
        return
    rapport = globale_apres / globale_avant
    for colonne in etapes.ORDRE_COLONNES_ENERGIE:
        valeur = _nombre(avant.get(colonne))
        if valeur is not None:
            apres[colonne] = valeur * rapport


def _nombre(valeur):
    """Un flottant lisible, ou ``None`` — jamais une valeur de remplacement."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return None if nombre != nombre else nombre
