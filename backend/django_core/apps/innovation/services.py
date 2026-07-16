"""Services (écritures/orchestration) du module ``apps.innovation``."""
from django.db import IntegrityError, transaction

from .models import Idee, VoteIdee

# ── Votes (NTIDE2) ──────────────────────────────────────────────────────────


class VoteInterdit(ValueError):
    """Levée quand le vote est refusé (auteur de sa propre idée, doublon)."""


@transaction.atomic
def voter(idee, user):
    """Crée un vote pour ``idee`` au nom de ``user`` et incrémente le compteur
    dénormalisé. L'auteur d'une idée ne peut pas voter pour la sienne
    (« Voter ← auteurs en lecture », NTIDE5). Refuse un doublon (unique
    ``(idee, votant)``, NTIDE2)."""
    from django.db.models import F

    if idee.auteur_id and idee.auteur_id == user.id:
        raise VoteInterdit('Vous ne pouvez pas voter pour votre propre idée.')
    try:
        vote = VoteIdee.objects.create(
            company=idee.company, idee=idee, votant=user)
    except IntegrityError as exc:
        raise VoteInterdit('Vous avez déjà voté pour cette idée.') from exc
    Idee.objects.filter(pk=idee.pk).update(votes_count=F('votes_count') + 1)
    idee.refresh_from_db(fields=['votes_count'])
    return vote


@transaction.atomic
def retirer_vote(vote):
    """Supprime un vote et décrémente le compteur dénormalisé (jamais sous
    zéro)."""
    from django.db.models import F

    idee_id = vote.idee_id
    vote.delete()
    Idee.objects.filter(pk=idee_id, votes_count__gt=0).update(
        votes_count=F('votes_count') - 1)
