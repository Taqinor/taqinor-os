"""D-ACAL-46 — le plan RÉEL des panneaux d'un devis agricole (ACAL1199) et
les journées types d'irradiance à ce plan (ACAL1200).

Brouillon de niveau 15 : les pans servis par le calepinage
(``apps.calepinage.selectors_devis.productible_pose_servi``) ; devis non
brouillon : le plan RANGÉ (``etude_params.pvgis_fige.plan``), jamais la
simulation vivante. Aucune donnée neuve du calepinage, aucun ombrage ni
perte de la cascade : seul le plan sert. Ne lève jamais.
"""
from __future__ import annotations

import logging

from apps.ventes.coherence.registre import TOLERANCES
from apps.ventes.domain.regles_calcul import (
    REGLES_POSE_REELLE_2111, regles_au_moins)

logger = logging.getLogger('apps.ventes.pompage')

SOURCE_POSE = 'pose_calepinage'
MOTIF_ENSOLEILLEMENT = 'ensoleillement indisponible au plan des panneaux'


def _nombre(valeur):
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _plan_depuis_servi(servi, kwc):
    if not isinstance(servi, dict):
        return None, 'aucune simulation du calepinage'
    if servi.get('perime'):
        return None, servi.get('motif') or 'simulation périmée'
    pans = []
    for pan in servi.get('pans') or ():
        inclinaison = _nombre((pan or {}).get('inclinaison_deg'))
        azimut = _nombre((pan or {}).get('azimut_deg'))
        if inclinaison is None or azimut is None:
            return None, 'un pan sans inclinaison ou orientation lisible'
        pans.append({'pan': pan.get('pan'), 'kwc': _nombre(pan.get('kwc')),
                     'inclinaison_deg': inclinaison, 'azimut_deg': azimut})
    if not pans:
        return None, 'aucun pan posé au calepinage'
    simule = _nombre(servi.get('kwc_simule'))
    if kwc is not None and simule and (
            abs(float(kwc) - simule) / simule
            > TOLERANCES['kwc_calepinage_ratio']):
        return None, 'lignes du devis différentes du calepinage'
    return {'source': SOURCE_POSE, 'pans': pans,
            'calcule_le': servi.get('calcule_le')}, ''


def diagnostic_plan_pose_pompage(devis, *, kwc=None):
    """``(plan | None, motif)`` — le motif dit pourquoi le site sert."""
    if devis is None or not getattr(devis, 'pk', None):
        return None, 'devis non enregistré'
    if not regles_au_moins(devis, REGLES_POSE_REELLE_2111):
        return None, 'règles d’avant le 21/11'
    if getattr(devis, 'mode_installation', None) != 'agricole':
        return None, 'marché non agricole'
    if getattr(devis, 'statut', 'brouillon') != 'brouillon':
        etude = getattr(devis, 'etude_params', None)
        fige = etude.get('pvgis_fige') if isinstance(etude, dict) else None
        plan = fige.get('plan') if isinstance(fige, dict) else None
        if isinstance(plan, dict) and plan.get('pans'):
            return dict(plan), ''
        return None, 'aucun plan rangé au devis'
    try:
        from apps.calepinage.selectors_devis import productible_pose_servi
        servi = productible_pose_servi(
            devis.pk, getattr(devis, 'company', None),
            tolerance_kwc_ratio=TOLERANCES['kwc_calepinage_ratio'])
    except Exception:  # noqa: BLE001 — lecture cross-app, jamais bloquante (D-ENF22-BLE001)
        logger.warning('plan de pose illisible (devis %s)',
                       getattr(devis, 'pk', None), exc_info=True)
        return None, 'calepinage illisible'
    if servi is None:
        return None, 'aucun calepinage lié'
    return _plan_depuis_servi(servi, kwc)


def plan_pose_pompage(devis, *, kwc=None):
    """Le plan des panneaux du devis agricole, ou ``None`` (site)."""
    return diagnostic_plan_pose_pompage(devis, kwc=kwc)[0]


MOTIF_POMPE_EXISTANTE = 'pompe existante : débit déclaré'


