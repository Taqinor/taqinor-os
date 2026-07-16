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

from django.utils import timezone

from .models import EngineAction


class ActionNotApproved(Exception):
    """Levée si on tente d'appliquer une action non approuvée (jamais de client)."""


def propose_action(company, *, kind, reason_fr, payload=None, auto=False):
    """Crée une action PROPOSÉE. ``reason_fr`` (une phrase FR) est obligatoire."""
    if not (reason_fr and str(reason_fr).strip()):
        raise ValueError(
            "Une raison en une phrase (français) est obligatoire pour proposer "
            "une action.")
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
