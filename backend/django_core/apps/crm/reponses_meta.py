"""Réponses BRUTES des formulaires Meta Lead Ads (décision fondateur du 17/11/2026).

Meta efface les données d'un lead au bout de 90 jours ; jusqu'ici seules les
colonnes MAPPÉES survivaient chez nous. Chaque réponse Graph d'un lead
(``field_data`` avec chaque question et sa valeur, ``created_time``, ``id``,
identifiants d'annonce/formulaire quand Meta les donne) est désormais gardée
TELLE QUELLE sur la ligne ``WebsiteLeadPayload`` (``source=meta_lead_ads``) de
la soumission, sous deux clés de son ``payload`` :

* ``REPONSES`` (``reponses_meta``) — la réponse Graph nettoyée de tout jeton ;
* ``RECUES_LE`` (``reponses_meta_recues_le``) — l'horodatage ISO de la garde.

Les clés de la notification déjà présentes (``leadgen_id``, ``ad_id``…) ne
bougent pas, ni ``processed``/``error``. La première réponse gardée fait foi :
un rejeu, un retry Meta ou le pull quotidien ne la réécrivent pas (idempotent).

Vie privée (loi 09-08) : l'effacement d'un lead (``dsr_provider.
_anonymiser_copies_brutes``) remplace le ``payload`` ENTIER des lignes du
lead — ces clés partent avec, par construction. Un lead déjà anonymisé ne
reçoit plus jamais de réponses (garde ``_lead_efface``) : un retry Meta ou le
pull des 90 jours ne ressuscite pas la donnée effacée.
"""
import copy
import logging

from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)

REPONSES = 'reponses_meta'
RECUES_LE = 'reponses_meta_recues_le'

#: Clés jamais gardées : ``paging`` porte des URL ``next`` qui embarquent le
#: jeton d'accès en clair ; le reste est le jeton lui-même sous ses noms usuels.
_CLES_INTERDITES = frozenset({'access_token', 'paging', 'token'})

#: Questions Meta dont la réponse est une coordonnée personnelle : masquées
#: comme les ``LEAD_PII_FIELDS`` pour un utilisateur sans ``client_pii_voir``.
QUESTIONS_PII = frozenset({
    'email', 'work_email', 'phone_number', 'work_phone_number', 'telephone',
    'whatsapp', 'street_address', 'adresse', 'post_code', 'zip_code'})


def _secret(cle, valeur):
    cle = str(cle).lower()
    if cle in _CLES_INTERDITES or 'token' in cle or 'secret' in cle:
        return True
    return isinstance(valeur, str) and 'access_token=' in valeur


def nettoyer_reponse_graph(reponse):
    """Copie profonde de la réponse Graph SANS rien qui ressemble à un jeton
    (clé ``*token*``/``*secret*``/``paging``, ou valeur portant
    ``access_token=``). Le reste est gardé verbatim."""
    if isinstance(reponse, dict):
        return {k: nettoyer_reponse_graph(v) for k, v in reponse.items()
                if not _secret(k, v)}
    if isinstance(reponse, list):
        return [nettoyer_reponse_graph(v) for v in reponse
                if not _secret('', v)]
    return copy.deepcopy(reponse)


def _lead_efface(lead):
    """Lead anonymisé (loi 09-08) ou à la corbeille : on n'y touche plus."""
    from .dsr_provider import LEAD_NOM_ANONYMISE
    if lead is None:
        return False
    return (getattr(lead, 'nom', None) == LEAD_NOM_ANONYMISE
            or bool(getattr(lead, 'is_deleted', False)))


def poser_reponses(raw, reponse, lead=None):
    """Pose la réponse Graph sur ``raw.payload`` (sans sauver). Renvoie
    ``True`` si le payload a changé. Ne fait rien : réponse non-dict, payload
    caviardé, réponses déjà gardées (la première fait foi), lead effacé."""
    payload = raw.payload if isinstance(raw.payload, dict) else {}
    if (not isinstance(reponse, dict) or payload.get('caviarde')
            or isinstance(payload.get(REPONSES), dict)
            or _lead_efface(lead if lead is not None else raw.lead)):
        return False
    payload = dict(payload)
    payload[REPONSES] = nettoyer_reponse_graph(reponse)
    payload[RECUES_LE] = timezone.now().isoformat()
    raw.payload = payload
    return True


def cloturer_ligne_meta(raw, lead, reponse):
    """Webhook et rejeu (``webhooks._process_meta_lead_entry``) : la ligne
    devient traitée et rattachée au lead — mêmes trois champs qu'avant — et
    garde la réponse Graph brute dans la MÊME écriture."""
    raw.lead = lead
    raw.processed = True
    raw.error = ''
    champs = ['lead', 'processed', 'error']
    leadgen_id = (raw.payload or {}).get('leadgen_id') if isinstance(raw.payload, dict) else None
    # Un retry Meta crée une NOUVELLE ligne de notification : les réponses
    # restent sur la première ligne qui les garde, jamais recopiées.
    deja = leadgen_id and any(
        isinstance((r.payload or {}).get(REPONSES), dict)
        for r in _lignes_du_leadgen(raw.company, leadgen_id).exclude(pk=raw.pk))
    if not deja and poser_reponses(raw, reponse, lead):
        champs.append('payload')
    raw.save(update_fields=champs)


