"""Récepteur des leads du site public taqinor.ma.

Le Worker Cloudflare du site (apps/web — émetteur, jamais modifié ici)
POSTe chaque lead qualifié vers ce endpoint avec un secret statique dans
l'en-tête ``X-Webhook-Secret``. Principes :

1. JAMAIS perdre un lead : la charge utile brute est stockée
   (WebsiteLeadPayload) AVANT toute tentative de mapping.
2. RÈGLE FONDATEUR (18/08/2026) — CHAQUE soumission du site crée un
   NOUVEAU lead, toujours. Plus jamais de fusion silencieuse d'un
   « visiteur revenant » : c'est ainsi qu'un lead de test a disparu dans
   un ancien lead au même e-mail, introuvable pour son auteur. Seule
   subsiste une garde TECHNIQUE anti-rejeu (même téléphone reçu dans les
   60 s : double-clic, relance réseau), qui complète la soumission EN
   COURS. Les rapprochements se font ensuite en VISIBILITÉ — note chatter
   « Doublon possible », bandeaux du rail identité — puis par FUSION
   MANUELLE (``services.merge_leads``), jamais automatiquement.
3. Tenant résolu CÔTÉ SERVEUR (env WEBSITE_LEADS_COMPANY_ID, sinon la
   première Company) — rien ne vient du payload.
4. Un lead SOUS LE SEUIL arrive volontairement (le site transmet
   ``qualified: false`` — apps/web/src/pages/api/capture-lead.ts) : c'est le
   RÉCEPTEUR qui fait le tri. Il est créé et étiqueté comme tout lead (jamais
   rejeté, jamais perdu), mais sa notification d'arrivée porte la mention
   « (sous le seuil) » et l'alerte URGENTE de rappel n'est pas déclenchée —
   le rappel demandé reste visible sur la fiche (préférence de contact + note
   chatter), sans réveiller un commercial pour une facture < 1 000 MAD.
"""

import hashlib
import hmac
import json
import logging
import re
import unicodedata

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods

from authentication.models import Company
from core.idempotency import dedupe_event

from .models import Lead, LeadActivity, WebsiteLeadPayload

logger = logging.getLogger(__name__)

#: Garde TECHNIQUE anti-rejeu (jamais une déduplication métier) : même
#: téléphone reçu deux fois dans cette fenêtre = la MÊME soumission renvoyée
#: (double-clic, relance réseau) → on complète la fiche en cours. Au-delà,
#: toute soumission est un nouveau lead (règle fondateur, cf. docstring).
DEDUP_WINDOW_SECONDS = 60

#: Étiquette posée sur un lead que le SITE a déclaré sous le seuil de facture
#: (``qualified: false``) — une constante depuis que le tri du récepteur
#: s'appuie dessus (étiquetage + notification atténuée).
SOUS_SEUIL_TAG = 'Sous le seuil 1 000 MAD'

#: Ordre fondateur (24/08/2026) — champs GPS protégés contre l'écrasement dans
#: la boucle de complétion anti-rejeu de ``_map_and_link_lead`` : une fois
#: posés, plus jamais remplacés par un renvoi ultérieur de la même soumission
#: (voir le commentaire au point d'usage).
_GPS_FIELDS = ('gps_lat', 'gps_lng')


def _is_sous_seuil(data) -> bool:
    """Le site a-t-il déclaré CETTE soumission sous le seuil de facture ?

    Strictement ``qualified is False`` (jamais « absent » ni « falsy ») : un
    payload sans le drapeau (anciens workers) reste un lead ordinaire."""
    return data.get('qualified') is False


#: WJ124 — régions agronomiques (8 zones FAO) émises par le site
#: (``apps/web/src/lib/lead.ts:REGIONS_AGRICOLES``). SOURCE DE VÉRITÉ :
#: ``apps/ventes/quote_engine/agricole/agronomy.py`` (ET0_MONTHLY) — recopiée
#: ici en constante plain, jamais importée (frontière inter-apps crm↛ventes).
_REGIONS_AGRICOLES = (
    'souss-massa', 'doukkala', 'tadla', 'saiss', 'oriental',
    'draa-tafilalet', 'gharb-loukkos', 'haouz',
)


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
    # Un contour est un POLYGONE : moins de 3 sommets valides n'en est pas un
    # (même règle que validateLead côté tunnel) — ignoré proprement, jamais
    # rangé (le test webhook l'épingle : [[lat, lng]] seul → roof_outline None).
    return out if len(out) >= 3 else None


def _a_un_contour(valeur):
    """Vrai quand ``valeur`` est un contour de toit exploitable (≥ 3 sommets).

    MÊME seuil que ``_clean_roof_outline`` et que le tunnel (``validateLead``) :
    un polygone commence à 3 sommets. Une seule définition, partagée par la
    note d'historique et la notification — jamais deux règles qui divergent."""
    return isinstance(valeur, list) and len(valeur) >= 3


