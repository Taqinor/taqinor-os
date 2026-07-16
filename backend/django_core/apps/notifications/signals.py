"""Producteurs d'évènements pour le moteur de notifications (ERR50).

Avant : ``notify()`` n'était appelé que par les digests planifiés et les tests —
le moteur était inerte pour les évènements métier. On câble ici les producteurs
DEPUIS l'app notifications (en miroir de ``apps/publicapi/signals.py``), sans
jamais éditer crm/ventes/sav/automation/compta : on connecte simplement des
récepteurs à leurs ``pre_save``/``post_save``.

Producteurs câblés :
- ``LEAD_ASSIGNED``    : quand le ``owner`` d'un Lead passe à un utilisateur
  (création avec owner, ou réassignation).
- ``DEVIS_ACCEPTED``   : quand un Devis passe au statut « accepté » (transition).
- ``SAV_TICKET_OPENED`` (YEVNT4) : à la CRÉATION d'un ``sav.Ticket``.
- ``APPROVAL_REQUESTED``/``APPROVAL_DECIDED`` (YEVNT8) : sur
  ``automation.AutomationApproval`` (création → approbateur ; décision →
  demandeur) ET ``compta.DemandeApprobationConfig`` (même paire).
- ``APPROVAL_REQUESTED``/``APPROVAL_DECIDED`` (VX99) : étend le câblage YEVNT8
  aux 2 sources restantes de l'agrégateur ``reporting/approbations.py`` qui
  passent par un ``save()`` ordinaire : ``installations.DemandeAchat``
  (brouillon→soumise → managers ; décision approuvée/refusée →
  ``created_by``) et ``ged.DemandeApprobation`` (création en_attente →
  l'``approbateur`` désigné s'il existe, sinon les managers ; décision →
  ``demandeur``). La 3e source de l'agrégateur, ``contrats.EtapeApprobation``,
  est créée via ``bulk_create()`` dans ``lancer_workflow_approbation`` —
  ``bulk_create`` n'émet JAMAIS de signal ``post_save`` (aucun paramètre ne
  l'active), donc sa notification de CRÉATION ne peut pas être câblée depuis
  ce seul fichier (voir le ``[BLOCKED]`` laissé sur cette sous-tâche).

Tout est best-effort : ``notify()`` isole déjà ses propres exceptions, et les
récepteurs en rajoutent une couche pour ne JAMAIS bloquer le save d'origine.

``FACTURE_OVERDUE`` est temporel (pas une transition de save) ; il est émis par
le balayage quotidien (``sweeps.py``), pas par un signal de save.
"""
import logging

from django.db.models.signals import post_save, pre_save

from .models import EventType
from .services import notify

logger = logging.getLogger(__name__)

_OLD_OWNER_ATTR = '_notif_old_owner_id'
_OLD_STATUT_ATTR = '_notif_old_statut'
_OLD_DEMANDE_STATUT_ATTR = '_notif_old_demande_statut'
_OLD_DA_STATUT_ATTR = '_notif_old_da_statut'
_OLD_GED_DEMANDE_STATUT_ATTR = '_notif_old_ged_demande_statut'


# ── Lead → LEAD_ASSIGNED ─────────────────────────────────────────────────────
def lead_pre_save(sender, instance, **kwargs):
    old = None
    if instance.pk:
        try:
            old = sender.objects.filter(pk=instance.pk).values_list(
                'owner_id', flat=True).first()
        except Exception:  # noqa: BLE001
            old = None
    setattr(instance, _OLD_OWNER_ATTR, old)


def lead_post_save(sender, instance, created, **kwargs):
    old_owner = getattr(instance, _OLD_OWNER_ATTR, None)
    new_owner = instance.owner_id
    if not new_owner or new_owner == old_owner:
        return
    try:
        ville = getattr(instance, 'ville', '') or ''
        notify(
            user=instance.owner,
            event_type=EventType.LEAD_ASSIGNED,
            title='Nouveau lead assigné',
            body=(instance.nom or '') + (f' — {ville}' if ville else ''),
            link=f'/leads/{instance.pk}',
            reason='assigne_a_vous',  # VX212(a)
        )
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.exception('notify LEAD_ASSIGNED failed (lead %s)', instance.pk)


