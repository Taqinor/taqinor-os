"""Services (écritures/orchestration) du module ``apps.innovation``.

Le chatter (« historique ») réutilise ``apps.records.services.log_activity``
(ARC8, générique) — jamais un modèle ``*Activity`` maison.
"""
from django.db import IntegrityError, transaction

from .models import Idee, VoteIdee

# ── Machine à états (NTIDE5) ────────────────────────────────────────────────

# {statut_cible: {statuts_de_depart_autorises}}
_TRANSITIONS = {
    Idee.Statut.EXAMINEE: {Idee.Statut.OUVERT},
    Idee.Statut.RETENUE: {Idee.Statut.EXAMINEE},
    Idee.Statut.REALISEE: {Idee.Statut.RETENUE},
    # Fermeture optionnelle depuis n'importe quel statut ACTIF (pas déjà
    # réalisée/fermée — ces deux-là sont terminales).
    Idee.Statut.FERMEE: set(Idee.STATUTS_ACTIFS),
}


class TransitionInvalide(ValueError):
    """Levée quand la transition demandée n'est pas légale depuis le statut
    courant de l'idée."""


def transitionner(idee, *, target, user, note=''):
    """Applique une transition de statut si elle est légale, journalise le
    changement dans le chatter générique (``records.Activity``, ARC8).

    Lève ``TransitionInvalide`` si le statut courant n'autorise pas
    ``target``. ``note`` (optionnelle) est jointe au journal (utilisée par
    l'action ``fermer``, NTIDE5, qui accepte une note de fermeture)."""
    autorises = _TRANSITIONS.get(target)
    if autorises is None or idee.statut not in autorises:
        raise TransitionInvalide(
            f"Transition invalide depuis « {idee.get_statut_display()} » "
            f"vers « {Idee.Statut(target).label} ».")

    old = idee.statut
    idee.statut = target
    idee.save(update_fields=['statut', 'updated_at'])

    from apps.records.models import Activity
    from apps.records.services import log_activity
    log_activity(
        idee, Activity.Kind.MODIFICATION, user=user, field='statut',
        field_label='Statut', old_value=old, new_value=target,
        body=note or '', company=idee.company)
    return idee


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
