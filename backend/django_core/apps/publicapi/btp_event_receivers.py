"""NTCON31 — abonnés ``apps.publicapi`` aux évènements BTP du bus
``core.events`` (``btp_reserve_levee``/``btp_rfi_repondu``/
``btp_visa_approuve``/``btp_dgd_finalise``, voir leur docstring dans
``core/events.py``) : traduit chaque signal en webhook sortant
(``delivery.dispatch_event``, MÊME transport que tous les autres webhooks,
aucun nouveau mécanisme).

Câblé via ``connect()`` depuis ``PublicApiConfig.ready()`` (``dispatch_uid``
explicite, même patron que ``scm_event_receivers.py``) — jamais un import
direct ``apps.btp_chantier`` → ``apps.publicapi`` : c'est ``btp_chantier`` qui
émet sur le bus, sans savoir qui écoute.

AUCUN COÛT INTERNE dans les charges utiles : ni déboursé (NTCON11), ni
exposition aux pénalités (NTCON15), ni ``prix_achat``. Le payload du DGD porte
son ``solde_du_ht`` CONTRACTUEL — le chiffre que le client signe.
"""
import logging

from core import events

from .constants import (
    EVENT_BTP_DGD_FINALISE, EVENT_BTP_RESERVE_LEVEE, EVENT_BTP_RFI_REPONDU,
    EVENT_BTP_VISA_APPROUVE,
)

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


def on_btp_reserve_levee(sender, reserve=None, company=None, user=None,
                         **kwargs):
    if reserve is None:
        return
    _livrer(getattr(company, 'id', None) or reserve.company_id,
            EVENT_BTP_RESERVE_LEVEE, {
                'reserve_id': reserve.id,
                'chantier_id': reserve.chantier_id,
                'lot': reserve.lot,
                'gravite': reserve.gravite,
                'statut': reserve.statut,
                'date_levee': (reserve.date_levee.isoformat()
                               if reserve.date_levee else None),
            }, f'réserve {reserve.id}')


def on_btp_rfi_repondu(sender, rfi=None, company=None, reponse=None,
                       user=None, **kwargs):
    if rfi is None:
        return
    _livrer(getattr(company, 'id', None) or rfi.company_id,
            EVENT_BTP_RFI_REPONDU, {
                'rfi_id': rfi.id,
                'chantier_id': rfi.chantier_id,
                'numero': rfi.numero,
                'statut': rfi.statut,
                'reponse_id': getattr(reponse, 'id', None),
            }, f'RFI {rfi.id}')


def on_btp_visa_approuve(sender, visa=None, company=None, user=None, **kwargs):
    if visa is None:
        return
    _livrer(getattr(company, 'id', None) or visa.company_id,
            EVENT_BTP_VISA_APPROUVE, {
                'visa_id': visa.id,
                'chantier_id': visa.chantier_id,
                'reference': visa.reference,
                'type_visa': visa.type_visa,
                'statut': visa.statut,
                'date_revue': (visa.date_revue.isoformat()
                               if visa.date_revue else None),
            }, f'visa {visa.id}')


def on_btp_dgd_finalise(sender, dgd=None, company=None, user=None, **kwargs):
    if dgd is None:
        return
    _livrer(getattr(company, 'id', None) or dgd.company_id,
            EVENT_BTP_DGD_FINALISE, {
                'dgd_id': dgd.id,
                'chantier_id': dgd.chantier_id,
                'reference': dgd.reference,
                'statut': dgd.statut,
                # Montant CONTRACTUEL (celui que le client signe), jamais un
                # coût interne.
                'solde_du_ht': str(dgd.solde_du_ht),
                'date_finalisation': (dgd.date_finalisation.isoformat()
                                      if dgd.date_finalisation else None),
            }, f'DGD {dgd.id}')


def connect():
    """Branche les récepteurs BTP. Appelé depuis ``PublicApiConfig.ready()``."""
    events.btp_reserve_levee.connect(
        on_btp_reserve_levee, dispatch_uid='publicapi_btp_reserve_levee')
    events.btp_rfi_repondu.connect(
        on_btp_rfi_repondu, dispatch_uid='publicapi_btp_rfi_repondu')
    events.btp_visa_approuve.connect(
        on_btp_visa_approuve, dispatch_uid='publicapi_btp_visa_approuve')
    events.btp_dgd_finalise.connect(
        on_btp_dgd_finalise, dispatch_uid='publicapi_btp_dgd_finalise')
