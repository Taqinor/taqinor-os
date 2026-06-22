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


def _clean_roof_point(raw):
    """Normalise un pin de toiture en {'lat': float, 'lng': float} ou None.

    Accepte {lat,lng} ou {latitude,longitude} ; rejette silencieusement tout
    point hors bornes ([-90,90] / [-180,180]) ou non numérique."""
    if not isinstance(raw, dict):
        return None
    lat = raw.get('lat', raw.get('latitude'))
    lng = raw.get('lng', raw.get('lon', raw.get('longitude')))
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return {'lat': lat, 'lng': lng}


def _clean_decimal(raw, *, lo=None, hi=None):
    """Normalise une valeur en float, ou None si non numérique / hors bornes.

    Style tolérant identique au reste du webhook : on ne lève jamais — une
    valeur invalide est simplement ignorée (skip). Quand ``lo``/``hi`` sont
    fournis (même garde de bornes que ``_clean_roof_point`` pour lat/lng), une
    valeur hors plage est rejetée silencieusement."""
    if raw in (None, ''):
        return None
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    if lo is not None and val < lo:
        return None
    if hi is not None and val > hi:
        return None
    return val


def _clean_roof_outline(raw):
    """Normalise un contour rough optionnel en liste de [lat, lng], ou None.

    Le client n'est PAS obligé de dessiner : un contour absent/vide → None."""
    if not isinstance(raw, list) or not raw:
        return None
    out = []
    for pt in raw:
        if isinstance(pt, dict):
            p = _clean_roof_point(pt)
            if p:
                out.append([p['lat'], p['lng']])
        elif isinstance(pt, (list, tuple)) and len(pt) == 2:
            try:
                out.append([float(pt[0]), float(pt[1])])
            except (TypeError, ValueError):
                continue
    return out or None


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
    # Q2 — pin de toiture (+ contour optionnel) pointé par le client. On
    # n'accepte qu'un point {lat, lng} numérique valide ; tout le reste est
    # ignoré (jamais d'erreur). roofOutline est un polygone rough optionnel.
    point = _clean_roof_point(data.get('roofPoint') or data.get('roof_point'))
    if point is not None:
        fields['roof_point'] = point
    outline = _clean_roof_outline(
        data.get('roofOutline') or data.get('roof_outline'))
    if outline is not None:
        fields['roof_outline'] = outline
    bill_kwh = data.get('billKwh') or data.get('bill_kwh')
    if bill_kwh not in (None, ''):
        try:
            fields['bill_kwh'] = float(bill_kwh)
        except (TypeError, ValueError):
            pass

    # ── Champs de capture toiture-3D (additifs, optionnels, tolérants) ──
    # Facture hiver/été (MAD/mois) + toggle été différent ; raccordement ;
    # adresse ; pin GPS. Toute valeur invalide est ignorée (jamais d'erreur).
    facture_hiver = _clean_decimal(
        data.get('factureHiver', data.get('facture_hiver')))
    if facture_hiver is not None:
        fields['facture_hiver'] = facture_hiver
    facture_ete = _clean_decimal(
        data.get('factureEte', data.get('facture_ete')))
    if facture_ete is not None:
        fields['facture_ete'] = facture_ete
    if 'eteDifferente' in data or 'ete_differente' in data:
        fields['ete_differente'] = bool(
            data.get('eteDifferente', data.get('ete_differente')))
    raccordement = data.get('raccordement')
    if raccordement in Lead.Raccordement.values:
        fields['raccordement'] = raccordement
    adresse = data.get('adresse') or data.get('address')
    if adresse:
        fields['adresse'] = str(adresse).strip() or None
    # GPS : mêmes bornes que _clean_roof_point (lat ∈ [-90,90], lng ∈ [-180,180]).
    gps_lat = _clean_decimal(
        data.get('gpsLat', data.get('gps_lat')), lo=-90, hi=90)
    if gps_lat is not None:
        fields['gps_lat'] = gps_lat
    gps_lng = _clean_decimal(
        data.get('gpsLng', data.get('gps_lng')), lo=-180, hi=180)
    if gps_lng is not None:
        fields['gps_lng'] = gps_lng

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
            # Re-POST idempotent (< 1 min) : on COMPLÈTE sans jamais écraser une
            # donnée déjà captée. Un second payload plus pauvre (champ absent →
            # None/'') ne doit pas annuler ce que le premier a rempli. On
            # n'écrit donc que les valeurs réellement renseignées.
            for key, value in fields.items():
                if value is None or value == '':
                    continue
                setattr(existing, key, value)
            existing.save()
            lead, created = existing, False
            # Trace la mise à jour idempotente dans le chatter (les champs ont
            # pu être écrasés par le re-POST du site dans la fenêtre < 1 min).
            LeadActivity.objects.create(
                company=lead.company, lead=lead, user=None,
                kind=LeadActivity.Kind.NOTE,
                body='Mis à jour via le site web (doublon < 1 min)',
            )
        else:
            # Responsable par défaut de la société (Paramètres) si configuré.
            from .services import default_responsable_for
            fields.setdefault('owner', default_responsable_for(company))
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