# ── Devis → DEVIS_ACCEPTED ───────────────────────────────────────────────────
def devis_pre_save(sender, instance, **kwargs):
    old = None
    if instance.pk:
        try:
            old = sender.objects.filter(pk=instance.pk).values_list(
                'statut', flat=True).first()
        except Exception:  # noqa: BLE001
            old = None
    setattr(instance, _OLD_STATUT_ATTR, old)


def devis_post_save(sender, instance, created, **kwargs):
    from apps.ventes.models import Devis
    old = getattr(instance, _OLD_STATUT_ATTR, None)
    if instance.statut != Devis.Statut.ACCEPTE or old == Devis.Statut.ACCEPTE:
        return
    recipient = getattr(instance, 'created_by', None)
    if recipient is None:
        return
    try:
        notify(
            user=recipient,
            event_type=EventType.DEVIS_ACCEPTED,
            title='Devis accepté',
            body=f'Le devis {instance.reference} a été accepté.',
            # QX12be — deep-link qui ATTERRIT : /devis/<pk> n'existe pas côté
            # front ; DevisList consomme le param ?devis=<pk>.
            link=f'/ventes/devis?devis={instance.pk}',
        )
    except Exception:  # noqa: BLE001
        logger.exception('notify DEVIS_ACCEPTED failed (devis %s)', instance.pk)


# ── Devis → DEVIS_EXPIRED (YEVNT2) ──────────────────────────────────────────
# Contrairement aux autres producteurs de ce module (qui diffent pre/post_save
# sur le modèle), YEVNT2 s'abonne DIRECTEMENT à ``core.events.devis_expired`` —
# le signal domain-event posé par ``ventes.services.expire_stale_devis``
# (M6) : plus simple ici (le sweep ne pose l'événement QU'à la transition
# réelle envoyé→expiré, donc aucune diffing pre/post_save n'est nécessaire).
def devis_expired_receiver(sender, devis, ancien_statut, **kwargs):
    recipient = getattr(devis, 'created_by', None)
    if recipient is None:
        return
    try:
        notify(
            user=recipient,
            event_type=EventType.DEVIS_EXPIRED,
            title='Devis expiré',
            body=(f'Le devis {devis.reference} a expiré automatiquement '
                  '(date de validité dépassée). Pensez à relancer le client.'),
            # QX12be — deep-link qui atterrit (voir devis_post_save).
            link=f'/ventes/devis?devis={devis.pk}',
        )
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.exception('notify DEVIS_EXPIRED failed (devis %s)', devis.pk)


# ── Facture soldée → FACTURE_PAYEE (ARC36) ───────────────────────────────────
# S'abonne à ``core.events.facture_payee`` (YEVNT6 — émis SYNCHRONE au passage
# résiduel→0, tous chemins d'encaissement confondus) pour notifier le VENDEUR
# (créateur de la facture, repli créateur du devis lié). Le signal frère
# ``facture_paid`` (YDOCF4) porte le même fait métier — il est DÉPRÉCIÉ pour
# l'abonnement (documenté dans la docstring du bus) : on n'écoute que
# ``facture_payee`` pour ne jamais notifier deux fois.
def facture_payee_receiver(sender, instance, company, **kwargs):
    recipient = getattr(instance, 'created_by', None)
    if recipient is None:
        devis = getattr(instance, 'devis', None)
        recipient = getattr(devis, 'created_by', None)
    if recipient is None:
        return
    try:
        notify(
            user=recipient,
            event_type=EventType.FACTURE_PAYEE,
            title='Facture intégralement réglée',
            body=(f'La facture {instance.reference} est intégralement '
                  'réglée.'),
            link=f'/factures/{instance.pk}',
            company=company,
        )
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.exception(
            'notify FACTURE_PAYEE failed (facture %s)', instance.pk)