def _lignes_du_leadgen(company, leadgen_id):
    from .models import WebsiteLeadPayload
    leadgen_id = str(leadgen_id or '').strip()
    cible = Q(payload__leadgen_id=leadgen_id)
    if leadgen_id.isdigit():
        cible |= Q(payload__leadgen_id=int(leadgen_id))
    return (WebsiteLeadPayload.objects
            .filter(company=company,
                    source=WebsiteLeadPayload.Source.META_LEAD_ADS)
            .filter(cible).order_by('received_at', 'pk'))


def conserver_reponses_meta(*, company, leadgen_id, reponse, lead):
    """Pull adsengine et commande de récupération : garde la réponse Graph sur
    LA ligne brute de ce ``leadgen_id`` (la plus ancienne), ou en crée une
    (``source=meta_lead_ads``, rattachée au lead, société du lead) quand aucune
    n'existe — jamais de doublon. Renvoie ``'gardee'``, ``'deja'`` ou
    ``'ignoree'``."""
    from .models import Lead, WebsiteLeadPayload
    if not isinstance(lead, Lead) or not isinstance(reponse, dict):
        return 'ignoree'
    if lead.company_id != getattr(company, 'pk', None) or _lead_efface(lead):
        return 'ignoree'
    lignes = list(_lignes_du_leadgen(company, leadgen_id))
    if any(isinstance((r.payload or {}).get(REPONSES), dict) for r in lignes):
        return 'deja'
    if lignes:
        raw = lignes[0]
        if not poser_reponses(raw, reponse, lead):
            return 'ignoree'
        raw.save(update_fields=['payload'])
        return 'gardee'
    raw = WebsiteLeadPayload(
        source=WebsiteLeadPayload.Source.META_LEAD_ADS, company=company,
        lead=lead, processed=True, error='',
        payload={'leadgen_id': str(leadgen_id),
                 'form_id': str(reponse.get('form_id') or ''),
                 'ad_id': str(reponse.get('ad_id') or ''),
                 'created_time': reponse.get('created_time'),
                 'origine': 'pull'})
    poser_reponses(raw, reponse, lead)
    raw.save()
    return 'gardee'


def creer_lead_meta_pull(reponse_graph, **kwargs):
    """Pull adsengine (``tasks.pull_ad_leads_for_company``) : crée le lead par
    le service HABITUEL puis garde la réponse Graph brute. La garde est
    best-effort : elle ne fait jamais échouer la capture du lead (seul le
    délai souple Celery remonte, comme partout — ACEL71).

    Le service est relu sur ``services`` À L'APPEL : les tests du pull qui le
    remplacent (``patch('apps.crm.services.create_lead_from_meta_lead_ads')``)
    restent valables."""
    from celery.exceptions import SoftTimeLimitExceeded

    from . import services
    lead = services.create_lead_from_meta_lead_ads(**kwargs)
    try:
        conserver_reponses_meta(
            company=kwargs.get('company'), leadgen_id=kwargs.get('leadgen_id'),
            reponse=reponse_graph, lead=lead)
    except SoftTimeLimitExceeded:
        raise
    except Exception:  # noqa: BLE001 — la garde ne casse jamais la capture (D-ENF22-BLE001)
        logger.warning(
            'reponses_meta: réponses Meta non gardées (leadgen %s)',
            kwargs.get('leadgen_id'), exc_info=True)
    return lead


def _texte_reponse(valeurs):
    if isinstance(valeurs, list):
        return ', '.join(str(v) for v in valeurs if v not in (None, ''))
    return '' if valeurs is None else str(valeurs)


def reponses_meta_du_lead(lead, *, masquer_pii=False):
    """Lecture seule : ``{'reponses': [{question, reponse}], 'recues_le'}``
    dans l'ordre du formulaire, depuis la PREMIÈRE ligne brute du lead qui
    garde des réponses Meta ; ``None`` sans réponse gardée. ``masquer_pii``
    remplace les coordonnées (``QUESTIONS_PII``) par le masque de la fiche."""
    from .models import WebsiteLeadPayload
    if lead is None or not getattr(lead, 'pk', None):
        return None
    lignes = (WebsiteLeadPayload.objects
              .filter(company_id=lead.company_id, lead=lead,
                      source=WebsiteLeadPayload.Source.META_LEAD_ADS)
              .order_by('received_at', 'pk').values_list('payload', flat=True))
    for payload in lignes:
        brut = (payload or {}).get(REPONSES) if isinstance(payload, dict) else None
        if not isinstance(brut, dict):
            continue
        reponses = []
        for entree in brut.get('field_data') or []:
            if not isinstance(entree, dict):
                continue
            question = str(entree.get('name') or '')
            texte = _texte_reponse(entree.get('values'))
            if masquer_pii and question.strip().lower() in QUESTIONS_PII and texte:
                texte = '•••'
            reponses.append({'question': question, 'reponse': texte})
        return {'reponses': reponses, 'recues_le': payload.get(RECUES_LE)}
    return None
