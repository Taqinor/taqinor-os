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
from django.views.decorators.http import require_POST, require_http_methods

from authentication.models import Company

from .models import Lead, LeadActivity, WebsiteLeadPayload

logger = logging.getLogger(__name__)

#: Fenêtre d'idempotence : même téléphone reçu deux fois dans cette fenêtre
#: (relance réseau, double clic) = mise à jour, pas de doublon.
DEDUP_WINDOW_SECONDS = 60

#: Champs d'attribution first-touch préservés sur un visiteur revenant (QJ8).
#: Ces valeurs sont posées au PREMIER contact et ne doivent jamais être écrasées
#: par un re-POST ultérieur (campagne différente du visiteur revenant).
_FIRST_TOUCH_FIELDS = frozenset([
    'fbclid', 'utm_source', 'utm_medium',
    'utm_campaign', 'utm_content', 'utm_term',
])


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


# QK1 — Mode marché du site → Lead.type_installation (tolérant FR/EN).
_MARKET_MODE_ALIASES = {
    'residentiel': 'residentiel',
    'residential': 'residentiel',
    'commercial': 'commercial',
    'industriel': 'industriel',
    'industrial': 'industriel',
    'agricole': 'agricole',
    'agricultural': 'agricole',
    'pompage': 'agricole',
}

# QK1 — Langue du site → Lead.langue_preferee ('fr'/'darija' uniquement).
# L'arabe du site est rapproché du darija (langue des messages WhatsApp).
_LANGUE_ALIASES = {
    'fr': 'fr',
    'darija': 'darija',
    'ar': 'darija',
}


def _clean_choice(raw, values):
    """Normalise une clé de choix (str, lowercase) si elle appartient à
    ``values`` ; sinon None (jamais d'erreur — style tolérant du webhook)."""
    if raw in (None, ''):
        return None
    key = str(raw).strip().lower()
    return key if key in values else None


def _clean_futures_charges(raw):
    """Normalise les charges futures en liste triée de clés autorisées, ou None.

    Accepte une liste (['clim', 've']) OU un dict ({'clim': True, 've': False}).
    Toute clé hors ``Lead.FUTURES_CHARGES_KEYS`` est ignorée silencieusement."""
    allowed = Lead.FUTURES_CHARGES_KEYS
    keys = []
    if isinstance(raw, dict):
        keys = [k for k, v in raw.items() if v]
    elif isinstance(raw, (list, tuple)):
        keys = list(raw)
    else:
        return None
    out = sorted({str(k).strip().lower() for k in keys} & set(allowed))
    return out or None


