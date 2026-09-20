"""CAL205 — commentaires sur un calepinage : la primitive plateforme
``records``, rien d'autre.

``apps.records.models.Comment`` (FG7) est le modèle GÉNÉRIQUE de commentaire
— rattaché à N'IMPORTE quel enregistrement par ``ContentType``, avec
@mentions déjà résolues et notifiées (``apps.records.views._notify_mentions``)
et un suivi (``Follower``) déjà notifié (``apps.records.services.
notify_followers``). ``calepinage.calepinage`` est déjà déclaré cible
(``platform.py`` → ``PLATFORM['record_targets']``) : aucun modèle de
commentaire maison n'est créé ici.

CE QUE CE MODULE AJOUTE, EN PLUS DE LA PRIMITIVE
---------------------------------------------------
Le RESPONSABLE d'un calepinage (son créateur, ``cree_par``) doit être notifié
d'un nouveau commentaire même s'il n'a ni été @mentionné, ni suivi
explicitement le calepinage — un commentaire qui ne notifie que ses
@mentions laisserait le porteur du dossier hors-jeu par défaut. Le nom
affiché est TOUJOURS résolu depuis l'utilisateur agissant (``request.user``),
jamais un prénom codé en dur (CLAUDE.md).

Journaliser/notifier ne fait JAMAIS échouer le dépôt d'un commentaire déjà
réussi (best-effort, avalé et tracé — patron ``services/journal.py``).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = [
    'CommentaireInvalide', 'commentaires_du_calepinage',
    'responsable_du_calepinage', 'deposer_commentaire',
]


class CommentaireInvalide(ValueError):
    """Erreur métier, message français, champ fautif nommé."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def commentaires_du_calepinage(calepinage):
    """Les commentaires d'un calepinage, du plus récent au plus ancien.

    Lecture PURE, générique par ``ContentType`` — jamais un second modèle."""
    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import Comment

    if calepinage is None or not getattr(calepinage, 'pk', None):
        return Comment.objects.none()
    content_type = ContentType.objects.get_for_model(type(calepinage))
    return (Comment.objects
            .filter(content_type=content_type, object_id=calepinage.pk)
            .select_related('author')
            .order_by('-created_at', '-id'))


def responsable_du_calepinage(calepinage):
    """L'utilisateur RESPONSABLE d'un calepinage : son créateur — jamais un
    prénom codé en dur. ``None`` si aucun créateur n'est connu."""
    return getattr(calepinage, 'cree_par', None)


def deposer_commentaire(calepinage, texte, *, user=None):
    """Dépose un commentaire (primitive ``records``) et notifie EN PLUS le
    RESPONSABLE du calepinage — les @mentions et les abonnés sont déjà
    notifiés par la primitive elle-même.

    Raises:
        CommentaireInvalide: calepinage non enregistré, ou corps vide —
            champ nommé dans les deux cas.
    """
    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import Comment
    from apps.records.views import _notify_mentions

    corps = (texte or '').strip()
    if calepinage is None or not getattr(calepinage, 'pk', None):
        raise CommentaireInvalide(
            "Impossible de commenter un calepinage qui n'est pas encore "
            'enregistré.', champ='calepinage')
    if not corps:
        raise CommentaireInvalide('Le commentaire ne peut pas être vide.',
                                  champ='body')

    content_type = ContentType.objects.get_for_model(type(calepinage))
    commentaire = Comment.objects.create(
        company=calepinage.company, content_type=content_type,
        object_id=calepinage.pk, body=corps, author=user)

    try:
        _notify_mentions(corps, user, calepinage.company,
                         content_type=content_type, object_id=calepinage.pk)
    except Exception:  # noqa: BLE001 — une notif ne casse jamais le dépôt
        logger.exception(
            'CAL205 : notification de mention en échec (calepinage %s)',
            calepinage.pk)

    _notifier_responsable(calepinage, commentaire, user=user)
    return commentaire


def _notifier_responsable(calepinage, commentaire, *, user=None):
    """Notifie le RESPONSABLE — best-effort, jamais un prénom en dur."""
    responsable = responsable_du_calepinage(calepinage)
    if responsable is None or responsable == user:
        return
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify

        auteur_nom = getattr(user, 'username', '') or 'Un équipier'
        notify(
            responsable, EventType.CHAT_MENTION,
            f'{auteur_nom} a commenté votre calepinage',
            body=commentaire.body[:200], company=calepinage.company)
    except Exception:  # noqa: BLE001 — une notif ne casse jamais le dépôt
        logger.exception(
            'CAL205 : notification du responsable en échec (calepinage %s)',
            calepinage.pk)
