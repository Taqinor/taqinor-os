"""NTI18N43 — abonné ``apps.publicapi`` à la bascule de langue.

Écoute ``core.events.langue_changed`` (émis quand la langue de document d'un
client, ou la langue par défaut de la société, change — voir sa docstring dans
``core/events.py``) et le traduit en webhook sortant ``langue_changed`` via
``delivery.dispatch_event`` : MÊME transport que tous les autres webhooks,
aucun nouveau mécanisme, aucune file séparée.

Câblé par ``connect()`` depuis ``PublicApiConfig.ready()`` (``dispatch_uid``
explicite, même patron que ``uxviews_event_receivers.py``) — jamais un import
direct ``apps.crm``/``apps.parametres`` → ``apps.publicapi`` : ce sont ces apps
qui émettent sur le bus, sans savoir qui écoute.

CHARGE UTILE — exactement les trois clés nommées par le plan
(``client_id``, ``ancienne_langue``, ``nouvelle_langue``), plus ``portee`` qui
distingue une bascule CLIENT d'une bascule SOCIÉTÉ. ``client_id`` vaut ``None``
pour une bascule société : l'intégration tierce sait alors que le changement
porte sur le réglage global et non sur une fiche. Aucune donnée personnelle
n'est ajoutée : ni nom, ni e-mail, ni téléphone — un code de langue et un
identifiant suffisent à déclencher une re-synchronisation côté tiers.
"""
import logging

from core import events

from .constants import EVENT_LANGUE_CHANGED

logger = logging.getLogger(__name__)


def on_langue_changed(sender, company=None, portee=None, client_id=None,
                      ancienne_langue=None, nouvelle_langue=None, user=None,
                      **kwargs):
    """Livre le webhook ``langue_changed`` (best-effort, jamais bloquant)."""
    company_id = getattr(company, 'id', None) or company
    if not company_id:
        return
    payload = {
        'client_id': client_id,
        'ancienne_langue': ancienne_langue,
        'nouvelle_langue': nouvelle_langue,
        'portee': portee,
    }
    from . import delivery
    try:
        delivery.dispatch_event(company_id, EVENT_LANGUE_CHANGED, payload)
    except Exception:  # noqa: BLE001 — best-effort, un webhook ne casse
        # jamais la bascule de langue elle-même.
        logger.exception(
            '%s: dispatch webhook échoué (portée %s, client %s)',
            EVENT_LANGUE_CHANGED, portee, client_id)


def connect():
    """Branche le récepteur. Appelé depuis ``PublicApiConfig.ready()``."""
    events.langue_changed.connect(
        on_langue_changed, dispatch_uid='publicapi_langue_changed')
