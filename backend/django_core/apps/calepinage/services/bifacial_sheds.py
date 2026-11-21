"""ACAL465 — le gain bifacial HEURE PAR HEURE, par ``pvlib`` ``infinite_sheds``.

Le gain mensuel constant de ``services/bifacial.py::gain_bifacial`` (facteur de
vue isotrope, ni soleil ni irradiance horaire) reste le REPLI. Quand le site
fournit la série HORIZONTALE (GHI, DHI), ce module appelle
``pvlib.bifacial.infinite_sheds.get_irradiance`` (pvlib 0.16.1, déjà dans
l'image) avec la position du soleil de CHAQUE heure, et rend un gain par heure.

Rien n'est codé en dur : bifacialité (fiche), albédo mensuel (saisi), mismatch
arrière (saisi), hauteur / pas / taux d'occupation / inclinaison / azimut (le
document). Les deux coefficients de structure de pvlib (``shade_factor``,
``transmission_factor``) sont passés à ``0.0`` — aucune perte de structure ni
de busbars n'est supposée ; leurs défauts de pvlib (-0,02 et 0) seraient des
constantes d'un autre outil. Le DNI se déduit de GHI, DHI et du zénith
(``pvlib.irradiance.dni``). Modèle : Mikofski et al., « Bifacial Performance
Modeling in Large Arrays », IEEE PVSC 2019, doi:10.1109/PVSC40753.2019.8980572.

Fonction PURE : aucun réseau, aucune base.
"""
from __future__ import annotations

import math

from apps.calepinage.services import etapes as _etapes
from core.calepinage.soleil import position_solaire
from .valeurs import nombre as _nombre

MODELE = 'infinite_sheds'
MODELE_REPLI = 'facteurs_de_vue_isotrope'

REFERENCE = (
    'pvlib.bifacial.infinite_sheds.get_irradiance (pvlib 0.16.1) — Mikofski, '
    'Darawali, Hamer, Neubert, Newmiller, « Bifacial Performance Modeling in '
    'Large Arrays », IEEE PVSC 2019, doi:10.1109/PVSC40753.2019.8980572 ; '
    'PVsyst — Bifacial systems (https://www.pvsyst.com/help/project-design/'
    'bifacial-systems/index.html).')

MOTIF_HORIZONTALE_ABSENTE = (
    "La série d'irradiance HORIZONTALE du site (GHI, DHI) n'est pas "
    "disponible : le gain mensuel par facteurs de vue isotropes s'applique.")

#: La clé du contexte où la simulation pose la série horizontale, DÉJÀ
#: ré-indexée sur l'heure légale du site comme celle du pan.
CLE_HORIZONTALE_LEGALE = 'serie_horizontale_legale'

#: Un point de série se reconnaît à ces quatre champs (clé d'alignement).
CLE_POINT = ('annee', 'mois', 'jour', 'heure')


def cle_du_point(point):
    """``(annee, mois, jour, heure)`` d'un point, ou ``None``."""
    if not isinstance(point, dict):
        return None
    valeurs = tuple(_nombre(point.get(nom)) for nom in CLE_POINT)
    return None if None in valeurs else tuple(int(v) for v in valeurs)


def _position(point, meteo, latitude, longitude):
    moment = _etapes.instant_utc(point, meteo)
    if moment is None:
        return None
    try:
        return position_solaire(
            latitude, longitude, annee=moment.year, mois=moment.month,
            jour=moment.day,
            heure_utc=moment.hour + moment.minute / 60.0
            + moment.second / 3600.0)
    except (TypeError, ValueError):
        return None


