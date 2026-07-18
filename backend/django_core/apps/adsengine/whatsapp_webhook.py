"""ADSDEEP24 — Récepteur webhook WhatsApp Cloud API (topic ``messages``).

Deux endpoints publics (pas de session / JWT — l'authenticité est prouvée par la
signature Meta, jamais par un utilisateur connecté) :

  GET  /api/django/adsengine/whatsapp/webhook/
       Poignée de main de souscription Meta : ``hub.mode=subscribe`` +
       ``hub.verify_token`` + ``hub.challenge``. Renvoie ``hub.challenge`` en
       texte brut si le token correspond à ``WHATSAPP_CLOUD_VERIFY_TOKEN``.

  POST /api/django/adsengine/whatsapp/webhook/
       Messages entrants signés (``X-Hub-Signature-256`` vérifiée contre
       ``WHATSAPP_CLOUD_APP_SECRET``). On extrait l'objet ``referral`` des
       messages entrants (présent UNIQUEMENT quand la conversation vient d'une
       pub CTWA — dossier leads-capi §5) → ``CtwaReferral`` (attribution par ad
       d'une conversation WhatsApp). Le lead CRM est rattaché par téléphone via
       ``apps.crm.selectors`` (jamais un import des modèles crm).

NO-OP TOTAL SANS CONFIGURATION : tant que ``WHATSAPP_CLOUD_VERIFY_TOKEN`` ET
``WHATSAPP_CLOUD_APP_SECRET`` ne sont pas TOUS DEUX définis, tout appel (GET ou
POST) répond 404 sans le moindre effet de bord — le webhook n'existe pas tant
que le fondateur n'a pas provisionné les jetons (gate ADSENG34 : coût/BSP).
Aucun appel réseau sortant depuis ce module.
"""
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


def _verify_token():
    return (getattr(settings, 'WHATSAPP_CLOUD_VERIFY_TOKEN', '') or '').strip()


def _app_secret():
    return (getattr(settings, 'WHATSAPP_CLOUD_APP_SECRET', '') or '').strip()


def _is_configured():
    """Le webhook n'est ACTIF que si les DEUX jetons sont provisionnés."""
    return bool(_verify_token() and _app_secret())


def _resolve_company():
    """Société cible, résolue CÔTÉ SERVEUR (jamais du corps de requête), au même
    patron que les autres webhooks Meta de l'ERP : ``WHATSAPP_CLOUD_COMPANY_ID``
    si posé, sinon la 1re ``Company`` (scaffold mono-société)."""
    from authentication.models import Company

    company_id = getattr(settings, 'WHATSAPP_CLOUD_COMPANY_ID', None)
    if company_id:
        return Company.objects.filter(pk=company_id).first()
    return Company.objects.order_by('pk').first()


def _check_signature(request, secret):
    """Vrai si ``X-Hub-Signature-256`` est présente ET valide (HMAC-SHA256 du
    corps brut avec ``secret``). Absente ou mal formée → False (rejet)."""
    sig_header = request.META.get('HTTP_X_HUB_SIGNATURE_256', '')
    if not sig_header or not sig_header.startswith('sha256='):
        return False
    expected = 'sha256=' + hmac.new(
        secret.encode(), request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig_header, expected)


def _parse_ts(value):
    """Horodatage WhatsApp (epoch secondes, str/int) → datetime aware UTC, ou
    None si illisible (jamais d'erreur)."""
    if value in (None, ''):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=dt_timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def _phone_key(phone):
    """Clé téléphone normalisée via ``crm.selectors`` (jamais un import des
    modèles crm) ; '' si vide ou en cas d'échec (best-effort)."""
    if not phone:
        return ''
    try:
        from apps.crm.selectors import normalize_phone_key
        return normalize_phone_key(phone) or ''
    except Exception:  # noqa: BLE001 — la clé n'empêche jamais l'enregistrement
        return ''


def _lead_id_for_phone(company, phone):
    """id du lead CRM rattaché par téléphone via ``crm.selectors`` (jamais un
    import des modèles crm) ; None si aucun match (best-effort)."""
    if not phone:
        return None
    try:
        from apps.crm.selectors import find_lead_id_by_phone
        return find_lead_id_by_phone(company, phone)
    except Exception:  # noqa: BLE001 — le rattachement n'est jamais bloquant
        return None


@method_decorator(csrf_exempt, name='dispatch')
class WhatsAppCloudWebhookView(View):
    """ADSDEEP24 — Webhook WhatsApp Cloud API (vérification GET + messages POST).

    Public, gated par ``WHATSAPP_CLOUD_VERIFY_TOKEN`` +
    ``WHATSAPP_CLOUD_APP_SECRET`` : no-op total (404) tant qu'ils ne sont pas
    tous deux configurés."""

    def get(self, request):
        if not _is_configured():
            return HttpResponse('Non configuré.', status=404)
        mode = request.GET.get('hub.mode', '')
        token = request.GET.get('hub.verify_token', '')
        challenge = request.GET.get('hub.challenge', '')
        if mode == 'subscribe' and hmac.compare_digest(token, _verify_token()):
            return HttpResponse(
                challenge, content_type='text/plain', status=200)
        return HttpResponse('Vérification refusée.', status=403)

    def post(self, request):
        if not _is_configured():
            return HttpResponse('Non configuré.', status=404)
        if not _check_signature(request, _app_secret()):
            logger.warning(
                'adsengine.whatsapp_webhook: signature absente ou invalide.')
            return HttpResponse('Signature invalide.', status=403)

        try:
            payload = json.loads(request.body or b'{}')
            if not isinstance(payload, dict):
                raise ValueError('payload non-objet')
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({'detail': 'JSON invalide.'}, status=400)

        company = _resolve_company()
        if company is None:
            logger.error('adsengine.whatsapp_webhook: aucune Company résolue.')
            return JsonResponse(
                {'detail': 'Aucune société résolue.'}, status=202)

        stored = self._process(company, payload)
        return JsonResponse({'ok': True, 'referrals': stored}, status=200)

    @staticmethod
    def _process(company, payload):
        """Extrait les ``referral`` des messages entrants → upsert idempotent
        d'un ``CtwaReferral`` par ``(company, wa_message_id)``. Best-effort :
        un webhook mal formé ne fait jamais planter le serveur (200 renvoyé)."""
        from .models import CtwaReferral

        stored = 0
        try:
            for entry in (payload.get('entry') or []):
                for change in (entry.get('changes') or []):
                    value = change.get('value') or {}
                    for msg in (value.get('messages') or []):
                        referral = msg.get('referral') or {}
                        if not referral:
                            continue
                        wa_message_id = str(msg.get('id') or '').strip()
                        if not wa_message_id:
                            continue
                        phone = str(msg.get('from') or '').strip()
                        CtwaReferral.objects.update_or_create(
                            company=company,
                            wa_message_id=wa_message_id[:128],
                            defaults={
                                'ad_id': str(
                                    referral.get('source_id') or '')[:64],
                                'ctwa_clid': str(
                                    referral.get('ctwa_clid') or '')[:255],
                                'source_type': str(
                                    referral.get('source_type') or '')[:16],
                                'headline': str(referral.get('headline') or ''),
                                'ts': _parse_ts(msg.get('timestamp')),
                                'phone_key': _phone_key(phone)[:32],
                                'crm_lead_id': _lead_id_for_phone(
                                    company, phone),
                            })
                        stored += 1
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning(
                'adsengine.whatsapp_webhook: traitement échoué.',
                exc_info=True)
        return stored
