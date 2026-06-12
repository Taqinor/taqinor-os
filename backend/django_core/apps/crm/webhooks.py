"""Récepteur des leads du site public taqinor.ma.

Le Worker Cloudflare du site (apps/web — émetteur, jamais modifié ici)
POSTe chaque lead qualifié vers ce endpoint avec un secret statique dans
l'en-tête ``X-Webhook-Secret``. Principes :

1. JAMAIS perdre un lead : la charge utile brute est stockée
   (WebsiteLeadPayload) AVANT toute tentative de mapping.
2. Idempotent : même téléphone reçu dans la même minute → mise à jour du
   lead existant, jamais de doublon.
3. Tenant résolu CÔTÉ SERVEUR (env WEBSITE_LEADS_COMPANY_ID, sinon la
   première Company) — rien ne vient du payload.
4. Un lead sous le seuil ne devrait pas arriver (filtré par le site) ;
   s'il arrive quand même : accepté et étiqueté, jamais rejeté.
"""

import hmac
import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from authentication.models import Company

from .models import Lead, LeadActivity, WebsiteLeadPayload

logger = logging.getLogger(__name__)

#: Fenêtre d'idempotence : même téléphone reçu deux fois dans cette fenêtre
#: (relance réseau, double clic) = mise à jour, pas de doublon.
DEDUP_WINDOW_SECONDS = 60


def _secret_ok(request) -> bool:
    expected = getattr(settings, 'WEBSITE_LEAD_WEBHOOK_SECRET', '') or ''
    provided = request.headers.get('X-Webhook-Secret', '')
    if not expected:
        # Pas de secret configuré → endpoint fermé (jamais ouvert par défaut)
        return False
    return hmac.compare_digest(expected, provided)


def _resolve_company():
    company_id = getattr(settings, 'WEBSITE_LEADS_COMPANY_ID', None)
    if company_id:
        return Company.objects.filter(pk=company_id).first()
    return Company.objects.order_by('pk').first()


def _map_payload_to_fields(data: dict) -> dict:
    """Payload du site (lead.ts:LeadRecord) → champs du modèle Lead."""
    band = data.get('band') or {}
    roi_band = ' · '.join(
        str(v) for v in (band.get('kwcLabel'), band.get('paybackLabel')) if v
    ) or None
    consent_ts = None
    if data.get('consentTimestamp'):
        consent_ts = parse_datetime(str(data['consentTimestamp']))

    utm = data.get('utm') or {}
    fields = {
        'nom': str(data.get('fullName') or '').strip()[:255] or 'Lead site web',
        'telephone': str(data.get('phoneE164') or data.get('phone') or '').strip()[:50],
        'ville': (str(data.get('city')).strip()[:120] if data.get('city') else None),
        'roof_type': (str(data.get('roofType')).strip()[:30] if data.get('roofType') else None),
        'bill_range_bucket': data.get('billRange') if data.get('billRange') in Lead.BillRangeBucket.values else None,
        'roi_band': roi_band,
        'whatsapp_opt_in': bool(data['whatsappOptIn']) if 'whatsappOptIn' in data else None,
        'consent_timestamp': consent_ts,
        'fbclid': (str(data.get('fbclid')).strip()[:500] if data.get('fbclid') else None),
        'canal': Lead.Canal.SITE_WEB,
        'source': Lead.Source.SITE_WEB,
    }
    for key in ('utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'):
        value = utm.get(key) or data.get(key)
        fields[key] = str(value).strip()[:300] if value else None
    if fields['whatsapp_opt_in'] and fields['telephone']:
        fields['whatsapp'] = fields['telephone']
    # Sous le seuil (ne devrait pas arriver — le site filtre) : étiqueté.
    if data.get('qualified') is False:
        fields['tags'] = 'Sous le seuil 1 000 MAD'
    return fields


@csrf_exempt
@require_POST
def website_lead_webhook(request):
    if not _secret_ok(request):
        return JsonResponse({'detail': 'Secret invalide ou absent.'}, status=401)

    try:
        data = json.loads(request.body.decode('utf-8'))
        if not isinstance(data, dict):
            raise ValueError('payload non-objet')
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'detail': 'JSON invalide.'}, status=400)

    company = _resolve_company()
    raw = WebsiteLeadPayload.objects.create(
        company=company,
        payload=data,
        remote_addr=(request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                     or request.META.get('REMOTE_ADDR'))[:64],
    )

    if company is None:
        raw.error = 'Aucune Company résolue — payload conservé pour rejeu.'
        raw.save(update_fields=['error'])
        logger.error('website_lead_webhook: aucune Company (payload #%s)', raw.pk)
        return JsonResponse({'detail': 'Stocké, mapping différé.', 'payload_id': raw.pk}, status=202)

    try:
        fields = _map_payload_to_fields(data)
        telephone = fields.get('telephone') or ''

        existing = None
        if telephone:
            window_start = timezone.now() - timezone.timedelta(seconds=DEDUP_WINDOW_SECONDS)
            existing = (
                Lead.objects
                .filter(company=company, telephone=telephone,
                        source=Lead.Source.SITE_WEB,
                        date_creation__gte=window_start)
                .order_by('-date_creation')
                .first()
            )

        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.save()
            lead, created = existing, False
        else:
            lead = Lead.objects.create(company=company, **fields)
            created = True
            LeadActivity.objects.create(
                company=lead.company, lead=lead, user=None,
                kind=LeadActivity.Kind.CREATION,
                body='Lead créé via le site web',
            )

        raw.lead = lead
        raw.processed = True
        raw.save(update_fields=['lead', 'processed'])
        return JsonResponse(
            {'detail': 'Lead créé.' if created else 'Lead mis à jour (doublon < 1 min).',
             'lead_id': lead.pk, 'payload_id': raw.pk},
            status=201 if created else 200,
        )
    except Exception as exc:  # noqa: BLE001 — la donnée brute prime
        raw.error = f'{type(exc).__name__}: {exc}'
        raw.save(update_fields=['error'])
        logger.exception('website_lead_webhook: mapping échoué (payload #%s)', raw.pk)
        return JsonResponse(
            {'detail': 'Stocké, mapping échoué — payload rejouable.', 'payload_id': raw.pk},
            status=202,
        )
