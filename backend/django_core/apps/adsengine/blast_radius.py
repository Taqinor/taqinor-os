"""AGEN8 — Rayon d'explosion : née PAUSED → budget test fixe → auto-pause maison.

dd-assumption-engine §10.2 point 5 : « née PAUSED → budget test fixe → auto-pause
maison sur désapprobation/négatifs (**Meta n'en offre AUCUN — vérifié comme
absence — à construire via polling + Ad Rules Engine**) ». Ce module borne le
rayon d'explosion d'un créatif GÉNÉRÉ :

  1. **Née PAUSED** — invariant permanent (règle #3) déjà garanti au niveau du
     client Meta (``meta_client.FORCED_STATUS='PAUSED'``) : aucun asset/ad ne part
     jamais actif du moteur. Ce module ne fait que RAISONNER dessus.
  2. **Budget test fixe** — un créatif généré n'entre dans le bandit qu'APRÈS
     avoir dépensé son budget de test (config ``ADSENGINE_TEST_BUDGET_MAD``,
     défaut 30 MAD) SANS désapprobation (``can_enter_bandit``). En dessous, il
     reste hors bandit (rayon borné).
  3. **Auto-pause maison** — Meta n'offre AUCUNE auto-pause native (absence
     vérifiée) : on POLLE ``effective_status`` (miroir local ``AdMirror.status``,
     alimenté par la sync) et, sur désapprobation / signal négatif, on met l'ad en
     PAUSE (client gardé PAUSED-only), on retire le bras du bandit, on écrit une
     ``EngineAction`` d'audit et on émet une alerte 🔴 — dans le cycle de polling
     courant. C'est le pendant maison de l'Ad Rules Engine.

Le cœur (budget test + décision de pause) est PUR ; seul ``poll_and_autopause``
lit/écrit la base. Aucune migration (config env + champs/JSON existants).
"""
from __future__ import annotations

import logging
import os
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

# Budget de test fixe par défaut (MAD) — le créatif né PAUSED doit l'avoir
# dépensé avant d'entrer dans le bandit (§10.2 point 5). Raisonné, recalibrable
# via l'environnement — jamais un chiffre figé en dur ailleurs.
DEFAULT_TEST_BUDGET_MAD = Decimal('30')


def test_budget_mad():
    """Budget de test fixe (MAD) : ``ADSENGINE_TEST_BUDGET_MAD`` ou le défaut.
    Valeur illisible → défaut (jamais un budget fabriqué / négatif)."""
    raw = os.environ.get('ADSENGINE_TEST_BUDGET_MAD', '')
    if not raw:
        return DEFAULT_TEST_BUDGET_MAD
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return DEFAULT_TEST_BUDGET_MAD
    return value if value > 0 else DEFAULT_TEST_BUDGET_MAD


# ── Budget test (cœur PUR) ───────────────────────────────────────────────────
def has_cleared_test_budget(spend_mad, *, budget_mad=None):
    """Vrai si la dépense cumulée atteint le budget de test fixe. Fonction PURE."""
    budget = budget_mad if budget_mad is not None else test_budget_mad()
    try:
        return Decimal(str(spend_mad)) >= Decimal(str(budget))
    except (InvalidOperation, ValueError, TypeError):
        return False


def can_enter_bandit(spend_mad, *, status='', budget_mad=None):
    """Vrai si un créatif généré peut ENTRER dans le bandit : budget test purgé
    ET pas de désapprobation Meta. Fonction PURE (délègue la détection de refus à
    ``anomaly.detect_disapproved``). Un statut vide = « pas encore de verdict de
    révision » → on n'assume jamais « OK » : reste hors bandit."""
    from . import anomaly

    if not has_cleared_test_budget(spend_mad, budget_mad=budget_mad):
        return False
    detection = anomaly.detect_disapproved(status)
    # Refus confirmé OU statut inconnu (insufficient_data) ⇒ pas d'entrée.
    return not (detection.fired or detection.insufficient_data)


def arm_spend_mad(company, arm):
    """Dépense cumulée (MAD) d'un bras, depuis ses ``ArmDailyStat`` (alimentés
    par la sync). 0 si aucune stat. Scopé société."""
    from django.db.models import Sum

    from .models import ArmDailyStat

    total = (ArmDailyStat.objects
             .filter(company=company, arm=arm)
             .aggregate(s=Sum('spend'))['s'])
    return total or Decimal('0')


def eligible_arms_for_bandit(company, *, status_lookup=None):
    """Bras (générés, actifs, avec ad_id) ayant purgé leur budget test SANS refus
    — donc éligibles au bandit. ``status_lookup(ad_id) -> (status, reason)``
    optionnel (défaut : ``AdMirror.status``). Lecture seule."""
    lookup = status_lookup or _default_status_lookup(company)
    eligible = []
    for arm in _monitored_arms(company):
        status, _ = lookup(arm.ad_id)
        if can_enter_bandit(arm_spend_mad(company, arm), status=status):
            eligible.append(arm)
    return eligible


# ── Auto-pause maison (polling effective_status) ─────────────────────────────
def _monitored_arms(company):
    """Bras SURVEILLÉS : actifs, portant un créatif GÉNÉRÉ (``creative_asset``)
    et un ``ad_id`` Meta (jointure statut). Ce sont les créatifs dont le rayon
    d'explosion est borné."""
    from .models import ExperimentArm

    return list(
        ExperimentArm.objects
        .filter(company=company, is_active=True,
                creative_asset__isnull=False)
        .exclude(ad_id='')
        .select_related('creative_asset'))


