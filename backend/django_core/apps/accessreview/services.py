"""Services de la gouvernance des accès (NTSEC19).

Génération des items d'une campagne (un par compte du périmètre) et
attestation/révocation. Une révocation retire le rôle via
``apps.roles.services`` — jamais d'import direct de ``roles.models``.
"""
from __future__ import annotations

from django.utils import timezone


def users_in_scope(campaign):
    """Comptes de la société entrant dans le périmètre de la campagne."""
    from authentication.models import CustomUser
    qs = CustomUser.objects.filter(company=campaign.company, is_active=True)
    if campaign.perimetre == campaign.Perimetre.ROLE and campaign.perimetre_ref:
        qs = qs.filter(role_id=campaign.perimetre_ref)
    return qs


def generate_items(campaign):
    """Crée un ``AccessReviewItem`` par compte du périmètre (idempotent).

    Renvoie le nombre d'items créés. Chaque item fige un instantané du rôle
    courant (``role_snapshot``)."""
    from .models import AccessReviewItem
    created = 0
    existing = set(
        AccessReviewItem.objects.filter(campagne=campaign)
        .values_list('user_id', flat=True))
    for user in users_in_scope(campaign):
        if user.pk in existing:
            continue
        snapshot = {'role_id': user.role_id,
                    'role_nom': getattr(user.role, 'nom', '')
                    if user.role_id else ''}
        AccessReviewItem.objects.create(
            company=campaign.company, campagne=campaign, user=user,
            role_snapshot=snapshot)
        created += 1
    return created


def attester(item, *, decision, reviewer, commentaire=''):
    """Enregistre la décision d'un manager sur un item.

    ``decision=revoque`` retire le rôle de l'utilisateur via
    ``apps.roles.services`` (scopé société). Renvoie l'item mis à jour."""
    from .models import AccessReviewItem

    item.decision = decision
    item.reviewer = reviewer
    item.commentaire = commentaire or ''
    item.decided_at = timezone.now()
    item.save(update_fields=[
        'decision', 'reviewer', 'commentaire', 'decided_at'])

    if decision == AccessReviewItem.Decision.REVOQUE:
        from apps.roles.services import remove_role_from_user
        role_id = (item.role_snapshot or {}).get('role_id') or item.user.role_id
        remove_role_from_user(item.user, role_id)
    return item
