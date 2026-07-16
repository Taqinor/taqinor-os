"""ADSENG21 — Applicateur de budgets ABO (dd-treasury §b). AUTH-sensible.

Transforme une sortie de bandit / un signal de pacing en une PROPOSITION
``EngineAction`` de changement de budget ad set — JAMAIS un appel direct à Meta
(le SEUL chemin vers ``meta_client`` reste ``services.apply_action`` sur une
action APPROUVÉE). Ce module garantit, prouvé en test :

  * tout pas quotidien est BORNÉ à ``MAX_STEP_PCT`` (15 %) — un pas > 15 % est
    STRUCTURELLEMENT impossible car ``cap_daily_step`` est la seule fabrique du
    budget proposé, et ``assert_step_within_cap`` re-garde au dispatch ;
  * le budget proposé ne dépasse jamais le plafond quotidien (borné aussi au
    plafond dès la proposition — « plafonds inviolables ») ;
  * l'``adset_id`` ciblé appartient bien aux MIROIRS de CETTE société
    (DEFER ADSENG21) — jamais toucher un id hors des miroirs de la société ;
  * ``enable_cbo`` est REFUSÉ sous le plancher Madgicx complet : < 8 ad sets OU
    < 2 semaines de spend consistant (dd-treasury §B2) — garde au niveau
    SERVICE, pas une simple alerte UI. ``enable_cbo`` n'existe qu'en
    proposition (jamais appliqué programmatiquement par le moteur — cf.
    ``services._dispatch``).
"""
from __future__ import annotations

import datetime

from . import guardrails, pacing

# Pas quotidien maximal (%). Le seuil de reset Meta ~20 % est NON vérifié : on
# garde 15 % comme marge de sécurité délibérée (dd-treasury §B4 / PLAN.md).
MAX_STEP_PCT = 15
# Plancher Madgicx (dd-treasury §B2) : CBO interdit sous CES seuils.
CBO_MIN_ADSETS = 8
CBO_MIN_CONSISTENT_DAYS = 14  # « ≥ 2 semaines »
CBO_MIN_CONSISTENT_ACTIVE_DAYS = 10  # « consistant » = peu de trous sur 14 j


class BudgetApplierError(guardrails.GuardrailViolation):
    """Base des refus de l'applicateur (sous-classe de ``GuardrailViolation`` :
    une action refusée n'atteint jamais le client, ``apply_action`` la marque
    ``echouee``)."""


class MirrorOwnershipViolation(BudgetApplierError):
    """La cible (adset/campaign) n'appartient pas aux miroirs de la société."""


class BudgetStepViolation(BudgetApplierError):
    """Le pas quotidien demandé dépasse ``MAX_STEP_PCT``."""


class CboFloorViolation(BudgetApplierError):
    """CBO refusé sous le plancher Madgicx (< 8 ad sets OU < 2 sem.)."""


def _mad_to_centimes(mad):
    """MAD (unités majeures) → centimes (unités mineures Meta — contrat G2)."""
    try:
        return int(round(float(mad) * 100))
    except (TypeError, ValueError):
        return None


# ── Bornage du pas quotidien (≤ 15 %) ─────────────────────────────────────
def cap_daily_step(current_mad, target_mad, *, max_pct=MAX_STEP_PCT):
    """Borne le budget cible à ±``max_pct`` du courant (UN pas quotidien). Le
    résultat ne peut JAMAIS s'écarter de plus de ``max_pct`` du courant —
    c'est la SEULE fabrique du budget proposé, donc un pas > 15 % est
    structurellement impossible. Budget courant ≤ 0 → aucun mouvement
    (fail-safe : pas de base)."""
    try:
        current = float(current_mad)
        target = float(target_mad)
    except (TypeError, ValueError):
        return current_mad
    if current <= 0:
        return current
    upper = current * (1 + max_pct / 100.0)
    lower = current * (1 - max_pct / 100.0)
    return max(lower, min(target, upper))


