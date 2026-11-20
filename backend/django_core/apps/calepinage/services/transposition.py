"""ACAL455 — une série HORIZONTALE (GHI, DNI, DHI) transposée vers le PLAN d'un
pan par ``pvlib`` (comme PVsyst, HelioScope, Aurora), modèle et albédo NOMMÉS.

Soleil : ``core.calepinage.soleil.position_solaire`` au MILIEU de l'heure (UTC =
heure + 0,5 h − ``meteo.heure.decalage_minutes``). Puis
``pvlib.irradiance.get_total_irradiance`` (modèle et albédo mensuel SAISIS,
``get_extra_radiation``, ``get_relative_airmass``). Rien n'est supposé (mémo
``docs/decisions/calx198-pvlib.md`` §5) : réglage absent, épingle sans GPS ou
plusieurs décalages ⇒ ``EntreeInvalide`` nommant la clé — jamais l'isotrope ni
l'albédo 0,25 par défaut de pvlib. Import paresseux de pvlib ; fonction pure.
"""
from __future__ import annotations

import copy
import datetime
import math

from core.calepinage.soleil import position_solaire

from . import etapes as _etapes
from .pvgis_serie import EntreeInvalide, _bloc_serie

__all__ = ['MODELES_TRANSPOSITION', 'transposer_serie_horizontale']

CHAMP_MODELE = 'parametres.simulation.modele_transposition'
CHAMP_ALBEDO = 'parametres.simulation.albedo_mensuel'
CHAMP_DECALAGE = 'meteo.heure.decalage_minutes'

#: Le jeu de coefficients Perez de ``pvlib`` (son défaut), NOMMÉ au résultat.
JEU_PEREZ = 'allsitescomposite1990'

#: Les modèles admis et la référence publiée avec chacun.
MODELES_TRANSPOSITION = {
    'isotropic': 'Liu et Jordan (1963) — ciel isotrope '
                 '(pvlib.irradiance.isotropic)',
    'haydavies': 'Hay et Davies (1980) — circumsolaire + isotrope '
                 '(pvlib.irradiance.haydavies)',
    'perez': 'Perez et al. (1990) — jeu de coefficients pvlib '
             f'« {JEU_PEREZ} » (pvlib.irradiance.perez)',
}


def _modele(contexte):
    saisie = _etapes.reglage(contexte, 'modele_transposition') or {}
    modele = str(saisie.get('valeur') or '').strip().lower()
    if modele not in MODELES_TRANSPOSITION:
        raise EntreeInvalide(
            f'Aucun modèle de transposition saisi avec sa source '
            f'(« {CHAMP_MODELE} » : isotropic, haydavies ou perez) : la série '
            "horizontale déposée ne se transpose pas vers le plan d'un pan "
            "sans un modèle choisi par la société, et aucun n'est choisi à "
            'sa place.', champ=CHAMP_MODELE)
    return modele


def _albedos(contexte):
    """Les douze albédos SAISIS et leur source — ou un refus nommé."""
    from .etapes.bifacial import _albedos_mensuels

    saisie = _etapes.reglage(contexte, 'albedo_mensuel')
    valeurs, _mode, motif = _albedos_mensuels(contexte)
    if not saisie or motif or any(v is None for v, _s in valeurs):
        raise EntreeInvalide(
            f'Aucun albédo mensuel saisi avec sa source (« {CHAMP_ALBEDO} ») : '
            "la composante réfléchie par le sol ne se calcule pas sans lui, et "
            "l'albédo 0,25 que pvlib prend par défaut n'est jamais repris. "
            f'{motif}'.strip(), champ=CHAMP_ALBEDO)
    return [float(v) for v, _s in valeurs], saisie.get('source')


def _decalage_minutes(serie):
    heure = ((serie.get('meteo') or {}).get('heure') or {})
    decalages = list(heure.get('decalage_minutes') or [])
    if len(decalages) != 1:
        raise EntreeInvalide(
            f'La série horizontale porte {len(decalages)} décalages horaires '
            f'(« {CHAMP_DECALAGE} » : {decalages}) : la position du soleil se '
            "calcule sur UN décalage, et choisir l'heure d'été ou d'hiver à la "
            'place du fichier décalerait le soleil en silence.',
            champ=CHAMP_DECALAGE)
    return int(decalages[0])


