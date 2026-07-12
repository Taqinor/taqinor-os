"""Récepteurs d'événements métier (M6) — YSUBS5, YSERV2, YSERV10.

Abonne ``sav`` aux événements du cœur métier exposés par ``core.events``, pour
réagir à la résiliation d'un contrat (``apps.contrats``) SANS que ``contrats``
importe ``sav`` ni l'inverse. Câblé au démarrage par ``SavConfig.ready``.

Contient aussi (XSAV24) le récepteur intra-app qui journalise la CRÉATION
d'un ``Ticket`` dans son ``TicketActivity`` (chatter) — quel que soit le
chemin de création (API, WhatsApp, e-mail, tâche planifiée...), pour que
« sans activité depuis N jours » (auto-clôture) ait toujours un point de
départ fiable, jamais la simple date de dernière sauvegarde du ticket.
"""
import logging

from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from core.events import (
    chantier_receptionne, contrat_resilie, devis_accepted,
    intervention_completed,
)
from .models import Ticket

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Ticket, dispatch_uid="sav_log_creation_on_ticket_created")
def _log_creation_on_ticket_created(sender, instance, created, **kwargs):
    """XSAV24 — journalise automatiquement la création d'un ``Ticket`` dans
    son historique (une seule fois, à l'INSERT). Remplace les appels
    explicites équivalents (désormais retirés de ``views.py`` /
    ``services.py`` pour éviter une entrée en double) : TOUT chemin de
    création (API, WhatsApp XSAV26, alias e-mail, visite préventive
    planifiée, etc.) obtient désormais la même trace de création — condition
    dont dépend le sweep d'auto-clôture pour calculer une inactivité fiable
    sur un ticket qui n'a jamais reçu d'autre activité."""
    if not created:
        return
    try:
        from . import activity
        activity.log_creation(instance, getattr(instance, 'created_by', None))
    except Exception:  # pragma: no cover - défensif (best-effort)
        logger.warning(
            'sav: échec journalisation création ticket #%s',
            getattr(instance, 'pk', None), exc_info=True)


@receiver(contrat_resilie, dispatch_uid="sav_deprovision_on_contrat_resilie")
def _deprovisionner_maintenance_on_contrat_resilie(
        sender, contrat_id, company, date_effet, **kwargs):
    """YSUBS5 — à la résiliation d'un contrat, stoppe la facturation
    récurrente et les visites préventives futures du ``ContratMaintenance``
    lié (résolu via ``contrats.selectors.contrat_id_maintenance_lie`` —
    JAMAIS un import du modèle ``contrats``, frontière cross-app).

    Un contrat sans maintenance liée ne déclenche RIEN (no-op silencieux) —
    la très grande majorité des contrats (vente, PPA, garantie...) n'a pas
    de ``ContratMaintenance`` associé. Best-effort : une erreur ne doit
    jamais remonter (la résiliation, côté ``contrats``, est déjà actée)."""
    try:
        from apps.contrats.selectors import contrat_maintenance_lie_id

        maintenance_id = contrat_maintenance_lie_id(company, contrat_id)
        if not maintenance_id:
            return

        from .models import ContratMaintenance

        ContratMaintenance.objects.filter(
            id=maintenance_id, company=company,
        ).update(actif=False, facturation_active=False)
    except Exception:  # pragma: no cover - défensif (best-effort)
        logger.warning(
            'sav: échec de-provisioning maintenance sur résiliation du '
            'contrat #%s', contrat_id, exc_info=True)


@receiver(intervention_completed, dispatch_uid="sav_advance_ticket_on_intervention_completed")
def _avancer_ticket_on_intervention_completed(sender, intervention, company,
                                              user, **kwargs):
    """YSERV2 — quand une Intervention (``apps.installations``) passe à
    TERMINEE/VALIDEE, si elle porte un ticket SAV lié : pose
    ``Ticket.date_resolution`` (si vide) et avance le ticket vers RESOLU —
    JAMAIS en arrière (un ticket déjà RESOLU/CLOTURE, ou annulé, ne bouge
    pas). Idempotent : re-émettre le signal (double clic, retry) ne produit
    aucun second effet — la note chatter n'est posée qu'au changement réel.

    Best-effort : une erreur ici ne doit jamais remonter (l'intervention,
    côté installations, est déjà actée)."""
    try:
        ticket = getattr(intervention, 'ticket', None)
        if ticket is None:
            return
        from . import activity
        from .models import Ticket

        if ticket.statut not in Ticket.OPEN_STATUTS or ticket.annule:
            return  # déjà résolu/clôturé/annulé — ne recule jamais.

        update_fields = []
        if not ticket.date_resolution:
            ticket.date_resolution = timezone.localdate()
            update_fields.append('date_resolution')
        # YSERV12 — une intervention terminée = résolution SUR SITE (jamais
        # écrasé si déjà posé explicitement).
        if not ticket.canal_resolution:
            ticket.canal_resolution = ticket.CanalResolution.SUR_SITE
            update_fields.append('canal_resolution')
        ancien_statut = ticket.statut
        ticket.statut = Ticket.Statut.RESOLU
        update_fields.append('statut')
        ticket.save(update_fields=update_fields)
        activity.log_note(
            ticket, user,
            f"Intervention {intervention.get_type_intervention_display()} "
            'terminée — ticket avancé automatiquement vers Résolu '
            f'(depuis {ancien_statut}).')
        # ARC37 — sav devient émetteur du bus (core.events.ticket_resolu),
        # même point d'émission unique que la transition manuelle gardée
        # (apps/sav/views.py).
        from . import services as sav_services
        sav_services.emettre_ticket_resolu(
            ticket, company=company, user=user, ancien_statut=ancien_statut)
    except Exception:  # pragma: no cover - défensif (best-effort)
        logger.warning(
            'sav: échec avancement ticket sur intervention terminée '
            '#%s', getattr(intervention, 'pk', None), exc_info=True)


