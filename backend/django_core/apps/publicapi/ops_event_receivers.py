"""NTOBS26 — abonnés ``apps.publicapi`` aux évènements d'exploitation du bus
``core.events`` (``incident_opened``/``incident_resolved``, émis par
``apps.statuspage.receivers`` ; ``maintenance_window_announced``, émis par
``core.maintenance_windows.MaintenanceWindowListCreateView.perform_create``) :
traduit chaque signal en webhook sortant (``delivery.dispatch_event``, MÊME
transport que tous les autres webhooks, aucun nouveau mécanisme).

Câblé via ``connect()`` depuis ``PublicApiConfig.ready()`` (``dispatch_uid``
explicite, même patron que ``btp_event_receivers.py``/``i18n_event_receivers.
py``) — jamais un import direct ``apps.statuspage``/``core`` →
``apps.publicapi`` dans l'autre sens : ce sont ces couches qui émettent sur
le bus, sans savoir qui écoute.

Un incident/une fenêtre SYSTÈME (``company=None``, visible de tous les
tenants) n'a aucune société unique vers laquelle router un webhook — ces
évènements-là ne livrent donc rien ici (même garde que ``on_langue_changed``
pour une bascule société-large)."""
import logging

from core import events

from .constants import (
    EVENT_INCIDENT_OPENED, EVENT_INCIDENT_RESOLVED,
    EVENT_MAINTENANCE_WINDOW_ANNOUNCED,
)

logger = logging.getLogger(__name__)


def _livrer(company, event, payload, contexte):
    """Livraison best-effort : un webhook ne casse jamais le geste métier."""
    company_id = getattr(company, 'id', None) or company
    if not company_id:
        return
    from . import delivery
    try:
        delivery.dispatch_event(company_id, event, payload)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.exception('%s: dispatch webhook échoué (%s)', event, contexte)


def on_incident_opened(sender, incident=None, company=None, **kwargs):
    if incident is None:
        return
    _livrer(company, EVENT_INCIDENT_OPENED, {
        'incident_id': incident.id,
        'titre': incident.titre,
        'severite': incident.severite,
        'statut': incident.statut,
        'region': incident.region,
        'debute_le': (incident.debute_le.isoformat()
                      if incident.debute_le else None),
    }, f'incident {incident.id}')


def on_incident_resolved(sender, incident=None, company=None, **kwargs):
    if incident is None:
        return
    _livrer(company, EVENT_INCIDENT_RESOLVED, {
        'incident_id': incident.id,
        'titre': incident.titre,
        'severite': incident.severite,
        'statut': incident.statut,
        'region': incident.region,
        'resolu_le': (incident.resolu_le.isoformat()
                      if incident.resolu_le else None),
    }, f'incident {incident.id}')


def on_maintenance_window_announced(sender, fenetre=None, company=None,
                                    user=None, **kwargs):
    if fenetre is None:
        return
    _livrer(company, EVENT_MAINTENANCE_WINDOW_ANNOUNCED, {
        'fenetre_id': fenetre.id,
        'region': fenetre.region,
        'impact': fenetre.impact,
        'statut': fenetre.statut,
        'debute_le': (fenetre.debute_le.isoformat()
                      if fenetre.debute_le else None),
        'termine_le': (fenetre.termine_le.isoformat()
                       if fenetre.termine_le else None),
    }, f'fenêtre {fenetre.id}')


def connect():
    """Branche les récepteurs. Appelé depuis ``PublicApiConfig.ready()``."""
    events.incident_opened.connect(
        on_incident_opened, dispatch_uid='publicapi_incident_opened')
    events.incident_resolved.connect(
        on_incident_resolved, dispatch_uid='publicapi_incident_resolved')
    events.maintenance_window_announced.connect(
        on_maintenance_window_announced,
        dispatch_uid='publicapi_maintenance_window_announced')
