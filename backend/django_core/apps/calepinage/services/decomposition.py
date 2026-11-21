"""ACAL456 — direct (DNI) et diffus (DHI) DÉDUITS d'un global horizontal (GHI)
par un modèle de décomposition ``pvlib`` NOMMÉ, déclaré hypothèse.

Un fichier qui ne porte que le global horizontal ne dit ni le direct ni le
diffus. Mémo ``docs/decisions/calx198-pvlib.md`` §5 : décomposer par un modèle
est une HYPOTHÈSE, qui se déclare dans le rapport. Le modèle est celui que la
société a saisi (``parametres.simulation.modele_decomposition``) — jamais un
choix fait à sa place. Fonction pure ; import paresseux de ``pvlib``.

* ``erbs`` — Erbs, Klein et Duffie (1982), ``pvlib.irradiance.erbs`` : DNI et
  DHI rendus par le modèle.
* ``disc`` — Maxwell (1987), ``pvlib.irradiance.disc`` : le modèle rend le DNI ;
  le DHI se déduit du bilan ``GHI − DNI·cos(zénith)`` (celui de
  ``pvlib.irradiance.complete_irradiance``). Pression : défaut de pvlib
  (101325 Pa, niveau de la mer), l'altitude du site n'étant pas lue ici.

Les bornes (``min_cos_zenith``, ``max_zenith``) sont les défauts de pvlib. La
nuit (zénith ≥ 90°) DNI = DHI = 0 : aucune valeur n'est inventée.
"""
from __future__ import annotations

import math

from .pvgis_serie import EntreeInvalide

__all__ = ['MODELES_DECOMPOSITION', 'HYPOTHESE', 'deduire_direct_diffus']

CHAMP_MODELE = 'parametres.simulation.modele_decomposition'

HYPOTHESE = 'composantes déduites du global, non mesurées'

#: Les modèles admis et la référence publiée avec chacun.
MODELES_DECOMPOSITION = {
    'erbs': 'Erbs, Klein et Duffie (1982) (pvlib.irradiance.erbs)',
    'disc': 'Maxwell (1987), modèle DISC ; diffus = global − direct·cos(zénith) '
            '(pvlib.irradiance.disc, pression 101325 Pa par défaut de pvlib)',
}


def deduire_direct_diffus(ghi, zeniths_deg, instants_utc, modele):
    """``(dni, dhi)`` — deux listes de flottants, un par heure.

    Args:
        ghi: global horizontal (W/m2), un par instant.
        zeniths_deg: zénith du soleil au milieu de l'heure (degrés).
        instants_utc: les instants (``datetime`` UTC, avec ``tzinfo``) de ces zéniths.
        modele: ``'erbs'`` ou ``'disc'``.

    Raises:
        EntreeInvalide: modèle inconnu, ou le modèle ne rend pas de nombre
            en plein jour.
    """
    if modele not in MODELES_DECOMPOSITION:
        raise EntreeInvalide(
            f'Modèle de décomposition « {modele} » inconnu (« {CHAMP_MODELE} » '
            ': erbs ou disc).', champ=CHAMP_MODELE)
    import numpy as np
    import pandas as pd
    from pvlib import irradiance

    glob = np.array(ghi, dtype=float)
    zenith = np.array(zeniths_deg, dtype=float)
    temps = pd.DatetimeIndex(instants_utc, tz='UTC')
    if modele == 'erbs':
        rendu = irradiance.erbs(glob, zenith, temps)
        dni, dhi = rendu['dni'].to_numpy(), rendu['dhi'].to_numpy()
    else:
        dni = irradiance.disc(glob, zenith, temps)['dni'].to_numpy()
        dhi = glob - dni * np.cos(np.radians(zenith))
    nuit = zenith >= 90.0
    dni, dhi = np.where(nuit, 0.0, dni), np.where(nuit, 0.0, dhi)
    for rang in range(len(glob)):
        if not (math.isfinite(dni[rang]) and math.isfinite(dhi[rang])):
            raise EntreeInvalide(
                f'La décomposition ({modele}) ne rend pas de nombre à '
                f"{instants_utc[rang].strftime('%Y-%m-%dT%H:%M:%S')} UTC (global {glob[rang]:g} "
                f'W/m², zénith {zenith[rang]:.2f}°).', champ=CHAMP_MODELE)
    return [float(v) for v in dni], [float(v) for v in dhi]