# ── Bon de commande créé → BON_COMMANDE_CREE (ARC36) ────────────────────────
# S'abonne à ``core.events.bon_commande_cree`` (YEVNT6 — émis à la conversion
# d'un devis accepté en BC). Notifie le « magasinier » : il n'existe pas de
# rôle legacy dédié — la résolution passe par ``resolve_recipients`` (FG4) :
# une ``NotificationRoutingRule`` route l'événement vers l'utilisateur/rôle
# entrepôt ; sans règle, repli managers (admin/responsable), comme les autres
# événements routables.
def bon_commande_cree_receiver(sender, instance, company, **kwargs):
    try:
        from .services import (
            notify_many, resolve_recipients, resolve_recipients_reason,
        )
        recipients = resolve_recipients(company, EventType.BON_COMMANDE_CREE)
        # VX212(a) — « pourquoi je reçois ça » : règle de routage explicite,
        # ou repli manager historique.
        reason = resolve_recipients_reason(company, EventType.BON_COMMANDE_CREE)
        notify_many(
            recipients, EventType.BON_COMMANDE_CREE,
            'Bon de commande créé',
            body=(f'Le bon de commande {instance.reference} a été créé — '
                  'matériel à préparer.'),
            link=f'/bons-commande/{instance.pk}',
            company=company,
            reason=reason,
        )
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.exception(
            'notify BON_COMMANDE_CREE failed (bc %s)', instance.pk)


# ── Ticket SAV résolu → SAV_TICKET_RESOLU (ARC37) ───────────────────────────
# S'abonne à ``core.events.ticket_resolu`` (nouveau signal, sav devient
# émetteur du bus). Notifie le technicien assigné, repli managers.
def ticket_resolu_receiver(sender, ticket, company, user, ancien_statut,
                           **kwargs):
    try:
        from .sweeps import _notify_user_or_managers
        technicien = getattr(ticket, 'technicien_responsable', None)
        _notify_user_or_managers(
            technicien, company, EventType.SAV_TICKET_RESOLU,
            'Ticket SAV résolu',
            body=f'Le ticket {ticket.reference} est passé à Résolu.',
            link=f'/sav/tickets/{ticket.pk}',
        )
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.exception(
            'notify SAV_TICKET_RESOLU failed (ticket %s)', ticket.pk)


# ── Équipement SAV remplacé → SAV_EQUIPEMENT_REMPLACE (ARC37) ──────────────
# S'abonne à ``core.events.equipement_remplace`` (nouveau signal, sav devient
# émetteur du bus). Notifie les managers de la société (pas d'owner dédié sur
# un équipement du parc).
def equipement_remplace_receiver(sender, equipement, ticket, company, user,
                                 **kwargs):
    try:
        from .sweeps import _managers
        numero = getattr(equipement, 'numero_serie', '') or f'#{equipement.pk}'
        for mgr in _managers(company):
            notify(
                mgr, EventType.SAV_EQUIPEMENT_REMPLACE,
                'Équipement SAV remplacé',
                body=(f'Équipement {numero} remplacé (ticket '
                      f'{getattr(ticket, "reference", ticket.pk)}).'),
                link=f'/sav/tickets/{ticket.pk}',
                company=company,
            )
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.exception(
            'notify SAV_EQUIPEMENT_REMPLACE failed (equipement %s)',
            getattr(equipement, 'pk', '?'))


# ── Projet — changement de statut → PROJET_STATUT_CHANGE (ARC37) ───────────
# S'abonne à ``core.events.projet_status_change`` (nouveau signal,
# gestion_projet devient émetteur du bus, en plus du chemin EXISTANT vers le
# moteur automation qui reste inchangé). Notifie le responsable du projet.
def projet_status_change_receiver(sender, projet, company, user,
                                  ancien_statut, nouveau_statut, **kwargs):
    responsable = getattr(projet, 'responsable', None)
    if responsable is None:
        return
    try:
        notify(
            responsable, EventType.PROJET_STATUT_CHANGE,
            'Statut de projet modifié',
            body=(f'Le projet {projet.nom} est passé de {ancien_statut} à '
                  f'{nouveau_statut}.'),
            link=f'/gestion-projet/projets/{projet.pk}',
            company=company,
        )
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.exception(
            'notify PROJET_STATUT_CHANGE failed (projet %s)',
            getattr(projet, 'pk', '?'))


