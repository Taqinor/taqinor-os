"""ENG7 — Orchestration de la boucle propose→approuve→applique.

Le seul chemin qui atteint ``meta_client`` est ``apply_action`` SUR UNE ACTION
APPROUVÉE. Une action ``proposee`` / ``rejetee`` / ``appliquee`` / ``echouee``
n'atteint JAMAIS le client (garde de sécurité en tête de ``apply_action``, testée).
Il n'existe aucun chemin d'auto-application : ``apply_action`` doit être appelé
explicitement, jamais déclenché par une proposition.

Pattern : ``contrats.EtapeApprobation`` (statut local persistant + acteur posé
côté serveur), pas le registre stateless ``apps/agent``.
"""
from __future__ import annotations

import logging

from django.utils import timezone

from .models import EngineAction

logger = logging.getLogger(__name__)


# ── ENG8 — Toggles de capacités (par société) ────────────────────────────────
# Chaque ``kind`` auto-applicable est associé au champ booléen de capacité qui,
# une fois activé sur la ``GuardrailConfig`` de la société, autorise l'exécution
# SANS approbation humaine (mais avec une trace ``EngineAction auto=True`` +
# journalisation). Tout kind ABSENT de ce mapping exige TOUJOURS l'approbation.
CAPABILITY_FOR_KIND = {
    EngineAction.Kind.ROTATE_CREATIVE: 'auto_rotate_creative',
    EngineAction.Kind.REBALANCE_BUDGET: 'auto_rebalance_within_band',
}


def capability_enabled(config, kind):
    """ENG8 — Vrai si le ``kind`` est couvert par une capacité ACTIVÉE.

    ``config`` ``None`` (aucune GuardrailConfig) ou kind hors mapping →
    ``False`` : par défaut, tout exige l'approbation (aucune auto-application).
    """
    if config is None:
        return False
    field = CAPABILITY_FOR_KIND.get(kind)
    if not field:
        return False
    return bool(getattr(config, field, False))


class ActionNotApproved(Exception):
    """Levée si on tente d'appliquer une action non approuvée (jamais de client)."""


class CreativePolicyNotPassed(ValueError):
    """ENG15 — Levée si une création d'ad référence un asset non validé policy."""


# Kinds qui créent une ad et peuvent donc référencer un ``CreativeAsset``.
_AD_CREATING_KINDS = frozenset({
    EngineAction.Kind.CREATE_AD, EngineAction.Kind.ROTATE_CREATIVE,
})


def assert_creative_ok_for_ad(company, kind, payload):
    """ENG15 — Garde-fou policy créative : un asset dont ``policy_stamp.passed``
    n'est pas vrai NE PEUT PAS être référencé par une action de création d'ad.

    No-op si le kind ne crée pas d'ad ou si aucun ``creative_asset_id`` n'est
    référencé. Lève ``CreativePolicyNotPassed`` (sous-classe de ``ValueError``)
    sinon — l'action n'est jamais créée."""
    if kind not in _AD_CREATING_KINDS:
        return
    asset_id = (payload or {}).get('creative_asset_id')
    if not asset_id:
        return
    from .models import CreativeAsset
    asset = CreativeAsset.objects.filter(company=company, id=asset_id).first()
    if asset is None:
        raise CreativePolicyNotPassed(
            "Créatif introuvable pour cette société.")
    if not asset.is_policy_passed:
        raise CreativePolicyNotPassed(
            "Créatif non validé (policy_stamp.passed absent) : il ne peut pas "
            "être référencé par une création d'ad.")


def propose_action(company, *, kind, reason_fr, payload=None, auto=False):
    """Crée une action PROPOSÉE. ``reason_fr`` (une phrase FR) est obligatoire."""
    if not (reason_fr and str(reason_fr).strip()):
        raise ValueError(
            "Une raison en une phrase (français) est obligatoire pour proposer "
            "une action.")
    assert_creative_ok_for_ad(company, kind, payload)
    return EngineAction.objects.create(
        company=company, kind=kind, payload=payload or {},
        reason_fr=str(reason_fr).strip(),
        status=EngineAction.Statut.PROPOSEE, auto=auto)


def approve_action(action, *, user):
    """Approuve une action PROPOSÉE (acteur posé côté serveur)."""
    if action.status != EngineAction.Statut.PROPOSEE:
        raise ValueError("Seule une action proposée peut être approuvée.")
    action.status = EngineAction.Statut.APPROUVEE
    action.approved_by = user
    action.save(update_fields=['status', 'approved_by', 'updated_at'])
    return action


def reject_action(action, *, user, commentaire=''):
    """Rejette une action PROPOSÉE (elle ne pourra jamais être appliquée)."""
    if action.status != EngineAction.Statut.PROPOSEE:
        raise ValueError("Seule une action proposée peut être rejetée.")
    action.status = EngineAction.Statut.REJETEE
    action.approved_by = user
    if commentaire:
        action.error = str(commentaire)
    action.save(update_fields=['status', 'approved_by', 'error', 'updated_at'])
    return action


