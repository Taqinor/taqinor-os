# -*- coding: utf-8 -*-
"""ACAL461 — étape « ombrage du diffus » : ``gd`` × facteur de vue du ciel.

Les étapes d'ombrage existantes ne dératent que le direct ``gb``. Le diffus
d'un pan masqué par un voisin est réduit lui aussi : l'atelier (ACAL460)
écrit le facteur dans ``zones[].geometry.skyViewFactor.facteur``. Cette étape
ne touche QUE ``gd`` (aucun double compte) ; elle est hors ``ETAPES_OMBRAGE``
(D-ACAL-6). PVsyst évalue l'ombrage diffus à part de celui du faisceau :
https://www.pvsyst.com/help/project-design/shadings/index.html
"""
from __future__ import annotations

from apps.calepinage.services import etapes
from apps.calepinage.services.pvgis_serie import MOTIF_COMPOSANTES_ABSENTES

from ..valeurs import nombre as _nombre
from .acces_module import _repere_du_pan

POSTE = 'ombrage_diffus'
CHAMP = 'ombrage.skyViewFactor'

MOTIF_SANS_FACTEUR = (
    "Le document de toiture ne porte aucun facteur de vue du ciel : "
    "l'ombrage de la lumière diffuse n'est pas calculé, et rien n'est "
    "supposé.")
MOTIF_HORIZON_INCLUS = (
    "Le facteur de vue du ciel déclare inclure l'horizon lointain "
    "(« horizon: true ») : l'horizon a son propre poste, l'appliquer ici le "
    "compterait deux fois.")
REFERENCE = ('PVsyst — Shadings (ombrage du diffus à part du faisceau) : '
             'https://www.pvsyst.com/help/project-design/shadings/index.html.'
             ' Lecture du document : zones[].geometry.skyViewFactor (ACAL389).')

__all__ = ['POSTE', 'CHAMP', 'MOTIF_SANS_FACTEUR', 'MOTIF_HORIZON_INCLUS',
           'facteur_du_pan', 'appliquer']


def facteur_du_pan(contexte):
    """Le bloc ``skyViewFactor`` du pan simulé (dict), ou ``None``.

    Sans pan nommé, le bloc n'est rendu que si UN SEUL pan en porte un.
    """
    ombrage = contexte.get('ombrage')
    layout = ((ombrage.get('layout') if isinstance(ombrage, dict) else None)
              or contexte.get('layout'))
    if not isinstance(layout, dict):
        return None
    repere = _repere_du_pan(contexte)
    blocs = []
    for zone in (layout.get('zones') or []):
        geometrie = zone.get('geometry') if isinstance(zone, dict) else None
        bloc = (geometrie.get('skyViewFactor')
                if isinstance(geometrie, dict) else None)
        if not isinstance(bloc, dict):
            continue
        if repere is None:
            blocs.append(bloc)
        elif repere in (str(zone.get('label')), str(zone.get('id'))):
            return bloc
    return blocs[0] if len(blocs) == 1 else None


def appliquer(serie, contexte):
    """``(serie, etape)`` — le diffus multiplié par le facteur du pan."""
    from apps.calepinage.services.chaine_pertes import LIBELLES

    libelle = LIBELLES[POSTE]
    bloc = facteur_du_pan(contexte if isinstance(contexte, dict) else {})
    facteur = _nombre(bloc.get('facteur')) if bloc else None
    if facteur is None or not 0.0 <= facteur <= 1.0:
        return serie, etapes.etape_omise(libelle, MOTIF_SANS_FACTEUR,
                                         champ=CHAMP)
    methode = bloc.get('methode')
    if isinstance(methode, dict) and methode.get('horizon') is True:
        return serie, etapes.etape_omise(libelle, MOTIF_HORIZON_INCLUS,
                                         champ=CHAMP + '.methode.horizon')
    points = (serie or {}).get('points') or []
    if not points or any(p.get('gd_i_w_m2') is None for p in points):
        return serie, etapes.etape_omise(libelle, MOTIF_COMPOSANTES_ABSENTES)
    suite = []
    for point in points:
        copie = dict(point)
        copie['gd_i_w_m2'] = point['gd_i_w_m2'] * facteur
        _recomposer(point, copie)
        suite.append(copie)
    rendue = dict(serie)
    rendue['points'] = suite
    entree = {'facteur': round(facteur, 6),
              'methode': dict(methode) if isinstance(methode, dict) else {},
              'composantes_touchees': 'gd_i_w_m2 seule (le direct et le '
                                      'réfléchi ne sont pas touchés)'}
    return rendue, etapes.etape_appliquee(
        libelle, source='document', reference=REFERENCE, entree=entree)


def _recomposer(avant, apres):
    """``gi = gb + gd + gr`` et l'énergie suit le même rapport (patron
    ``ombrage_proche._reporter``)."""
    globale = ((_nombre(avant.get('gb_i_w_m2')) or 0.0) + apres['gd_i_w_m2']
               + (_nombre(avant.get('gr_i_w_m2')) or 0.0))
    globale_avant = _nombre(avant.get('gi_w_m2'))
    apres['gi_w_m2'] = globale
    if not globale_avant:
        return
    for colonne in etapes.ORDRE_COLONNES_ENERGIE:
        valeur = _nombre(avant.get(colonne))
        if valeur is not None:
            apres[colonne] = valeur * (globale / globale_avant)