# ── SAV Ticket → SAV_TICKET_OPENED (YEVNT4) ─────────────────────────────────
def sav_ticket_post_save(sender, instance, created, **kwargs):
    """À la CRÉATION d'un ticket SAV → notifie le technicien assigné, sinon
    les managers de la société. Best-effort, ne casse jamais la création."""
    if not created:
        return
    try:
        from .sweeps import _notify_user_or_managers
        company = getattr(instance, 'company', None)
        technicien = getattr(instance, 'technicien_responsable', None)
        client_nom = ''
        try:
            client_nom = getattr(instance.client, 'nom', '') or ''
        except Exception:  # noqa: BLE001
            client_nom = ''
        title = 'Ticket SAV ouvert'
        body = (
            f"Le ticket SAV « {instance.reference} » "
            + (f'({client_nom}) ' if client_nom else '')
            + f'a été ouvert (priorité : {instance.get_priorite_display()}).'
        )
        link = f'/sav/tickets/{instance.pk}'
        # `_notify_user_or_managers` retombe déjà sur les managers si
        # `technicien` est None — un seul appel couvre les deux cas.
        _notify_user_or_managers(
            technicien, company, EventType.SAV_TICKET_OPENED, title, body, link)
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.exception(
            'notify SAV_TICKET_OPENED failed (ticket %s)', instance.pk)


# ── automation.AutomationApproval → APPROVAL_REQUESTED / APPROVAL_DECIDED ───
# (YEVNT8)

def automation_approval_pre_save(sender, instance, **kwargs):
    old = None
    if instance.pk:
        try:
            old = sender.objects.filter(pk=instance.pk).values_list(
                'status', flat=True).first()
        except Exception:  # noqa: BLE001
            old = None
    setattr(instance, _OLD_STATUT_ATTR, old)


def automation_approval_post_save(sender, instance, created, **kwargs):
    from apps.automation.models import AutomationApproval
    try:
        from .sweeps import _managers
        company = instance.company
        link = f'/automation/approvals/{instance.pk}'
        if created:
            title = "Approbation demandée"
            body = instance.description or 'Une action attend votre approbation.'
            for approver in _managers(company):
                notify(
                    approver, EventType.APPROVAL_REQUESTED, title, body=body,
                    link=link, company=company, reason='manager')
            return

        old = getattr(instance, _OLD_STATUT_ATTR, None)
        if instance.status == old or instance.status == AutomationApproval.Status.PENDING:
            return  # pas une décision (toujours en attente, ou pas de transition).
        requester = getattr(instance, 'requested_by', None)
        if requester is None:
            return
        decided_label = (
            'approuvée' if instance.status == AutomationApproval.Status.APPROVED
            else 'rejetée')
        body = f'{instance.description or "Votre demande"} a été {decided_label}.'
        notify(
            requester, EventType.APPROVAL_DECIDED, 'Approbation décidée',
            body=body, link=link, company=company)
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.exception(
            'notify APPROVAL_* failed (automation approval %s)', instance.pk)


# ── compta.DemandeApprobationConfig → APPROVAL_REQUESTED / APPROVAL_DECIDED ─
# (YEVNT8)

def demande_approbation_pre_save(sender, instance, **kwargs):
    old = None
    if instance.pk:
        try:
            old = sender.objects.filter(pk=instance.pk).values_list(
                'statut', flat=True).first()
        except Exception:  # noqa: BLE001
            old = None
    setattr(instance, _OLD_DEMANDE_STATUT_ATTR, old)


