"""AGEN9 — Audit de génération + rollback (services sur le schéma AGEN1).

dd-assumption-engine §10.2 point 6 : « version table de faits, verdicts par claim,
décisions, statuts Meta, id du bras — **rollback = pause + décote posterior +
quarantaine gabarit** ». Ce module pose ces champs d'audit (portés par
``CreativeGenerationBatch`` : ``fact_table_version`` / ``claim_verdicts`` /
``template_quarantined``, ajoutés par le lane models) et exécute le rollback en
quelques appels — jamais un chantier lent :

  * **PAUSE** — chaque bras (``ExperimentArm``) portant un asset du lot est
    désactivé (``is_active=False``) et son ad Meta mise en PAUSE (via le client
    gardé PAUSED-only — invariant permanent #3, jamais d'activation) ; une
    ``EngineAction`` d'audit (auto=True, approuvée SYSTÈME) est écrite.
  * **DÉCOTE POSTERIOR** — le posterior Beta(α, β) des nœuds d'hypothèse fournis
    est ramené vers son prior Beta(α₀, β₀) : l'évidence accumulée par un créatif
    qu'on annule est DÉVALUÉE (jamais figée à tort).
  * **QUARANTAINE GABARIT** — ``batch.template_quarantined=True`` + un marqueur
    cache (sans expiration) par (société, gabarit) : ``is_template_quarantined``
    le lit, et la chaîne de génération (AGEN7 ``video_queue``) refuse alors de
    régénérer ce gabarit.

Aucune migration : uniquement des champs / JSON / cache existants. Le cœur
numérique (``decay_posterior``) est PUR (testable sans base).
"""
from __future__ import annotations

import datetime
import logging

logger = logging.getLogger(__name__)

# Facteur de décote par défaut : 0 = reset total au prior, 1 = inchangé. 0.5
# dévalue de moitié l'évidence accumulée (raisonné, pas une constante de la
# nature — recalibrable comme les demi-vies ASG §8.1).
DEFAULT_DECAY_FACTOR = 0.5

# Préfixe de clé cache du registre de quarantaine (Redis en prod, LocMem sous
# les tests — partagé entre worker/beat et vues web).
_QUARANTINE_PREFIX = 'adsengine:genaudit:quarantine:'


# ── Registre de quarantaine (cache-backed, aucune migration) ─────────────────
def _quarantine_key(company, template_key):
    cid = getattr(company, 'pk', company)
    return f'{_QUARANTINE_PREFIX}{cid}:{template_key}'


def quarantine_template(company, template_key):
    """Met un gabarit en quarantaine pour la société (marqueur cache persistant).
    Un ``template_key`` vide est ignoré (no-op) — on ne met jamais « tout » en
    quarantaine par accident. Best-effort : une panne cache ne casse rien."""
    if company is None or not template_key:
        return False
    from django.core.cache import cache
    try:
        cache.set(_quarantine_key(company, template_key), True, None)  # sans TTL
    except Exception:  # noqa: BLE001 — best-effort
        logger.warning('generation_audit: quarantaine non posée', exc_info=True)
        return False
    return True


def lift_quarantine(company, template_key):
    """Lève la quarantaine d'un gabarit (marqueur cache retiré)."""
    if company is None or not template_key:
        return False
    from django.core.cache import cache
    try:
        cache.delete(_quarantine_key(company, template_key))
    except Exception:  # noqa: BLE001 — best-effort
        return False
    return True


def is_template_quarantined(company, template_key):
    """Vrai si le gabarit est en quarantaine pour la société. ``template_key``
    vide → False (aucun gabarit ciblé). Best-effort (panne cache → False)."""
    if company is None or not template_key:
        return False
    from django.core.cache import cache
    try:
        return bool(cache.get(_quarantine_key(company, template_key)))
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquer une génération
        return False


# ── Décote posterior (cœur PUR + application) ────────────────────────────────
def decay_posterior(alpha, beta, alpha0, beta0, *, factor=DEFAULT_DECAY_FACTOR):
    """Ramène un posterior Beta(α, β) vers son prior Beta(α₀, β₀) d'un ``factor``.

    ``factor`` borné [0, 1] : 0 = reset total au prior (évidence effacée), 1 =
    inchangé. Nouvelle valeur = prior + (posterior − prior) × factor. Fonction
    PURE (aucune I/O). Renvoie ``(alpha, beta)``."""
    f = max(0.0, min(1.0, float(factor)))
    new_alpha = float(alpha0) + (float(alpha) - float(alpha0)) * f
    new_beta = float(beta0) + (float(beta) - float(beta0)) * f
    return new_alpha, new_beta