def plan_du_calcul(devis, *, facture, mode_pompe, coordonnees, profils_site):
    """ACAL1201 — ``(plan_irradiation, profils de la pose | None)`` du calcul
    d'eau : forme ``production.plan_irradiation`` du contrat
    ``etude_pompage_preview.json`` (ACAL1198). Sans profils du site : repli."""
    from apps.parametres.pvgis_profils import PVGIS_ANGLE_DEG, PVGIS_ASPECT_DEG

    if profils_site is None:
        return {'source': 'repli', 'pans': [], 'plan_reference': None,
                'motif': None}, None
    panneau = (facture or {}).get('panneau') or {}
    kwc = ((facture or {}).get('nb_panneaux') or 0) * (
        _nombre(panneau.get('pmax_wc')) or 0.0) / 1000.0 or None
    plan, motif = diagnostic_plan_pose_pompage(devis, kwc=kwc)
    pose = None
    if plan and mode_pompe == 'existante':
        motif = MOTIF_POMPE_EXISTANTE
    elif plan:
        coords = coordonnees or {}
        pose = profils_horaires_pose(lat=coords.get('lat'),
                                     lon=coords.get('lon'), plan=plan)
        motif = '' if pose else MOTIF_ENSOLEILLEMENT
    if pose:
        return {'source': SOURCE_POSE, 'pans': plan['pans'],
                'plan_reference': None, 'motif': None}, pose
    return {'source': 'site_reference', 'pans': [], 'motif': motif or None,
            'plan_reference': {'inclinaison_deg': PVGIS_ANGLE_DEG,
                               'aspect_deg': PVGIS_ASPECT_DEG}}, None


def _profils_du_pan(lat, lon, pan):
    """Les 12 journées types d'UN pan, même formule que
    ``pompage.profils_horaires_site`` (forme de la saison × E_m ÷ jours ×
    1 000), PVGIS lu au plan du pan ; ``None`` au moindre manque."""
    from apps.parametres.pvgis_profils import (
        SAISON_MOIS_PVGIS, productible_mensuel_live, profil_horaire_live,
        vers_heure_locale)
    from core.calepinage.geo import boussole_vers_aspect
    from core.pompage.volumes import JOURS_PAR_MOIS

    from ..etude_horaire import saison_du_mois

    plan = {'angle_deg': pan['inclinaison_deg'],
            'aspect_deg': boussole_vers_aspect(pan['azimut_deg'])}
    if plan['aspect_deg'] is None:
        return None
    formes = {}
    for saison, mois in SAISON_MOIS_PVGIS.items():
        forme_utc = profil_horaire_live(lat, lon, mois, **plan)
        formes[saison] = vers_heure_locale(forme_utc) if forme_utc else None
    mensuel = productible_mensuel_live(lat, lon, **plan)
    if not mensuel or len(mensuel) != 12:
        return None
    profils = []
    for index in range(12):
        forme, e_m = formes.get(saison_du_mois(index + 1)), _nombre(mensuel[index])
        if not forme or e_m is None or e_m <= 0:
            return None
        jour_kwh_kwc = e_m / JOURS_PAR_MOIS[index]
        profils.append([part * jour_kwh_kwc * 1000.0 for part in forme])
    return profils


def profils_horaires_pose(*, lat, lon, plan):
    """ACAL1200 — les 12 journées types (24 h, W/m², heure locale) au plan
    RÉEL : PVGIS pan par pan, moyenne pondérée par les kWc ; ``None`` (le
    site sert, motif :data:`MOTIF_ENSOLEILLEMENT`) sans GPS ou au moindre
    pan sans réponse — jamais de repli sur la table des villes."""
    pans = (plan or {}).get('pans') or ()
    poids = [_nombre(pan.get('kwc')) or 0.0 for pan in pans]
    if lat is None or lon is None or not pans or sum(poids) <= 0:
        return None
    try:
        par_pan = [_profils_du_pan(lat, lon, pan) for pan in pans]
    except Exception:  # noqa: BLE001 — réseau PVGIS : le site sert (D-ENF22-BLE001)
        logger.warning('ACAL1200 — PVGIS au plan indisponible', exc_info=True)
        return None
    if any(profils is None for profils in par_pan):
        return None
    somme_kwc = sum(poids)  # irradiance W/m² pondérée par les kWc (pas d'argent)
    return [[round(sum(p * profils[m][h] for p, profils in zip(poids, par_pan))
                   / somme_kwc, 2) for h in range(24)] for m in range(12)]
