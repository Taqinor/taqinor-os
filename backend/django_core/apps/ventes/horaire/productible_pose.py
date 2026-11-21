"""ACAL999 (D-ACAL-36) — LE résolveur de la base de production d'un devis.

Brouillon résidentiel de niveau 15 : la pose réelle SERVIE par le calepinage
(``apps.calepinage.selectors_devis.productible_pose_servi``, contrat
``calepinage_productible_pose.json``) ; devis non brouillon : la base RANGÉE
au bloc horaire (``etude_params.etude_horaire.base_production``), jamais la
simulation vivante (même gel qu'ACON20). ``None`` ⇒ chemin d'aujourd'hui.
Ne lève jamais.
"""
from __future__ import annotations

import logging

from apps.ventes.coherence.registre import TOLERANCES
from apps.ventes.domain.regles_calcul import (
    REGLES_POSE_REELLE_2111, regles_au_moins)

logger = logging.getLogger('apps.ventes.etude_horaire')

SOURCE_POSE = 'calepinage_enregistre'


def base_depuis_servi(servi, *, kwc=None):
    """``(base, motif)`` depuis le productible posé servi — pure (ACAL992).

    ``base`` = ``{kwh_kwc_annuel, kwh_kwc_mensuel, pertes_incluses,
    source}`` ; ``None`` quand rien n'est servi, périmé, incomplet, ou que
    ``kwc`` s'écarte du kWc simulé au-delà de la tolérance du registre."""
    if not isinstance(servi, dict):
        return None, 'aucune simulation du calepinage'
    if servi.get('perime'):
        return None, servi.get('motif') or 'simulation périmée'
    annuel, mensuel = servi.get('kwh_kwc_annuel'), servi.get('kwh_kwc_mensuel')
    if (not servi.get('pertes_et_ombrage_inclus') or not annuel
            or not isinstance(mensuel, list) or len(mensuel) != 12):
        return None, 'résultat du calepinage incomplet'
    simule = servi.get('kwc_simule')
    if kwc is not None and simule:
        ecart = abs(float(kwc) - float(simule)) / float(simule)
        if ecart > TOLERANCES['kwc_calepinage_ratio']:
            return None, 'lignes du devis différentes du calepinage'
    return {'kwh_kwc_annuel': annuel, 'kwh_kwc_mensuel': list(mensuel),
            'pertes_incluses': True, 'source': SOURCE_POSE}, ''


def _base_rangee(devis):
    etude = getattr(devis, 'etude_params', None)
    bloc = etude.get('etude_horaire') if isinstance(etude, dict) else None
    base = bloc.get('base_production') if isinstance(bloc, dict) else None
    if not isinstance(base, dict) or not base.get('kwh_kwc_annuel'):
        return None, 'aucune base rangée au bloc horaire'
    return dict(base), ''


def _kwc_du_devis(devis):
    from apps.ventes.domain.scenario import puissance_kwc_du_devis
    return puissance_kwc_du_devis(devis)


def diagnostic_base_de_production(devis, *, kwc=None):
    """``(base | None, motif)`` — le motif dit pourquoi la ville sert."""
    if devis is None or not getattr(devis, 'pk', None):
        return None, 'devis non enregistré'
    if not regles_au_moins(devis, REGLES_POSE_REELLE_2111):
        return None, 'règles d’avant le 21/11'
    if getattr(devis, 'mode_installation', None) != 'residentiel':
        return None, 'marché non résidentiel'
    if getattr(devis, 'statut', 'brouillon') != 'brouillon':
        return _base_rangee(devis)
    try:
        from apps.calepinage.selectors_devis import productible_pose_servi
        servi = productible_pose_servi(
            devis.pk, getattr(devis, 'company', None),
            tolerance_kwc_ratio=TOLERANCES['kwc_calepinage_ratio'])
        return base_depuis_servi(
            servi, kwc=_kwc_du_devis(devis) if kwc is None else kwc)
    except Exception:  # noqa: BLE001 — lecture cross-app, jamais bloquante (D-ENF22-BLE001)
        logger.warning('base de production illisible (devis %s)',
                       getattr(devis, 'pk', None), exc_info=True)
        return None, 'calepinage illisible'


def base_de_production(devis, *, kwc=None):
    """La base de production du devis, ou ``None`` (chemin d'aujourd'hui)."""
    return diagnostic_base_de_production(devis, kwc=kwc)[0]
