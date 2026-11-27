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
#: ADEV155 (D-ACAL-108, niveau 15 seulement) — la base du PLAN PAR DÉFAUT d'un lead sans
#: toit tracé (``conception/porte_calepinage.productible_du_plan_par_defaut``).
SOURCE_PLAN_PAR_DEFAUT = 'plan_par_defaut'
#: ACAL1237 — la base rangée À L'ENVOI (``domain/envoi.geler_document_engage``) quand le bloc
#: horaire n'en porte pas (sans 12 mois de consommation, l'étude horaire est ``None``).
CLE_BASE_ENVOI = 'base_production_envoi'


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
    # ADEV155 — la source servie (le contrat de la pose dit toujours ``SOURCE_POSE``).
    return {'kwh_kwc_annuel': annuel, 'kwh_kwc_mensuel': list(mensuel),
            'pertes_incluses': True, 'source': servi.get('source') or SOURCE_POSE}, ''


def _base_rangee(devis):
    etude = getattr(devis, 'etude_params', None)
    bloc = etude.get('etude_horaire') if isinstance(etude, dict) else None
    base = bloc.get('base_production') if isinstance(bloc, dict) else None
    if not isinstance(base, dict) or not base.get('kwh_kwc_annuel'):
        base = etude.get(CLE_BASE_ENVOI) if isinstance(etude, dict) else None  # ACAL1237
    if not isinstance(base, dict) or not base.get('kwh_kwc_annuel'):
        return None, 'aucune base rangée au bloc horaire'
    return dict(base), ''


def base_a_ranger_a_l_envoi(devis):
    """ACAL1237 — la base que le BROUILLON imprime, à ranger sous :data:`CLE_BASE_ENVOI` (appel
    avant la bascule) ; ``None`` quand le bloc horaire la porte déjà, au niveau ≤ 14 ou en ville."""
    bloc = (getattr(devis, 'etude_params', None) or {}).get('etude_horaire')
    base = bloc.get('base_production') if isinstance(bloc, dict) else None
    if isinstance(base, dict) and base.get('kwh_kwc_annuel'):
        return None
    return base_de_production(devis)


def _base_du_plan_rangee(devis):
    """ADEV155 — la base du PLAN PAR DÉFAUT rangée sur un brouillon né du moteur, ou ``None``.
    Résidentiel : ``etude_horaire.base_production`` (source ``plan_par_defaut``). C&I : l'étude
    ne range pas la base telle quelle, mais son bloc ``etude_ci.production`` porte ses 12
    kWh/kWc (``moteur_ci/production.bloc_production_ci``, origine ``calepinage``) et ses
    ``hypotheses`` la source (``base_etude_ci``) : la base en est relue, aucune clé neuve."""
    rangee = _base_rangee(devis)[0]
    if rangee and rangee.get('source') == SOURCE_PLAN_PAR_DEFAUT:
        return rangee
    etude = getattr(devis, 'etude_params', None)
    ci = etude.get('etude_ci') if isinstance(etude, dict) else None
    ci = ci if isinstance(ci, dict) else {}
    production = ci.get('production') if isinstance(ci.get('production'), dict) else {}
    mensuel = production.get('kwh_kwc_mensuel')
    if (production.get('source') != 'calepinage' or not isinstance(mensuel, list) or len(mensuel) != 12
            or any(m is None for m in mensuel)
            or not any(isinstance(h, dict) and h.get('source') == SOURCE_PLAN_PAR_DEFAUT
                       for h in ci.get('hypotheses') or ())):
        return None
    return {'kwh_kwc_annuel': round(sum(float(m) for m in mensuel), 1), 'kwh_kwc_mensuel': list(mensuel),
            'pertes_incluses': True, 'source': SOURCE_PLAN_PAR_DEFAUT}


def _kwc_du_devis(devis):
    from apps.ventes.domain.scenario import puissance_kwc_du_devis
    return puissance_kwc_du_devis(devis)


def diagnostic_base_de_production(devis, *, kwc=None, marches=('residentiel',)):
    """``(base | None, motif)`` — le motif dit pourquoi la ville sert.
    ``marches`` : ACAL1195 — seule l'étude C&I passe ``('commercial', 'industriel')``."""
    servi_moteur = getattr(devis, 'productible_pose_moteur', None)
    if servi_moteur is not None and getattr(devis, 'pk', None) is None:
        # Relecture E6 M1 — le devis EN MÉMOIRE du moteur unique (jamais enregistré) porte
        # le productible de SA pose (``conception/moteur._base_de_la_pose``) : mêmes gardes.
        if not regles_au_moins(devis, REGLES_POSE_REELLE_2111):
            return None, 'règles d’avant le 21/11'
        if getattr(devis, 'mode_installation', None) not in marches:
            return None, 'marché non résidentiel'
        return base_depuis_servi(servi_moteur, kwc=_kwc_du_devis(devis) if kwc is None else kwc)
    if devis is None or not getattr(devis, 'pk', None):
        return None, 'devis non enregistré'
    if not regles_au_moins(devis, REGLES_POSE_REELLE_2111):
        return None, 'règles d’avant le 21/11'
    if getattr(devis, 'mode_installation', None) not in marches:
        return None, 'marché non résidentiel'
    if getattr(devis, 'statut', 'brouillon') != 'brouillon':
        return _base_rangee(devis)
    try:
        from apps.calepinage.selectors_devis import productible_pose_servi
        servi = productible_pose_servi(
            devis.pk, getattr(devis, 'company', None),
            tolerance_kwc_ratio=TOLERANCES['kwc_calepinage_ratio'])
        rangee = _base_du_plan_rangee(devis) if servi is None else None
        if rangee:
            # ADEV155 — brouillon né du moteur d'un lead SANS toit tracé (résidentiel ou C&I) : il
            # garde la base du plan par défaut rangée (aucune simulation au rendu) tant
            # qu'aucune pose n'est servie.
            return rangee, ''
        return base_depuis_servi(
            servi, kwc=_kwc_du_devis(devis) if kwc is None else kwc)
    except Exception:  # noqa: BLE001 — lecture cross-app, jamais bloquante (D-ENF22-BLE001)
        logger.warning('base de production illisible (devis %s)',
                       getattr(devis, 'pk', None), exc_info=True)
        return None, 'calepinage illisible'


def base_de_production(devis, *, kwc=None, marches=('residentiel',)):
    """La base de production du devis, ou ``None`` (chemin d'aujourd'hui)."""
    return diagnostic_base_de_production(devis, kwc=kwc, marches=marches)[0]


def base_etude_ci(devis, *, kwc=None):
    """ACAL1195 (D-ACAL-44) — ``(base | None, hypothèse | None)`` de l'étude C&I d'un BROUILLON de niveau
    15 (un devis émis garde son bloc figé) : la base dit sa forme horaire supposée (comme ACAL1169), son
    absence dit son motif ; niveau ≤ 14 ou non brouillon : ``(None, None)``, chemin d'aujourd'hui."""
    from apps.ventes.horaire.base import FORME_HORAIRE_BASE

    if getattr(devis, 'statut', None) != 'brouillon' or not regles_au_moins(devis, REGLES_POSE_REELLE_2111):
        return None, None
    base, motif = diagnostic_base_de_production(devis, kwc=kwc, marches=('commercial', 'industriel'))
    if base:
        return base, {'cle': 'forme_horaire', 'valeur': FORME_HORAIRE_BASE, 'statut': 'estimation',
                      'source': base['source']}
    return None, {'cle': 'base_production', 'valeur': None, 'statut': 'estimation',
                  'source': 'production de la ville : ' + motif}