def demande_approbation_post_save(sender, instance, created, **kwargs):
    from apps.compta.models import DemandeApprobationConfig
    try:
        from .sweeps import _managers
        company = instance.company
        link = f'/compta/approbations/{instance.pk}'
        label = instance.devis_reference or instance.devis_id or ''
        if created:
            title = "Approbation demandée"
            body = f'Composition non-standard à valider ({label}) : {instance.motif}'
            for approver in _managers(company):
                notify(
                    approver, EventType.APPROVAL_REQUESTED, title, body=body,
                    link=link, company=company, reason='manager')
            return

        old = getattr(instance, _OLD_DEMANDE_STATUT_ATTR, None)
        if (instance.statut == old
                or instance.statut == DemandeApprobationConfig.Statut.EN_ATTENTE):
            return  # pas une décision.
        requester = getattr(instance, 'demandeur', None)
        if requester is None:
            return
        decided_label = (
            'approuvée'
            if instance.statut == DemandeApprobationConfig.Statut.APPROUVEE
            else 'refusée')
        body = f'Votre demande ({label}) a été {decided_label}.'
        if instance.commentaire_decision:
            body += f' Motif : {instance.commentaire_decision}'
        notify(
            requester, EventType.APPROVAL_DECIDED, 'Approbation décidée',
            body=body, link=link, company=company)
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.exception(
            'notify APPROVAL_* failed (demande approbation %s)', instance.pk)


# ── installations.DemandeAchat → APPROVAL_REQUESTED / APPROVAL_DECIDED ──────
# (VX99 — 2e des 3 sources muettes de l'agrégateur reporting/approbations.py)
#
# ``DemandeAchat`` passe brouillon → SOUMISE via un ``save(update_fields=…)``
# ordinaire (``DemandeAchatViewSet.soumettre`` / la vue reste inchangée) : le
# ``post_save`` observe donc la transition normalement, contrairement à
# ``contrats.EtapeApprobation`` (bulk_create, cf. docstring de tête). La
# demande n'a pas d'approbateur dédié (rôle responsable/admin, cf. FG310) :
# on notifie les managers, comme pour ``AutomationApproval``/
# ``DemandeApprobationConfig``. La décision (approuvée/refusée) notifie
# ``created_by``.
def demande_achat_pre_save(sender, instance, **kwargs):
    old = None
    if instance.pk:
        try:
            old = sender.objects.filter(pk=instance.pk).values_list(
                'statut', flat=True).first()
        except Exception:  # noqa: BLE001
            old = None
    setattr(instance, _OLD_DA_STATUT_ATTR, old)


def demande_achat_post_save(sender, instance, created, **kwargs):
    from apps.installations.models import DemandeAchat
    try:
        from .sweeps import _managers
        old = getattr(instance, _OLD_DA_STATUT_ATTR, None)
        company = instance.company
        link = f'/installations/demandes-achat/{instance.pk}'

        if instance.statut == DemandeAchat.Statut.SOUMISE and old != instance.statut:
            title = 'Réquisition à approuver'
            # VX212(b) — contexte décisionnel dans le corps (email ET in-app) :
            # montant estimé (client-safe, `montant_estime`, JAMAIS
            # `prix_achat`) + objet — pour ne plus approuver « à l'aveugle »
            # depuis l'email seul (jamais de bouton « Approuver » par lien
            # email — pas de mutation non-authentifiée).
            montant = instance.montant_estime
            body = (
                f'La réquisition {instance.reference} attend votre '
                f'approbation.\nMontant estimé : {montant} DH.\n'
                f'Objet : {instance.objet}')
            for approver in _managers(company):
                notify(
                    approver, EventType.APPROVAL_REQUESTED, title, body=body,
                    link=link, company=company, reason='manager')
            return

        if old == instance.statut or old is None:
            return
        if instance.statut not in (
                DemandeAchat.Statut.APPROUVEE, DemandeAchat.Statut.REFUSEE):
            return
        requester = getattr(instance, 'created_by', None)
        if requester is None:
            return
        decided_label = (
            'approuvée' if instance.statut == DemandeAchat.Statut.APPROUVEE
            else 'refusée')
        body = f'Votre réquisition {instance.reference} a été {decided_label}.'
        if instance.statut == DemandeAchat.Statut.REFUSEE and instance.motif_refus:
            body += f' Motif : {instance.motif_refus}'
        notify(
            requester, EventType.APPROVAL_DECIDED, 'Approbation décidée',
            body=body, link=link, company=company)
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.exception(
            'notify APPROVAL_* failed (demande achat %s)', instance.pk)