def decay_node(node, *, factor=DEFAULT_DECAY_FACTOR):
    """Applique la décote posterior à un ``AssumptionNode`` (vers son prior) et
    persiste. Renvoie le nœud. L'évidence d'un nœud lié à un créatif annulé est
    dévaluée — jamais figée."""
    node.alpha, node.beta = decay_posterior(
        node.alpha, node.beta, node.alpha0, node.beta0, factor=factor)
    node.save(update_fields=['alpha', 'beta', 'updated_at'])
    return node


# ── Audit (services sur le schéma du lot) ────────────────────────────────────
def record_audit(batch, *, fact_table_version=None, claim_verdicts=None):
    """AGEN9 — Pose les champs d'audit d'un lot (jamais depuis un client API :
    lecture seule côté serializer). Fusionne les verdicts fournis dans
    ``claim_verdicts`` (jamais un écrasement muet du reste). Renvoie le lot."""
    fields = []
    if fact_table_version is not None:
        batch.fact_table_version = fact_table_version
        fields.append('fact_table_version')
    if claim_verdicts is not None:
        merged = dict(batch.claim_verdicts or {})
        merged.update(claim_verdicts)
        batch.claim_verdicts = merged
        fields.append('claim_verdicts')
    if fields:
        fields.append('updated_at')
        batch.save(update_fields=fields)
    return batch


def _batch_assets(batch):
    """Assets rattachés à un lot : ses items de backlog + l'asset accroche
    source (dédupliqués). Lecture seule."""
    assets = {}
    for item in batch.backlog_items.select_related('asset').all():
        if item.asset_id:
            assets[item.asset_id] = item.asset
    if batch.source_hook_asset_id:
        assets[batch.source_hook_asset_id] = batch.source_hook_asset
    return list(assets.values())


def _batch_arms(batch, *, active_only=True):
    """Bras d'expérience portant un asset du lot (jointure ``creative_asset``)."""
    from .models import ExperimentArm

    assets = _batch_assets(batch)
    if not assets:
        return []
    qs = ExperimentArm.objects.filter(
        company_id=batch.company_id, creative_asset__in=assets)
    if active_only:
        qs = qs.filter(is_active=True)
    return list(qs)


def audit_snapshot(batch):
    """AGEN9 — Photo d'audit d'un lot (§10.2 point 6) : version table de faits,
    verdicts par claim, décisions humaines, statuts Meta des ads liées, et les
    bras (id + label). Lecture seule, JSON-safe."""
    arms = _batch_arms(batch, active_only=False)
    return {
        'batch_id': batch.pk,
        'fact_table_version': batch.fact_table_version,
        'claim_verdicts': dict(batch.claim_verdicts or {}),
        'template_quarantined': bool(batch.template_quarantined),
        'human_decision': {
            'status': batch.status,
            'approved_by_id': batch.approved_by_id,
            'approved_at': (batch.approved_at.isoformat()
                            if batch.approved_at else None),
            'note': batch.note,
        },
        'arms': [
            {'arm_id': a.pk, 'label': a.label, 'ad_id': a.ad_id,
             'is_active': a.is_active}
            for a in arms
        ],
        'meta_statuses': _meta_statuses_for_arms(batch, arms),
    }


def _meta_statuses_for_arms(batch, arms):
    """Statuts Meta (``AdMirror.status``) des ads des bras, par ``ad_id``."""
    from .models import AdMirror

    ad_ids = [a.ad_id for a in arms if a.ad_id]
    if not ad_ids:
        return {}
    mirrors = AdMirror.objects.filter(
        company_id=batch.company_id, meta_id__in=ad_ids)
    return {m.meta_id: m.status for m in mirrors}


def _emit_critical_alert(company, *, message, entity_key, action=None):
    """Émet une ``EngineAlert`` 🔴 CRITICAL dédiée (dédup par ``entity_key`` sur
    un cooldown court). Best-effort : l'alerte est déjà journalisée."""
    from django.utils import timezone

    from . import guardrails
    from .models import EngineAlert
    from .rules import SEVERITY_CRITICAL

    logger.warning('generation_audit ALERTE société=%s: %s',
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
            detail={'source': 'generation_audit.rollback'})
    except Exception:  # pragma: no cover - défensif
        logger.warning('generation_audit: échec persistance alerte', exc_info=True)
        return None


