"""Lectures de la messagerie interne (recherche, listes scopées).

Toujours scopé société ET appartenance : on ne lit jamais une conversation dont
l'utilisateur n'est pas membre, jamais cross-tenant.
"""
from django.db.models import Q


def member_conversation_ids(user, company):
    """IDs des conversations (de la société) dont `user` est membre."""
    from .models import ConversationMember
    return list(
        ConversationMember.objects.filter(
            user=user, conversation__company=company)
        .values_list('conversation_id', flat=True))


def search_messages(user, company, query, *, limit=50):
    """S5 — recherche company- + appartenance-scopée sur les corps de messages
    ET les transcriptions vocales, UNIQUEMENT dans les conversations de
    l'appelant. Jamais cross-tenant.

    Retourne une liste de Message (préchargés) triés du plus récent au plus
    ancien. `icontains` (Postgres) ; pas de dépendance trigram requise."""
    from .models import Message

    q = (query or '').strip()
    if not q:
        return []
    conv_ids = member_conversation_ids(user, company)
    if not conv_ids:
        return []
    return list(
        Message.objects.filter(
            company=company,
            conversation_id__in=conv_ids,
            deleted_at__isnull=True,
        ).filter(
            Q(body__icontains=q)
            | Q(attachments__transcript__icontains=q)
        ).select_related('conversation', 'sender')
        .distinct()
        .order_by('-created_at', '-id')[:limit])