def assert_step_within_cap(current_mad, new_mad, *, company=None,
                           max_pct=MAX_STEP_PCT):
    """Garde ré-appliquée AVANT le dispatch (belt-and-suspenders) : lève
    ``BudgetStepViolation`` si |Δ| courant→proposé dépasse ``max_pct``,
    même si le payload a été fabriqué hors ``cap_daily_step``. Budget courant
    absent/≤ 0 → inopérant (fail-safe, jamais un skip silencieux)."""
    try:
        current = float(current_mad)
        new = float(new_mad)
    except (TypeError, ValueError):
        raise guardrails.GuardrailInoperative(
            "Pas quotidien non évaluable : budgets illisibles.")
    if current <= 0:
        raise guardrails.GuardrailInoperative(
            "Pas quotidien non évaluable : budget courant inconnu ou nul.")
    change = abs(new - current) / current * 100.0
    if change > max_pct + 1e-9:
        msg = (f"Pas quotidien {change:.1f}% > maximum {max_pct}% "
               f"(applicateur de budget).")
        if company is not None:
            guardrails.emit_alert(
                company, alert_type=guardrails.ALERT_GUARDRAIL, message=msg)
        raise BudgetStepViolation(msg)
    return True


# ── Validation de propriété des miroirs (DEFER ADSENG21) ──────────────────
def adset_belongs_to_company(company, adset_meta_id):
    from .models import AdSetMirror
    if not adset_meta_id:
        return False
    return AdSetMirror.objects.filter(
        company=company, meta_id=str(adset_meta_id)).exists()


def campaign_belongs_to_company(company, campaign_meta_id):
    from .models import AdCampaignMirror
    if not campaign_meta_id:
        return False
    return AdCampaignMirror.objects.filter(
        company=company, meta_id=str(campaign_meta_id)).exists()


def _raise_mirror(company, label, meta_id):
    msg = (f"Cible {label} « {meta_id} » absente des miroirs de la société : "
           f"aucun budget n'est appliqué à un objet hors miroirs.")
    if company is not None:
        guardrails.emit_alert(
            company, alert_type=guardrails.ALERT_GUARDRAIL, message=msg)
    raise MirrorOwnershipViolation(msg)


def validate_adset_target(company, payload):
    """DEFER ADSENG21 — Un changement de budget DOIT cibler un ad set POSSÉDÉ
    par la société : ``adset_id`` vide → violation ; présent mais hors miroirs
    → violation (l'action n'atteint jamais le client)."""
    payload = payload or {}
    adset_id = payload.get('adset_id')
    if not adset_id:
        _raise_mirror(company, 'ad set', '(aucun)')
    if not adset_belongs_to_company(company, adset_id):
        _raise_mirror(company, 'ad set', adset_id)
    return True


# ── Plancher CBO (dd-treasury §B2) ────────────────────────────────────────
def has_consistent_spend(company, adset_meta_id, *, as_of=None,
                         window_days=CBO_MIN_CONSISTENT_DAYS,
                         min_active_days=CBO_MIN_CONSISTENT_ACTIVE_DAYS):
    """« Spend consistant ≥ 2 sem. » = dépense > 0 sur ≥ ``min_active_days``
    jours DISTINCTS parmi les ``window_days`` derniers (consistant = peu de
    trous). Ad set absent des miroirs → False (rien à mesurer)."""
    from django.contrib.contenttypes.models import ContentType

    from .models import AdSetMirror, InsightSnapshot
    as_of = as_of or datetime.date.today()
    start = as_of - datetime.timedelta(days=window_days - 1)
    adset = AdSetMirror.objects.filter(
        company=company, meta_id=str(adset_meta_id)).first()
    if adset is None:
        return False
    ct = ContentType.objects.get_for_model(AdSetMirror)
    active_days = (InsightSnapshot.objects
                   .filter(company=company, content_type=ct,
                           object_id=adset.pk, date__gte=start,
                           date__lte=as_of, spend__gt=0)
                   .values('date').distinct().count())
    return active_days >= min_active_days


def cbo_floor_reason(company, campaign_meta_id, *, as_of=None):
    """None si CBO permis ; sinon une RAISON FR. Refuse si < 8 ad sets OU si
    < 8 ad sets à spend consistant ≥ 2 semaines (l'UN OU l'AUTRE plancher
    suffit — dd-treasury §B2)."""
    from .models import AdCampaignMirror, AdSetMirror
    campaign = AdCampaignMirror.objects.filter(
        company=company, meta_id=str(campaign_meta_id)).first()
    if campaign is None:
        return "Campagne absente des miroirs de la société : CBO refusé."
    adsets = list(AdSetMirror.objects.filter(
        company=company, campaign=campaign))
    if len(adsets) < CBO_MIN_ADSETS:
        return (f"CBO refusé : {len(adsets)} ad set(s) < plancher "
                f"{CBO_MIN_ADSETS} (concentration probable sur le bruit, "
                f"dd-treasury §B2).")
    consistent = sum(
        1 for a in adsets
        if has_consistent_spend(company, a.meta_id, as_of=as_of))
    if consistent < CBO_MIN_ADSETS:
        return (f"CBO refusé : {consistent} ad set(s) à spend consistant "
                f"≥ 2 semaines < plancher {CBO_MIN_ADSETS} (dd-treasury §B2).")
    return None


