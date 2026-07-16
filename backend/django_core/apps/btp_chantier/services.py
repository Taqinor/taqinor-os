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


# ── NTCON3 — RFI ─────────────────────────────────────────────────────────────

def _prochain_numero_rfi(chantier):
    """Numéro de RFI SUIVANT pour ce chantier (jamais ``count()+1``).

    Verrouille la ligne ``chantier`` (``select_for_update``) le temps du
    calcul pour sérialiser des créations concurrentes sur le MÊME chantier,
    puis prend le plus haut ``numero`` déjà UTILISÉ + 1 — pattern
    ``gestion_projet.services.prochain_numero_situation``. Doit être appelé
    dans une transaction atomique par l'appelant.
    """
    from django.db.models import Max

    from .models import RFI

    chantier.__class__.objects.select_for_update().get(pk=chantier.pk)
    plus_haut = RFI.objects.filter(
        chantier=chantier).aggregate(Max('numero'))['numero__max'] or 0
    return plus_haut + 1


@transaction.atomic
def creer_rfi(*, company, chantier, pose_par, delai_jours=5, **kwargs):
    """NTCON3 — crée un RFI, numéro race-safe par chantier + échéance en
    jours OUVRÉS (férié-aware, ``notifications.calendar_utils``). Notifie le
    destinataire (best-effort)."""
    from apps.notifications.calendar_utils import ajouter_jours_ouvres

    from .models import RFI

    numero = _prochain_numero_rfi(chantier)
    date_limite = ajouter_jours_ouvres(
        timezone.localdate(), delai_jours, company)
    rfi = RFI.objects.create(
        company=company, chantier=chantier, numero=numero,
        pose_par=pose_par, delai_jours=delai_jours,
        date_limite_reponse=date_limite, **kwargs)
    if rfi.destinataire_user_id:
        _notifier_btp(
            rfi.destinataire_user, 'APPROVAL_REQUESTED',
            f'RFI #{rfi.numero} en attente de réponse', rfi.question[:200],
            company=company, link=f'/btp/rfi/{rfi.id}')
    return rfi


def repondre_rfi(rfi, *, auteur, texte):
    """NTCON3 — ajoute une réponse et clôt le cycle (statut → repondu)."""
    from .models import RFI, RFIReponse

    if rfi.statut == RFI.Statut.CLOS:
        raise TransitionInvalide(f'RFI {rfi.pk} : déjà clos.')
    with transaction.atomic():
        reponse = RFIReponse.objects.create(
            company=rfi.company, rfi=rfi, texte=texte, auteur=auteur)
        rfi.statut = RFI.Statut.REPONDU
        rfi.save(update_fields=['statut'])
    if rfi.pose_par_id and rfi.pose_par_id != getattr(auteur, 'id', None):
        _notifier_btp(
            rfi.pose_par, 'APPROVAL_DECIDED', f'RFI #{rfi.numero} répondu',
            texte[:200], company=rfi.company, link=f'/btp/rfi/{rfi.id}')
    return reponse


def clore_rfi(rfi, *, user):
    """NTCON3 — clôt un RFI répondu (ou directement ouvert, sans réponse)."""
    from .models import RFI

    if rfi.statut == RFI.Statut.CLOS:
        raise TransitionInvalide(f'RFI {rfi.pk} : déjà clos.')
    rfi.statut = RFI.Statut.CLOS
    rfi.save(update_fields=['statut'])
    return rfi