def _noter_trace_toit(lead):
    """L-DESSIN (ordre fondateur 25/08/2026) — une NOTE d'historique quand le
    client a dessiné son toit.

    « When the client draws his roof i still do not receive the drawing » : le
    contour arrivait bien en base (``Lead.roof_outline``) mais RIEN dans la
    fiche ne disait qu'il était là — ni l'historique, ni l'écran. Cette note
    est le reçu : elle date l'arrivée du tracé et dit où le voir. Best-effort
    comme toutes les écritures annexes de ce webhook : un échec ne remet
    jamais le lead en cause.

    AUCUN CHIFFRE INVENTÉ : seul le nombre RÉEL de sommets est écrit — la
    surface, elle, est calculée et affichée côté fiche à partir de ces mêmes
    sommets (``frontend traceToit.js``), jamais estimée ici."""
    contour = getattr(lead, 'roof_outline', None)
    if not _a_un_contour(contour):
        return
    try:
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE,
            body=(
                'Toit dessiné par le client sur la carte du site : '
                f'{len(contour)} points. Le tracé est visible sur la fiche '
                '(section « Toiture & site ») et déjà chargé dans '
                '« Concevoir la toiture (3D) ».'
            ),
        )
    except Exception as _exc:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'website_lead_webhook: note de tracé de toit échouée '
            '(lead #%s) : %s', getattr(lead, 'pk', None), _exc)


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
    # WJ124 — le tunnel ANNONCE aussi au visiteur le nombre de modules du
    # dimensionnement (`nbPanneaux`) et le bassin de stockage suggéré
    # (`bassinM3` — un VOLUME en m³ : le besoin journalier de pointe, borne
    # basse de la fourchette 1-3×, cf. apps/web/src/lib/lead.ts:231 et
    # mon-toit.astro `s.bassinM3 = ag.m3Jour`). Les DEUX moitiés du contrat
    # les émettaient déjà (lead.ts:ESTIMATE_SHOWN_NUMERIC_KEYS) mais cette
    # whitelist les jetait : le commercial recomptait les modules à la main.
    'nbPanneaux', 'bassinM3',
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

    def _bool(camel, snake):
        val = data.get(camel, data.get(snake))
        if isinstance(val, bool):
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
    # WJ124 — région agronomique : ÉMISE par le site depuis WJ124 mais jamais
    # persistée jusqu'ici (trou de mapping constaté à l'audit). Elle atterrit
    # désormais dans le blob web_questionnaire, comme toute réponse sans
    # colonne Lead dédiée.
    _choice('regionAgricole', 'region_agricole', _REGIONS_AGRICOLES)

    # ── QX51 — Mode COMMERCIAL (catégorie + réponses par catégorie) ──
    # Clés snake_case alignées sur COMMERCIAL_CATEGORY_QUESTIONS (générateur) et
    # etude_params. Bornées, choix fermés ; byte-identique sans ces champs.
    _choice('categorieCommerciale', 'categorie_commerciale',
            ('hotel', 'restaurant', 'commerce', 'bureau', 'sante', 'ecole',
             'hammam', 'boulangerie', 'froid', 'autre'))
    _num('chambres', 'chambres', hi=100000)
    _num('occupationPct', 'occupation_pct', hi=100)
    _num('chambresFroides', 'chambres_froides', hi=10000)
    _num('effectif', 'effectif', hi=1000000)
    _num('lits', 'lits', hi=100000)
    _num('surfaceVenteM2', 'surface_vente_m2', hi=1000000)
    _num('volumeM3', 'volume_m3', hi=10000000)
    # Température de consigne (froid) : peut être NÉGATIVE (ex. -18 °C).
    _num('temperatureConsigne', 'temperature_consigne', lo=-60, hi=60)
    _choice('cuisson', 'cuisson', ('electrique', 'gaz'))
    _choice('four', 'four', ('electrique', 'gaz'))
    _choice('chauffe', 'chauffe', ('electrique', 'gaz'))
    _choice('horaires', 'horaires', ('midi', 'soir', 'continu'))
    _bool('cuissonNocturne', 'cuisson_nocturne')
    _bool('piscine', 'piscine')
    _bool('blanchisserie', 'blanchisserie')
    _bool('internat', 'internat')
    _bool('fermetureEstivale', 'fermeture_estivale')
    _bool('saisonnaliteRecolte', 'saisonnalite_recolte')
    _bool('gardeNuit', 'garde_nuit')
    _bool('clim', 'clim')

    # ── QX51 — Mode INDUSTRIEL v2 (profil de charge affiné) ──
    _choice('equipes', 'equipes', ('1x8', '2x8', '3x8', 'continu'))
    _bool('weekend', 'weekend')
    _num('cosPhiConnu', 'cos_phi_connu', hi=1)
    _num('groupeKva', 'groupe_kva', hi=1000000)
    _num('dieselDhMois', 'diesel_dh_mois')
    _num('surfaceToitureM2', 'surface_toiture_m2', hi=1000000)
    _bool('ombriere', 'ombriere')
    _bool('terrain', 'terrain')

    # ── L-BACK (24/08/2026) — questionnaire d'appel repris par le tunnel web
    # (présence en journée + équipements électriques). Ces clés portent DÉJÀ
    # les noms EXACTS des colonnes ``crm.Lead`` (voir models.py, L4/L-BACK) —
    # ``_map_payload_to_fields`` les extrait ensuite directement sur
    # ``fields`` (jamais laissées dans le reste ``web_questionnaire``), même
    # style tolérant : une clé absente/invalide n'écrase rien.
    _choice('occupation_jour', 'occupation_jour', Lead.OccupationJour.values)
    _bool('equip_piscine', 'equip_piscine')
    _num('equip_piscine_pompe_kw', 'equip_piscine_pompe_kw', hi=1000)
    _bool('equip_voiture_electrique', 'equip_voiture_electrique')
    _num('equip_ve_km_semaine', 'equip_ve_km_semaine', hi=100000)
    _bool('equip_clim', 'equip_clim')
    _num('equip_clim_pieces', 'equip_clim_pieces', hi=1000)
    _bool('equip_chauffe_eau_electrique', 'equip_chauffe_eau_electrique')

    # ── L-WEBT2 (24/08/2026) — précisions FACULTATIVES kW/créneau, reprises
    # du tunnel web (section « Affiner mon profil », visible uniquement pour
    # un équipement déjà coché) : mêmes 10 colonnes ``crm.Lead`` que le
    # commercial saisit à l'appel (L-BACK/L-BACK2, models.py), mêmes bornes
    # que leurs équivalents ci-dessus (kW ≤ 1000, comme
    # ``equip_piscine_pompe_kw``), créneaux WHITELISTÉS sur les enums réels
    # (une valeur hors choices est silencieusement ignorée — jamais d'erreur,
    # jamais un défaut inventé). ``_map_payload_to_fields`` les extrait
    # ensuite directement sur ``fields`` comme le reste du bloc L-BACK.
    _num('equip_chauffe_eau_kw', 'equip_chauffe_eau_kw', hi=1000)
    _choice('equip_chauffe_eau_creneau', 'equip_chauffe_eau_creneau',
            Lead.CreneauChauffeEau.values)
    _num('equip_ve_chargeur_kw', 'equip_ve_chargeur_kw', hi=1000)
    _choice('equip_ve_creneau', 'equip_ve_creneau', Lead.CreneauVe.values)
    _num('equip_clim_kw', 'equip_clim_kw', hi=1000)
    _choice('equip_clim_creneau', 'equip_clim_creneau', Lead.CreneauClim.values)
    _num('equip_piscine_heures_jour', 'equip_piscine_heures_jour', hi=24)
    _choice('equip_piscine_creneau', 'equip_piscine_creneau',
            Lead.CreneauPiscine.values)
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
    if questionnaire.get('region_agricole'):
        parts.append(f"région {questionnaire['region_agricole']}")
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

    # QX51 — Commercial : catégorie + réponses par catégorie (résumé compact).
    cat = questionnaire.get('categorie_commerciale')
    if cat:
        cat_lbl = {
            'hotel': 'hôtel/riad', 'restaurant': 'restaurant/café',
            'commerce': 'commerce', 'bureau': 'bureau', 'sante': 'santé',
            'ecole': 'école privée', 'hammam': 'hammam/spa', 'boulangerie':
            'boulangerie', 'froid': 'entrepôt froid', 'autre': 'commerce',
        }.get(cat, cat)
        parts.append(f"catégorie {cat_lbl}")
    if questionnaire.get('chambres') is not None:
        parts.append(f"{fmt(questionnaire['chambres'])} chambres")
    if questionnaire.get('occupation_pct') is not None:
        parts.append(f"occupation {fmt(questionnaire['occupation_pct'])} %")
    if questionnaire.get('effectif') is not None:
        parts.append(f"effectif {fmt(questionnaire['effectif'])}")
    if questionnaire.get('lits') is not None:
        parts.append(f"{fmt(questionnaire['lits'])} lits")
    if questionnaire.get('chambres_froides') is not None:
        parts.append(f"{fmt(questionnaire['chambres_froides'])} chambres froides")
    if questionnaire.get('temperature_consigne') is not None:
        parts.append(f"consigne {fmt(questionnaire['temperature_consigne'])} °C")
    for key, label in (('cuisson', 'cuisson'), ('four', 'four'),
                       ('chauffe', 'chauffe')):
        if questionnaire.get(key):
            parts.append(f"{label} {questionnaire[key]}")
    for flag, label in (('cuisson_nocturne', 'cuisson nocturne'),
                        ('piscine', 'piscine'), ('blanchisserie', 'blanchisserie'),
                        ('internat', 'internat'),
                        ('fermeture_estivale', 'fermeture estivale')):
        if questionnaire.get(flag) is True:
            parts.append(label)

    # QX51 — Industriel v2 : profil de charge (équipes, groupe, diesel, surface).
    equipes = questionnaire.get('equipes')
    if equipes:
        parts.append({'continu': 'marche continue'}.get(equipes, f"équipes {equipes}"))
    if questionnaire.get('weekend') is True:
        parts.append('week-end travaillé')
    if questionnaire.get('cos_phi_connu') is not None:
        parts.append(f"cos φ {fmt(questionnaire['cos_phi_connu'])}")
    if questionnaire.get('groupe_kva') is not None:
        parts.append(f"groupe {fmt(questionnaire['groupe_kva'])} kVA")
    if questionnaire.get('diesel_dh_mois') is not None:
        parts.append(f"diesel {fmt(questionnaire['diesel_dh_mois'])} MAD/mois")
    if questionnaire.get('surface_toiture_m2') is not None:
        parts.append(f"toiture {fmt(questionnaire['surface_toiture_m2'])} m²")
    for flag, label in (('ombriere', 'ombrière'), ('terrain', 'terrain')):
        if questionnaire.get(flag) is True:
            parts.append(label)

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
    # T-TRACE (25/08/2026) — clé ADDITIVE `appareil_id` : l'uuid que le SITE
    # pose dans le localStorage du visiteur (contrat
    # contract_samples/visite_externe.json). C'est ce qui relie la fiche aux
    # visites ANONYMES qui l'ont précédée. Alias camelCase/EN tolérés comme
    # partout ailleurs dans ce mapping ; absente = None (jamais '' — la
    # colonne est nullable et NULL veut dire « inconnu », pas « vide »).
    appareil = (data.get('appareil_id') or data.get('appareilId')
                or data.get('deviceId') or data.get('device_id'))
    appareil = str(appareil).strip()[:64] if appareil else ''
    fields['appareil_id'] = appareil or None
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
    # Référence courte PROVISOIRE générée côté client (buildClientRef(),
    # « TQ-XXXX ») — anti-garbage minimal (lettres/chiffres/tirets, 4-24).
    # WREF2 : elle n'est plus la référence de la fiche. `_map_and_link_lead`
    # la RETIRE de ce dict et lui substitue la référence attribuée par le
    # serveur (voir `assign_client_ref`) ; elle reste tracée dans le payload
    # brut (WebsiteLeadPayload.payload) et dans la note de création.
    client_ref_raw = data.get('clientRef') or data.get('client_ref')
    if client_ref_raw:
        candidate = str(client_ref_raw).strip()[:24]
        if re.match(r'^[A-Za-z0-9-]{4,24}$', candidate):
            fields['client_ref'] = candidate
    # Diaspora/MRE : numéro E.164 étranger (indicatif ≠ 212).
    if 'phoneIsForeign' in data or 'phone_is_foreign' in data:
        foreign = data.get('phoneIsForeign', data.get('phone_is_foreign'))
        if isinstance(foreign, bool):
            fields['phone_is_foreign'] = foreign
    # Landing page de première visite (first-touch) : posée à la création,
    # jamais réécrite — chaque soumission crée désormais sa propre fiche.
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
        # depuis la création du lead.
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
        # L-BACK — présence en journée + équipements du script d'appel :
        # colonnes Lead DÉDIÉES (jamais laissées dans web_questionnaire).
        occ = questionnaire.pop('occupation_jour', None)
        if occ is not None:
            fields['occupation_jour'] = occ
        for equip_key in (
                'equip_piscine', 'equip_voiture_electrique', 'equip_clim',
                'equip_chauffe_eau_electrique'):
            val = questionnaire.pop(equip_key, None)
            if val is not None:
                fields[equip_key] = val
        piscine_kw = questionnaire.pop('equip_piscine_pompe_kw', None)
        if piscine_kw is not None:
            fields['equip_piscine_pompe_kw'] = piscine_kw
        ve_km = questionnaire.pop('equip_ve_km_semaine', None)
        if ve_km is not None:
            fields['equip_ve_km_semaine'] = int(ve_km)
        clim_pieces = questionnaire.pop('equip_clim_pieces', None)
        if clim_pieces is not None:
            fields['equip_clim_pieces'] = int(clim_pieces)
        # L-WEBT2 (24/08/2026) — précisions kW/créneau facultatives : mêmes
        # colonnes Lead que les 6+2 champs déjà commercial-only (L-BACK/
        # L-BACK2), désormais aussi alimentables par le client lui-même
        # depuis le tunnel. Une clé absente/invalide ne touche jamais le
        # champ correspondant (même discipline que le reste de ce bloc).
        for equip_key in (
                'equip_chauffe_eau_kw', 'equip_chauffe_eau_creneau',
                'equip_ve_chargeur_kw', 'equip_ve_creneau',
                'equip_clim_kw', 'equip_clim_creneau',
                'equip_piscine_heures_jour', 'equip_piscine_creneau'):
            val = questionnaire.pop(equip_key, None)
            if val is not None:
                fields[equip_key] = val
        if questionnaire:
            fields['web_questionnaire'] = questionnaire
    estimate = _clean_estimate_shown(
        data.get('estimateShown', data.get('estimate_shown')))
    if estimate:
        fields['web_estimate'] = estimate

    if fields['whatsapp_opt_in'] and fields['telephone']:
        fields['whatsapp'] = fields['telephone']
    # Sous le seuil : le site le transmet VOLONTAIREMENT (`qualified: false`,
    # capture-lead.ts) et c'est ici que le tri se fait — étiquetage ci-dessous,
    # puis notification atténuée dans `_map_and_link_lead` (cf. docstring §4).
    if _is_sous_seuil(data):
        fields['tags'] = SOUS_SEUIL_TAG
    return fields


