"""NTUX32 — abonnés ``apps.publicapi`` aux évènements des objets UX du bus
``core.events`` (``saved_view_shared``/``record_restored``, voir leur
docstring dans ``core/events.py``) : traduit chaque signal en webhook sortant
(``delivery.dispatch_event``, MÊME transport que tous les autres webhooks,
aucun nouveau mécanisme).

Câblé via ``connect()`` depuis ``PublicApiConfig.ready()`` (``dispatch_uid``
explicite, même patron que ``btp_event_receivers.py``) — jamais un import
direct ``apps.uxviews``/``apps.trash`` → ``apps.publicapi`` : ce sont ces apps
qui émettent sur le bus, sans savoir qui écoute.

AUCUNE DONNÉE SENSIBLE dans les charges utiles : la configuration d'une vue
(filtres/colonnes) n'est jamais incluse (nom + écran + visibilité seulement) ;
le payload de restauration ne porte que le type d'objet + son id — jamais
``donnees_snapshot`` (best-effort, affichage seul, cf. ``apps/trash/models.py``).
"""
import logging

from core import events

from .constants import EVENT_RECORD_RESTORED, EVENT_SAVED_VIEW_SHARED

logger = logging.getLogger(__name__)


def _livrer(company_id, event, payload, contexte):
    """Livraison best-effort : un webhook ne casse jamais le geste métier."""
    if not company_id:
        return
    from . import delivery
    try:
        delivery.dispatch_event(company_id, event, payload)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.exception('%s: dispatch webhook échoué (%s)', event, contexte)


def on_saved_view_shared(sender, view=None, company=None, user=None,
                         action=None, **kwargs):
    if view is None:
        return
    _livrer(getattr(company, 'id', None) or getattr(view, 'company_id', None),
            EVENT_SAVED_VIEW_SHARED, {
                'view_id': view.pk,
                'ecran': view.ecran,
                'nom': view.nom,
                'action': action,
            }, f'vue {view.pk}')


def on_record_restored(sender, element=None, obj=None, company=None,
                       user=None, **kwargs):
    if element is None:
        return
    _livrer(getattr(company, 'id', None) or getattr(element, 'company_id', None),
            EVENT_RECORD_RESTORED, {
                'element_id': element.pk,
                'type': element.cle_modele,
                'object_id': element.object_id,
                'restaure': obj is not None,
            }, f'corbeille {element.pk}')


def connect():
    """Branche les récepteurs UX. Appelé depuis ``PublicApiConfig.ready()``."""
    events.saved_view_shared.connect(
        on_saved_view_shared, dispatch_uid='publicapi_saved_view_shared')
    events.record_restored.connect(
        on_record_restored, dispatch_uid='publicapi_record_restored')
