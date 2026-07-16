"""Services ÉCRITURE du vertical BTP/EPC (Groupe NTCON).

Toute mutation d'état (transition de statut, capture de signature,
génération de facture / impact budget, verrouillage DGD…) passe par ce
module — jamais une écriture directe depuis la vue. Les écritures cross-app
(facture ``ventes``, notification) passent par les ``services.py``/
``notify()`` de l'app CIBLE via import FONCTION-LOCAL, jamais un import de
modèle d'une autre app.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .models import ReserveChantier, ReserveChantierHistorique


class TransitionInvalide(ValueError):
    """Transition de statut illégale (état → état non autorisé)."""


def _notifier_btp(user, event_type_name, titre, corps, *, company=None, link=None):
    """Notification best-effort via ``apps.notifications`` (jamais d'exception).

    ``event_type_name`` est le nom d'un membre EXISTANT de ``EventType``
    (registre fermé — ``apps/notifications`` est hors périmètre d'édition de
    ce lot). On réutilise l'événement le plus proche sémantiquement, comme
    ``qhse.services._notifier_capa`` réutilise ``MAINTENANCE_DUE`` pour les
    relances CAPA — précédent déjà établi dans ce dépôt.
    """
    if user is None:
        return None
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify
        event_type = getattr(EventType, event_type_name, None)
        if event_type is None:
            return None
        return notify(
            user, event_type, titre, body=corps, link=link,
            company=company or getattr(user, 'company', None))
    except Exception:  # pragma: no cover - défensif, best-effort
        return None


@transaction.atomic
def _transitionner_reserve(reserve, nouveau_statut, *, auteur, motif=''):
    """Change le statut d'une réserve et journalise la transition (NTCON2)."""
    ancien = reserve.statut
    reserve.statut = nouveau_statut
    reserve.save(update_fields=['statut', 'updated_at'])
    ReserveChantierHistorique.objects.create(
        company=reserve.company, reserve=reserve,
        ancien_statut=ancien, nouveau_statut=nouveau_statut,
        motif=motif, auteur=auteur)
    return reserve


def enregistrer_creation_reserve(reserve, *, created_by):
    """NTCON1 — journalise la création + notifie le responsable si la
    gravité est bloquante (appelé depuis ``ReserveChantierViewSet.perform_
    create`` juste après ``serializer.save()``)."""
    ReserveChantierHistorique.objects.create(
        company=reserve.company, reserve=reserve, ancien_statut='',
        nouveau_statut=reserve.statut, auteur=created_by)
    if (reserve.gravite == ReserveChantier.Gravite.BLOQUANTE
            and reserve.responsable_leve_id):
        _notifier_btp(
            reserve.responsable_leve, 'APPROVAL_REQUESTED',
            'Réserve bloquante à lever',
            f'Réserve #{reserve.id} ({reserve.lot or "chantier"}) requiert '
            'une action.', company=reserve.company,
            link=f'/btp/reserves/{reserve.id}')
    return reserve


def lever_reserve(reserve, *, user, signature_nom, ip_adresse='', user_agent=''):
    """NTCON2 — lève une réserve : capture la signature typée du constatant,
    horodate/attribue serveur, journalise, notifie le créateur.

    Lève ``TransitionInvalide`` si la réserve n'est pas dans un état levable
    (``ouverte``/``en_cours``/``contestee``). L'APPEL doit avoir DÉJÀ vérifié
    qu'une photo « après » existe (garde côté vue — 400 sans photo).
    """
    from .models import SignatureBtp

    if reserve.statut not in (
            ReserveChantier.Statut.OUVERTE, ReserveChantier.Statut.EN_COURS,
            ReserveChantier.Statut.CONTESTEE):
        raise TransitionInvalide(
            f'Réserve {reserve.pk} : impossible de lever depuis « '
            f'{reserve.statut} ».')

    with transaction.atomic():
        from django.contrib.contenttypes.models import ContentType
        signature = SignatureBtp.objects.create(
            company=reserve.company,
            content_type=ContentType.objects.get_for_model(ReserveChantier),
            object_id=reserve.pk,
            contexte='levee_reserve',
            signataire_nom=signature_nom,
            signataire=user,
            ip_adresse=ip_adresse,
            user_agent=user_agent,
        )
        reserve.date_levee = timezone.now()
        reserve.leve_par = user
        reserve.save(update_fields=['date_levee', 'leve_par', 'updated_at'])
        _transitionner_reserve(
            reserve, ReserveChantier.Statut.LEVEE, auteur=user)

    if reserve.created_by_id and reserve.created_by_id != getattr(user, 'id', None):
        _notifier_btp(
            reserve.created_by, 'APPROVAL_DECIDED', 'Réserve levée',
            f'Réserve #{reserve.id} a été levée par {user}.',
            company=reserve.company, link=f'/btp/reserves/{reserve.id}')
    return signature


def contester_reserve(reserve, *, user, motif):
    """NTCON2 — réouvre une réserve « levée » (contestée + motif). Lève
    ``TransitionInvalide`` si la réserve n'est pas levée."""
    if reserve.statut != ReserveChantier.Statut.LEVEE:
        raise TransitionInvalide(
            f'Réserve {reserve.pk} : seule une réserve levée peut être '
            'contestée.')
    reserve.motif_contestation = motif
    reserve.save(update_fields=['motif_contestation', 'updated_at'])
    _transitionner_reserve(
        reserve, ReserveChantier.Statut.CONTESTEE, auteur=user, motif=motif)
    return reserve