# ── L-QUEST (fondateur 25/08/2026) — réponses du CLIENT depuis son lien ──
#
# Le client qui remplit son questionnaire chez lui envoie EXACTEMENT le même
# vocabulaire métier que le site : on réutilise donc le mapping ci-dessus
# (`_map_payload_to_fields`) au lieu d'écrire une SECONDE validation, et on se
# contente de ne garder que les clés de la section concernée.
#
# Deux ajustements, tous deux documentés ici plutôt que dupliqués ailleurs :
#   (a) une poignée de clés que le site nomme autrement (le site envoie
#       `city`, la page questionnaire envoie le nom de colonne `ville`) ;
#   (b) quatre colonnes `Lead` que le mapping du site n'atteint pas du tout
#       (le site ne les collecte pas) : elles sont nettoyées ICI avec les
#       MÊMES primitives (`_clean_decimal`/`_clean_choice`), pas avec un
#       nouveau style de validation. Le comportement du webhook site est
#       strictement inchangé (aucune de ces clés n'y est ajoutée).

#: (a) nom de colonne Lead → clé que `_map_payload_to_fields` lit réellement.
_QUEST_ALIAS_ENTREE = {
    'ville': 'city',
}


def _quest_conso(raw):
    return _clean_decimal(raw, lo=0, hi=1_000_000)


def _quest_surface(raw):
    return _clean_decimal(raw, lo=0, hi=1_000_000)


def _quest_tranche(raw):
    if raw in (None, ''):
        return None
    return str(raw).strip()[:100] or None


def _quest_type_toiture(raw):
    return _clean_choice(raw, Lead.TypeToiture.values)


#: (b) colonnes Lead hors de portée du mapping site → nettoyeur dédié.
_QUEST_NETTOYEURS_HORS_SITE = {
    'conso_mensuelle_kwh': _quest_conso,
    'surface_toiture_m2': _quest_surface,
    'tranche_onee': _quest_tranche,
    'type_toiture': _quest_type_toiture,
}


