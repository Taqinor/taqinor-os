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


def on_appointment_effectue(sender, **kwargs):
    """PUB30 — Sur ``appointment_effectue`` (émis par ``crm``, jamais importé
    ici), pousse l'événement CAPI dédié « visite technique effectuée » via
    ``capi_crm`` (même famille/gating que ADSENG32). Best-effort : un échec
    n'empêche jamais la transition déjà actée côté crm."""
    appointment = kwargs.get('appointment')
    company = kwargs.get('company')
    if appointment is None or company is None:
        return
    lead_id = getattr(appointment, 'lead_id', None)
    if not lead_id:
        return
    try:
        from . import capi_crm
        capi_crm.emit_appointment_effectue_event(
            company, lead_id, appointment.pk)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'adsengine.on_appointment_effectue: émission échouée '
            '(appointment %s)', getattr(appointment, 'pk', '?'),
            exc_info=True)


def connect():
    """Abonne les récepteurs domaine (appelé depuis ``apps.py`` ``ready()``)."""
    from core.events import appointment_effectue, meta_lead_captured
    meta_lead_captured.connect(
        on_meta_lead_captured, dispatch_uid='adsengine_meta_lead_captured')
    appointment_effectue.connect(
        on_appointment_effectue, dispatch_uid='adsengine_appointment_effectue')
