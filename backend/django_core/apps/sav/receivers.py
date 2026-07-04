"""Récepteurs d'événements métier (M6) — YSUBS5, YSERV2.

Abonne ``sav`` aux événements du cœur métier exposés par ``core.events``, pour
réagir à la résiliation d'un contrat (``apps.contrats``) SANS que ``contrats``
importe ``sav`` ni l'inverse. Câblé au démarrage par ``SavConfig.ready``.
"""
import logging

from django.dispatch import receiver
from django.utils import timezone

from core.events import contrat_resilie, intervention_completed

logger = logging.getLogger(__name__)


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
    except Exception:  # pragma: no cover - défensif (best-effort)
        logger.warning(
            'sav: échec avancement ticket sur intervention terminée '
            '#%s', getattr(intervention, 'pk', None), exc_info=True)