@receiver(devis_accepted, dispatch_uid="sav_creer_contrat_on_devis_accepted")
def _creer_contrat_maintenance_on_devis_accepted(sender, devis, user,
                                                 ancien_statut, **kwargs):
    """XCTR1 — quand un devis contenant une ligne récurrente
    (``stock.Produit.est_recurrent``) passe à accepté, crée idempotent le
    ``ContratMaintenance`` correspondant (jamais deux fois pour le même
    devis, y compris si le signal est ré-émis). Un devis sans ligne
    récurrente ne déclenche rien. Best-effort : une erreur ici ne doit
    jamais remonter (l'acceptation, côté ventes, est déjà actée)."""
    try:
        from .services import creer_contrat_depuis_devis_accepte

        creer_contrat_depuis_devis_accepte(devis=devis, user=user)
    except Exception:  # pragma: no cover - défensif (best-effort)
        logger.warning(
            'sav: échec création contrat de maintenance sur devis accepté '
            '#%s', getattr(devis, 'pk', None), exc_info=True)


@receiver(chantier_receptionne, dispatch_uid="sav_proposer_contrat_on_chantier_receptionne")
def _proposer_contrat_maintenance_on_chantier_receptionne(
        sender, installation, user, ancien_statut, **kwargs):
    """YSERV10 — à la réception d'un chantier, si le client n'a AUCUN
    ``ContratMaintenance`` actif (``selectors.client_a_contrat_actif``),
    crée une ``records.Activity`` « Proposer le contrat d'entretien »
    assignée au commercial du chantier (échéance J+14) + une notification
    ``notifications.notify()``. Idempotent : une SEULE activité par
    chantier (marqueur dans ``note``, même pattern que le rappel détracteur
    NPS de ``apps/compta/services.py``). Client déjà sous contrat -> aucun
    effet. Best-effort : une erreur ici ne doit jamais remonter (la
    réception, côté installations, est déjà actée)."""
    try:
        client = getattr(installation, 'client', None)
        if client is None:
            return

        from .selectors import client_a_contrat_actif

        if client_a_contrat_actif(client, installation.company):
            return  # déjà sous contrat — aucune offre à proposer.

        # Commercial responsable : le créateur du devis à l'origine du
        # chantier (fallback : propriétaire du lead lié) — même chemin que
        # les autres relances commerciales de ce dépôt.
        devis = getattr(installation, 'devis', None)
        assigne = getattr(devis, 'created_by', None) if devis else None
        if assigne is None:
            lead = getattr(installation, 'lead', None)
            assigne = getattr(lead, 'owner', None) if lead else None
        if assigne is None:
            return  # aucun destinataire résolvable — pas d'activité orpheline.

        from apps.records.models import Activity, ActivityType

        marque = f'[yserv10:{installation.id}]'
        ct = ContentType.objects.get_for_model(type(client))
        deja = Activity.objects.filter(
            company=installation.company, content_type=ct,
            object_id=client.id, note__contains=marque).exists()
        if deja:
            return

        atype = ActivityType.objects.filter(
            company=installation.company, nom='Appel').first()
        if atype is None:
            atype = ActivityType.objects.create(
                company=installation.company, nom='Appel', ordre=10)

        Activity.objects.create(
            company=installation.company, content_type=ct,
            object_id=client.id, activity_type=atype,
            summary="Proposer le contrat d'entretien"[:255],
            due_date=timezone.localdate() + timezone.timedelta(days=14),
            assigned_to=assigne,
            note=f'{marque} Chantier réceptionné sans contrat de '
                 "maintenance actif — proposer un contrat d'entretien.",
            created_by=None,
        )

        from apps.notifications.services import notify
        from apps.notifications.models import EventType

        notify(
            assigne, EventType.SAV_ACTIVITE_DUE,
            "Proposer un contrat d'entretien",
            body=(f'Le chantier #{installation.id} a été réceptionné sans '
                  'contrat de maintenance actif.'),
            link='/crm/clients',
            company=installation.company,
        )
    except Exception:  # pragma: no cover - défensif (best-effort)
        logger.warning(
            'sav: échec offre auto de contrat entretien sur chantier '
            'réceptionné #%s', getattr(installation, 'pk', None),
            exc_info=True)