# ── ged.DemandeApprobation → APPROVAL_REQUESTED / APPROVAL_DECIDED ─────────
# (VX99 — 3e des 3 sources muettes de l'agrégateur reporting/approbations.py)
#
# Créée par ``demander_revue``/``request_review(_avec_routage)`` via un
# ``save()`` ordinaire (jamais de bulk_create ici) : le ``post_save`` observe
# la création normalement. ``approbateur`` peut être posé dès la création
# (choix manuel ou routage XGED20) — s'il existe, on le notifie directement ;
# sinon repli managers (même patron que les autres producteurs de ce module).
# La décision (approuve/rejete, ``approve_demande``/``reject_demande``)
# notifie le ``demandeur``.
def ged_demande_approbation_pre_save(sender, instance, **kwargs):
    old = None
    if instance.pk:
        try:
            old = sender.objects.filter(pk=instance.pk).values_list(
                'statut', flat=True).first()
        except Exception:  # noqa: BLE001
            old = None
    setattr(instance, _OLD_GED_DEMANDE_STATUT_ATTR, old)


def ged_demande_approbation_post_save(sender, instance, created, **kwargs):
    from apps.ged.models import APPROBATION_APPROUVE, APPROBATION_EN_ATTENTE
    try:
        from .sweeps import _managers, _notify_user_or_managers
        company = instance.company
        doc_label = getattr(instance.document, 'nom', None) or instance.document_id
        link = f'/ged/documents/{instance.document_id}'

        if created:
            title = 'Approbation demandée'
            body = f'Une revue est demandée sur le document « {doc_label} ».'
            approbateur = getattr(instance, 'approbateur', None)
            if approbateur is not None:
                notify(
                    approbateur, EventType.APPROVAL_REQUESTED, title,
                    body=body, link=link, company=company,
                    reason='assigne_a_vous')
            else:
                for approver in _managers(company):
                    notify(
                        approver, EventType.APPROVAL_REQUESTED, title,
                        body=body, link=link, company=company,
                        reason='manager')
            return

        old = getattr(instance, _OLD_GED_DEMANDE_STATUT_ATTR, None)
        if instance.statut == old or instance.statut == APPROBATION_EN_ATTENTE:
            return  # pas une décision.
        requester = getattr(instance, 'demandeur', None)
        decided_label = (
            'approuvée' if instance.statut == APPROBATION_APPROUVE
            else 'rejetée')
        body = f'Votre demande de revue ({doc_label}) a été {decided_label}.'
        if instance.commentaire:
            body += f' Commentaire : {instance.commentaire}'
        _notify_user_or_managers(
            requester, company, EventType.APPROVAL_DECIDED,
            'Approbation décidée', body, link)
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.exception(
            'notify APPROVAL_* failed (ged demande approbation %s)',
            instance.pk)


# ── Contrat signé → CONTRAT_SIGNE (ARC35) ────────────────────────────────────
# S'abonne à ``core.events.contrat_signe`` (YDOCF5 — seam posé par
# CONTRAT16/17, jusqu'ici SANS abonné, catalogué ``ALLOWED_UNCONSUMED``).
# Notifie l'utilisateur qui a agi à la signature (``user``), sinon les
# managers de la société (même repli que les autres producteurs de ce module).
def contrat_signe_receiver(sender, contrat, user, company, **kwargs):
    try:
        from .sweeps import _notify_user_or_managers

        ref = (contrat.reference or '').strip() or f'#{contrat.pk}'
        _notify_user_or_managers(
            user, company, EventType.CONTRAT_SIGNE,
            'Contrat signé',
            body=f'Le contrat {ref} a été intégralement signé.',
            link=f'/contrats/{contrat.pk}',
        )
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.exception(
            'notify CONTRAT_SIGNE failed (contrat %s)', getattr(contrat, 'pk', '?'))


