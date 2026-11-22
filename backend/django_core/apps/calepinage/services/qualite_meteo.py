"""ACAL763 — le RAPPORT DE QUALITÉ d'un fichier météo déposé : quatre lignes de nombres.

Le lecteur strict (``meteo_fichier.lire_serie_meteo``) refuse un trou, un doublon, un
horodatage sans fuseau. Il ne regarde ni la couverture de l'année, ni le signe des valeurs,
ni si l'heure du fichier est celle du soleil. Ce module le fait, au dépôt, et rend des
NOMBRES — jamais un verdict ni un seuil : le fichier reste accepté ou refusé comme avant.

  * ``couverture`` : heures lues, années, mois sans aucune mesure par année ;
  * ``decalage`` : médiane, sur les jours complets, de l'écart entre le centre des heures de
    la mesure (``gi_w_m2`` pondérant l'heure écrite) et celui du soleil calculé
    (``position_solaire``, sinus de l'élévation pondérant la même heure). Positif = la mesure
    tombe APRÈS le soleil. Les deux utilisent la même étiquette d'heure : une convention
    « début d'heure » vs « milieu d'heure » est donc un biais de 30 minutes assumé et non
    corrigé ici ;
  * ``negatifs`` : par colonne d'irradiance présente, le nombre de valeurs négatives et la
    plus petite ;
  * ``extraterrestre`` : heures où l'irradiance dépasse l'irradiance extraterrestre normale
    du jour (``pvlib.irradiance.get_extra_radiation``).

``decalage`` et ``extraterrestre`` exigent le point du site, que le fichier ne porte pas : sans
épingle ils valent ``None`` et ``motifs`` dit pourquoi.
"""
from __future__ import annotations

import datetime
import math
import statistics
from collections import defaultdict

from core.calepinage.soleil import position_solaire

__all__ = ['MOTIF_SANS_EPINGLE', 'rapport_de_qualite']

MOTIF_SANS_EPINGLE = 'épingle du site absente'
MOTIF_DECALAGE_MIXTE = (
    "le fichier déclare plusieurs décalages horaires : l'heure du soleil ne peut pas être "
    'placée sans choisir à la place de la société')
MOTIF_SANS_JOUR_COMPLET = 'aucun jour complet (24 heures) avec de la lumière dans ce fichier'

#: Les colonnes d'irradiance qu'un point peut porter (lecteur plan et lecteur horizontal).
COLONNES_IRRADIANCE = ('gi_w_m2', 'ghi_w_m2', 'dni_w_m2', 'dhi_w_m2',
                       'gb_i_w_m2', 'gd_i_w_m2', 'gr_i_w_m2')
HEURES_PAR_JOUR = 24  # un jour complet : 24 heures consécutives écrites


def _couverture(points):
    mois_par_annee = defaultdict(set)
    for p in points:
        mois_par_annee[p['annee']].add(p['mois'])
    annees = sorted(mois_par_annee)
    return {
        'heures_lues': len(points),
        'annees': annees,
        'mois_absents': {str(a): [m for m in range(1, 13) if m not in mois_par_annee[a]]
                         for a in annees},
    }


def _negatifs(points):
    sortie = {}
    for colonne in COLONNES_IRRADIANCE:
        valeurs = [p[colonne] for p in points if p.get(colonne) is not None]
        if not valeurs:
            continue
        neg = [v for v in valeurs if v < 0]
        sortie[colonne] = {'nombre': len(neg), 'plus_petite': min(neg) if neg else None}
    return sortie


def _colonne_principale(points):
    for colonne in ('gi_w_m2', 'ghi_w_m2'):
        if any(p.get(colonne) is not None for p in points):
            return colonne
    return None


def _jours(points):
    jours = defaultdict(list)
    for p in points:
        jours[(p['annee'], p['mois'], p['jour'])].append(p)
    return jours


def _decalage(points, colonne, latitude, longitude, decalage_minutes):
    """``(bloc, motif)`` : le bloc ``decalage`` ou ``None`` et son motif."""
    if decalage_minutes is None:
        return None, MOTIF_DECALAGE_MIXTE
    ecarts = []
    for (annee, mois, jour), du_jour in _jours(points).items():
        if len(du_jour) != HEURES_PAR_JOUR:
            continue
        poids_mesure = poids_soleil = som_mesure = som_soleil = 0.0
        for p in du_jour:
            instant = (datetime.datetime(annee, mois, jour, p['heure'], tzinfo=datetime.timezone.utc)
                       - datetime.timedelta(minutes=decalage_minutes))
            pos = position_solaire(latitude, longitude, annee=instant.year, mois=instant.month,
                                   jour=instant.day, heure_utc=instant.hour + instant.minute / 60.0)
            soleil = max(0.0, math.sin(math.radians(pos.elevation_deg)))
            mesure = max(0.0, p[colonne] or 0.0)
            poids_mesure += mesure
            som_mesure += mesure * p['heure']
            poids_soleil += soleil
            som_soleil += soleil * p['heure']
        if poids_mesure > 0 and poids_soleil > 0:
            ecarts.append((som_mesure / poids_mesure - som_soleil / poids_soleil) * 60.0)
    if not ecarts:
        return None, MOTIF_SANS_JOUR_COMPLET
    return {'ecart_median_min': round(statistics.median(ecarts), 1), 'jours_mesures': len(ecarts),
            'decalage_declare_min': decalage_minutes}, None


def _extraterrestre(points, colonne):
    from pvlib.irradiance import get_extra_radiation

    reference = {}
    dessus = []
    for p in points:
        valeur = p.get(colonne)
        if valeur is None:
            continue
        jour = (p['annee'], p['mois'], p['jour'])
        if jour not in reference:
            reference[jour] = float(get_extra_radiation(datetime.date(*jour).timetuple().tm_yday))
        if valeur > reference[jour]:
            dessus.append((valeur, reference[jour]))
    forte = max(dessus) if dessus else None
    return {'heures_au_dessus': len(dessus),
            'plus_forte_w_m2': forte[0] if forte else None,
            'reference_w_m2': round(forte[1], 1) if forte else None}


def rapport_de_qualite(points, *, latitude, longitude, decalage_minutes=None):
    """Les quatre lignes de qualité d'une série lue (``serie['points']``).

    ``latitude`` / ``longitude`` : l'épingle du calepinage, ou ``None`` (alors ``decalage`` et
    ``extraterrestre`` valent ``None``, motif « épingle du site absente »). ``decalage_minutes`` :
    le décalage UTC déclaré par le fichier (``meteo.heure.decalage_minutes`` quand il est unique),
    ``None`` s'il y en a plusieurs. Aucun verdict : des nombres.
    """
    colonne = _colonne_principale(points)
    motifs = {}
    decalage = extra = None
    if latitude is None or longitude is None:
        motifs = {'decalage': MOTIF_SANS_EPINGLE, 'extraterrestre': MOTIF_SANS_EPINGLE}
    elif colonne is not None:
        decalage, motif = _decalage(points, colonne, latitude, longitude, decalage_minutes)
        if motif:
            motifs['decalage'] = motif
        extra = _extraterrestre(points, colonne)
    return {'couverture': _couverture(points), 'decalage': decalage,
            'negatifs': _negatifs(points), 'extraterrestre': extra, 'motifs': motifs}