def _default_status_lookup(company):
    """Fabrique un lookup ``ad_id -> (status, reason)`` lisant ``AdMirror.status``
    (miroir de ``effective_status`` alimenté par la sync). Reason toujours '' —
    le miroir ne porte pas le motif de refus détaillé."""
    from .models import AdMirror

    mirrors = {
        m.meta_id: m.status
        for m in AdMirror.objects.filter(company=company)
    }

    def lookup(ad_id):
        return mirrors.get(ad_id, ''), ''

    return lookup


def evaluate_ad_status(status, *, rejection_reason=''):
    """Verdict d'auto-pause pour un ``effective_status`` (délègue à
    ``anomaly.detect_disapproved``). ``fired`` True ⇒ refus confirmé ⇒ pause.
    Fonction PURE."""
    from . import anomaly

    return anomaly.detect_disapproved(status, rejection_reason=rejection_reason)


def _pause_arm(company, arm, *, detection, client):
    """Met l'ad d'un bras en PAUSE (client gardé PAUSED-only), désactive le bras,
    écrit une ``EngineAction`` d'audit auto et émet une alerte 🔴. Renvoie
    ``(action, paused_bool)``."""
    from . import guardrails
    from .models import EngineAction

    reason = (detection.message_fr
              or f"Auto-pause maison : ad {arm.ad_id} en refus Meta.")
    arm.is_active = False
    arm.save(update_fields=['is_active', 'updated_at'])

    action = EngineAction.objects.create(
        company=company, kind=EngineAction.Kind.PAUSE,
        payload={'source': 'blast_radius.autopause',
                 'target_type': 'ad', 'target_meta_id': arm.ad_id,
                 'arm_id': arm.pk, 'computed': detection.computed},
        reason_fr=reason,
        status=EngineAction.Statut.APPROUVEE, auto=True)

    paused = False
    if client is not None:
        # Gardé PAUSED-only AVANT l'appel (jamais d'activation, invariant #3).
        guardrails.enforce_paused_only('PAUSED', company=company)
        try:
            client.update_status_paused(object_id=arm.ad_id, level='ad')
            paused = True
        except Exception:  # pragma: no cover - défensif, isolation
            logger.warning('blast_radius: pause ad %s échouée', arm.ad_id,
                           exc_info=True)

    _emit_critical_alert(
        company,
        message=(f"🔴 Auto-pause du créatif généré (ad {arm.ad_id}) : "
                 f"{reason}"),
        entity_key=f'blastradius:autopause:{arm.ad_id}'[:80],
        action=action)
    return action, paused


def _emit_critical_alert(company, *, message, entity_key, action=None):
    """Émet une ``EngineAlert`` 🔴 CRITICAL dédiée (dédup ``entity_key`` sur un
    cooldown court). Best-effort : l'alerte est déjà journalisée."""
    import datetime

    from django.utils import timezone

    from . import guardrails
    from .models import EngineAlert
    from .rules import SEVERITY_CRITICAL

    logger.warning('blast_radius ALERTE société=%s: %s',
                   getattr(company, 'pk', company), message)
    if company is None:
        return None
    try:
        since = timezone.now() - datetime.timedelta(hours=6)
        existing = (EngineAlert.objects
                    .filter(company=company, entity_key=entity_key,
                            resolved=False, created_at__gte=since)
                    .order_by('-created_at').first())
        if existing is not None:
            return existing
        return EngineAlert.objects.create(
            company=company, alert_type=guardrails.ALERT_ANOMALY,
            message=message, severity=SEVERITY_CRITICAL, entity_key=entity_key,
            cooldown_hours=6, action=action,
            detail={'source': 'blast_radius.autopause'})
    except Exception:  # pragma: no cover - défensif
        logger.warning('blast_radius: échec persistance alerte', exc_info=True)
        return None


def poll_and_autopause(company, *, client=None, status_lookup=None, now=None):
    """AGEN8 — UN cycle de polling : met en PAUSE tout créatif généré désapprouvé.

    Pour chaque bras surveillé (actif, généré, avec ad_id), lit son
    ``effective_status`` (via ``status_lookup`` ou ``AdMirror.status``) et, sur
    refus confirmé (``detect_disapproved.fired``), met l'ad en PAUSE (client gardé
    PAUSED-only), retire le bras, écrit une ``EngineAction`` d'audit et émet une
    alerte 🔴 — le tout DANS ce cycle. Statut inconnu ⇒ jamais de pause (on
    n'assume pas « refusé » sans preuve). Best-effort par bras.

    Renvoie ``{'polled', 'paused', 'alerted'}``.
    """
    lookup = status_lookup or _default_status_lookup(company)
    polled = paused = alerted = 0
    for arm in _monitored_arms(company):
        polled += 1
        status, reason = lookup(arm.ad_id)
        detection = evaluate_ad_status(status, rejection_reason=reason)
        if not detection.fired:
            continue  # OK / statut inconnu : jamais de pause spéculative
        try:
            _, was_paused = _pause_arm(
                company, arm, detection=detection, client=client)
        except Exception:  # pragma: no cover - défensif, isolation par bras
            logger.warning('blast_radius: auto-pause bras %s échouée', arm.pk,
                           exc_info=True)
            continue
        alerted += 1
        if was_paused:
            paused += 1

    result = {'polled': polled, 'paused': paused, 'alerted': alerted}
    if polled:
        logger.info('blast_radius.poll_and_autopause: %s', result)
    return result