def gain_horaire(*, points, horizontale, meteo, latitude, longitude,
                 inclinaison_deg, azimut_pvgis_deg, taux_occupation,
                 hauteur_centre_m, pas_rangee_m, albedos_par_mois,
                 bifacialite_pct, mismatch_pct=None):
    """Le gain de face arrière de CHAQUE point — ou ``None`` si incalculable.

    Args:
        points: les points de la série du pan (heure légale, décalage posé).
        horizontale: ``{(annee, mois, jour, heure): (ghi, dhi)}``.
        azimut_pvgis_deg: 0 = sud, -90 = est, +90 = ouest (convention PVGIS) ;
            pvlib attend l'azimut depuis le nord : ``180 + azimut``.
        hauteur_centre_m: hauteur du CENTRE de la rangée (convention pvlib).
        albedos_par_mois: douze albédos (mois 1 → 12) saisis.
        mismatch_pct: le mismatch arrière saisi, ou ``None`` (gain brut).

    Returns:
        ``{gains_pct, gain_annuel_pct, mensuel_pct, heures}`` — ``gains_pct``
        aligné sur ``points`` (``0.0`` hors jour ; ``None`` pour une heure
        sans horizontale). ``None`` si aucune heure n'est calculable.
    """
    import numpy as np
    import pvlib
    from pvlib.bifacial import infinite_sheds

    gains = [None] * len(points)
    candidats = []
    for rang, point in enumerate(points):
        valeurs = horizontale.get(cle_du_point(point))
        if valeurs is None:
            continue
        ghi, dhi = valeurs
        if ghi is None or dhi is None:
            continue
        if ghi <= 0.0:
            gains[rang] = 0.0
            continue
        position = _position(point, meteo, latitude, longitude)
        if position is None:
            continue
        if position.elevation_deg <= 0.0:
            gains[rang] = 0.0
            continue
        mois = int(_nombre(point.get('mois')) or 0)
        if not 1 <= mois <= 12 or albedos_par_mois[mois - 1] is None:
            continue
        candidats.append((rang, mois, ghi, min(dhi, ghi), position))
    if not candidats:
        return None

    zenith = np.array([90.0 - c[4].elevation_deg for c in candidats])
    ghi = np.array([c[2] for c in candidats])
    dhi = np.array([c[3] for c in candidats])
    dni = np.nan_to_num(np.asarray(pvlib.irradiance.dni(ghi, dhi, zenith),
                                   dtype=float), nan=0.0)
    sortie = infinite_sheds.get_irradiance(
        surface_tilt=float(inclinaison_deg),
        surface_azimuth=180.0 + float(azimut_pvgis_deg),
        solar_zenith=zenith,
        solar_azimuth=np.array([180.0 + c[4].azimut_depuis_sud_deg
                                for c in candidats]),
        gcr=float(taux_occupation), height=float(hauteur_centre_m),
        pitch=float(pas_rangee_m), ghi=ghi, dhi=dhi, dni=dni,
        albedo=np.array([albedos_par_mois[c[1] - 1] for c in candidats]),
        model='isotropic', bifaciality=float(bifacialite_pct) / 100.0,
        shade_factor=0.0, transmission_factor=0.0)
    avant = np.asarray(sortie['poa_front'], dtype=float)
    total = np.asarray(sortie['poa_global'], dtype=float)
    arriere = np.nan_to_num(total - avant, nan=0.0)
    avant = np.nan_to_num(avant, nan=0.0)
    garde = 1.0 if mismatch_pct is None else max(0.0, 1.0 - mismatch_pct / 100.0)
    arriere = arriere * garde

    somme_avant = [0.0] * 12
    somme_arriere = [0.0] * 12
    for (rang, mois, *_reste), front, back in zip(candidats, avant, arriere):
        gains[rang] = (100.0 * back / front) if front > 0.0 else 0.0
        somme_avant[mois - 1] += float(front)
        somme_arriere[mois - 1] += float(back)
    total_avant = sum(somme_avant)
    if total_avant <= 0.0 or not math.isfinite(total_avant):
        return None
    return {
        'gains_pct': gains,
        'gain_annuel_pct': 100.0 * sum(somme_arriere) / total_avant,
        'mensuel_pct': [100.0 * b / a if a > 0.0 else None
                        for a, b in zip(somme_avant, somme_arriere)],
        'heures': len(candidats),
    }