def champs_lead_depuis_reponses(reponses, cles_autorisees):
    """L-QUEST — Réponses du client (une section) → champs ``Lead`` propres.

    UNE seule validation, celle du site (`_map_payload_to_fields`) ; on ne
    retient ensuite que ``cles_autorisees`` (la whitelist de la section, donc
    une section ne peut JAMAIS écrire un champ d'une autre : une réponse
    « contact » ne touche pas le GPS) et uniquement les valeurs NON vides —
    le mapping du site pose des valeurs de CRÉATION par défaut (nom, canal,
    e-mail à ``None``…) qui ne doivent jamais retomber ici, et un champ absent
    du corps ne peut donc jamais écraser une valeur déjà connue du lead.

    ``False`` et ``0`` sont des réponses LÉGITIMES (« non, pas de piscine »)
    et sont conservés — seuls ``None`` et la chaîne vide sont écartés.
    Ne lève jamais : une valeur invalide est simplement ignorée."""
    if not isinstance(reponses, dict):
        return {}

    entree = dict(reponses)
    for colonne, cle_site in _QUEST_ALIAS_ENTREE.items():
        if colonne in entree and cle_site not in entree:
            entree[cle_site] = entree[colonne]

    fields = _map_payload_to_fields(entree)
    for colonne, nettoyeur in _QUEST_NETTOYEURS_HORS_SITE.items():
        if colonne in reponses:
            valeur = nettoyeur(reponses[colonne])
            if valeur is not None:
                fields[colonne] = valeur

    out = {}
    for cle in cles_autorisees:
        if cle not in fields:
            continue
        val = fields[cle]
        if val is None or (isinstance(val, str) and not val.strip()):
            continue
        out[cle] = val
    return out


# ── WREF2 (fondateur 21/08/2026) — RÉFÉRENCE CLIENT ATTRIBUÉE PAR LE SERVEUR ──
#
# Le code remis au client n'est plus le « TQ-XXXX » tiré au hasard par le
# navigateur : c'est « NOM-N » — le nom de famille tel qu'il l'a tapé, suivi
# d'un compteur en chiffres, attribué ICI à la création du lead.
#   · pas de préfixe de marque (le client dit son nom, pas notre marque) ;
#   · suffixe UNIQUEMENT numérique (zéro ambiguïté à l'oral : pas de O/0, I/1) ;
#   · unique par (société, radical de nom) — « BENALI-1 » et « AMRANI-1 »
#     coexistent, et deux sociétés locataires ont chacune leur compteur.
# Le téléphone reste la CLÉ DE RAPPROCHEMENT primaire (dédup, garde anti-rejeu) ;
# cette référence est la clé de secours HUMAINE (dictée sur WhatsApp/au comptoir).
CLIENT_REF_SLUG_MAX = 12
CLIENT_REF_FALLBACK_SLUG = 'LEAD'
#: Réessais sur course (même discipline que `core.numbering.MAX_ATTEMPTS`).
CLIENT_REF_MAX_ATTEMPTS = 5
#: Nom de repli posé par `_map_payload_to_fields` quand le site n'a pas de
#: `fullName` — jamais un nom de famille, donc jamais un radical « WEB ».
_CLIENT_REF_PLACEHOLDER_NOM = 'lead site web'


def _slugify_ref_part(raw):
    """Radical A-Z d'un morceau de nom : accents dépliés, tout le reste jeté.

    « Benâli » → BENALI, « O'Brien » → OBRIEN, « El-Amrani » → ELAMRANI,
    « أمين » → '' (l'écriture arabe ne se translittère pas ici : on rend une
    chaîne vide et l'appelant passe au repli suivant — jamais un radical
    inventé). Tronqué à ``CLIENT_REF_SLUG_MAX`` pour rester dictable.
    """
    if not raw:
        return ''
    deplie = ''.join(
        c for c in unicodedata.normalize('NFKD', str(raw))
        if not unicodedata.combining(c)
    )
    return re.sub(r'[^A-Z]', '', deplie.upper())[:CLIENT_REF_SLUG_MAX]


def client_ref_slug(nom, prenom=''):
    """Radical de la référence = le NOM DE FAMILLE tel que le client l'a tapé.

    Règle retenue : le DERNIER mot de ``nom`` (le site capture un `fullName`
    unique, « Amina Benali » → BENALI ; « Youssef El Amrani » → AMRANI, jamais
    ELAMRANI — le client se présente par « Amrani », pas par sa particule).
    Replis successifs, dans l'ordre, dès qu'un candidat ne donne aucune lettre
    latine : le ``nom`` entier recollé (« Mohamed أمين » → MOHAMED), puis le
    dernier mot du ``prenom``, puis le ``prenom`` entier, puis
    ``CLIENT_REF_FALLBACK_SLUG`` (nom en écriture non latine, nom vide).
    """
    nom = (nom or '').strip()
    if nom.lower() == _CLIENT_REF_PLACEHOLDER_NOM:
        nom = ''
    candidats = []
    for source in (nom, (prenom or '').strip()):
        if not source:
            continue
        mots = source.split()
        if mots:
            candidats.append(mots[-1])
        candidats.append(source)
    for candidat in candidats:
        slug = _slugify_ref_part(candidat)
        if slug:
            return slug
    return CLIENT_REF_FALLBACK_SLUG


def _next_client_ref(company, slug):
    """« SLUG-N » avec N = PLUS HAUT NUMÉRO UTILISÉ + 1 pour cette société.

    JAMAIS ``count()+1`` (règle du dépôt, cf. `core.numbering` : le compte
    rétrécit quand une fiche est supprimée et deux fiches se retrouvent avec
    le même code). On lit les références déjà posées qui commencent par
    « SLUG- », on ne retient que celles de la forme EXACTE ``^SLUG-\\d+$``
    (« AMRANI-9B » ne doit pas faire avancer le compteur) et on prend le
    maximum des queues numériques.

    Lecture sur ``all_objects`` (et non ``objects``) : ``Lead`` est en
    soft-delete — une fiche mise à la corbeille SORT du manager par défaut
    mais sa ligne, et donc sa référence, existent toujours (et peuvent être
    restaurées). La compter permettrait de re-donner « AMRANI-3 » à un second
    client : c'est la même collision que ``count()+1``, par une autre porte.
    """
    queue_re = re.compile(rf'^{re.escape(slug)}-(\d+)$')
    plus_haut = 0
    refs = (
        Lead.all_objects
        .filter(company=company, client_ref__startswith=f'{slug}-')
        .values_list('client_ref', flat=True)
    )
    for ref in refs:
        m = queue_re.match(ref or '')
        if m:
            plus_haut = max(plus_haut, int(m.group(1)))
    return f'{slug}-{plus_haut + 1}'


