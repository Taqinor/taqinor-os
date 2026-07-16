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

import hashlib
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
from core.idempotency import dedupe_event

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
    # QW2 — la landing page de première visite est une donnée d'attribution :
    # protégée à l'identique de l'UTM/fbclid sur un visiteur revenant.
    'page',
])


#: QW9 — Tolérance de dérive d'horloge pour l'en-tête `X-Webhook-Timestamp`
#: (déjà émis par le site — lib/lead.ts + proposition-track.ts). Une requête
#: dont l'horodatage dépasse cette tolérance (rejeu capturé) est rejetée ;
#: l'ABSENCE de l'en-tête (anciens workers) reste tolérée — jamais bloquant.
WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS = 600


def _freshness_ok(request) -> bool:
    """QW9 — Rejette un rejeu capturé via l'horodatage `X-Webhook-Timestamp`.

    Tolérant de l'ABSENCE de l'en-tête (anciens workers du site, ou tout appel
    qui ne le fournit pas) — dans ce cas on laisse passer (comportement actuel
    préservé). Seul un en-tête PRÉSENT mais hors tolérance (> ~10 min, passé
    OU futur) est rejeté. Une valeur non parsable est traitée comme absente
    (jamais bloquant sur un format inattendu)."""
    raw = request.headers.get('X-Webhook-Timestamp', '')
    if not raw:
        return True
    ts = parse_datetime(raw)
    if ts is None:
        return True
    if timezone.is_naive(ts):
        ts = timezone.make_aware(ts, timezone.utc)
    skew = abs((timezone.now() - ts).total_seconds())
    return skew <= WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS


def _secret_ok(request) -> bool:
    expected = getattr(settings, 'WEBSITE_LEAD_WEBHOOK_SECRET', '') or ''
    provided = request.headers.get('X-Webhook-Secret', '')
    if not expected:
        # Pas de secret configuré → endpoint fermé (jamais ouvert par défaut)
        return False
    return hmac.compare_digest(expected, provided)


