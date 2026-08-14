"""NTSCM39 — abonnés ``apps.publicapi`` aux évènements SCM du bus
``core.events`` (``scm_rupture_imminente_detectee``/``scm_cycle_sop_cloture``,
voir leur docstring dans ``core/events.py``) : traduit chaque signal en
webhook sortant (``delivery.dispatch_event``, MÊME transport que tous les
autres webhooks du système, aucun nouveau mécanisme).

Câblé via ``connect()`` depuis ``PublicApiConfig.ready()`` (``dispatch_uid``
explicite, même patron que ``apps/publicapi/signals.py::connect`` — jamais un
import direct ``apps.scm`` -> ``apps.publicapi`` : c'est ``apps.scm`` qui émet
sur le bus, sans savoir qui écoute)."""
import logging

from core import events

from .constants import EVENT_SCM_CYCLE_SOP_CLOTURE, EVENT_SCM_RUPTURE_IMMINENTE

logger = logging.getLogger(__name__)


def on_scm_rupture_imminente_detectee(
        sender, company=None, produit_id=None, produit_nom=None,
        rupture_date=None, quantite_suggeree=None, **kwargs):
    if company is None:
        return
    from . import delivery
    try:
        # `rupture_date` arrive déjà en ISO-8601 (str) ou `None` — voir
        # `selectors.tableau_bord_reappro`, qui sérialise la date AVANT de la
        # poser dans la ligne consommée par `apps.scm.services.
        # detecter_ruptures_imminentes_et_notifier` (émetteur de ce signal).
        delivery.dispatch_event(company.id, EVENT_SCM_RUPTURE_IMMINENTE, {
            'produit_id': produit_id,
            'produit_nom': produit_nom,
            'rupture_date': rupture_date,
            'quantite_suggeree': quantite_suggeree,
        })
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.exception(
            'scm_rupture_imminente_detectee: dispatch webhook échoué '
            '(société %s, produit %s)', company.id, produit_id)


def on_scm_cycle_sop_cloture(sender, cycle=None, user=None, **kwargs):
    if cycle is None:
        return
    from . import delivery
    try:
        delivery.dispatch_event(cycle.company_id, EVENT_SCM_CYCLE_SOP_CLOTURE, {
            'cycle_id': cycle.id,
            'periode': cycle.periode,
        })
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.exception(
            'scm_cycle_sop_cloture: dispatch webhook échoué (cycle %s)',
            cycle.id)


def connect():
    """Branche les récepteurs SCM. Appelé depuis ``PublicApiConfig.ready()``."""
    events.scm_rupture_imminente_detectee.connect(
        on_scm_rupture_imminente_detectee,
        dispatch_uid='publicapi_scm_rupture_imminente')
    events.scm_cycle_sop_cloture.connect(
        on_scm_cycle_sop_cloture,
        dispatch_uid='publicapi_scm_cycle_sop_cloture')