def assign_client_ref(lead):
    """Attribue et PERSISTE la référence serveur du lead ; la renvoie.

    Même discipline que la numérotation des documents (`core.numbering`) :
    plus-haut-utilisé+1, dans un savepoint (``transaction.atomic``), avec
    quelques réessais. Différence ASSUMÉE et documentée : ``Lead.client_ref``
    n'a PAS de contrainte d'unicité en base, donc aucune ``IntegrityError`` ne
    viendra arbitrer une vraie course. Poser cette contrainte serait un pari
    sur des données existantes qu'on ne contrôle pas (les anciens « TQ-XXXX »
    tirés au hasard par le navigateur PEUVENT déjà être en double en base — 4
    caractères d'entropie) : une migration qui pose une contrainte unique
    échouerait alors en production sur des lignes historiques. On garde donc
    l'algorithme + le re-contrôle d'existence DANS le savepoint (fenêtre de
    course réduite à quelques millisecondes) et on assume le résidu : deux
    homonymes qui soumettent EXACTEMENT en même temps peuvent partager un
    numéro. C'est une clé de secours humaine — le téléphone reste la clé de
    rapprochement, et la garde d'idempotence QW10 couvre déjà le cas fréquent
    (la MÊME soumission renvoyée).
    """
    slug = client_ref_slug(lead.nom, lead.prenom)
    derniere_exc = None
    for _ in range(CLIENT_REF_MAX_ATTEMPTS):
        candidat = _next_client_ref(lead.company, slug)
        try:
            with transaction.atomic():
                deja_pris = (
                    Lead.all_objects
                    .filter(company=lead.company, client_ref=candidat)
                    .exclude(pk=lead.pk)
                    .exists()
                )
                if deja_pris:
                    continue
                lead.client_ref = candidat
                lead.save(update_fields=['client_ref'])
            return candidat
        except IntegrityError as exc:  # pragma: no cover — sans contrainte unique
            derniere_exc = exc
    if derniere_exc is not None:
        raise derniere_exc
    return lead.client_ref


def _owners_habilites(company, owner_ids):
    """Sous-ensemble de ``owner_ids`` réellement ATTRIBUABLE aujourd'hui.

    MÊMES filtres que ``services.pick_round_robin_owner`` (le chemin normal
    d'attribution) : utilisateur de la société, ``is_active=True``, et
    habilité au CRM — permission ``crm_creer``, ou rôle legacy admin/
    responsable pour les comptes sans Role. Renvoie un ``set`` de pk."""
    from django.contrib.auth import get_user_model
    from django.db.models import Q

    ids = {pk for pk in owner_ids if pk}
    if not ids:
        return set()
    User = get_user_model()
    return set(
        User.objects.filter(
            pk__in=ids, company=company, is_active=True,
        ).filter(
            Q(role__permissions__contains=['crm_creer'])
            | Q(role__isnull=True, role_legacy__in=['admin', 'responsable']),
        ).values_list('pk', flat=True)
    )


def _pick_owner_from_duplicates(dupes, *, telephone='', email='', company=None):
    """QW11 (héritage du commercial, 18/08/2026 — décision fondateur) —
    Choisit l'owner à HÉRITER parmi les doublons trouvés À LA CRÉATION, avant
    toute décision d'attribution : un lead qui EST un doublon n'entre jamais
    dans le round-robin/territoires.

    DEUX filtres d'éligibilité, sans lesquels l'héritage attribuait un lead à
    un compte que TOUS les autres chemins d'attribution refusent :

    1. le doublon ARCHIVÉ ne transmet pas son owner. ``find_duplicates_by_contact``
       inclut délibérément les archivés (pour le SIGNALEMENT — une fiche
       classée spam/injoignable reste mentionnée dans la note chatter), mais
       une vraie nouvelle demande ne doit pas être attribuée « comme » une
       fiche mise au rebut ;
    2. l'owner doit être ACTIF et habilité au CRM — mêmes filtres que
       ``services.pick_round_robin_owner`` (``_owners_habilites``). Sans cela,
       le commercial parti (``is_active=False``) restait propriétaire de tous
       les leads de son ancien téléphone : ``notify_new_lead`` ciblait un
       compte mort et aucun commercial actif ne voyait jamais le lead.

    Priorité au doublon en IDENTITÉ FORTE (même e-mail ET même téléphone,
    ``is_strong_identity_match``) parmi les éligibles ; à défaut, le doublon
    le PLUS RÉCENT (``date_creation``, pk en départage). Renvoie
    ``(None, None)`` si ``dupes`` est vide ou si AUCUN doublon éligible n'a
    d'owner attribuable — l'appelant replie alors sur le comportement normal
    (territoires/round-robin), strictement inchangé.

    Renvoie ``(owner, doublon_origine)`` — ``doublon_origine`` est le Lead
    dont l'owner est hérité, utile pour la note chatter."""
    from .services import is_strong_identity_match

    candidats = [d for d in dupes if d.owner_id and not d.is_archived]
    if not candidats:
        return None, None
    if company is None:
        company = candidats[0].company
    habilites = _owners_habilites(company, {d.owner_id for d in candidats})
    dupes_avec_owner = [d for d in candidats if d.owner_id in habilites]
    if not dupes_avec_owner:
        return None, None
    forts = [d for d in dupes_avec_owner
             if is_strong_identity_match(d, phone=telephone, email=email)]
    pool = forts or dupes_avec_owner
    origine = max(pool, key=lambda d: (d.date_creation, d.pk))
    return origine.owner, origine


#: Marqueur de la note sobre qui REMPLACE l'alerte urgente de rappel (QW4)
#: quand le lead est sous le seuil — sert aussi d'idempotence par lead.
CALLBACK_SOUS_SEUIL_MARKER = 'auto — rappel demandé, lead sous le seuil'


def _note_rappel_sous_seuil(lead):
    """Consigne la demande de rappel d'un lead SOUS LE SEUIL sans réveiller
    personne : UNE note chatter sobre, aucune notification (l'alerte urgente
    ``notify_lead_callback_requested`` est réservée aux leads au-dessus du
    seuil — une facture < 1 000 MAD n'est pas « plus urgente qu'un lead
    générique »). La demande reste donc visible sur la fiche (préférence de
    contact + cette note), elle ne se transforme simplement plus en alerte.

    No-op si le lead n'a pas demandé de rappel ; idempotent par lead (la garde
    anti-rejeu < 60 s repasse ici pour la MÊME soumission)."""
    if getattr(lead, 'contact_preference', None) != Lead.ContactPreference.PHONE_OK:
        return
    already = LeadActivity.objects.filter(
        lead=lead, kind=LeadActivity.Kind.NOTE,
        body__startswith=CALLBACK_SOUS_SEUIL_MARKER,
    ).exists()
    if already:
        return
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=(f'{CALLBACK_SOUS_SEUIL_MARKER} : demande consignée, '
              'aucune alerte urgente envoyée.'),
    )


def _flag_possible_duplicates(lead, *, telephone='', email='', dupes=None,
                              inherited_owner=None, inherited_from=None):
    """Détection de doublon posée EN VISIBILITÉ sur le lead qui vient d'être
    créé — jamais une fusion (règle fondateur du 18/08/2026).

    On cherche les leads de la MÊME société partageant le téléphone OU l'e-mail
    normalisé et, s'il y en a, on pose UNE note chatter sobre sur le NOUVEAU
    lead. Aucun lead existant n'est lu en écriture : les fiches déjà en base
    ressortent intactes de ce chemin. ``dupes`` peut être fourni PRÉ-CALCULÉ
    par l'appelant (``_map_and_link_lead`` les a déjà cherchés pour décider de
    l'attribution, QW11) pour ne jamais interroger deux fois la même requête ;
    sinon ils sont recherchés ici.

    « Identité forte » = un lead existant partage À LA FOIS l'e-mail exact ET
    le téléphone normalisé exact ; la note le dit alors explicitement (« très
    probablement le même client »), et l'appelant l'expose dans la réponse
    HTTP. Le rail identité (GET ``/crm/leads/<id>/duplicates/``) s'allume seul
    sur le nouveau lead — cette note ne fait que l'expliquer dans le chatter.

    QW11 — quand ``inherited_owner``/``inherited_from`` sont fournis (l'owner
    du nouveau lead a été HÉRITÉ d'un doublon, cf. ``_pick_owner_from_duplicates``),
    la même note mentionne explicitement l'héritage.

    Renvoie ``(ids_des_doublons, match_fort)``."""
    from .services import find_duplicates_by_contact, is_strong_identity_match

    if dupes is None:
        dupes = find_duplicates_by_contact(
            lead.company, phone=telephone or None, email=email or None,
            exclude_pk=lead.pk)
    if not dupes:
        return [], False
    dupes = sorted(dupes, key=lambda le: le.pk)
    match_fort = any(
        is_strong_identity_match(le, phone=telephone, email=email)
        for le in dupes)
    shown = dupes[:5]
    refs = ', '.join(
        f'#{le.pk} ({(le.nom or "sans nom").strip()})' for le in shown)
    if len(dupes) > len(shown):
        refs += f' (+{len(dupes) - len(shown)} autre(s))'
    label = 'lead' if len(dupes) == 1 else 'leads'
    body = (f'Doublon possible : même téléphone/email que {label} {refs}'
            ' — à examiner')
    if match_fort:
        body += (' — même e-mail ET même téléphone : très probablement '
                 'le même client')
    if inherited_owner is not None and inherited_from is not None:
        owner_name = inherited_owner.get_full_name() or inherited_owner.username
        body += (f" — attribué à {owner_name} comme la fiche d'origine "
                 f"#{inherited_from.pk}")
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE, body=body)
    return [le.pk for le in dupes], match_fort


