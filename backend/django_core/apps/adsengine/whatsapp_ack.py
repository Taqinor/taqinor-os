"""CADV41 (D-CADV-5) — accusé WhatsApp automatique hors heures, gabarit UTILITAIRE.

Un lead Meta arrivé hors heures ouvrées, qui a coché la case WhatsApp, reçoit UN
message d'accusé par l'API Cloud, tracé au chatter et SANS poser
``first_contacted_at`` : un accusé automatique n'est pas un premier contact. Rien
ne part sans les trois variables (D-ADEP-3 : absentes en prod). Le CRM est lu par
``selectors``/``services``, jamais par ses modèles. Best-effort : un échec ne casse
jamais la capture du lead, et le rattrapage suivant retentera.
"""
import logging
from datetime import timedelta

import httpx
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .api_version import GRAPH_BASE_URL

logger = logging.getLogger(__name__)

#: Corps de la note de chatter, et preuve durable de l'envoi (un seul par lead).
NOTE_ACCUSE = 'Accusé WhatsApp automatique envoyé'
#: Le pull de rattrapage rejoue 48 h de leads : passé ce délai, le lead attend le
#: commercial, on n'accuse plus réception d'une demande ancienne.
FRAICHEUR = timedelta(hours=2)
#: Nom de repli de ``create_lead_from_meta_lead_ads`` : jamais un prénom.
_NOM_DE_REPLI_META = 'Lead Meta Ads'
_LANGUE_GABARIT = 'fr'
_TIMEOUT_SECONDES = 5.0
#: Verrou posé avant l'envoi : webhook et pull concurrents n'envoient qu'une fois.
_VERROU_SECONDES = 24 * 3600


def configuration():
    """``(jeton, id du numéro, gabarit)``, ou ``None`` s'il en manque un."""
    trio = (
        getattr(settings, 'WHATSAPP_CLOUD_ACCESS_TOKEN', ''),
        getattr(settings, 'WHATSAPP_CLOUD_PHONE_NUMBER_ID', ''),
        getattr(settings, 'WHATSAPP_ACK_TEMPLATE', ''),
    )
    return trio if all(trio) else None


def _prenom(lead):
    brut = (lead.prenom or '').strip() or (lead.nom or '').strip()
    if not brut or brut == _NOM_DE_REPLI_META:
        return ''
    return brut.split()[0]


def _numero(lead):
    from apps.ventes.utils.phone import normalize_phone_e164

    return normalize_phone_e164(lead.whatsapp or lead.telephone) or ''


def _accuse_du(company, lead, created_time):
    """Toutes les conditions de D-CADV-5, de la moins chère à la plus chère."""
    from apps.crm import selectors as crm

    societe_du_numero = getattr(settings, 'WHATSAPP_CLOUD_COMPANY_ID', None)
    if societe_du_numero and str(societe_du_numero) != str(company.pk):
        return False
    if lead.whatsapp_opt_in is not True or lead.first_contacted_at:
        return False
    if not crm.peut_contacter(lead, canal='whatsapp'):
        return False
    maintenant = timezone.now()
    arrivee = crm.arrivee_lead_meta(lead, created_time)
    if maintenant - arrivee > FRAICHEUR:
        return False
    return (crm.hors_heures_ouvrees(company, arrivee)
            and crm.hors_heures_ouvrees(company, maintenant)
            and not crm.lead_porte_note(lead, NOTE_ACCUSE))


def _poster(trio, numero, prenom):
    jeton, id_numero, gabarit = trio
    reponse = httpx.post(
        f'{GRAPH_BASE_URL}/{id_numero}/messages',
        json={
            'messaging_product': 'whatsapp', 'to': numero, 'type': 'template',
            'template': {
                'name': gabarit, 'language': {'code': _LANGUE_GABARIT},
                'components': [{'type': 'body', 'parameters': [
                    {'type': 'text', 'text': prenom}]}],
            },
        },
        headers={'Authorization': f'Bearer {jeton}'},
        timeout=_TIMEOUT_SECONDES)
    reponse.raise_for_status()


def envoyer_accuse_si_du(company, lead, created_time=None):
    """Envoie l'accusé s'il est dû ; ``True`` si un message est parti."""
    from apps.crm.services import ajouter_note_lead_si_nouvelle

    trio = configuration()
    if trio is None or not _accuse_du(company, lead, created_time):
        return False
    numero, prenom = _numero(lead), _prenom(lead)
    if not numero or not prenom:
        return False
    verrou = f'adsengine:accuse-whatsapp:{lead.pk}'
    if not cache.add(verrou, 1, _VERROU_SECONDES):
        return False
    try:
        _poster(trio, numero, prenom)
    except httpx.HTTPError:
        cache.delete(verrou)  # le rattrapage suivant retentera
        logger.warning('Accusé WhatsApp non envoyé (lead %s)', lead.pk, exc_info=True)
        return False
    ajouter_note_lead_si_nouvelle(
        company=company, lead_id=lead.pk, user=None, body=NOTE_ACCUSE)
    return True
