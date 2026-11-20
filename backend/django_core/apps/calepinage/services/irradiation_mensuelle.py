"""ACAL451 — l'irradiation INCIDENTE mensuelle sur le plan des modules.

``chaine_pertes.appliquer_chaine`` capture UNE fois l'irradiation incidente
annuelle AVANT la chaîne (les étapes optiques réécrivent ``gi_w_m2``). Ce
module en fait la même lecture mois par mois — ``Σ Δt × gi_w_m2 ÷ 1000`` des
points du mois civil — pour que le bilan mensuel irradiation → énergie, comme
la page « résultats principaux » de PVsyst
(https://www.pvsyst.com/help/project-design/results/index.html), ait sa
colonne d'irradiation. Aucune constante, aucune règle neuve : la même série,
le même poids (kWc du pan) que l'annuelle.
"""
from __future__ import annotations

from .valeurs import nombre as _nombre

#: Clé du contexte où ``appliquer_chaine`` (phase ``pan`` ou chaîne entière)
#: pose ``{mois: kWh/m² | None}`` de la série d'ENTRÉE.
CLE_IRRADIATION_MENSUELLE = 'irradiation_mensuelle'

#: Clé du contexte où l'appelant d'un toit à plusieurs pans pose
#: ``{clé du pan: {mois: kWh/m² | None}}`` (jumeau de ``CLE_CASCADES_PAR_PAN``).
CLE_IRRADIATIONS_MENSUELLES_PAR_PAN = 'irradiations_mensuelles_par_pan'


def par_mois(serie):
    """``{mois: Σ gi × Δt ÷ 1000}`` d'une série — ``None`` sans point du mois."""
    pas = float((serie or {}).get('pas_minutes') or 60)
    heures = pas / 60.0
    sommes = {mois: None for mois in range(1, 13)}
    for point in (serie or {}).get('points') or ():
        if not isinstance(point, dict):
            continue
        mois = _nombre(point.get('mois'))
        globale = _nombre(point.get('gi_w_m2'))
        if mois is None or globale is None or int(mois) not in sommes:
            continue
        sommes[int(mois)] = (sommes[int(mois)] or 0.0) + (
            globale / 1000.0 * heures)
    return sommes


def ponderer(mensuelles, kwcs):
    """Moyenne des ``mensuelles`` pondérée par ``kwcs`` (kWc de chaque pan).

    Même poids que l'annuelle (``Σ irradiation × kWc ÷ Σ kWc``) ; un mois sans
    valeur dans aucun pan reste ``None``. ``None`` si rien n'est lisible.
    """
    lecture = {}
    for mois in range(1, 13):
        poids = 0.0
        somme = 0.0
        for mensuelle, kwc in zip(mensuelles, kwcs):
            valeur = (mensuelle or {}).get(mois)
            if valeur is None or not kwc:
                continue
            somme += valeur * kwc
            poids += kwc
        lecture[mois] = somme / poids if poids else None
    if all(valeur is None for valeur in lecture.values()):
        return None
    return lecture


def mensuelles_des_pans(contexte, cles_equipees):
    """``{clé du pan: {mois: …}}`` — posées par l'appelant (plusieurs pans),
    sinon celle de l'unique pan équipé (``CLE_IRRADIATION_MENSUELLE``)."""
    posees = contexte.get(CLE_IRRADIATIONS_MENSUELLES_PAR_PAN)
    if isinstance(posees, dict) and posees:
        return posees
    if len(cles_equipees) == 1:
        return {cles_equipees[0]: contexte.get(CLE_IRRADIATION_MENSUELLE)}
    return {}


def publier(lecture, annees):
    """Les 12 lignes ``{mois, irradiation_plan_kwh_m2}`` de l'année moyenne.

    ``lecture`` (sortie de :func:`ponderer`, fenêtre entière) est ramenée à
    l'année moyenne comme les autres énergies. ``None`` ⇒ liste vide.
    """
    if lecture is None:
        return []
    return [{'mois': mois,
             'irradiation_plan_kwh_m2': (
                 None if lecture[mois] is None
                 else round(lecture[mois] / (annees if annees > 1 else 1),
                            3))}
            for mois in range(1, 13)]
