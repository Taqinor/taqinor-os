"""PUB89 — Score de qualité de la chaîne d'attribution (assurance données).

Un webhook mort biaise SILENCIEUSEMENT la récompense proxy pendant des semaines :
les conversations CTWA cessent d'arriver, ou arrivent sans clic-id / sans
téléphone matché, et le bandit continue d'optimiser sur une récompense creuse.
Ce module SCORE, par enregistrement de la chaîne (``CtwaReferral`` — le maillon
de la récompense proxy), la complétude de la jointure sur 4 dimensions :

    * ``clid``          — le click-id CTWA est présent ;
    * ``phone_matched`` — la clé téléphone normalisée est présente ET rapprochée
      d'un lead CRM (``crm_lead_id``) ;
    * ``stage_known``   — le lead rapproché résout à une étape de pipeline lisible
      (jointure cross-app SANCTIONNÉE ``crm.selectors.lead_current_stage``) ;
    * ``ad_resolved``   — l'``ad_id`` résout à un ``AdMirror`` connu de la société.

Le score société = complétude moyenne de tous les enregistrements ; une
**tendance** compare une fenêtre récente à la précédente (horodatage propre au
module), et une **alerte** est levée sous seuil. C'est l'assurance qualité des
données dont TOUT le reste (récompense, bandit, regret) dépend.

Le cœur (:func:`chain_quality`, :func:`trend`) est **pur** : zéro I/O, testable
sur des drapeaux synthétiques. La couche modèle (:func:`attribution_quality`,
:func:`check_attribution_quality`) lit ``CtwaReferral``/``AdMirror`` (in-app) +
le stage via le sélecteur crm ; l'alerte est **brake-only** (un ``EngineAlert``
INFO/attention, JAMAIS une nouvelle ``EngineAction`` ni une reprise auto).
"""
from __future__ import annotations

import datetime
import logging

logger = logging.getLogger(__name__)

# Les 4 maillons de la chaîne d'attribution scorés (ordre = ordre d'affichage).
DEFAULT_DIMENSIONS = ('clid', 'phone_matched', 'stage_known', 'ad_resolved')

# Sous ce score de complétude moyenne, la chaîne est jugée dégradée → alerte.
DEFAULT_THRESHOLD = 0.60
# Fenêtre récente (jours) pour la tendance globale.
DEFAULT_RECENT_DAYS = 14
# En dessous de ce nombre d'enregistrements par fenêtre, la tendance n'est pas
# fiable (régime bas-volume : jamais un verdict de tendance sur n minuscule).
DEFAULT_MIN_TREND_SAMPLES = 5


# ── Cœur pur ─────────────────────────────────────────────────────────────────
def record_completeness(flags, dimensions=DEFAULT_DIMENSIONS):
    """Complétude d'UN enregistrement = fraction de dimensions satisfaites. Pure."""
    if not dimensions:
        return 0.0
    present = sum(1 for d in dimensions if flags.get(d))
    return present / len(dimensions)


def chain_quality(records, dimensions=DEFAULT_DIMENSIONS):
    """Score de qualité d'un lot d'enregistrements de chaîne. Fonction PURE.

    ``records`` : liste de dicts de drapeaux booléens (une clé par dimension).
    Renvoie ::

        {'score', 'n', 'per_dimension_rate': {dim: taux}, 'weakest_dimension',
         'insufficient_data'}

    Sans aucun enregistrement, ``score`` None et ``insufficient_data`` vrai
    (jamais un 0 % trompeur : « pas de données » ≠ « chaîne cassée »).
    """
    n = len(records)
    if n == 0:
        return {'score': None, 'n': 0,
                'per_dimension_rate': {d: None for d in dimensions},
                'weakest_dimension': None, 'insufficient_data': True}
    per_dim = {d: sum(1 for r in records if r.get(d)) / n for d in dimensions}
    score = sum(record_completeness(r, dimensions) for r in records) / n
    weakest = min(dimensions, key=lambda d: per_dim[d])
    return {
        'score': round(score, 4), 'n': n,
        'per_dimension_rate': {d: round(v, 4) for d, v in per_dim.items()},
        'weakest_dimension': weakest,
        'insufficient_data': False,
    }


def trend(recent_score, prior_score, *, recent_n=0, prior_n=0,
          min_samples=DEFAULT_MIN_TREND_SAMPLES):
    """Tendance HONNÊTE entre deux fenêtres. Fonction pure.

    Renvoie ``{'delta', 'direction', 'insufficient_data'}``. Sous ``min_samples``
    de chaque côté (ou une fenêtre absente), ``insufficient_data`` est vrai et
    ``direction`` vaut ``'inconnue'`` — jamais un verdict de tendance sur trop peu
    de données. Sinon ``direction`` ∈ {``'hausse'``, ``'baisse'``, ``'stable'``}.
    """
    if (recent_score is None or prior_score is None
            or recent_n < min_samples or prior_n < min_samples):
        return {'delta': None, 'direction': 'inconnue',
                'insufficient_data': True}
    delta = round(recent_score - prior_score, 4)
    if delta > 0.01:
        direction = 'hausse'
    elif delta < -0.01:
        direction = 'baisse'
    else:
        direction = 'stable'
    return {'delta': delta, 'direction': direction, 'insufficient_data': False}


