# -*- coding: utf-8 -*-
"""ACAL467 — la TABLE d'ombrage DIRECT par direction du soleil, lue par
l'étape « ombrage proche ».

Le document porte, par pan, ``zones[].geometry.shadeTable`` (contrat ACAL389,
écrit par ACAL459) : ``{azimutsDeg[], hauteursDeg[], facteurs[][]}``, lignes =
hauteurs, colonnes = azimuts, 1 = aucun ombrage, azimut 0 = nord, 90 = est.
Le facteur de la case la plus proche de la direction du soleil de l'heure
multiplie le SEUL direct ``gb_i_w_m2`` (PVsyst : faisceau par direction du
soleil, diffus à part — ACAL461). Aucune interpolation inventée.

La direction vient de ``core.calepinage.soleil.position_solaire`` ; la lecture
du site et de l'instant est celle de ``etapes/horizon.py``.
"""
from __future__ import annotations

from apps.calepinage.services import etapes
from core.calepinage.soleil import position_solaire
from ..valeurs import nombre as _nombre
from .acces_module import _repere_du_pan

#: Demi-tour en degrés : passe l'azimut « depuis le sud » du noyau solaire
#: (0 = sud) au repère du document (0 = nord, 90 = est), ACAL389.
DEMI_TOUR_DEG = 180.0

#: Tour complet en degrés (écart circulaire entre deux azimuts).
TOUR_DEG = 360.0

#: Le champ nommé quand la table sert.
CHAMP = 'zones[].geometry.shadeTable'

#: La référence publiée dans ``cascade[].reference``.
REFERENCE = (
    "PVsyst — Near shadings : table de facteurs d'ombrage par direction du "
    "soleil (faisceau ; diffus à part) : https://www.pvsyst.com/help/"
    'project-design/shadings/index.html. Table : ACAL389 / ACAL459, '
    'position du soleil : core.calepinage.soleil.')

__all__ = ['CHAMP', 'REFERENCE', 'appliquer_table']


def _table_du_pan(contexte):
    """La ``shadeTable`` lue du pan simulé, ou ``None``.

    Sans pan nommé, la table n'est rendue que si UN SEUL pan en porte une.
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
        bloc = (geometrie.get('shadeTable')
                if isinstance(geometrie, dict) else None)
        if not isinstance(bloc, dict):
            continue
        if repere is None:
            blocs.append(bloc)
        elif repere in (str(zone.get('label')), str(zone.get('id'))):
            return _forme_valide(bloc)
    return _forme_valide(blocs[0]) if len(blocs) == 1 else None


def _forme_valide(bloc):
    """``(azimuts, hauteurs, facteurs)`` ou ``None`` : refusée en bloc."""
    azimuts = [_nombre(v) for v in (bloc.get('azimutsDeg') or ())]
    hauteurs = [_nombre(v) for v in (bloc.get('hauteursDeg') or ())]
    lignes = bloc.get('facteurs')
    if (not azimuts or not hauteurs or None in azimuts or None in hauteurs
            or not isinstance(lignes, (list, tuple))
            or len(lignes) != len(hauteurs)):
        return None
    facteurs = []
    for ligne in lignes:
        if not isinstance(ligne, (list, tuple)) or len(ligne) != len(azimuts):
            return None
        lue = [_nombre(v) for v in ligne]
        if any(v is None or not 0.0 <= v <= 1.0 for v in lue):
            return None
        facteurs.append(lue)
    return azimuts, hauteurs, facteurs


def appliquer_table(serie, contexte):
    """``(serie dératée, entree)`` ou ``None`` si la table ne peut pas servir.

    ``None`` ⇒ l'appelant retombe sur la matrice 12 × 24, comme avant.
    """
    table = _table_du_pan(contexte)
    points = (serie or {}).get('points') or []
    site = contexte.get('site') or {}
    lat, lon = _nombre(site.get('lat')), _nombre(site.get('lon'))
    meteo = contexte.get('meteo') or {}
    if (table is None or not points or lat is None or lon is None
            or any(p.get('gb_i_w_m2') is None for p in points)
            or etapes.instant_utc(points[0], meteo) is None):
        return None
    azimuts, hauteurs, facteurs = table
    from .ombrage_proche import _reporter

    suite, ombrees = [], 0
    for point in points:
        instant = etapes.instant_utc(point, meteo)
        if instant is None:
            suite.append(point)
            continue
        soleil = position_solaire(
            lat, lon, annee=instant.year, mois=instant.month,
            jour=instant.day, heure_utc=instant.hour + instant.minute / 60.0)
        azimut = (soleil.azimut_depuis_sud_deg + DEMI_TOUR_DEG) % TOUR_DEG
        ligne = _plus_proche(hauteurs, soleil.elevation_deg, circulaire=False)
        colonne = _plus_proche(azimuts, azimut, circulaire=True)
        facteur = facteurs[ligne][colonne]
        directe = _nombre(point.get('gb_i_w_m2')) or 0.0
        ombrees += 1 if facteur < 1.0 and directe > 0.0 else 0
        copie = dict(point)
        copie['gb_i_w_m2'] = directe * facteur
        _reporter(point, copie)
        suite.append(copie)
    rendue = dict(serie)
    rendue['points'] = suite
    return rendue, {
        'source_ombrage': 'table', 'champ': CHAMP,
        'table': f'{len(hauteurs)} hauteurs × {len(azimuts)} azimuts',
        'convention': '1 = aucun ombrage ; case la plus proche, sans '
                      'interpolation',
        'heures_ombrees': ombrees, 'heures_lues': len(points),
        'composantes_touchees': 'gb_i_w_m2 seule (diffus et réfléchi '
                                'intacts)'}


def _plus_proche(valeurs, cible, *, circulaire):
    """Le rang de la valeur la plus proche de ``cible`` (écart circulaire)."""
    def ecart(valeur):
        delta = abs(valeur - cible)
        return min(delta, TOUR_DEG - delta) if circulaire else delta
    return min(range(len(valeurs)), key=lambda rang: ecart(valeurs[rang]))