def connect():
    """Branche les récepteurs. Appelé depuis ``AppConfig.ready()``."""
    from apps.automation.models import AutomationApproval
    from apps.compta.models import DemandeApprobationConfig
    from apps.crm.models import Lead
    from apps.ged.models import DemandeApprobation as GedDemandeApprobation
    from apps.installations.models import DemandeAchat
    from apps.sav.models import Ticket
    from apps.ventes.models import Devis
    from core.events import (
        bon_commande_cree, contrat_signe, devis_expired, equipement_remplace,
        facture_payee, projet_status_change, ticket_resolu,
    )

    pre_save.connect(lead_pre_save, sender=Lead,
                     dispatch_uid='notifications_lead_pre')
    post_save.connect(lead_post_save, sender=Lead,
                      dispatch_uid='notifications_lead_assigned')
    pre_save.connect(devis_pre_save, sender=Devis,
                     dispatch_uid='notifications_devis_pre')
    post_save.connect(devis_post_save, sender=Devis,
                      dispatch_uid='notifications_devis_accepted')
    devis_expired.connect(devis_expired_receiver,
                          dispatch_uid='notifications_devis_expired')
    # ARC36 — événements documentaires YEVNT6 désormais consommés.
    facture_payee.connect(facture_payee_receiver,
                          dispatch_uid='notifications_facture_payee')
    bon_commande_cree.connect(bon_commande_cree_receiver,
                              dispatch_uid='notifications_bon_commande_cree')
    contrat_signe.connect(contrat_signe_receiver,
                          dispatch_uid='notifications_contrat_signe')
    ticket_resolu.connect(ticket_resolu_receiver,
                          dispatch_uid='notifications_ticket_resolu')
    equipement_remplace.connect(
        equipement_remplace_receiver,
        dispatch_uid='notifications_equipement_remplace')
    projet_status_change.connect(
        projet_status_change_receiver,
        dispatch_uid='notifications_projet_status_change')
    post_save.connect(sav_ticket_post_save, sender=Ticket,
                      dispatch_uid='notifications_sav_ticket_opened')
    pre_save.connect(automation_approval_pre_save, sender=AutomationApproval,
                     dispatch_uid='notifications_automation_approval_pre')
    post_save.connect(
        automation_approval_post_save, sender=AutomationApproval,
        dispatch_uid='notifications_automation_approval_events')
    pre_save.connect(
        demande_approbation_pre_save, sender=DemandeApprobationConfig,
        dispatch_uid='notifications_demande_approbation_pre')
    post_save.connect(
        demande_approbation_post_save, sender=DemandeApprobationConfig,
        dispatch_uid='notifications_demande_approbation_events')
    # VX99 — installations.DemandeAchat et ged.DemandeApprobation, les 2
    # sources de l'agrégateur reporting/approbations.py qui passent par un
    # save() ordinaire (contrats.EtapeApprobation reste [BLOCKED], bulk_create).
    pre_save.connect(
        demande_achat_pre_save, sender=DemandeAchat,
        dispatch_uid='notifications_demande_achat_pre')
    post_save.connect(
        demande_achat_post_save, sender=DemandeAchat,
        dispatch_uid='notifications_demande_achat_events')
    pre_save.connect(
        ged_demande_approbation_pre_save, sender=GedDemandeApprobation,
        dispatch_uid='notifications_ged_demande_approbation_pre')
    post_save.connect(
        ged_demande_approbation_post_save, sender=GedDemandeApprobation,
        dispatch_uid='notifications_ged_demande_approbation_events')