def _map_payload_to_fields(data: dict) -> dict:
    """Payload du site (lead.ts:LeadRecord) → champs du modèle Lead."""
    band = data.get('band')
    if not isinstance(band, dict):
        band = {}
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
        'email': str(data.get('email') or '').strip()[:254] or None,
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

    # ── QK1 — Ne plus JETER la qualification déjà captée par le site ──
    # Mode marché (Résidentiel/Industriel/Commercial/Agricole) → type_installation.
    market_mode = (data.get('marketMode') or data.get('market_mode')
                   or data.get('mode') or data.get('typeInstallation')
                   or data.get('type_installation'))
    if market_mode not in (None, ''):
        mapped_mode = _MARKET_MODE_ALIASES.get(str(market_mode).strip().lower())
        if mapped_mode:
            fields['type_installation'] = mapped_mode
    # Langue du visiteur (fr/ar/darija) → langue préférée des messages.
    langue = data.get('langue') or data.get('language') or data.get('lang')
    if langue not in (None, ''):
        mapped_langue = _LANGUE_ALIASES.get(str(langue).strip().lower())
        if mapped_langue:
            fields['langue_preferee'] = mapped_langue
    # Distributeur d'électricité (ONEE/Lydec/Redal/autre).
    distributeur = _clean_choice(
        data.get('distributeur', data.get('utility')),
        Lead.Distributeur.values)
    if distributeur is not None:
        fields['distributeur'] = distributeur
    # Âge de la toiture (années, bornes plausibles 0–200).
    roof_age = _clean_decimal(
        data.get('roofAge', data.get('roof_age')), lo=0, hi=200)
    if roof_age is not None:
        fields['roof_age'] = int(roof_age)
    # Propriétaire / locataire.
    ownership = _clean_choice(data.get('ownership'), Lead.Ownership.values)
    if ownership is not None:
        fields['ownership'] = ownership
    # Horizon du projet.
    timeline = _clean_choice(
        data.get('projectTimeline', data.get('project_timeline')),
        Lead.ProjectTimeline.values)
    if timeline is not None:
        fields['project_timeline'] = timeline
    # Intention de financement.
    financing = _clean_choice(
        data.get('financingIntent', data.get('financing_intent')),
        Lead.FinancingIntent.values)
    if financing is not None:
        fields['financing_intent'] = financing
    # Charges futures prévues (clim / VE / pompe).
    futures = _clean_futures_charges(
        data.get('futuresCharges', data.get('futures_charges',
                                            data.get('futureLoads'))))
    if futures is not None:
        fields['futures_charges'] = futures

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
        email = fields.get('email') or ''

        existing = None
        is_window_dedup = False
        # ── Couche 1 : dédup < 60 s (double-clic / relance réseau) ────────────
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
            if existing is not None:
                is_window_dedup = True

        # ── Couche 2 (QJ8) : dédup visiteur revenant — téléphone OU email ─────
        # Si la fenêtre courte n'a rien trouvé, on cherche un lead existant dans
        # la MÊME société par téléphone ou email normalisé (sans limite de temps).
        # Préserve l'attribution first-touch (UTM/fbclid) : jamais écrasée.
        # Périmètre : uniquement `company` — jamais de fusion cross-company.
        # Les leads sans téléphone dédupliquent par email.
        if existing is None:
            from .services import find_duplicates_by_contact
            dupes = find_duplicates_by_contact(
                company, phone=telephone or None, email=email or None)
            # Prend le lead le plus récent (find_duplicates_by_contact retourne
            # une liste non ordonnée — on trie par date_creation desc).
            if dupes:
                dupes_sorted = sorted(
                    dupes, key=lambda lead_: lead_.date_creation, reverse=True)
                existing = dupes_sorted[0]

        if existing:
            # Re-POST ou visiteur revenant : on COMPLÈTE sans jamais écraser une
            # donnée déjà captée. Un second payload plus pauvre (champ absent →
            # None/'') ne doit pas annuler ce que le premier a rempli. On
            # n'écrit donc que les valeurs réellement renseignées.
            # Attribution first-touch (UTM/fbclid) : préservée sur visiteur revenant.
            for key, value in fields.items():
                if value is None or value == '':
                    continue
                # Sur un visiteur revenant (couche 2), l'attribution first-touch
                # du lead existant prime sur celle du nouveau payload.
                if (not is_window_dedup
                        and key in _FIRST_TOUCH_FIELDS
                        and getattr(existing, key, None)):
                    continue
                setattr(existing, key, value)
            existing.save()
            lead, created = existing, False
            # Trace la mise à jour dans le chatter.
            if is_window_dedup:
                chatter_body = 'Mis à jour via le site web (doublon < 1 min)'
            else:
                chatter_body = 'Visiteur revenant : lead existant mis à jour via le site web'
            LeadActivity.objects.create(
                company=lead.company, lead=lead, user=None,
                kind=LeadActivity.Kind.NOTE,
                body=chatter_body,
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
            # QJ2 (a) — speed-to-lead : notifie le owner dès la création.
            try:
                from .services import notify_new_lead
                notify_new_lead(lead)
            except Exception as _exc:  # noqa: BLE001 — best-effort, jamais bloquant
                logger.warning(
                    'website_lead_webhook: notify_new_lead échoué (lead #%s) : %s',
                    lead.pk, _exc)

        # QK6 — photo de facture/compteur/toiture jointe à la capture :
        # attachée au lead (+ OCR si configuré), best-effort — une photo
        # invalide ou un stockage en panne ne remet JAMAIS le lead en cause.
        try:
            from .intake_photo import attach_capture_photo
            attach_capture_photo(lead, data)
        except Exception as _exc:  # noqa: BLE001 — le lead prime sur la photo
            logger.warning(
                'website_lead_webhook: photo non jointe (lead #%s) : %s',
                lead.pk, _exc)

        raw.lead = lead
        raw.processed = True
        raw.save(update_fields=['lead', 'processed'])
        if created:
            detail = 'Lead créé.'
        elif is_window_dedup:
            detail = 'Lead mis à jour (doublon < 1 min).'
        else:
            detail = 'Lead existant mis à jour (visiteur revenant).'
        return JsonResponse(
            {'detail': detail, 'lead_id': lead.pk, 'payload_id': raw.pk},
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


# ── XMKT32 — Sync Meta Lead Ads → leads CRM (gated, API officielle) ──────────
#
# Deux jetons distincts (settings, jamais du corps de requête) :
#   META_LEAD_ADS_VERIFY_TOKEN  — poignée de main GET de Meta (souscription
#                                  du webhook, hub.challenge).
#   META_LEAD_ADS_ACCESS_TOKEN  — token de page utilisé pour APPELER le Graph
#                                  API officiel et récupérer le détail du lead
#                                  (jamais de scraping — Meta ne pousse que
#                                  l'id, pas les données du formulaire).
# Sans jeton configuré : la vérification GET répond 404, et le POST est un
# no-op silencieux (200, rien n'est créé) — jamais d'exception au webhook.


def _meta_lead_ads_company():
    company_id = getattr(settings, 'META_LEAD_ADS_COMPANY_ID', None)
    if company_id:
        return Company.objects.filter(pk=company_id).first()
    return Company.objects.order_by('pk').first()


def fetch_meta_lead_data(leadgen_id, access_token):
    """Récupère le détail d'un lead Meta via le Graph API officiel.

    Isolé dans sa propre fonction pour rester facilement simulable en test
    (monkeypatch) — le test simulé décrit dans XMKT32 n'appelle jamais un
    vrai serveur Meta. Renvoie un dict ``{'field_data': [...]}`` ou lève sur
    échec réseau/HTTP (capté par l'appelant).
    """
    import urllib.request

    url = (f'https://graph.facebook.com/v19.0/{leadgen_id}'
           f'?access_token={access_token}')
    with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
        return json.loads(resp.read().decode('utf-8'))


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def meta_lead_ads_webhook(request):
    verify_token = getattr(settings, 'META_LEAD_ADS_VERIFY_TOKEN', '') or ''
    access_token = getattr(settings, 'META_LEAD_ADS_ACCESS_TOKEN', '') or ''

    if request.method == 'GET':
        # Poignée de main de souscription Meta (Graph API webhooks).
        if not verify_token:
            return JsonResponse({'detail': 'Non configuré.'}, status=404)
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge', '')
        if mode == 'subscribe' and hmac.compare_digest(verify_token, token or ''):
            from django.http import HttpResponse
            return HttpResponse(challenge, content_type='text/plain')
        return JsonResponse({'detail': 'Vérification refusée.'}, status=403)

    # POST — notification de nouveau lead.
    if not access_token:
        # Sans jeton : no-op silencieux (défaut OFF), jamais d'exception.
        logger.info('meta_lead_ads_webhook: aucun access token configuré — no-op.')
        return JsonResponse({'detail': 'Non configuré — ignoré.'}, status=200)

    try:
        data = json.loads(request.body.decode('utf-8'))
        if not isinstance(data, dict):
            raise ValueError('payload non-objet')
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'detail': 'JSON invalide.'}, status=400)

    company = _meta_lead_ads_company()
    if company is None:
        logger.error('meta_lead_ads_webhook: aucune Company résolue.')
        return JsonResponse({'detail': 'Aucune société résolue.'}, status=202)

    created_leads = []
    try:
        entries = data.get('entry') or []
        for entry in entries:
            for change in (entry.get('changes') or []):
                value = change.get('value') or {}
                leadgen_id = value.get('leadgen_id')
                if not leadgen_id:
                    continue
                campaign_name = value.get('campaign_name', '') or ''
                adset_name = value.get('adset_name', '') or ''
                try:
                    lead_data = fetch_meta_lead_data(leadgen_id, access_token)
                except Exception as exc:  # noqa: BLE001 — un lead en échec
                    # ne doit jamais bloquer les autres entrées du batch.
                    logger.warning(
                        'meta_lead_ads_webhook: fetch échoué pour %s : %s',
                        leadgen_id, exc)
                    continue
                field_data = lead_data.get('field_data') or []
                from .services import create_lead_from_meta_lead_ads
                lead = create_lead_from_meta_lead_ads(
                    company=company, leadgen_id=leadgen_id,
                    field_data=field_data, campaign_name=campaign_name,
                    adset_name=adset_name)
                created_leads.append(lead.pk)
        return JsonResponse({'detail': 'Traité.', 'lead_ids': created_leads},
                            status=200)
    except Exception:
        logger.exception('meta_lead_ads_webhook: traitement échoué.')
        return JsonResponse({'detail': 'Erreur de traitement.'}, status=202)