def _map_and_link_lead(raw, data, company):
    """QX16 — Cœur du mapping payload → Lead, factorisé hors de la vue pour
    être réutilisable par le REJEU (``replay_website_lead_payload``) sans
    dupliquer la logique. Persiste ``raw.lead``/``raw.processed`` et renvoie
    ``(lead, created, detail, extra)`` (``extra`` = signaux de doublon à
    exposer dans la réponse HTTP). Laisse toute exception se propager — les
    appelants (vue webhook, action replay) décident comment la consigner sur
    ``raw.error``.

    RÈGLE FONDATEUR (18/08/2026) : une soumission du site = un NOUVEAU lead.
    Le SEUL cas où un lead existant est complété ici est la garde technique
    anti-rejeu < 60 s (même téléphone + source site web) — c'est la même
    soumission qui revient, pas un visiteur revenant."""
    fields = _map_payload_to_fields(data)
    # WREF2 — le « TQ-XXXX » du navigateur est PROVISOIRE : il ne s'écrit
    # jamais sur la fiche. On le sort du dict AVANT toute écriture, ce qui
    # garantit les deux moitiés de la règle : (a) à la création, c'est
    # `assign_client_ref` qui pose « NOM-N » ; (b) sur le chemin anti-rejeu
    # < 60 s, le renvoi de la MÊME soumission ne peut PAS réattribuer ni
    # écraser la référence déjà donnée au client. Le code provisoire reste
    # conservé tel quel dans le payload brut (WebsiteLeadPayload.payload) et
    # rappelé dans la note de création.
    # WREF2-PONT — le transfert reste volontairement fire-and-forget, zéro-
    # perte : l'écran de succès du site relève désormais la référence SERVEUR
    # après coup (option B, GO fondateur 21/08/2026 — voir
    # `public_lead_ref_views.lead_ref_lookup`), mais cette relève PEUT
    # échouer silencieusement (panne réseau, timeout, tentatives épuisées) —
    # le client garde alors CE code provisoire. Il doit donc rester
    # RETROUVABLE dans tous les cas : champ dédié + indexé par les trois
    # recherches, jamais silencieusement perdu — sinon on recrée exactement
    # le bug fondateur d'origine.
    provisional_ref = fields.pop('client_ref', None)
    if provisional_ref:
        fields['client_ref_provisoire'] = provisional_ref
    telephone = fields.get('telephone') or ''
    email = fields.get('email') or ''
    # Le TRI promis au site (capture-lead.ts : « le récepteur accepte le
    # drapeau et fait le tri lui-même ») se joue sur ce booléen : le lead est
    # créé et étiqueté comme tout autre, mais sa notification d'arrivée est
    # marquée et l'alerte URGENTE de rappel (QW4) n'est pas déclenchée.
    sous_seuil = _is_sous_seuil(data)

    # QW10 — Garde CONCURRENTE via `idempotencyKey` (lib/lead.ts — jeton
    # généré côté navigateur à l'ouverture de la session de saisie).
    # `cache.add` est atomique : deux POSTs simultanés avec la MÊME clé ne
    # peuvent jamais tous les deux se croire « premiers » — la requête
    # PERDANTE attend brièvement que la gagnante commite son lead, puis
    # rejoint la garde anti-rejeu < 60 s ci-dessous (jamais de logique
    # dupliquée). Best-effort : sans clé (anciens workers) ou cache
    # indisponible, comportement inchangé (la garde < 60 s et le dédup dur
    # `dedupe_event` restent la protection).
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

    dup_ids, match_fort = [], False

    # ── Garde TECHNIQUE anti-rejeu < 60 s (double-clic / relance réseau) ──
    # C'est la SEULE circonstance où ce webhook touche un lead déjà en base :
    # la même soumission qui revient dans la minute. Ce n'est PAS une
    # déduplication métier — un visiteur qui revient une heure, un jour ou un
    # mois plus tard obtient sa propre fiche (règle fondateur), et le
    # rapprochement se fait ensuite par bandeau + fusion manuelle.
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
        # Renvoi de la MÊME soumission : on COMPLÈTE sans jamais écraser une
        # donnée déjà captée par du vide. Un second payload plus pauvre
        # (champ absent → None/'') ne doit pas annuler ce que le premier a
        # rempli — on n'écrit donc que les valeurs réellement renseignées.
        #
        # ORDRE FONDATEUR (24/08/2026) — le GPS ne doit JAMAIS être écrasé ni
        # supplanté par l'adresse : une fois gps_lat/gps_lng posés sur CE
        # lead (pin explicite du client), aucun renvoi ultérieur de la même
        # soumission — même porteur d'une valeur non vide, p. ex. un pas
        # suivant du tunnel où seule l'adresse a été retouchée — ne les
        # remplace. Une mise à jour qui n'apporte pas de nouvelles
        # coordonnées explicites ne touche donc jamais aux existantes ;
        # contrairement aux autres champs (complétés par tout non-vide), le
        # GPS suit la même discipline « jamais d'écrasement » que
        # `services._MERGE_FILL_FIELDS` (fusion manuelle de leads).
        # L-DESSIN — état AVANT la fusion : un contour qui arrive sur ce
        # deuxième envoi (le visiteur a dessiné puis re-soumis dans la minute)
        # mérite sa note, un contour déjà noté à la création n'en remet pas.
        avait_contour = _a_un_contour(getattr(existing, 'roof_outline', None))
        # CLIOVR (25/08/2026) — même discipline que le GPS ci-dessus, mais
        # généralisée à TOUT champ corrigé À LA MAIN : un second POST < 60 s
        # (retry réseau, étape suivante du tunnel) ne doit jamais écraser une
        # valeur qu'un commercial vient de corriger dans le CRM. « Manuel » =
        # une LeadActivity MODIFICATION portant un `user` réel — la vue CRM
        # (views.py:746) en écrit une à CHAQUE édition humaine ; ce webhook
        # et les autres chemins système (services.py, questionnaire.py)
        # écrivent toujours user=None, donc jamais comptés ici (sinon le
        # webhook se bloquerait lui-même). Une seule requête, avant la boucle.
        manually_touched = set(
            LeadActivity.objects
            .filter(lead=existing, kind=LeadActivity.Kind.MODIFICATION,
                    user__isnull=False)
            .values_list('field', flat=True)
        )
        # Snapshot AVANT écriture — sert au trace old→new ci-dessous, même
        # patron que `perform_update` (views.py:739) et
        # `update_lead_from_public_api` (services.py:3843).
        avant = Lead.objects.get(pk=existing.pk)
        for key, value in fields.items():
            if value is None or value == '':
                continue
            if key in _GPS_FIELDS and getattr(existing, key) is not None:
                continue
            if key in manually_touched:
                continue
            setattr(existing, key, value)
        existing.save()
        lead, created = existing, False
        # Trace la fusion comme partout ailleurs (activity.log_changes) : un
        # champ RÉELLEMENT écrit apparaît avec son ancienne et sa nouvelle
        # valeur ; aucune entrée si rien n'a changé. Remplace l'ancienne note
        # plate qui ne disait jamais QUEL champ avait bougé.
        from . import activity
        activity.log_changes(avant, lead, None)
        if not avait_contour:
            _noter_trace_toit(lead)
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
        # QW11 (18/08/2026, héritage du commercial — décision fondateur) — la
        # recherche de doublons se fait ICI, AVANT toute décision
        # d'attribution : un lead qui EST un doublon à la création N'ENTRE
        # PAS dans le round-robin/territoires, il hérite du commercial du
        # doublon le plus pertinent (priorité au match fort e-mail+téléphone,
        # sinon le doublon le plus récent qui a un owner). Si aucun doublon
        # n'a d'owner, comportement inchangé (territoires/round-robin,
        # NTCRM1/XSAL11). `dupes` est réutilisé plus bas par
        # `_flag_possible_duplicates` — jamais une 2e requête identique.
        from .services import find_duplicates_by_contact
        dupes = find_duplicates_by_contact(
            company, phone=telephone or None, email=email or None)
        inherited_owner, inherited_from = _pick_owner_from_duplicates(
            dupes, telephone=telephone, email=email, company=company)
        if inherited_owner is not None:
            fields.setdefault('owner', inherited_owner)
        else:
            # Responsable par défaut de la société (Paramètres) si configuré.
            # NTCRM1 — le moteur de territoires est consulté EN PREMIER (via
            # lead_attrs=fields) ; repli sur XSAL11 round-robin si aucun match.
            from .services import default_responsable_for
            fields.setdefault(
                'owner', default_responsable_for(company, lead_attrs=fields))
        lead = Lead.objects.create(company=company, **fields)
        created = True
        # WREF2 — référence client attribuée par le SERVEUR, immédiatement
        # après la création (avant la note de création, pour que celle-ci la
        # porte). Best-effort comme tous les blocs de cette fonction : une
        # attribution en échec laisse la fiche SANS référence (état déjà
        # possible aujourd'hui) mais ne remet JAMAIS le lead en cause.
        server_ref = None
        try:
            server_ref = assign_client_ref(lead)
        except Exception as _exc:  # noqa: BLE001 — le lead prime sur son code
            logger.warning(
                'website_lead_webhook: référence client non attribuée '
                '(lead #%s) : %s', lead.pk, _exc)
        creation_body = 'Lead créé via le site web'
        if server_ref:
            creation_body += f' — référence client : {server_ref}'
        if provisional_ref and provisional_ref != server_ref:
            creation_body += (
                f' (code provisoire affiché au visiteur : {provisional_ref})')
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.CREATION,
            body=creation_body,
        )
        # L-DESSIN — le tracé du client laisse une TRACE dans l'historique.
        _noter_trace_toit(lead)
        # QJ2 (a) — speed-to-lead : notifie le owner dès la création (voit
        # déjà l'owner hérité ci-dessus s'il y en a un — jamais un round-robin
        # notifié puis contredit par la note de doublon qui suit). Un lead
        # SOUS LE SEUIL est notifié lui aussi (jamais silencieux : il est bien
        # arrivé), mais la mention « (sous le seuil) » le dit dans le titre —
        # le commercial arbitre en voyant la notification, pas après l'appel.
        try:
            from .services import notify_new_lead
            notify_new_lead(lead, sous_seuil=sous_seuil)
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
        # Détection de doublon EN VISIBILITÉ (remplace l'ancienne fusion
        # silencieuse « visiteur revenant ») : note chatter sur le NOUVEAU
        # lead + signal « identité forte » — et, si l'attribution ci-dessus a
        # hérité d'un owner, la mention de l'héritage sur la MÊME note.
        # Réutilise `dupes` déjà calculés ci-dessus (jamais une 2e requête).
        # Best-effort — un rapprochement en échec ne remet jamais la capture
        # du lead en cause.
        try:
            dup_ids, match_fort = _flag_possible_duplicates(
                lead, telephone=telephone, email=email, dupes=dupes,
                inherited_owner=inherited_owner, inherited_from=inherited_from)
        except Exception as _exc:  # noqa: BLE001 — best-effort
            logger.warning(
                'website_lead_webhook: détection de doublon échouée '
                '(lead #%s) : %s', lead.pk, _exc)

    # ── T-TRACE (25/08/2026) — traçage anti-fraude de la demande ───────────
    # Placé APRÈS `notify_new_lead` À DESSEIN : la notification d'arrivée doit
    # dire « a visité le site N fois AVANT sa demande », donc elle lit
    # l'historique alors qu'il ne contient encore QUE les passages anonymes —
    # jamais la demande elle-même. Ici on fait, dans l'ordre :
    #   1. rattacher au lead les visites ANONYMES déjà connues de cet appareil
    #      (on ne savait pas à qui elles appartenaient, maintenant si) ;
    #   2. enregistrer LA demande comme une visite de point `tunnel_lead` ;
    #   3. lever l'alerte ROUGE si cet appareil sert DÉJÀ un AUTRE lead.
    # Sur les DEUX chemins (création et complément anti-rejeu < 60 s) : une
    # demande vaut une trace, même quand elle complète la fiche en cours.
    # `raw.remote_addr` porte déjà l'IP extraite par la vue (X-Forwarded-For
    # d'abord) — jamais une IP venue du corps.
    # Best-effort intégral : le traçage ne remet JAMAIS le lead en cause.
    try:
        from .services import (
            alerter_appareil_partage, rattacher_visites_au_lead,
            tracer_et_correler,
        )
        rattacher_visites_au_lead(lead)
        tracer_et_correler(
            lead.company, point='tunnel_lead', lead=lead,
            appareil_id=(lead.appareil_id or ''),
            contexte='Demande de devis (site)',
            langue=(lead.langue_preferee or ''),
            ip=(getattr(raw, 'remote_addr', '') or ''),
        )
        alerter_appareil_partage(lead)
    except Exception as _exc:  # noqa: BLE001 — best-effort
        logger.warning(
            'website_lead_webhook: traçage T-TRACE échoué (lead #%s) : %s',
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

    # QW4 — rappel demandé (contact_preference=phone_ok) : notification
    # DISTINCTE et plus urgente qu'un lead générique, sur création ET sur
    # complément < 60 s (la préférence peut n'arriver qu'au second envoi).
    # Idempotent (marqueur chatter) — jamais best-effort bloquant.
    #
    # SOUS LE SEUIL : l'alerte urgente n'est PAS déclenchée (une facture
    # < 1 000 MAD ne réveille pas un commercial), mais la demande de rappel
    # ne disparaît pas pour autant — `contact_preference` reste posée sur la
    # fiche et une note chatter sobre la consigne, sans notification.
    try:
        if sous_seuil:
            _note_rappel_sous_seuil(lead)
        else:
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
    if not created:
        detail = 'Lead mis à jour (même envoi < 1 min).'
    elif not dup_ids:
        detail = 'Lead créé.'
    else:
        nb = len(dup_ids)
        pluriel = '' if nb == 1 else 's'
        detail = f'Lead créé — {nb} doublon{pluriel} possible{pluriel}'
        detail += (' : très probablement le même client.' if match_fort
                   else ' à examiner.')
    return lead, created, detail, {
        'doublons': dup_ids, 'match_fort': match_fort}


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
                # Ordre EXPLICITE (ne pas dépendre du Meta.ordering) : depuis
                # que chaque soumission crée sa fiche, plusieurs leads peuvent
                # partager un numéro — l'engagement se note sur le PLUS RÉCENT.
                candidates = (Lead.objects.filter(company=company)
                              .order_by('-date_creation'))
                for candidate in candidates:
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
        lead, created, detail, extra = _map_and_link_lead(raw, data, company)
        # `doublons`/`match_fort` sont ADDITIFS (le Worker du site ignore les
        # clés qu'il ne connaît pas) : ils disent au clair qu'un lead au même
        # téléphone/e-mail existe déjà, et si c'est très probablement le même
        # client — sans que RIEN n'ait été fusionné.
        # WREF2 — `client_ref` est ADDITIF lui aussi : la référence « NOM-N »
        # attribuée par le serveur est renvoyée à l'émetteur pour qu'il puisse
        # (le jour où son transfert n'est plus en arrière-plan) l'afficher au
        # client à la place du code provisoire. Peut être ``null`` : émetteur
        # sans nom exploitable, ou attribution en échec (best-effort ci-dessus).
        body = {'detail': detail, 'lead_id': lead.pk, 'payload_id': raw.pk,
                'client_ref': lead.client_ref}
        body.update(extra)
        return JsonResponse(body, status=201 if created else 200)
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
        lead, created, detail, _extra = _map_and_link_lead(
            raw, raw.payload, company)
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


def _meta_lead_ads_app_secret():
    return (getattr(settings, 'META_LEAD_ADS_APP_SECRET', '') or '').strip()


def _check_meta_lead_ads_signature(request, secret):
    """PUB26 — Vrai si ``X-Hub-Signature-256`` est présente ET valide
    (HMAC-SHA256 du corps brut avec ``secret``). Miroir EXACT de
    ``apps.adsengine.whatsapp_webhook._check_signature`` (même en-tête, même
    algorithme) — absente ou mal formée → False (rejet)."""
    sig_header = request.META.get('HTTP_X_HUB_SIGNATURE_256', '')
    if not sig_header or not sig_header.startswith('sha256='):
        return False
    expected = 'sha256=' + hmac.new(
        secret.encode(), request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig_header, expected)


def fetch_meta_lead_data(leadgen_id, access_token):
    """Récupère le détail d'un lead Meta via le Graph API officiel.

    Isolé dans sa propre fonction pour rester facilement simulable en test
    (monkeypatch) — le test simulé décrit dans XMKT32 n'appelle jamais un
    vrai serveur Meta. Renvoie un dict ``{'field_data': [...]}`` ou lève sur
    échec réseau/HTTP (capté par l'appelant).
    """
    import urllib.request

    # ADSENG2 — version depuis la SOURCE UNIQUE partagée (apps.adsengine.
    # api_version), jamais codée en dur : la v19.0 qui restait ici était morte
    # depuis 02/2025. Constante plain (aucun modèle adsengine importé).
    from apps.adsengine.api_version import GRAPH_BASE_URL

    url = f'{GRAPH_BASE_URL}/{leadgen_id}?access_token={access_token}'
    with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
        return json.loads(resp.read().decode('utf-8'))


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def meta_lead_ads_webhook(request):
    verify_token = getattr(settings, 'META_LEAD_ADS_VERIFY_TOKEN', '') or ''

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
    # FIXPUB1 — token d'accès : env (META_LEAD_ADS_ACCESS_TOKEN) prioritaire,
    # sinon le token de la MetaConnection activée de la société (repli
    # permanent). On journalise la SOURCE choisie, jamais le token lui-même.
    company = _meta_lead_ads_company()
    from apps.adsengine.selectors import resolve_lead_ads_access_token
    access_token, token_source = resolve_lead_ads_access_token(company)
    if not access_token:
        # Aucune source (ni env ni connexion) : no-op silencieux, jamais d'exception.
        logger.info(
            'meta_lead_ads_webhook: aucun access token (env ni connexion) — no-op.')
        return JsonResponse({'detail': 'Non configuré — ignoré.'}, status=200)
    logger.info('meta_lead_ads_webhook: token Lead Ads via %s.', token_source)

    # PUB26 — vérification HMAC (`X-Hub-Signature-256`) : n'importe qui pouvait
    # jusqu'ici poster de faux leads (META_LEAD_ADS_APP_SECRET était listé dans
    # WIRING_ENV_KEYS mais jamais vérifié). Rétro-compatible : secret absent →
    # warning + payload accepté quand même (comportement historique préservé) ;
    # secret présent + signature absente/invalide → 403.
    app_secret = _meta_lead_ads_app_secret()
    if app_secret:
        if not _check_meta_lead_ads_signature(request, app_secret):
            logger.warning(
                'meta_lead_ads_webhook: signature X-Hub-Signature-256 '
                'absente ou invalide.')
            return JsonResponse({'detail': 'Signature invalide.'}, status=403)
    else:
        logger.warning(
            'meta_lead_ads_webhook: META_LEAD_ADS_APP_SECRET non configuré — '
            'signature non vérifiée (rétro-compatibilité).')

    try:
        data = json.loads(request.body.decode('utf-8'))
        if not isinstance(data, dict):
            raise ValueError('payload non-objet')
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'detail': 'JSON invalide.'}, status=400)

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
                # ADSENG1 — Meta pousse ad_id/adgroup_id/form_id (JAMAIS
                # campaign_name/adset_name) : on capture ces clés de jointure
                # stables ; la résolution des noms se fait côté service.
                ad_id = value.get('ad_id', '') or ''
                adgroup_id = value.get('adgroup_id', '') or ''
                form_id = value.get('form_id', '') or ''
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
                    field_data=field_data, ad_id=ad_id,
                    adgroup_id=adgroup_id, form_id=form_id,
                    access_token=access_token)
                created_leads.append(lead.pk)
                # ADSDEEP17 — événement domaine (M6) : ``adsengine`` matérialise
                # un MetaLeadMirror (leads par ad) SANS que ``crm`` l'importe.
                # Best-effort : un abonné en échec ne casse jamais la capture.
                try:
                    from core.events import meta_lead_captured
                    meta_lead_captured.send(
                        sender='crm.meta_lead_ads_webhook', lead=lead,
                        company=company, leadgen_id=str(leadgen_id),
                        ad_id=ad_id, adset_id=adgroup_id, campaign_id='',
                        form_id=form_id,
                        created_time=value.get('created_time'),
                        is_organic=not bool(ad_id))
                except Exception:  # noqa: BLE001 — best-effort
                    logger.warning(
                        'meta_lead_ads_webhook: émission meta_lead_captured '
                        'échouée (leadgen %s)', leadgen_id, exc_info=True)
        return JsonResponse({'detail': 'Traité.', 'lead_ids': created_leads},
                            status=200)
    except Exception:
        logger.exception('meta_lead_ads_webhook: traitement échoué.')
        return JsonResponse({'detail': 'Erreur de traitement.'}, status=202)
