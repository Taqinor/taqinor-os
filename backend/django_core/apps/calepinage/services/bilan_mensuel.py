"""ACAL705 — ``production.bilan_mensuel`` : température ambiante et PR par mois.

Le tableau mensuel de PVsyst (GlobInc / T amb / E_Grid / PR) à partir de
valeurs DÉJÀ servies : la température est la moyenne des ``t2m_c`` des points
du mois (toutes années de la fenêtre) ; le PR du mois est
``p50_kwh ÷ (irradiation_plan_kwh_m2 × kWc)`` (irradiation du plan d'ACAL451).
Aucune constante. Un mois sans température ⇒ ``null`` ; une irradiation
absente ou nulle ⇒ ``pr`` ``null`` (jamais 0). Un résultat INCOMPLET
(D-ACAL-7, ``production.total.complete`` faux) ne publie aucun PR mensuel :
chaque ``pr`` est ``null`` avec le motif du PR annuel.
"""
from __future__ import annotations

from .valeurs import nombre as _nombre

__all__ = ['publier']


def _temperatures(serie):
    sommes = {mois: [0.0, 0] for mois in range(1, 13)}
    for point in (serie or {}).get('points') or ():
        if not isinstance(point, dict):
            continue
        mois, temperature = point.get('mois'), _nombre(point.get('t2m_c'))
        if mois in sommes and temperature is not None:
            sommes[mois][0] += temperature
            sommes[mois][1] += 1
    return {mois: (round(somme / n, 2) if n else None)
            for mois, (somme, n) in sommes.items()}


def publier(serie, production):
    """Les douze lignes ``{mois, temperature_ambiante_c, pr}``, ou ``[]``."""
    production = production or {}
    mensuel = {ligne.get('mois'): _nombre(ligne.get('p50_kwh'))
               for ligne in production.get('mensuel') or ()}
    if not mensuel:
        return []
    total = production.get('total') or {}
    kwc = _nombre(total.get('kwc'))
    irradiation = {ligne.get('mois'): _nombre(ligne.get('irradiation_plan_kwh_m2'))
                   for ligne in production.get('irradiation_mensuelle') or ()}
    temperatures = _temperatures(serie)
    incomplet = total.get('complete') is False
    lignes = []
    for mois in range(1, 13):
        energie, plan = mensuel.get(mois), irradiation.get(mois)
        pr = None
        if not incomplet and energie is not None and plan and kwc:
            pr = round(energie / (plan * kwc), 4)
        lignes.append({
            'mois': mois, 'temperature_ambiante_c': temperatures[mois],
            'pr': pr, 'pr_motif': ((total.get('performance_ratio_motif') or '')
                                   if incomplet else '')})
    return lignes