def _dispatch(client, action):
    """Route une action APPROUVÉE vers la bonne méthode de création du client.

    Toutes les créations naissent PAUSED (garanti par ``meta_client`` lui-même).
    Aucune activation n'est routable ici — le client n'en expose aucune.
    """
    payload = action.payload or {}
    kind = action.kind
    if kind == EngineAction.Kind.CREATE_CAMPAIGN:
        return client.create_campaign(
            name=payload.get('name', ''),
            objective=payload.get('objective', ''),
            special_ad_categories=payload.get('special_ad_categories'),
            extra_fields=payload.get('extra_fields'))
    if kind == EngineAction.Kind.CREATE_ADSET:
        return client.create_adset(
            name=payload.get('name', ''),
            campaign_id=payload.get('campaign_id', ''),
            extra_fields=payload.get('extra_fields'))
    if kind == EngineAction.Kind.CREATE_AD:
        return client.create_ad(
            name=payload.get('name', ''),
            adset_id=payload.get('adset_id', ''),
            extra_fields=payload.get('extra_fields'))
    if kind == EngineAction.Kind.ROTATE_CREATIVE:
        # Roter le créatif = créer une NOUVELLE ad (toujours PAUSED) portant le
        # nouveau créatif ; le client garantit le statut PAUSED (jamais d'activ.).
        return client.create_ad(
            name=payload.get('name', ''),
            adset_id=payload.get('adset_id', ''),
            extra_fields=payload.get('extra_fields'))
    if kind == EngineAction.Kind.REBALANCE_BUDGET:
        # Rééquilibrage de budget dans la bande. La méthode concrète de mise à
        # jour de budget du client atterrit avec le groupe budget (ADSENG) ; ici
        # on route déjà l'appel. Un client réel qui ne l'expose pas encore lève
        # (→ action « echouee », jamais d'application silencieuse ni d'activation).
        return client.update_adset_budget(
            adset_id=payload.get('adset_id', ''),
            daily_budget=payload.get('daily_budget'),
            extra_fields=payload.get('extra_fields'))
    raise ValueError(f"Type d'action non routable : {kind}")


def apply_action(action, *, connection=None, client=None):
    """Applique une action **UNIQUEMENT si elle est approuvée**.

    Garde de sécurité EN PREMIER : une action non ``approuvee`` lève
    ``ActionNotApproved`` AVANT toute construction/appel du client Meta (le
    client n'est jamais atteint). En cas d'échec Meta, l'action passe ``echouee``
    (erreur consignée) et l'exception est relancée ; en cas de succès, elle passe
    ``appliquee`` (``applied_at`` + ``result`` posés côté serveur).
    """
    if action.status != EngineAction.Statut.APPROUVEE:
        raise ActionNotApproved(
            "Action non approuvée : refus d'appliquer (le client Meta n'est "
            "jamais atteint).")

    if client is None:
        from .meta_client import MetaClient
        from .models import MetaConnection
        if connection is None:
            connection = MetaConnection.objects.filter(
                company=action.company, enabled=True).first()
        if connection is None:
            raise ActionNotApproved(
                "Aucune connexion Meta active : application impossible.")
        client = MetaClient.from_connection(connection)

    try:
        result = _dispatch(client, action)
    except Exception as exc:
        action.status = EngineAction.Statut.ECHOUEE
        action.error = str(exc)
        action.save(update_fields=['status', 'error', 'updated_at'])
        raise

    action.status = EngineAction.Statut.APPLIQUEE
    action.applied_at = timezone.now()
    action.result = result if isinstance(result, dict) else {'result': result}
    action.error = ''
    action.save(
        update_fields=['status', 'applied_at', 'result', 'error', 'updated_at'])
    return action


def execute_auto_action(company, *, kind, reason_fr, payload=None,
                        config=None, client=None, connection=None):
    """ENG8 — Exécute une action en respectant les toggles de capacités.

    * Capacité NON activée pour ce ``kind`` (défaut) → l'action est simplement
      PROPOSÉE (``auto=False``) : le chemin humain propose→approuve→applique reste
      obligatoire, comme pour tout le reste.
    * Capacité ACTIVÉE → on saute l'approbation humaine, MAIS on écrit quand même
      une ligne ``EngineAction`` (``auto=True``) marquée approuvée côté SYSTÈME
      (jamais un ``approved_by`` humain), on JOURNALISE, puis on applique via
      ``apply_action`` (qui passe par ``meta_client`` — statut PAUSED garanti,
      jamais d'activation). La trace d'audit existe toujours.

    ``config`` : ``GuardrailConfig`` de la société (résolue si non fournie).
    """
    if config is None:
        from .models import GuardrailConfig
        config = GuardrailConfig.objects.filter(company=company).first()

    if not capability_enabled(config, kind):
        # Capacité non activée → approbation humaine requise (aucun auto-apply).
        return propose_action(
            company, kind=kind, reason_fr=reason_fr, payload=payload, auto=False)

    if not (reason_fr and str(reason_fr).strip()):
        raise ValueError(
            "Une raison en une phrase (français) est obligatoire.")

    # ENG15 — même en auto, un asset non validé policy ne part jamais en prod.
    assert_creative_ok_for_ad(company, kind, payload)

    # Capacité activée : trace d'audit auto=True, approuvée côté système, appliquée.
    action = EngineAction.objects.create(
        company=company, kind=kind, payload=payload or {},
        reason_fr=str(reason_fr).strip(),
        status=EngineAction.Statut.APPROUVEE, auto=True)
    logger.info(
        'ENG8 auto-apply capacité=%s kind=%s société=%s action=%s',
        CAPABILITY_FOR_KIND.get(kind), kind, company.pk, action.pk)
    return apply_action(action, client=client, connection=connection)