def asset_provenance(asset):
    """PUB84 — Piste de provenance DURABLE d'UN asset créatif : le lot de
    génération ancrée qui l'a produit (fait cité → version de la table de
    faits → verdicts par claim → décision humaine), les bras qui le portent
    (avec statut Meta), et le ``policy_stamp`` posé à la génération (ENG16).
    Consultable sur la créathèque même après que le rapport de génération
    d'origine se soit « dispersé » (le lot ``CreativeGenerationBatch`` reste
    la source de vérité durable, jamais recalculée ici — simple lecture).

    ``None`` batch (asset uploadé manuellement, jamais issu d'un lot de
    génération ancrée) → provenance réduite à son ``policy_stamp`` (jamais une
    exception, jamais un lot fabriqué). Lecture seule, JSON-safe."""
    item = (asset.backlog_items
            .select_related('batch').order_by('-created_at').first())
    batch = item.batch if item else None

    if batch is None:
        return {
            'asset_id': asset.pk,
            'batch_id': None,
            'fact_table_version': None,
            'claim_verdicts': {},
            'template_quarantined': False,
            'human_decision': None,
            'meta_status': None,
            'policy_stamp': dict(asset.policy_stamp or {}),
        }

    snap = audit_snapshot(batch)
    arm = next(
        (a for a in _batch_arms(batch, active_only=False)
         if a.creative_asset_id == asset.pk),
        None)
    meta_status = (
        snap['meta_statuses'].get(arm.ad_id) if arm is not None else None)

    return {
        'asset_id': asset.pk,
        'batch_id': batch.pk,
        'fact_table_version': snap['fact_table_version'],
        'claim_verdicts': snap['claim_verdicts'],
        'template_quarantined': snap['template_quarantined'],
        'human_decision': snap['human_decision'],
        'meta_status': meta_status,
        'policy_stamp': dict(asset.policy_stamp or {}),
    }


def rollback_batch(batch, *, template_key='', nodes=None, client=None,
                   reason_fr='', now=None):
    """AGEN9 — Rollback d'un lot de génération en quelques appels (§10.2 point 6).

    1. **PAUSE** : chaque bras du lot est désactivé et son ad mise en PAUSE (via
       ``client`` gardé PAUSED-only ; sans client, la pause reste locale — le bras
       est quand même retiré du bandit) ; une ``EngineAction`` d'audit est écrite.
    2. **DÉCOTE POSTERIOR** : chaque nœud d'hypothèse fourni est ramené vers son
       prior (évidence dévaluée).
    3. **QUARANTAINE** : ``batch.template_quarantined=True`` + marqueur cache par
       (société, gabarit) — le gabarit ne peut plus régénérer (AGEN7).

    Émet une alerte 🔴. Renvoie un récapitulatif JSON-safe.
    """
    from django.utils import timezone

    from . import guardrails
    from .models import EngineAction

    company = batch.company
    reason = (reason_fr or '').strip() or (
        f"Rollback du lot #{batch.pk} : pause + décote posterior + quarantaine "
        f"gabarit (génération annulée).")

    # 1. PAUSE + désactivation des bras.
    arms = _batch_arms(batch, active_only=True)
    paused = 0
    action = None
    for arm in arms:
        arm.is_active = False
        arm.save(update_fields=['is_active', 'updated_at'])
        if arm.ad_id:
            # Trace d'audit : action de pause approuvée SYSTÈME (jamais humaine).
            action = EngineAction.objects.create(
                company=company, kind=EngineAction.Kind.PAUSE,
                payload={'source': 'generation_audit.rollback',
                         'target_type': 'ad', 'target_meta_id': arm.ad_id,
                         'batch_id': batch.pk, 'arm_id': arm.pk},
                reason_fr=reason,
                status=EngineAction.Statut.APPROUVEE, auto=True)
            if client is not None:
                # Gardé PAUSED-only AVANT l'appel (jamais d'activation, #3).
                guardrails.enforce_paused_only('PAUSED', company=company)
                try:
                    client.update_status_paused(object_id=arm.ad_id, level='ad')
                    paused += 1
                except Exception:  # pragma: no cover - défensif, isolation
                    logger.warning(
                        'generation_audit: pause ad %s échouée', arm.ad_id,
                        exc_info=True)

    # 2. DÉCOTE POSTERIOR des nœuds fournis.
    decayed = 0
    for node in (nodes or []):
        decay_node(node)
        decayed += 1

    # 3. QUARANTAINE gabarit (flag lot + marqueur cache).
    batch.template_quarantined = True
    batch.save(update_fields=['template_quarantined', 'updated_at'])
    quarantined = quarantine_template(company, template_key) if template_key \
        else False

    _emit_critical_alert(
        company,
        message=(f"🔴 Rollback du lot #{batch.pk} : {len(arms)} bras retiré(s), "
                 f"{decayed} posterior(s) décoté(s)"
                 + (f", gabarit « {template_key} » en quarantaine" if quarantined
                    else '') + "."),
        entity_key=f'genaudit:rollback:{batch.pk}'[:80],
        action=action)

    result = {
        'batch_id': batch.pk,
        'arms_deactivated': len(arms),
        'ads_paused': paused,
        'nodes_decayed': decayed,
        'template_quarantined': bool(batch.template_quarantined),
        'template_key': template_key,
        'quarantine_marked': quarantined,
        'at': (now or timezone.now()).isoformat(),
    }
    logger.info('generation_audit.rollback_batch: %s', result)
    return result
