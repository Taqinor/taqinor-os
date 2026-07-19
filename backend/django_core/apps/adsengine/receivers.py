"""ADSDEEP17 — Abonnés d'événements domaine (M6) du moteur publicitaire.

``adsengine`` réagit au fait métier « lead Meta capturé » (émis par le webhook
CRM existant) SANS jamais importer ``apps.crm`` : il matérialise un
``MetaLeadMirror`` (leads par ad). Le CRM est lu UNIQUEMENT via son
``selectors.py`` (normalisation du téléphone). Câblé dans ``apps.py`` ``ready()``.
"""
import logging

logger = logging.getLogger(__name__)


def _parse_dt(value):
    if not value:
        return None
    from django.utils.dateparse import parse_datetime
    try:
        return parse_datetime(str(value))
    except (ValueError, TypeError):
        return None


def on_meta_lead_captured(sender, **kwargs):
    """Upsert idempotent d'un ``MetaLeadMirror`` sur ``meta_lead_captured``.

    Idempotent par ``(company, leadgen_id)`` : webhook + pull-sync (ADSDEEP18)
    convergent, jamais de doublon. ``phone_key`` est normalisé via
    ``crm.selectors.normalize_phone_key`` (jamais un import des modèles CRM).
    Best-effort : une exception est journalisée, jamais propagée (ne casse pas
    la capture du lead côté CRM)."""
    from .models import MetaLeadMirror

    company = kwargs.get('company')
    leadgen_id = str(kwargs.get('leadgen_id') or '').strip()
    if company is None or not leadgen_id:
        return
    lead = kwargs.get('lead')

    phone_key = ''
    telephone = getattr(lead, 'telephone', '') or ''
    if telephone:
        try:
            from apps.crm.selectors import normalize_phone_key
            phone_key = normalize_phone_key(telephone) or ''
        except Exception:  # noqa: BLE001 — la clé n'empêche jamais le miroir
            phone_key = ''

    defaults = {
        'ad_id': str(kwargs.get('ad_id') or ''),
        'adset_id': str(kwargs.get('adset_id') or ''),
        'campaign_id': str(kwargs.get('campaign_id') or ''),
        'form_id': str(kwargs.get('form_id') or ''),
        'created_time': _parse_dt(kwargs.get('created_time')),
        'is_organic': bool(kwargs.get('is_organic')),
        'phone_key': phone_key[:32],
        'crm_lead_id': getattr(lead, 'pk', None),
    }
    try:
        MetaLeadMirror.objects.update_or_create(
            company=company, leadgen_id=leadgen_id, defaults=defaults)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'adsengine.on_meta_lead_captured: upsert échoué (leadgen %s)',
            leadgen_id, exc_info=True)


def on_lead_erased(sender, **kwargs):
    """PUB100 — Propage l'effacement CNDP d'un lead CRM aux miroirs adsengine.

    Anonymise (jamais ne supprime — on garde l'agrégat d'attribution par ad) les
    ``MetaLeadMirror`` et ``CtwaReferral`` qui référençaient ce lead : on efface
    le ``phone_key`` (PII normalisée) et on détache ``crm_lead_id``. Best-effort :
    une exception est journalisée, jamais propagée (l'effacement CRM ne casse
    jamais). Retrouve les miroirs par ``crm_lead_id`` d'abord, puis par
    ``phone_key`` (les deux clés de jointure QW10)."""
    from django.db.models import Q

    from .models import CtwaReferral, MetaLeadMirror

    company = kwargs.get('company')
    crm_lead_id = kwargs.get('crm_lead_id')
    phone_key = str(kwargs.get('phone_key') or '').strip()
    if company is None or (not crm_lead_id and not phone_key):
        return

    match = Q()
    if crm_lead_id:
        match |= Q(crm_lead_id=crm_lead_id)
    if phone_key:
        match |= Q(phone_key=phone_key)
    try:
        for model in (MetaLeadMirror, CtwaReferral):
            model.objects.filter(company=company).filter(match).update(
                phone_key='', crm_lead_id=None)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'adsengine.on_lead_erased: anonymisation échouée (lead %s)',
            crm_lead_id, exc_info=True)


def connect():
    """Abonne les récepteurs domaine (appelé depuis ``apps.py`` ``ready()``)."""
    from core.events import lead_erased, meta_lead_captured
    meta_lead_captured.connect(
        on_meta_lead_captured, dispatch_uid='adsengine_meta_lead_captured')
    lead_erased.connect(
        on_lead_erased, dispatch_uid='adsengine_lead_erased')