def assert_cbo_allowed(company, campaign_meta_id, *, as_of=None):
    """Lève ``CboFloorViolation`` (+ alerte) sous le plancher — la proposition
    ``enable_cbo`` n'atteint alors même pas la boîte d'approbation."""
    reason = cbo_floor_reason(company, campaign_meta_id, as_of=as_of)
    if reason:
        guardrails.emit_alert(
            company, alert_type=guardrails.ALERT_GUARDRAIL, message=reason)
        raise CboFloorViolation(reason)
    return True


# ── Propositions (propose-only — l'application reste la boucle ENG7) ───────
def _propose_budget_change(company, *, kind, adset_meta_id,
                           current_daily_budget_mad, target_daily_budget_mad,
                           reason_fr, config=None):
    validate_adset_target(company, {'adset_id': adset_meta_id})
    if config is None:
        from .models import GuardrailConfig
        config = GuardrailConfig.objects.filter(company=company).first()
    new_mad = cap_daily_step(current_daily_budget_mad, target_daily_budget_mad)
    # Plafond quotidien INVIOLABLE dès la proposition (borne aussi au plafond).
    if config is not None and config.daily_budget_ceiling_mad is not None:
        new_mad = min(float(new_mad), float(config.daily_budget_ceiling_mad))
    from . import services
    payload = {
        'adset_id': str(adset_meta_id),
        'current_budget': _mad_to_centimes(current_daily_budget_mad),
        'daily_budget': _mad_to_centimes(new_mad),
        'new_daily_budget_mad': round(float(new_mad), 2),
        'target_daily_budget_mad': round(float(target_daily_budget_mad), 2),
    }
    return services.propose_action(
        company, kind=kind, reason_fr=reason_fr, payload=payload)


def propose_rebalance_adset_budget(company, *, adset_meta_id,
                                   current_daily_budget_mad,
                                   target_daily_budget_mad, reason_fr,
                                   config=None):
    """Rééquilibrage ABO (sortie du bandit) : budget cible BORNÉ à ±15 %/jour
    ET au plafond quotidien. Propose-only."""
    return _propose_budget_change(
        company, kind=pacing.KIND_REBALANCE_ADSET_BUDGET,
        adset_meta_id=adset_meta_id,
        current_daily_budget_mad=current_daily_budget_mad,
        target_daily_budget_mad=target_daily_budget_mad,
        reason_fr=reason_fr, config=config)


def propose_increase_pace(company, *, adset_meta_id, current_daily_budget_mad,
                          reason_fr, bump_pct=None, config=None):
    """Sous-pacing → petit coup de pouce du budget quotidien, borné à 15 %/jour
    ET au plafond (``bump_pct`` défaut = MAX_STEP_PCT, le plus grand pas
    permis). Propose-only."""
    bump = MAX_STEP_PCT if bump_pct is None else min(
        float(bump_pct), MAX_STEP_PCT)
    target = float(current_daily_budget_mad) * (1 + bump / 100.0)
    return _propose_budget_change(
        company, kind=pacing.KIND_INCREASE_PACE, adset_meta_id=adset_meta_id,
        current_daily_budget_mad=current_daily_budget_mad,
        target_daily_budget_mad=target, reason_fr=reason_fr, config=config)


def propose_enable_cbo(company, *, campaign_meta_id, reason_fr, as_of=None):
    """Proposition « confier la campagne à l'allocateur Meta (CBO) ».
    REFUSÉE au niveau service sous le plancher Madgicx (< 8 ad sets OU
    < 2 sem. spend consistant) — elle n'atteint même pas la boîte
    d'approbation. Propose-only : le moteur n'active JAMAIS CBO
    programmatiquement (aucune méthode client)."""
    assert_cbo_allowed(company, campaign_meta_id, as_of=as_of)
    from . import services
    return services.propose_action(
        company, kind=pacing.KIND_ENABLE_CBO, reason_fr=reason_fr,
        payload={'campaign_id': str(campaign_meta_id)})