def transposer_serie_horizontale(serie, plan, contexte):
    """La série de ``plan``, transposée depuis la série horizontale ``serie``.

    Returns:
        dict à la forme de ``lire_serie_meteo`` (composantes disponibles), dont
        ``meteo.transposition = {modele, reference, albedo: {valeur, source}}``.

    Raises:
        EntreeInvalide: modèle ou albédo absent, épingle sans GPS, plusieurs
            décalages — le champ fautif est nommé.
    """
    modele = _modele(contexte)
    albedos, source_albedo = _albedos(contexte)
    lat, lon = plan.get('lat'), plan.get('lon')
    if lat is None or lon is None:
        raise EntreeInvalide(
            "Le site n'a pas de point GPS : la position du soleil, donc la "
            "transposition vers le plan, se calcule à une latitude et une "
            "longitude. Posez l'épingle du site (« roof_layout.pin »).",
            champ='site.pin')
    vers_utc = datetime.timedelta(minutes=30 - _decalage_minutes(serie))
    points = [p for p in (serie.get('points') or []) if isinstance(p, dict)]
    instants, zeniths, azimuts = [], [], []
    for point in points:
        instant = datetime.datetime(point['annee'], point['mois'], point['jour'],
                                    point['heure']) + vers_utc
        soleil = position_solaire(
            float(lat), float(lon), annee=instant.year, mois=instant.month,
            jour=instant.day, heure_utc=instant.hour + instant.minute / 60.0)
        instants.append(instant)
        zeniths.append(soleil.zenith_deg)
        # pvlib compte l'azimut en boussole (0 = Nord, 180 = Sud).
        azimuts.append((soleil.azimut_depuis_sud_deg + 180.0) % 360.0)

    import numpy as np
    import pandas as pd
    from pvlib import atmosphere, irradiance

    zenith = np.array(zeniths, dtype=float)
    rendu = irradiance.get_total_irradiance(
        float(plan.get('inclinaison_deg') or 0.0),
        (float(plan.get('azimut_pvgis_deg') or 0.0) + 180.0) % 360.0,
        zenith, np.array(azimuts, dtype=float),
        np.array([p['dni_w_m2'] for p in points], dtype=float),
        np.array([p['ghi_w_m2'] for p in points], dtype=float),
        np.array([p['dhi_w_m2'] for p in points], dtype=float),
        dni_extra=irradiance.get_extra_radiation(
            pd.DatetimeIndex(instants, tz='UTC')).to_numpy(),
        airmass=atmosphere.get_relative_airmass(zenith),
        albedo=np.array([albedos[p['mois'] - 1] for p in points], dtype=float),
        model=modele, model_perez=JEU_PEREZ)
    colonnes = {'gi_w_m2': 'poa_global', 'gb_i_w_m2': 'poa_direct',
                'gd_i_w_m2': 'poa_sky_diffuse', 'gr_i_w_m2': 'poa_ground_diffuse'}
    valeurs = {nous: np.asarray(rendu[eux], dtype=float)
               for nous, eux in colonnes.items()}
    sortie = []
    for rang, point in enumerate(points):
        transpose = {cle: point[cle] for cle in ('annee', 'mois', 'jour', 'heure')}
        transpose['h_sun_deg'] = None
        for nous, serie_plan in valeurs.items():
            valeur = float(serie_plan[rang])
            if not math.isfinite(valeur):
                raise EntreeInvalide(
                    f'La transposition ({modele}) ne rend pas de nombre pour '
                    f'« {nous} » à {instants[rang].isoformat()} UTC.',
                    champ='meteo.transposition')
            transpose[nous] = valeur
        transpose['t2m_c'] = point.get('t2m_c')
        transpose['ws10m'] = point.get('ws10m')
        sortie.append(transpose)

    meteo = copy.deepcopy(serie.get('meteo') or {})
    meteo['transposition'] = {
        'modele': modele, 'reference': MODELES_TRANSPOSITION[modele],
        'albedo': {'valeur': albedos, 'source': source_albedo}}
    annees = list(serie.get('annees') or [])
    return {'service': 'fichier', 'plan_des_donnees': 'plan', 'points': sortie,
            'composantes_disponibles': True, 'motif_composantes': None,
            'serie_horaire': _bloc_serie(sortie, annees, None, composantes=True),
            'meteo': meteo, 'annees': annees, 'url': None,
            'depuis_cache': False, 'identite': serie.get('identite')}