# ── Couche modèle (I/O, society-scopé) ────────────────────────────────────────
def _known_ad_ids(company):
    """Ensemble des ``meta_id`` d'``AdMirror`` de la société (résolution d'ad)."""
    from .models import AdMirror
    return set(AdMirror.objects.filter(company=company)
               .values_list('meta_id', flat=True))


def referral_flags(company, referral, known_ads, *, stage_cache=None):
    """Drapeaux de complétude d'un ``CtwaReferral`` (les 4 maillons). I/O minimal.

    ``stage_cache`` (optionnel) : dict ``{crm_lead_id: stage|None}`` pré-rempli
    pour éviter une requête par enregistrement ; sinon le stage est résolu via
    ``crm.selectors.lead_current_stage`` (jointure cross-app sanctionnée).
    """
    from apps.crm.selectors import lead_current_stage

    lead_id = referral.crm_lead_id
    if lead_id is None:
        stage = None
    elif stage_cache is not None and lead_id in stage_cache:
        stage = stage_cache[lead_id]
    else:
        stage = lead_current_stage(company, lead_id)
    return {
        'clid': bool(referral.ctwa_clid),
        'phone_matched': bool(referral.phone_key) and lead_id is not None,
        'stage_known': stage is not None,
        'ad_resolved': bool(referral.ad_id) and referral.ad_id in known_ads,
    }


def attribution_quality(company, *, now=None, recent_days=DEFAULT_RECENT_DAYS,
                        threshold=DEFAULT_THRESHOLD):
    """PUB89 — Score de qualité de la chaîne d'attribution d'une société.

    Lit tous les ``CtwaReferral`` (le maillon de la récompense proxy), score la
    complétude par enregistrement, agrège un score société + une tendance
    (fenêtre récente vs précédente) et signale ``below_threshold``. Society-
    scopé. Renvoie un dict JSON-sûr (score/tendance/taux par dimension).
    """
    from django.utils import timezone

    from .models import CtwaReferral

    now = now or timezone.now()
    known_ads = _known_ad_ids(company)
    cutoff = now - datetime.timedelta(days=recent_days)

    all_records = []
    recent_records = []
    prior_records = []
    for ref in CtwaReferral.objects.filter(company=company):
        flags = referral_flags(company, ref, known_ads)
        all_records.append(flags)
        stamp = ref.created_at
        if stamp is not None and stamp >= cutoff:
            recent_records.append(flags)
        else:
            prior_records.append(flags)

    overall = chain_quality(all_records)
    recent = chain_quality(recent_records)
    prior = chain_quality(prior_records)
    tr = trend(recent['score'], prior['score'],
               recent_n=recent['n'], prior_n=prior['n'])

    below = (overall['score'] is not None and overall['score'] < threshold)
    return {
        'score': overall['score'],
        'n': overall['n'],
        'per_dimension_rate': overall['per_dimension_rate'],
        'weakest_dimension': overall['weakest_dimension'],
        'insufficient_data': overall['insufficient_data'],
        'threshold': threshold,
        'below_threshold': below,
        'recent_score': recent['score'],
        'prior_score': prior['score'],
        'trend': tr,
    }


def check_attribution_quality(company, *, now=None,
                              recent_days=DEFAULT_RECENT_DAYS,
                              threshold=DEFAULT_THRESHOLD):
    """PUB89 — Calcule le score ET lève une alerte BRAKE-ONLY sous le seuil.

    L'alerte est un ``EngineAlert`` (anomalie, sévérité attention) SANS action
    liée : jamais une nouvelle ``EngineAction`` ni une reprise auto (invariant
    règle #3). Renvoie le dict de :func:`attribution_quality` enrichi de
    ``alert_id`` (None si aucune alerte). No-op propre sans enregistrement.
    """
    result = attribution_quality(
        company, now=now, recent_days=recent_days, threshold=threshold)
    result['alert_id'] = None
    if result['below_threshold']:
        from .models import EngineAlert
        pct = result['score'] * 100
        weak = result['weakest_dimension']
        alert = EngineAlert.objects.create(
            company=company,
            alert_type=EngineAlert.Type.ANOMALIE,
            severity=EngineAlert.Severity.ATTENTION,
            message=(
                f"🟠 Qualité de la chaîne d'attribution dégradée : "
                f"complétude {pct:.0f} % (< seuil {threshold * 100:.0f} %), "
                f"maillon le plus faible « {weak} ». La récompense proxy du "
                f"moteur est peut-être biaisée (webhook / jointure) — à "
                f"vérifier, jamais une pause automatique."),
            entity_key='data_quality:attribution',
            detail=result)
        result['alert_id'] = alert.pk
        logger.info(
            'data_quality: chaîne dégradée société=%s score=%.2f',
            company.pk, result['score'])
    return result