def _resolve_company():
    """Résolution serveur du tenant pour ce webhook public (jamais reçue du
    corps de requête). ``WEBSITE_LEADS_COMPANY_ID`` DOIT être posé en prod dès
    qu'une 2e ``Company`` existe (QXG5, gated ops check) : sans elle, le repli
    ci-dessous (1re Company par pk) est ARBITRAIRE et peut router
    silencieusement un lead vers le mauvais tenant.

    QXG5 (code guard) : on ne casse jamais l'endpoint (le repli reste "safe",
    jamais bloquant — « jamais perdre un lead »), mais on lève un
    ``logger.error`` LOUD dès que la config est ambiguë, pour qu'un défaut de
    configuration prod soit visible (logs/alerting) plutôt que silencieux."""
    company_id = getattr(settings, 'WEBSITE_LEADS_COMPANY_ID', None)
    if company_id:
        company = Company.objects.filter(pk=company_id).first()
        if company is None:
            logger.error(
                "_resolve_company: WEBSITE_LEADS_COMPANY_ID=%r ne correspond "
                "à aucune Company — vérifier la configuration prod.",
                company_id,
            )
        return company
    total = Company.objects.count()
    fallback = Company.objects.order_by('pk').first()
    if total > 1:
        logger.error(
            "_resolve_company: WEBSITE_LEADS_COMPANY_ID n'est pas configuré "
            "et %d Company existent — repli ARBITRAIRE sur la 1re (pk=%s). "
            "Risque de routage silencieux vers le mauvais tenant : poser "
            "WEBSITE_LEADS_COMPANY_ID en prod (QXG5).",
            total, getattr(fallback, 'pk', None),
        )
    return fallback


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
# Le site émet mode ∈ {residentiel, professionnel, agricole} (lead.ts
# LEAD_MODES) : 'professionnel' était ABSENT de cette table → chaque lead
# pro perdait silencieusement son type_installation. Rapproché
# d'« industriel » (même segment pro que l'alias EN 'industrial').
_MARKET_MODE_ALIASES = {
    'residentiel': 'residentiel',
    'residential': 'residentiel',
    'commercial': 'commercial',
    'industriel': 'industriel',
    'industrial': 'industriel',
    'professionnel': 'industriel',
    'professional': 'industriel',
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


#: Quote-journey — clés autorisées de `estimateShown` (les chiffres montrés
#: au visiteur). Whitelist CÔTÉ SERVEUR : le corps de requête n'est jamais
#: copié tel quel dans Lead.web_estimate.
_ESTIMATE_SHOWN_KEYS = frozenset([
    'kwc', 'prodKwh',
    'ecoMadMonthLow', 'ecoMadMonthHigh',
    'ecoMadYearLow', 'ecoMadYearHigh',
    'paybackLabel', 'tauxAutoconso', 'tauxCouverture',
    'pompeCv', 'champKwc', 'm3Jour',
])


def _clean_estimate_shown(raw):
    """`estimateShown` du site → dict whitelisté pour Lead.web_estimate.

    Ne garde que les clés connues (_ESTIMATE_SHOWN_KEYS) avec des valeurs
    scalaires (nombre, ou chaîne courte pour paybackLabel) — tout le reste
    (clés inconnues, dict/list/bool/None) est silencieusement ignoré, dans
    le style tolérant du webhook (jamais d'erreur)."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key, value in raw.items():
        if key not in _ESTIMATE_SHOWN_KEYS:
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            out[key] = value
        elif isinstance(value, str):
            value = value.strip()[:120]
            if value:
                out[key] = value
    return out


def _extract_web_questionnaire(data):
    """Nouveaux champs du questionnaire quote-journey (pro/agricole) du site
    → dict snake_case nettoyé, clés alignées sur le vocabulaire etude_params
    du générateur. Style tolérant du webhook : toute valeur invalide ou hors
    bornes est ignorée — jamais d'erreur.

    ``_map_payload_to_fields`` consomme ensuite les clés qui RÉUTILISENT une
    colonne Lead existante (hmt_m/debit_souhaite_m3h/pompe_cv_actuelle →
    pompe_*, pro_monthly_kwh/pro_monthly_mad → bill_kwh/facture_hiver) ; le
    reste va dans Lead.web_questionnaire."""
    out = {}

    def _num(camel, snake, lo=0, hi=None):
        val = _clean_decimal(data.get(camel, data.get(snake)), lo=lo, hi=hi)
        if val is not None:
            out[snake] = val

    def _choice(camel, snake, values):
        val = _clean_choice(data.get(camel, data.get(snake)), values)
        if val is not None:
            out[snake] = val

    # ── Mode PROFESSIONNEL ──
    # NB : `tensionRaccordement` (bt/mt = basse/moyenne tension) n'est PAS
    # Lead.raccordement (monophase/triphase) — vocabulaires distincts.
    _choice('tensionRaccordement', 'tension_raccordement', ('bt', 'mt'))
    _num('puissanceKva', 'puissance_kva', hi=100000)
    _choice('activityProfile', 'activity_profile',
            ('day', 'day_evening', 'continuous'))
    # `surfaceType` inclut ombrière/terrain : PAS Lead.type_toiture (taxonomie
    # toiture pure) ni surface_toiture_m2 (la surface peut être au sol).
    _choice('surfaceType', 'surface_type',
            ('bac_acier', 'terrasse', 'ombriere', 'terrain'))
    _num('surfaceM2', 'surface_m2', hi=1000000)
    has_gen = data.get('hasGenerator', data.get('has_generator'))
    if isinstance(has_gen, bool):
        out['has_generator'] = has_gen
    _num('proMonthlyKwh', 'pro_monthly_kwh')
    _num('proMonthlyMad', 'pro_monthly_mad')

    # ── Mode AGRICOLE (pompage) ──
    _choice('waterSource', 'water_source',
            ('puits', 'forage', 'bassin', 'riviere'))
    _num('profondeurM', 'profondeur_m', hi=2000)
    _num('hmtM', 'hmt_m', hi=2000)
    _num('debitM3h', 'debit_souhaite_m3h', hi=100000)
    _num('besoinM3j', 'besoin_m3j', hi=1000000)
    _num('heuresPompage', 'heures_pompage', hi=24)
    _choice('irrigation', 'irrigation',
            ('goutte', 'aspersion', 'gravitaire'))
    culture = data.get('culture')
    if culture not in (None, ''):
        culture = str(culture).strip()[:120]
        if culture:
            out['culture'] = culture
    _num('surfaceHa', 'surface_ha', hi=1000000)
    _choice('pompeActuelle', 'pompe_actuelle',
            ('aucune', 'diesel', 'butane', 'electrique'))
    _num('pompeCvActuelle', 'pompe_cv_actuelle', hi=10000)
    _num('fuelSpendMad', 'fuel_spend_mad')
    return out


def _fmt_qn_number(val):
    """Format FR compact d'un nombre du questionnaire pour le chatter
    (7.5 → '7,5' ; 2500 → '2 500'). Jamais d'erreur : une valeur non
    numérique est rendue telle quelle."""
    try:
        num = float(val)
    except (TypeError, ValueError):
        return str(val)
    if num == int(num):
        return f'{int(num):,}'.replace(',', ' ')
    return f'{num:g}'.replace('.', ',')


def _build_questionnaire_note(questionnaire, estimate, type_installation):
    """Résumé chatter FR compact du questionnaire web — réponses FOURNIES
    uniquement — suivi des chiffres montrés au visiteur (web_estimate).

    ``questionnaire`` est le dict COMPLET extrait du payload (y compris les
    réponses mappées sur des colonnes Lead : HMT, débit, CV pompe…), pour que
    le commercial voie tout d'un coup d'œil sans ouvrir chaque champ."""
    fmt = _fmt_qn_number
    parts = []

    # Agricole (pompage) — ordre : source d'eau → hydraulique → usage → pompe.
    water = questionnaire.get('water_source')
    if water:
        parts.append({'riviere': 'rivière'}.get(water, water))
    if questionnaire.get('profondeur_m') is not None:
        parts.append(f"profondeur {fmt(questionnaire['profondeur_m'])} m")
    if questionnaire.get('hmt_m') is not None:
        parts.append(f"HMT {fmt(questionnaire['hmt_m'])} m")
    if questionnaire.get('debit_souhaite_m3h') is not None:
        parts.append(f"{fmt(questionnaire['debit_souhaite_m3h'])} m³/h")
    if questionnaire.get('besoin_m3j') is not None:
        parts.append(f"besoin {fmt(questionnaire['besoin_m3j'])} m³/j")
    if questionnaire.get('heures_pompage') is not None:
        parts.append(f"{fmt(questionnaire['heures_pompage'])} h/j")
    irrigation = questionnaire.get('irrigation')
    if irrigation:
        parts.append({'goutte': 'goutte-à-goutte'}.get(irrigation, irrigation))
    if questionnaire.get('culture'):
        parts.append(f"culture {questionnaire['culture']}")
    if questionnaire.get('surface_ha') is not None:
        parts.append(f"{fmt(questionnaire['surface_ha'])} ha")
    pompe = questionnaire.get('pompe_actuelle')
    pompe_cv = questionnaire.get('pompe_cv_actuelle')
    if pompe == 'aucune':
        parts.append('aucune pompe actuelle')
    elif pompe:
        label = {'electrique': 'électrique'}.get(pompe, pompe)
        cv_txt = f" {fmt(pompe_cv)} CV" if pompe_cv is not None else ''
        parts.append(f"pompe {label}{cv_txt}")
    elif pompe_cv is not None:
        parts.append(f"pompe actuelle {fmt(pompe_cv)} CV")
    if questionnaire.get('fuel_spend_mad') is not None:
        parts.append(
            f"carburant {fmt(questionnaire['fuel_spend_mad'])} MAD/mois")

    # Professionnel — ordre : raccordement → activité → surface → énergie.
    tension = questionnaire.get('tension_raccordement')
    if tension:
        parts.append({'bt': 'raccordement BT', 'mt': 'raccordement MT'}.get(
            tension, tension))
    if questionnaire.get('puissance_kva') is not None:
        parts.append(f"{fmt(questionnaire['puissance_kva'])} kVA")
    activity = questionnaire.get('activity_profile')
    if activity:
        parts.append({
            'day': 'activité de jour',
            'day_evening': 'activité jour + soirée',
            'continuous': 'activité 24h/24',
        }.get(activity, activity))
    surface_type = questionnaire.get('surface_type')
    if surface_type:
        parts.append({'bac_acier': 'bac acier', 'ombriere': 'ombrière'}.get(
            surface_type, surface_type))
    if questionnaire.get('surface_m2') is not None:
        parts.append(f"{fmt(questionnaire['surface_m2'])} m²")
    has_gen = questionnaire.get('has_generator')
    if has_gen is True:
        parts.append('groupe électrogène présent')
    elif has_gen is False:
        parts.append('sans groupe électrogène')
    if questionnaire.get('pro_monthly_kwh') is not None:
        parts.append(f"{fmt(questionnaire['pro_monthly_kwh'])} kWh/mois")
    if questionnaire.get('pro_monthly_mad') is not None:
        parts.append(f"{fmt(questionnaire['pro_monthly_mad'])} MAD/mois")

    est_parts = []
    if estimate.get('kwc') is not None:
        est_parts.append(f"{fmt(estimate['kwc'])} kWc")
    if estimate.get('prodKwh') is not None:
        est_parts.append(f"{fmt(estimate['prodKwh'])} kWh/an")
    eco_low = estimate.get('ecoMadMonthLow')
    eco_high = estimate.get('ecoMadMonthHigh')
    if eco_low is not None and eco_high is not None:
        est_parts.append(f"économie {fmt(eco_low)}–{fmt(eco_high)} MAD/mois")
    elif eco_low is not None or eco_high is not None:
        eco = eco_low if eco_low is not None else eco_high
        est_parts.append(f"économie {fmt(eco)} MAD/mois")
    if estimate.get('paybackLabel'):
        est_parts.append(str(estimate['paybackLabel']))
    if estimate.get('tauxAutoconso') is not None:
        est_parts.append(f"autoconsommation {fmt(estimate['tauxAutoconso'])} %")
    if estimate.get('tauxCouverture') is not None:
        est_parts.append(f"couverture {fmt(estimate['tauxCouverture'])} %")
    if estimate.get('pompeCv') is not None:
        est_parts.append(f"pompe {fmt(estimate['pompeCv'])} CV")
    if estimate.get('champKwc') is not None:
        est_parts.append(f"champ {fmt(estimate['champKwc'])} kWc")
    if estimate.get('m3Jour') is not None:
        est_parts.append(f"{fmt(estimate['m3Jour'])} m³/j")

    mode = type_installation or 'web'
    body = f"Questionnaire web ({mode}) : " + ' · '.join(parts)
    if est_parts:
        body += ' — Estimation montrée : ' + ', '.join(est_parts)
    return body


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
    # QW1 — le site émet aussi `langue_preferee` (lead.ts:LEAD_LANGS = fr/ar),
    # à lire EN PLUS de langue/language/lang (jamais ce seul champ ignoré).
    langue = (data.get('langue_preferee') or data.get('langue')
              or data.get('language') or data.get('lang'))
    if langue not in (None, ''):
        mapped_langue = _LANGUE_ALIASES.get(str(langue).strip().lower())
        if mapped_langue:
            fields['langue_preferee'] = mapped_langue
    # Distributeur d'électricité (ONEE/Lydec/Redal/autre).
    # QW1 — le site envoie 'inconnu' (DISTRIBUTEURS de lead.ts) : vocabulaire
    # à rapprocher de Lead.Distributeur.AUTRE (jamais silencieusement jeté).
    distributeur = _clean_choice(
        data.get('distributeur', data.get('utility')),
        list(Lead.Distributeur.values) + ['inconnu'])
    if distributeur == 'inconnu':
        distributeur = Lead.Distributeur.AUTRE
    if distributeur is not None:
        fields['distributeur'] = distributeur
    # Âge de la toiture (années, bornes plausibles 0–200).
    # QW1 — le site envoie `roofAgeYears` (lead.ts), pas seulement `roofAge`.
    roof_age = _clean_decimal(
        data.get('roofAgeYears', data.get('roofAge', data.get('roof_age'))),
        lo=0, hi=200)
    if roof_age is not None:
        fields['roof_age'] = int(roof_age)
    # Propriétaire / locataire / décideur.
    # QW1 — le site envoie `occupantType` (OCCUPANT_TYPES: proprietaire/
    # locataire/decideur) ; le webhook ne lisait que `ownership`, un vocabulaire
    # différent. 'decideur' (locataire mais décideur des travaux) est rapproché
    # de PROPRIETAIRE (décide des travaux), jamais jeté.
    ownership = _clean_choice(
        data.get('occupantType', data.get('ownership')),
        list(Lead.Ownership.values) + ['decideur'])
    if ownership == 'decideur':
        ownership = Lead.Ownership.PROPRIETAIRE
    if ownership is not None:
        fields['ownership'] = ownership
    # Horizon du projet.
    # QW1 — le site envoie `projectTiming` (PROJECT_TIMINGS: maintenant/3mois/
    # renseignement), un vocabulaire DIFFÉRENT du `Lead.ProjectTimeline`
    # (immediat/3_mois/6_mois/plus_tard) — mappé explicitement ci-dessous
    # (jamais silencieusement jeté, jamais un simple alias 1:1).
    _PROJECT_TIMING_ALIASES = {
        'maintenant': Lead.ProjectTimeline.IMMEDIAT,
        '3mois': Lead.ProjectTimeline.MOINS_3_MOIS,
        'renseignement': Lead.ProjectTimeline.PLUS_TARD,
    }
    timeline_raw = data.get('projectTiming', data.get(
        'projectTimeline', data.get('project_timeline')))
    if timeline_raw not in (None, ''):
        mapped_timeline = _PROJECT_TIMING_ALIASES.get(str(timeline_raw).strip().lower())
        if mapped_timeline is None:
            # Rétro-compat : accepte aussi directement le vocabulaire CRM
            # (`projectTimeline`/`project_timeline` historique).
            mapped_timeline = _clean_choice(
                timeline_raw, Lead.ProjectTimeline.values)
        if mapped_timeline:
            fields['project_timeline'] = mapped_timeline
    # Intention de financement.
    # QW1 — le site envoie `financingIntent` en FR (comptant/financement/
    # indecis) ; `Lead.FinancingIntent` utilise cash/credit/indecis — mappé
    # explicitement (jamais un simple alias qui silencieusement jette
    # comptant/financement).
    _FINANCING_INTENT_ALIASES = {
        'comptant': Lead.FinancingIntent.CASH,
        'financement': Lead.FinancingIntent.CREDIT,
        'indecis': Lead.FinancingIntent.INDECIS,
    }
    financing_raw = data.get('financingIntent', data.get('financing_intent'))
    if financing_raw not in (None, ''):
        mapped_financing = _FINANCING_INTENT_ALIASES.get(str(financing_raw).strip().lower())
        if mapped_financing is None:
            mapped_financing = _clean_choice(
                financing_raw, Lead.FinancingIntent.values)
        if mapped_financing:
            fields['financing_intent'] = mapped_financing
    # Charges futures prévues (clim / VE / pompe).
    futures = _clean_futures_charges(
        data.get('futuresCharges', data.get('futures_charges',
                                            data.get('futureLoads'))))
    if futures is not None:
        fields['futures_charges'] = futures
    # QW1 — Ombrage déclaré par le client (lead.ts OMBRAGES = aucun/partiel/
    # important) : vocabulaire identique à `Lead.Ombrage` — champ auparavant
    # totalement omis du mapping.
    ombrage = _clean_choice(data.get('ombrage'), Lead.Ombrage.values)
    if ombrage is not None:
        fields['ombrage'] = ombrage
    # QW1 — Intérêt batterie (lead.ts `batteryInterest`, booléen) → le champ
    # de qualification le plus proche existant, `Lead.batterie_souhaitee`
    # (auparavant totalement omis du mapping).
    if 'batteryInterest' in data or 'battery_interest' in data:
        interest = data.get('batteryInterest', data.get('battery_interest'))
        if isinstance(interest, bool):
            fields['batterie_souhaitee'] = (
                Lead.BatterieSouhaitee.AVEC if interest
                else Lead.BatterieSouhaitee.SANS)

    # ── QW2 — Champs du site sans colonne d'accueil (additifs, tolérants) ──
    # Mode PROFESSIONNEL (WJ68) : raison sociale RÉUTILISE `societe` (jamais
    # de colonne `raison_sociale` dédiée — consigne founder).
    raison_sociale = data.get('raisonSociale') or data.get('raison_sociale')
    if raison_sociale:
        fields['societe'] = str(raison_sociale).strip()[:255] or None
    facility_type = _clean_choice(
        data.get('facilityType', data.get('facility_type')),
        Lead.FacilityType.values)
    if facility_type is not None:
        fields['facility_type'] = facility_type
    site_count = _clean_choice(
        data.get('siteCount', data.get('site_count')), Lead.SiteCount.values)
    if site_count is not None:
        fields['site_count'] = site_count
    # Créneau de visite technique préféré (statique).
    visit_window_part = _clean_choice(
        data.get('visitWindowPart', data.get('visit_window_part')),
        Lead.VisitWindowPart.values)
    if visit_window_part is not None:
        fields['visit_window_part'] = visit_window_part
    visit_window_week = _clean_choice(
        data.get('visitWindowWeek', data.get('visit_window_week')),
        Lead.VisitWindowWeek.values)
    if visit_window_week is not None:
        fields['visit_window_week'] = visit_window_week
    # Référence courte générée côté client — anti-garbage minimal (le format
    # émis par buildClientRef() côté site : lettres/chiffres/tirets, 4-24).
    client_ref_raw = data.get('clientRef') or data.get('client_ref')
    if client_ref_raw:
        candidate = str(client_ref_raw).strip()[:24]
        import re as _re_ref
        if _re_ref.match(r'^[A-Za-z0-9-]{4,24}$', candidate):
            fields['client_ref'] = candidate
    # Diaspora/MRE : numéro E.164 étranger (indicatif ≠ 212).
    if 'phoneIsForeign' in data or 'phone_is_foreign' in data:
        foreign = data.get('phoneIsForeign', data.get('phone_is_foreign'))
        if isinstance(foreign, bool):
            fields['phone_is_foreign'] = foreign
    # Landing page de première visite (first-touch, protégée comme l'UTM).
    page = data.get('page')
    if page:
        fields['page'] = str(page).strip()[:300] or None

    # QW3 — Préférence de contact EXPLICITE (« WhatsApp uniquement » / « Rappel
    # téléphonique OK »), DISTINCTE de `whatsapp_opt_in` (consentement
    # marketing) et de `canal` (canal marketing d'ORIGINE, toujours SITE_WEB
    # ci-dessus pour ce webhook — jamais réécrit par cette préférence).
    contact_preference = _clean_choice(
        data.get('contactPreference', data.get('contact_preference')),
        Lead.ContactPreference.values)
    if contact_preference is not None:
        fields['contact_preference'] = contact_preference
        # QX15 — horodate la POSE de la préférence (distinct de
        # date_creation) : le SLA rappel doit mesurer depuis ce moment, pas
        # depuis la création du lead (couche 2 dédup — visiteur revenant).
        fields['contact_preference_set_at'] = timezone.now()

    # ── Quote-journey — questionnaire pro/agricole + estimation montrée ──
    # RÉUTILISE d'abord les colonnes Lead existantes (pompage, profil
    # énergie) ; seul le RESTE atterrit dans web_questionnaire. Les clés kWh/
    # MAD pro ne remplissent bill_kwh/facture_hiver que si le payload ne les
    # a pas déjà posées explicitement (billKwh/factureHiver priment) — dans
    # ce cas la réponse reste visible dans web_questionnaire.
    questionnaire = _extract_web_questionnaire(data)
    if questionnaire:
        hmt = questionnaire.pop('hmt_m', None)
        if hmt is not None:
            fields['pompe_hmt_m'] = hmt
        debit = questionnaire.pop('debit_souhaite_m3h', None)
        if debit is not None:
            fields['pompe_debit_m3h'] = debit
        pompe_cv = questionnaire.pop('pompe_cv_actuelle', None)
        if pompe_cv is not None:
            fields['pompe_cv'] = pompe_cv
        if 'bill_kwh' not in fields:
            pro_kwh = questionnaire.pop('pro_monthly_kwh', None)
            if pro_kwh is not None:
                fields['bill_kwh'] = pro_kwh
        if 'facture_hiver' not in fields:
            pro_mad = questionnaire.pop('pro_monthly_mad', None)
            if pro_mad is not None:
                fields['facture_hiver'] = pro_mad
        if questionnaire:
            fields['web_questionnaire'] = questionnaire
    estimate = _clean_estimate_shown(
        data.get('estimateShown', data.get('estimate_shown')))
    if estimate:
        fields['web_estimate'] = estimate

    if fields['whatsapp_opt_in'] and fields['telephone']:
        fields['whatsapp'] = fields['telephone']
    # Sous le seuil (ne devrait pas arriver — le site filtre) : étiqueté.
    if data.get('qualified') is False:
        fields['tags'] = 'Sous le seuil 1 000 MAD'
    return fields


def _map_and_link_lead(raw, data, company):
    """QX16 — Cœur du mapping payload → Lead (création/mise à jour, dédup,
    tous les effets de bord best-effort), factorisé hors de la vue pour être
    réutilisable par le REJEU (``replay_website_lead_payload``) sans dupliquer
    la logique. Persiste ``raw.lead``/``raw.processed`` et renvoie
    ``(lead, created, detail)``. Laisse toute exception se propager — les
    appelants (vue webhook, action replay) décident comment la consigner sur
    ``raw.error``."""
    fields = _map_payload_to_fields(data)
    telephone = fields.get('telephone') or ''
    email = fields.get('email') or ''

    # QW10 — Garde CONCURRENTE via `idempotencyKey` (lib/lead.ts — jeton
    # généré côté navigateur à l'ouverture de la session de saisie).
    # `cache.add` est atomique : deux POSTs simultanés avec la MÊME clé ne
    # peuvent jamais tous les deux se croire « premiers » — la requête
    # PERDANTE attend brièvement que la gagnante commite son lead, puis
    # rejoint la dédup téléphone/email normale ci-dessous (jamais de
    # logique de fusion dupliquée). Best-effort : sans clé (anciens
    # workers) ou cache indisponible, comportement inchangé (couches 1/2
    # restent la seule protection).
    idempotency_key = str(
        data.get('idempotencyKey') or data.get('idempotency_key') or ''
    ).strip()[:64]
    if idempotency_key:
        try:
            import time as _time

            from django.core.cache import cache
            cache_key = f'qw10-idem:{company.pk}:{idempotency_key}'
            won = cache.add(cache_key, True, DEDUP_WINDOW_SECONDS)
            if not won:
                # Perdant de la course : laisse une chance à la requête
                # gagnante de commiter avant la recherche de doublon
                # ci-dessous (best-effort, jamais un blocage long).
                _time.sleep(0.15)
        except Exception:  # noqa: BLE001 — cache indisponible : no-op
            pass

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
        # YLEAD11 — une nouvelle touche sur un lead PERDU/COLD le
        # réactive (lève perdu, repositionne NEW/CONTACTED avance-seul).
        try:
            from .services import reactivate_lead_on_new_touch
            reactivate_lead_on_new_touch(lead, source='site web')
        except Exception as _exc:  # noqa: BLE001 — best-effort
            logger.warning(
                'website_lead_webhook: réactivation échouée (lead #%s) : %s',
                lead.pk, _exc)
        # QX14 — TOUS les autres chemins de création/mise à jour de lead
        # persistent le score via recompute_lead_score (views.py 561/574,
        # services.py 1088/1366/1429/2782) SAUF ce webhook — le score
        # jamais persisté casse silencieusement `?ordering=-score` et
        # `maybe_assign_mql` (XMKT21) pour la source #1 (site web).
        # Best-effort, même patron que les blocs ci-dessus.
        try:
            from .services import recompute_lead_score
            recompute_lead_score(lead)
        except Exception as _exc:  # noqa: BLE001 — best-effort
            logger.warning(
                'website_lead_webhook: recompute_lead_score échoué '
                '(lead #%s) : %s', lead.pk, _exc)
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
        # QX14 — même correctif côté création (voir commentaire ci-dessus,
        # branche mise à jour) : persiste le score dès la première visite.
        try:
            from .services import recompute_lead_score
            recompute_lead_score(lead)
        except Exception as _exc:  # noqa: BLE001 — best-effort
            logger.warning(
                'website_lead_webhook: recompute_lead_score échoué '
                '(lead #%s) : %s', lead.pk, _exc)
        # Quote-journey — visibilité commerciale immédiate : UNE note chatter
        # automatique résumant le questionnaire web (pro/agricole) + les
        # chiffres montrés au visiteur. Le dict COMPLET est repris du payload
        # (y compris les réponses déjà mappées sur des colonnes : HMT, débit,
        # CV pompe…). Même patron que les autres notes du webhook (company du
        # lead, user=None — attribution serveur). Best-effort : une note en
        # échec ne remet jamais le lead en cause.
        try:
            questionnaire_full = _extract_web_questionnaire(data)
            if questionnaire_full:
                LeadActivity.objects.create(
                    company=lead.company, lead=lead, user=None,
                    kind=LeadActivity.Kind.NOTE,
                    body=_build_questionnaire_note(
                        questionnaire_full,
                        fields.get('web_estimate') or {},
                        fields.get('type_installation')),
                )
        except Exception as _exc:  # noqa: BLE001 — best-effort
            logger.warning(
                'website_lead_webhook: note questionnaire échouée '
                '(lead #%s) : %s', lead.pk, _exc)

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

    # QW4 — rappel demandé (contact_preference=phone_ok) : notification
    # DISTINCTE et plus urgente qu'un lead générique, sur création ET
    # mise à jour (un visiteur revenant peut poser sa préférence après
    # coup). Idempotent (marqueur chatter) — jamais best-effort bloquant.
    try:
        from .services import notify_lead_callback_requested
        notify_lead_callback_requested(lead)
    except Exception as _exc:  # noqa: BLE001 — best-effort
        logger.warning(
            'website_lead_webhook: notify_lead_callback_requested échoué '
            '(lead #%s) : %s', lead.pk, _exc)

    # QX35 — lien de parrainage (`utm_source=parrainage`, le code du
    # parrain porté par `utm_campaign` — voir parrainage.astro) : crée
    # un Parrainage `en_attente` rattaché au filleul + notifie les
    # managers. Idempotent (un seul Parrainage par filleul_lead) —
    # best-effort, jamais bloquant pour la capture du lead.
    try:
        from .services import handle_parrainage_signup
        handle_parrainage_signup(lead)
    except Exception as _exc:  # noqa: BLE001 — best-effort
        logger.warning(
            'website_lead_webhook: handle_parrainage_signup échoué '
            '(lead #%s) : %s', lead.pk, _exc)

    raw.lead = lead
    raw.processed = True
    raw.save(update_fields=['lead', 'processed'])
    if created:
        detail = 'Lead créé.'
    elif is_window_dedup:
        detail = 'Lead mis à jour (doublon < 1 min).'
    else:
        detail = 'Lead existant mis à jour (visiteur revenant).'
    return lead, created, detail


@csrf_exempt
@require_POST
def website_lead_webhook(request):
    if not _secret_ok(request):
        return JsonResponse({'detail': 'Secret invalide ou absent.'}, status=401)
    if not _freshness_ok(request):
        # QW9 — horodatage hors tolérance : rejeu probable d'une requête
        # capturée. Rejeté AVANT toute écriture (même le brut n'est pas
        # stocké — un rejeu n'apporte aucune donnée nouvelle à conserver).
        return JsonResponse({'detail': 'Horodatage hors tolérance.'}, status=401)

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

    # QW7 — Ping d'engagement proposition (WJ55 : proposition-track.ts POSTe
    # {qualified:false, event_type, phoneE164, utm, page} vers CE MÊME webhook).
    # [Défensif — le correctif principal est côté source, WEB_PLAN WJ109.]
    # Un simple "le client a ouvert sa proposition" ne doit JAMAIS créer de
    # lead ni écraser nom/tags/utm/canal d'un lead déjà existant retrouvé par
    # téléphone — seule une note chatter + notification best-effort est
    # journalisée sur le lead déjà connu. Sans lead correspondant, l'événement
    # est silencieusement abandonné (jamais de lead fantôme « Lead site web »).
    event_type = data.get('event_type')
    if event_type:
        try:
            phone_raw = str(data.get('phoneE164') or data.get('phone') or '').strip()[:50]
            from apps.crm.services import normalize_phone
            phone_key = normalize_phone(phone_raw)
            matched = None
            if phone_key:
                for candidate in Lead.objects.filter(company=company):
                    if normalize_phone(candidate.telephone) == phone_key:
                        matched = candidate
                        break
            if matched is not None:
                LeadActivity.objects.create(
                    company=matched.company, lead=matched, user=None,
                    kind=LeadActivity.Kind.NOTE,
                    body=f'Engagement proposition : {event_type}',
                )
            raw.lead = matched
            raw.processed = True
            raw.save(update_fields=['lead', 'processed'])
        except Exception:  # noqa: BLE001 — un ping d'engagement ne doit
            # jamais faire échouer le webhook ni polluer le lead.
            logger.exception(
                'website_lead_webhook: engagement ping (event_type=%s) échoué', event_type)
        return JsonResponse(
            {'detail': 'Événement enregistré (sans mutation de lead).',
             'payload_id': raw.pk}, status=200)

    # YDATA12 — dédup DUR (contrainte unique DB, insérée AVANT tout effet)
    # en plus des couches 1/2 (téléphone/email) et de la garde cache QW10
    # ci-dessus : un event_id fourni par l'émetteur (idempotencyKey), sinon
    # un hash déterministe du payload normalisé. Le brut (raw) est déjà
    # stocké au-dessus, quoi qu'il arrive — seule la CRÉATION DE LEAD est
    # court-circuitée sur un doublon détecté.
    event_id = str(
        data.get('idempotencyKey') or data.get('idempotency_key') or ''
    ).strip()[:64]
    if not event_id:
        canonical = json.dumps(data, default=str, sort_keys=True).encode('utf-8')
        event_id = hashlib.sha256(canonical).hexdigest()
    if not dedupe_event(
            company=company, source='crm.website_lead', event_id=event_id):
        raw.processed = True
        raw.save(update_fields=['processed'])
        return JsonResponse(
            {'detail': 'Événement déjà traité (dédupliqué).',
             'payload_id': raw.pk}, status=200)

    try:
        lead, created, detail = _map_and_link_lead(raw, data, company)
        return JsonResponse(
            {'detail': detail, 'lead_id': lead.pk, 'payload_id': raw.pk},
            status=201 if created else 200,
        )
    except Exception as exc:  # noqa: BLE001 — la donnée brute prime
        raw.error = f'{type(exc).__name__}: {exc}'
        raw.save(update_fields=['error'])
        logger.exception('website_lead_webhook: mapping échoué (payload #%s)', raw.pk)
        # QX16 — « jamais perdre un lead » (module docstring) ne veut rien
        # dire si personne n'est prévenu : notifie les managers de la société
        # (repli founder) dès qu'un mapping échoue, avec un lien direct vers
        # la surface de rejeu. Best-effort — jamais bloquant pour la réponse
        # HTTP déjà décidée (202, payload conservé).
        try:
            from .services import _company_fallback_managers
            from apps.notifications.services import notify_many
            managers = _company_fallback_managers(company)
            if managers:
                notify_many(
                    managers, 'lead_new',
                    '⚠ Lead site web non mappé — action requise',
                    body=(f'Un payload du site web (#{raw.pk}) n\'a pas pu être '
                          f'converti en lead ({type(exc).__name__}). '
                          'Rejouable depuis Payloads leads site web.'),
                    link='/crm/payloads-site-web',
                    company=company,
                )
        except Exception:  # noqa: BLE001 — best-effort
            logger.warning(
                'website_lead_webhook: notification founder échouée (payload #%s)',
                raw.pk)
        return JsonResponse(
            {'detail': 'Stocké, mapping échoué — payload rejouable.', 'payload_id': raw.pk},
            status=202,
        )


def replay_website_lead_payload(raw):
    """QX16 — Rejoue un ``WebsiteLeadPayload`` non traité/en erreur à travers
    EXACTEMENT le même mapping que le webhook (``_map_and_link_lead``, source
    unique de vérité — jamais une seconde implémentation qui pourrait
    diverger). Résout la société DEPUIS le payload déjà stocké (jamais du
    payload brut re-résolu — ``raw.company`` a été posée côté serveur à la
    réception initiale ; si elle manquait, on retombe sur ``_resolve_company``
    comme le ferait un nouveau POST).

    Renvoie ``(ok: bool, detail: str, lead)``. Ne lève jamais — capte toute
    exception et la consigne sur ``raw.error`` comme le fait la vue webhook,
    pour que le rejeu reste rejouable indéfiniment (jamais une exception
    remontée casse l'appelant HTTP)."""
    company = raw.company or _resolve_company()
    if company is None:
        return False, 'Aucune Company résolue — rejeu impossible.', None
    try:
        lead, created, detail = _map_and_link_lead(raw, raw.payload, company)
        return True, detail, lead
    except Exception as exc:  # noqa: BLE001 — même contrat que la vue webhook
        raw.error = f'{type(exc).__name__}: {exc}'
        raw.save(update_fields=['error'])
        logger.exception(
            'replay_website_lead_payload: mapping échoué (payload #%s)', raw.pk)
        return False, f'Rejeu échoué : {exc}', None


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
