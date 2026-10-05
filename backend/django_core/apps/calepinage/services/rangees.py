"""ACAL230 - UNE definition ORIENTEE de la « rangee » d'un pan.

Le constat
==========
Le plan de pose, le classeur (colonne ``Rangee``) et la BOM de fixation ne
comptaient pas les memes rangees : le plan et le classeur groupaient les
modules sur leur ordonnee NORD seule (``export_tableur.rangees_du_pan``), la
fixation les projetait sur la ligne de plus grande pente de l'azimut du pan.
Pour un pan non plein sud (172, 188, 135, 200 degres), les modules d'une meme
rangee physique ne partagent plus la meme ordonnee : un pan de 3 rangees x 5
modules sortait en 15 reperes ``R`` sans fleche.

La definition unique
====================
* l'axe de GROUPEMENT est la ligne de plus grande pente du pan : la
  projection ``pente = est*sin(a) + nord*cos(a)`` (``a`` = azimut de face du
  pan, convention du document) ; deux modules sont sur la meme rangee quand
  leurs projections different de moins du centimetre (``PAS_DE_RANGEE_M``) ;
* l'axe de POSITION lui est perpendiculaire : ``est*cos(a) - nord*sin(a)`` ;
* la numerotation part de la rangee la plus BASSE de la pente (l'egout) ;
* SANS azimut connu, le regroupement historique par ordonnee est conserve
  (numerotation par ordonnee croissante, position = abscisse).

Ce module est le SEUL lecteur de cette definition : ``fixation`` l'appelle
(``positions_par_rangee``), le plan de pose et le classeur aussi
(``rangees_du_pan``). Cote navigateur, ``coupeRangees.js::pasRangeeMesure``
lit un PAS (pas un numero de rangee) : il n'est pas touche ici.
"""
from __future__ import annotations

import math

__all__ = ['PAS_DE_RANGEE_M', 'rangees_du_pan', 'positions_par_rangee',
           'centres_par_rangee']

#: Arrondi de groupement des rangees : le centimetre. Deux modules poses a
#: moins d'un centimetre l'un de l'autre sur l'axe de groupement sont sur la
#: meme rangee.
PAS_DE_RANGEE_M = 0.01


def _axes(azimut_deg):
    """``(groupement, position)`` : deux fonctions ``(est, nord) -> mesure``.

    Sans azimut : groupement sur l'ordonnee, position sur l'abscisse.
    """
    if azimut_deg is None:
        return (lambda est, nord: nord), (lambda est, nord: est)
    angle = math.radians(azimut_deg)
    sin_a, cos_a = math.sin(angle), math.cos(angle)
    return (lambda est, nord: est * sin_a + nord * cos_a,
            lambda est, nord: est * cos_a - nord * sin_a)


def _groupes(modules, azimut_deg):
    """``[[centre, ...] par rangee]`` dans l'ordre de NUMEROTATION.

    Les modules sont tries sur l'axe de groupement ; un ecart superieur au
    pas ouvre une nouvelle rangee. Sans azimut la numerotation suit
    l'ordonnee croissante ; avec un azimut elle part de l'egout (la
    projection sur la pente la plus grande), ce qui redonne EXACTEMENT la
    numerotation historique pour un pan plein sud.
    """
    groupement, _position = _axes(azimut_deg)
    mesures = sorted(((groupement(est, nord), (est, nord))
                      for est, nord in modules), key=lambda m: m[0])
    groupes, dernier = [], None
    for valeur, centre in mesures:
        if dernier is None or valeur - dernier > PAS_DE_RANGEE_M:
            groupes.append([])
        groupes[-1].append(centre)
        dernier = valeur
    if azimut_deg is not None:
        groupes.reverse()
    return groupes


def rangees_du_pan(modules, azimut_deg=None):
    """``centre -> numero de rangee`` (a partir de 1), orientee par l'azimut.

    PUBLIQUE parce qu'elle est la SEULE definition de « rangee » du module :
    le plan de pose (CAL211), le classeur (CAL179) et la nomenclature de
    fixation (CALX359) l'appellent. Deux definitions de la rangee feraient
    diverger le plan remis a l'equipe, le tableau remis au bureau d'etudes et
    les quantites de rails.
    """
    numeros = {}
    for rang, groupe in enumerate(_groupes(modules, azimut_deg), start=1):
        for centre in groupe:
            numeros[centre] = rang
    return {centre: numeros[centre] for centre in modules}


def positions_par_rangee(modules, azimut_deg=None):
    """``[[t, ...] par rangee]`` : positions TRIEES le long de chaque rangee."""
    _groupement, position = _axes(azimut_deg)
    return [sorted(position(est, nord) for est, nord in groupe)
            for groupe in _groupes(modules, azimut_deg)]


def centres_par_rangee(modules, azimut_deg=None):
    """``[(numero, [centre, ...])]`` - les centres de chaque rangee, dans
    l'ordre de pose : abscisse croissante pour un pan sans azimut ET pour un
    pan plein sud (comme avant) ; pour un pan tourne, le meme sens, mesure
    sur l'axe de position de la rangee.
    """
    _groupement, position = _axes(azimut_deg)
    sens = 1 if azimut_deg is None else -1
    return [(rang, sorted(groupe,
                          key=lambda c: sens * position(c[0], c[1])))
            for rang, groupe in enumerate(_groupes(modules, azimut_deg),
                                          start=1)]
