"""Rétention : purges des données de leads (SPL6, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
from django.utils import timezone


DEFAULT_WEBSITE_LEAD_PAYLOAD_RETENTION_DAYS = 180
DEFAULT_CHAT_SESSION_RETENTION_DAYS = 180


def _retention_days(setting_name, default_days):
    from django.conf import settings
    value = getattr(settings, setting_name, None)
    if value is None:
        return default_days
    try:
        return int(value)
    except (TypeError, ValueError):
        return default_days


def purge_website_lead_payloads(now, apply_) -> int:
    """QX42 — purge les ``WebsiteLeadPayload`` PROCESSED au-delà de la
    fenêtre de rétention. Les payloads NON traités ou en ERREUR (``error``
    non vide) sont EXEMPTÉS — ils doivent d'abord vieillir via la surface de
    rejeu QX16 (un payload en erreur reste la seule trace récupérable d'un
    lead potentiellement perdu ; on ne purge jamais une piste encore
    actionnable). Contrat ``core.retention`` : ``apply_=False`` (dry-run) ne
    supprime rien, renvoie le compte qui SERAIT supprimé."""
    from django.db.models import Q

    from .models import WebsiteLeadPayload

    days = _retention_days(
        'WEBSITE_LEAD_PAYLOAD_RETENTION_DAYS',
        DEFAULT_WEBSITE_LEAD_PAYLOAD_RETENTION_DAYS)
    if days <= 0:
        return 0
    cutoff = now - timezone.timedelta(days=days)
    qs = WebsiteLeadPayload.objects.filter(
        processed=True, received_at__lt=cutoff,
    ).filter(Q(error__isnull=True) | Q(error=''))
    count = qs.count()
    if apply_ and count:
        qs.delete()
    return count


def purge_stale_chat_sessions(now, apply_) -> int:
    """QX42 — purge les ``ChatSessionPublique`` (transcript PII d'un visiteur
    anonyme) inactives au-delà de la fenêtre de rétention (mesurée sur
    ``last_message_at`` — une session encore active récemment n'est jamais
    purgée même si ``created_at`` est ancien). Une session déjà liée à un
    Lead réel (``lead_id`` renseigné) garde son transcript — la conversation
    fait partie de l'historique du lead, pas une trace anonyme jetable.

    ACRM19 — SAUF celle d'un lead ANONYMISÉ : l'historique n'a plus de
    personne à qui appartenir, l'exemption ne la protège plus."""
    from django.db.models import Q

    from .dsr_provider import LEAD_NOM_ANONYMISE
    from .models import ChatSessionPublique

    days = _retention_days(
        'CHAT_SESSION_RETENTION_DAYS', DEFAULT_CHAT_SESSION_RETENTION_DAYS)
    if days <= 0:
        return 0
    cutoff = now - timezone.timedelta(days=days)
    qs = ChatSessionPublique.objects.filter(
        last_message_at__lt=cutoff).filter(
            Q(lead__isnull=True) | Q(lead__nom=LEAD_NOM_ANONYMISE))
    count = qs.count()
    if apply_ and count:
        qs.delete()
    return count
