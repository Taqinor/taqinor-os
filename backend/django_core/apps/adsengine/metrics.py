"""ENG10 — Service coût-par-signature (l'héro-métrique du moteur).

Blend déterministe : ``InsightSnapshot.spend`` (côté Meta, réconcilié avec les
miroirs) × leads CRM SIGNÉS attribués par ``utm_campaign`` (côté ERP). Le coût
par signature = dépense de la campagne ÷ nombre de signatures attribuées.

TRAÇABILITÉ (pattern Northbeam, exigence #7 de la recherche UX) : chaque chiffre
est accompagné de la LISTE des ids de leads qui le composent — jamais un chiffre
« boîte noire ». Le front peut donc rendre chaque nombre cliquable jusqu'au lead
réel.

FRONTIÈRE CROSS-APP : le CRM est lu UNIQUEMENT via ``apps.crm.selectors``
(``signed_leads_for_campaigns``) — jamais un import de ``apps.crm.models``
(contrat import-linter ENG20). Le stade « SIGNED » vient de ``STAGES.py`` (via le
sélecteur), jamais codé en dur ici.

ATTRIBUTION : la clé d'attribution d'une campagne est son ``name`` — convention
« Launch Kit » (le moteur nomme la campagne ET estampille la MÊME valeur dans
l'``utm_campaign`` des liens ; domaines 11-13 de la recherche). Le service reste
déterministe et testable sur fixtures.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db.models import Avg, Count, Sum

from .models import AdCampaignMirror, InsightSnapshot

# ── ADSDEEP6 — Objectif de campagne → métrique « résultats » homogène ─────────
# Meta rapporte ``results`` selon l'objectif, mais l'objectif lui-même n'a pas
# de nom métier partagé côté ERP. Cette table (DONNÉES, pas de logique) associe
# chaque objectif à la métrique qui FAIT SENS et à son libellé FR, pour que
# ``results``/``cpl`` aient une signification homogène par campagne et que le
# dashboard affiche « conversations » (CTWA) vs « leads » (OUTCOME_LEADS) plutôt
# qu'un « résultats » opaque. ``metric`` désigne une clé de
# ``platforms.base.normalize_insight_row`` (conversations/leads_count/…).
DEFAULT_RESULT_METRIC = {'metric': 'results', 'label_fr': 'résultats'}
RESULT_METRIC_BY_OBJECTIVE = {
    # CTWA / messagerie → conversations WhatsApp (action
    # messaging_conversation_started_7d).
    'OUTCOME_ENGAGEMENT': {'metric': 'conversations', 'label_fr': 'conversations'},
    'MESSAGES': {'metric': 'conversations', 'label_fr': 'conversations'},
    'CONVERSATIONS': {'metric': 'conversations', 'label_fr': 'conversations'},
    'OUTCOME_MESSAGES': {'metric': 'conversations', 'label_fr': 'conversations'},
    # Génération de leads → leads.
    'OUTCOME_LEADS': {'metric': 'leads_count', 'label_fr': 'leads'},
    'LEAD_GENERATION': {'metric': 'leads_count', 'label_fr': 'leads'},
    # Trafic → clics sur lien.
    'OUTCOME_TRAFFIC': {'metric': 'link_clicks', 'label_fr': 'clics sur lien'},
    'LINK_CLICKS': {'metric': 'link_clicks', 'label_fr': 'clics sur lien'},
    # Notoriété → impressions.
    'OUTCOME_AWARENESS': {'metric': 'impressions', 'label_fr': 'impressions'},
    'BRAND_AWARENESS': {'metric': 'impressions', 'label_fr': 'impressions'},
    # Ventes → résultats génériques (achats), libellé dédié.
    'OUTCOME_SALES': {'metric': 'results', 'label_fr': 'achats'},
    'CONVERSIONS': {'metric': 'results', 'label_fr': 'conversions'},
}


def result_metric_for_objective(objective):
    """ADSDEEP6 — Métrique « résultats » + libellé FR pour un objectif Meta.

    Renvoie un dict ``{metric, label_fr}`` ; repli sur ``résultats`` générique
    pour un objectif inconnu/absent (jamais d'erreur)."""
    key = (objective or '').strip().upper()
    return RESULT_METRIC_BY_OBJECTIVE.get(key, DEFAULT_RESULT_METRIC)


def real_lead_counts(company):
    """ADSDEEP19 — Comptes de leads RÉELS par ad et par campagne (MetaLeadMirror).

    Remplace le « Leads: 0 » issu des insights par le vrai nombre de leads
    capturés (webhook + pull, dédupliqués par ``leadgen_id``). Le ``campaign_id``
    d'un miroir peut être vide (le webhook leadgen ne le pousse pas) : dans ce
    cas la campagne est résolue via l'échelle miroir ``ad_id`` → ``AdMirror`` →
    ``AdSetMirror`` → ``AdCampaignMirror``. Company-scopé. Renvoie
    ``{by_ad, by_campaign, total}`` (``by_campaign`` clé = meta_id de campagne)."""
    from .models import AdMirror, MetaLeadMirror

    mirrors = list(MetaLeadMirror.objects.filter(company=company))
    total = len(mirrors)
    by_ad = {}
    for m in mirrors:
        if m.ad_id:
            by_ad[m.ad_id] = by_ad.get(m.ad_id, 0) + 1

    # Échelle ad_id → campagne (meta_id) via les miroirs (une seule requête).
    ad_to_campaign = {}
    ad_qs = (AdMirror.objects
             .filter(company=company)
             .select_related('adset__campaign'))
    for ad in ad_qs:
        camp = getattr(getattr(ad, 'adset', None), 'campaign', None)
        if camp is not None:
            ad_to_campaign[ad.meta_id] = camp.meta_id

    by_campaign = {}
    for m in mirrors:
        camp_id = m.campaign_id or ad_to_campaign.get(m.ad_id, '')
        if camp_id:
            by_campaign[camp_id] = by_campaign.get(camp_id, 0) + 1
    return {'by_ad': by_ad, 'by_campaign': by_campaign, 'total': total}


def conversations_per_ad(company):
    """ADSDEEP25 — Conversations WhatsApp RÉELLES par ad (``CtwaReferral``) +
    signatures rapprochées par téléphone.

    Complète la métrique AGRÉGÉE de Meta (``InsightSnapshot.conversations`` =
    ``messaging_conversation_started_7d``, un simple compteur) par le compte
    RÉEL de conversations CTWA reçues sur le webhook Cloud API (ADSDEEP24), PAR
    ad, avec la jointure signatures : « cette ad a produit N conversations, M
    signées ». Les signatures viennent du CRM (leads au stade SIGNÉ, clé
    ``STAGES.py``) rapprochées par ``phone_key`` normalisé QW10 — lu via
    ``crm.selectors.signed_lead_phone_keys`` (jamais un import de
    ``crm.models``). Company-scopé.

    Renvoie ``{by_ad, total_conversations, total_signed}`` où ``by_ad`` est une
    liste ordonnée par ``ad_id`` de ::

        {ad_id, conversations, unique_contacts, signed}

    ``conversations`` = nombre de messages CTWA reçus pour l'ad (chaque message
    entrant issu d'une pub = un démarrage de conversation) ; ``unique_contacts``
    = numéros distincts ; ``signed`` = numéros distincts qui ont signé.
    """
    from apps.crm.selectors import signed_lead_phone_keys

    from .models import CtwaReferral

    signed_keys = signed_lead_phone_keys(company)

    buckets = {}
    for ref in (CtwaReferral.objects
                .filter(company=company)
                .exclude(ad_id='')
                .only('ad_id', 'phone_key')):
        bucket = buckets.setdefault(
            ref.ad_id, {'conversations': 0, 'phones': set()})
        bucket['conversations'] += 1
        if ref.phone_key:
            bucket['phones'].add(ref.phone_key)

    by_ad = []
    total_conversations = total_signed = 0
    for ad_id in sorted(buckets):
        bucket = buckets[ad_id]
        phones = bucket['phones']
        conversations = bucket['conversations']
        signed = len(phones & signed_keys)
        by_ad.append({
            'ad_id': ad_id,
            'conversations': conversations,
            'unique_contacts': len(phones),
            'signed': signed,
        })
        total_conversations += conversations
        total_signed += signed
    return {
        'by_ad': by_ad,
        'total_conversations': total_conversations,
        'total_signed': total_signed,
    }


def _campaign_spend_map(company, campaigns):
    """Dépense cumulée (``InsightSnapshot.spend``) par miroir de campagne.

    Renvoie ``{campaign_pk: Decimal}`` — réconcilie avec les miroirs (une seule
    source : les instantanés rattachés à la campagne par FK générique)."""
    if not campaigns:
        return {}
    ct = ContentType.objects.get_for_model(AdCampaignMirror)
    rows = (InsightSnapshot.objects
            .filter(company=company, content_type=ct,
                    object_id__in=[c.pk for c in campaigns])
            .values('object_id')
            .annotate(spend=Sum('spend')))
    return {r['object_id']: (r['spend'] or Decimal('0')) for r in rows}


def cost_per_signature(company):
    """ENG10 — Métriques coût-par-signature PAR campagne, avec traçabilité.

    Renvoie une liste de dicts (ordonnée par ``meta_id``) ::

        {
          'campaign_meta_id': str,
          'campaign_name': str,
          'attribution_key': str,       # valeur utm_campaign attendue (= name)
          'spend': str,                 # Decimal sérialisé (dépense cumulée)
          'signed_count': int,          # nombre de signatures attribuées
          'cost_per_signature': str|None,  # spend/signed_count, None si 0 signé
          'signed_lead_ids': [int, ...],   # traçabilité — leads réels
        }

    Le CRM est lu via ``apps.crm.selectors.signed_leads_for_campaigns`` (jamais
    d'import de models). La dépense se réconcilie avec les miroirs.
    """
    from apps.crm.selectors import signed_leads_for_campaigns

    campaigns = list(
        AdCampaignMirror.objects.filter(company=company).order_by('meta_id'))
    spend_map = _campaign_spend_map(company, campaigns)

    # Clé d'attribution = nom de campagne (convention utm_campaign = name).
    attribution_keys = [c.name for c in campaigns if c.name]
    signed = signed_leads_for_campaigns(company, attribution_keys)

    results = []
    for camp in campaigns:
        key = camp.name or ''
        spend = spend_map.get(camp.pk, Decimal('0'))
        bucket = signed.get(key, {'signed_count': 0, 'signed_lead_ids': []})
        count = bucket['signed_count']
        cps = (spend / count) if count else None
        # ADSDEEP6 — libellé homogène de la métrique « résultats » par objectif.
        metric_info = result_metric_for_objective(camp.objective)
        results.append({
            'campaign_meta_id': camp.meta_id,
            'campaign_name': camp.name,
            'attribution_key': key,
            'spend': str(spend),
            'signed_count': count,
            'cost_per_signature': (str(cps) if cps is not None else None),
            'signed_lead_ids': list(bucket['signed_lead_ids']),
            'objective': camp.objective or '',
            'result_metric': metric_info['metric'],
            'result_metric_label': metric_info['label_fr'],
        })
    return results


# ── ADSDEEP44 — Métriques créatives dérivées PAR AD (barre Motion, benchmark §2) ─
# Toutes calculées depuis ``InsightSnapshot.video_metrics`` (ADSDEEP1, dossier
# insights-api §3) + ``impressions``. AUCUN champ vidéo « 3 s » n'existe chez Meta
# (dossier insights-api §3, video_play_actions/video_6_15_30_sec_watched_actions/
# video_p25-100_watched_actions/video_thruplay_watched_actions/
# video_avg_time_watched_actions) : le hook rate utilise DÉLIBÉRÉMENT ``s6``
# (video_6_sec_watched_actions), jamais un « video_3s » inventé — même si le
# benchmark générique concurrent (Motion) parle de 3 s. Chaque formule est
# NULL-SAFE : un dénominateur nul/absent OU un champ vidéo absent renvoie
# ``None`` — JAMAIS un 0 fabriqué (un 0 affiché laisserait croire à une mesure
# réelle de zéro plutôt qu'à une donnée manquante).
def hook_rate(video_metrics, impressions):
    """Hook rate = vues 6 s / impressions (PAS de champ 3 s — inexistant chez
    Meta, dossier insights-api §3). ``None`` si ``s6`` absent ou impressions
    nulles/absentes (jamais un faux 0)."""
    vm = video_metrics or {}
    s6 = vm.get('s6')
    if s6 is None or not impressions:
        return None
    return float(s6) / float(impressions)


def hold_rate(video_metrics):
    """Hold rate = ThruPlay / lectures (``plays``) — définition RETENUE par le
    dossier insights-api §3 (le benchmark générique concurrent dit « 15 s / 3 s » ;
    adapté ici puisque le champ 3 s n'existe pas chez Meta)."""
    vm = video_metrics or {}
    plays = vm.get('plays')
    thruplay = vm.get('thruplay')
    if not plays or thruplay is None:
        return None
    return float(thruplay) / float(plays)


def ratio_15s_to_6s(video_metrics):
    """Ratio de rétention 15 s / 6 s : au-delà du hook (6 s), la vidéo garde-t-elle
    l'attention ? ``None`` si l'un des deux champs est absent/nul."""
    vm = video_metrics or {}
    s6 = vm.get('s6')
    s15 = vm.get('s15')
    if not s6 or s15 is None:
        return None
    return float(s15) / float(s6)


_RETENTION_QUARTILES = ('p25', 'p50', 'p75', 'p100')


def retention_curve(video_metrics):
    """Courbe de rétention 25/50/75/100 % — chaque point = (vues au quartile) /
    lectures totales (``plays``). Un point sans donnée (ou ``plays`` nul/absent)
    est ``None`` (jamais un 0 fabriqué) ; les AUTRES points restent calculables
    indépendamment (une ad sans ``p100`` peut quand même exposer ``p25``)."""
    vm = video_metrics or {}
    plays = vm.get('plays')
    curve = {}
    for key in _RETENTION_QUARTILES:
        val = vm.get(key)
        curve[key] = (float(val) / float(plays)
                      if (plays and val is not None) else None)
    return curve


def watch_time_avg(video_metrics):
    """Temps de visionnage moyen (secondes, replays inclus) — passthrough
    null-safe du champ ``avg_time`` (dossier insights-api §3)."""
    vm = video_metrics or {}
    val = vm.get('avg_time')
    return float(val) if val is not None else None


def derived_ad_video_metrics(video_metrics, impressions):
    """ADSDEEP44 — Bundle des métriques créatives dérivées d'UN
    snapshot/agrégat (hook rate / hold rate / ratio 15-6 / courbe de rétention /
    temps de visionnage moyen). Chaque clé est indépendamment null-safe :
    l'absence d'une métrique vidéo (ex. ad statique, sans lecture) ne bloque
    jamais le calcul des autres."""
    return {
        'hook_rate': hook_rate(video_metrics, impressions),
        'hold_rate': hold_rate(video_metrics),
        'ratio_15s_to_6s': ratio_15s_to_6s(video_metrics),
        'retention': retention_curve(video_metrics),
        'watch_time_avg_s': watch_time_avg(video_metrics),
    }


# Clés CUMULATIVES (comptes AdsActionStats) sommées telles quelles sur une
# fenêtre ; ``avg_time`` est déjà une MOYENNE journalière côté Meta — la sommer
# fausserait le sens (elle est moyennée séparément, cf. ``sum_video_metrics``).
_VIDEO_SUM_KEYS = ('p25', 'p50', 'p75', 'p95', 'p100', 'plays', 's6', 's15',
                   's30', 'thruplay')


def sum_video_metrics(snapshots):
    """Somme des ``video_metrics`` (+ impressions) d'une liste de
    ``InsightSnapshot`` sur une fenêtre. Une clé JAMAIS rapportée par aucun
    snapshot de la fenêtre reste ABSENTE du résultat (jamais un 0 fabriqué pour
    une métrique jamais mesurée) ; ``avg_time`` est la MOYENNE (pas la somme)
    des jours où elle est présente. Renvoie ``(totals_dict, impressions|None)``."""
    totals = {}
    avg_times = []
    impressions = 0
    has_impressions = False
    for snap in snapshots:
        vm = getattr(snap, 'video_metrics', None) or {}
        for key in _VIDEO_SUM_KEYS:
            val = vm.get(key)
            if val is not None:
                totals[key] = totals.get(key, 0.0) + float(val)
        if vm.get('avg_time') is not None:
            avg_times.append(float(vm['avg_time']))
        impr = getattr(snap, 'impressions', None)
        if impr is not None:
            impressions += int(impr)
            has_impressions = True
    if avg_times:
        totals['avg_time'] = sum(avg_times) / len(avg_times)
    return totals, (impressions if has_impressions else None)


def ad_video_metrics_for_window(snapshots):
    """ADSDEEP44 — Bundle dérivé agrégé sur une fenêtre de ``InsightSnapshot``
    (somme des ``video_metrics`` + impressions, puis les mêmes formules
    dérivées null-safe que :func:`derived_ad_video_metrics`)."""
    totals, impressions = sum_video_metrics(snapshots)
    return derived_ad_video_metrics(totals, impressions)


def cost_per_signature_summary(company):
    """Agrégat société : dépense totale, signatures totales, coût-par-signature
    global + le détail par campagne. La dépense totale se réconcilie avec la
    somme des instantanés des miroirs de campagne."""
    per_campaign = cost_per_signature(company)
    total_spend = sum((Decimal(row['spend']) for row in per_campaign),
                      Decimal('0'))
    # ENGFIX4 — total signatures = nombre de leads DISTINCTS (union des ids), et
    # NON la somme des compteurs par campagne : deux miroirs de MÊME nom
    # partagent la même clé d'attribution → le même bucket signé, donc chaque
    # lead serait compté deux fois par une simple somme (gonflement du total,
    # écrasement du coût-par-signature héros). La dépense, elle, reste sommée
    # (chaque miroir porte sa propre dépense, clée par pk distinct).
    distinct_signed_ids = set()
    for row in per_campaign:
        distinct_signed_ids.update(row['signed_lead_ids'])
    total_signed = len(distinct_signed_ids)
    global_cps = (total_spend / total_signed) if total_signed else None
    return {
        'total_spend': str(total_spend),
        'total_signed': total_signed,
        'cost_per_signature': (str(global_cps) if global_cps is not None
                               else None),
        'campagnes': per_campaign,
    }


# ── ADSDEEP61 — Dashboard v2 : tuiles conversations + MER mixte ───────────────
# Doctrine (règle #7 devise-compte, dd-treasury) : la dépense Meta et le CA
# signé Odoo sont dans DEUX devises DIFFÉRENTES (compte pub souvent en USD, CA
# Odoo toujours en MAD). Un « blended MER » qui les DIVISERAIT l'un par
# l'autre fabriquerait un ratio faux (conversion silencieuse implicite) —
# JAMAIS fait ici : les deux chiffres sont renvoyés CÔTE À CÔTE, à comparer,
# jamais combinés en un seul nombre.
DASHBOARD_V2_WINDOW_DAYS = 14


def _sparkline(daily_map, start_date, end_date):
    """Liste ordonnée ``[{date, value}]`` pour CHAQUE jour de
    ``start_date..end_date`` inclus — un jour sans donnée vaut 0 (jamais un
    trou silencieux dans le graphique, la sparkline reste continue)."""
    points = []
    day = start_date
    while day <= end_date:
        raw = daily_map.get(day, 0)
        value = float(raw) if isinstance(raw, Decimal) else raw
        points.append({'date': day.isoformat(), 'value': value})
        day += datetime.timedelta(days=1)
    return points


def _ctwa_daily_counts(company, start_date, end_date):
    """Compte de conversations CTWA RÉELLES (``CtwaReferral``, ADSDEEP24) par
    JOUR d'horodatage (``ts``), borné à la fenêtre. Contrairement à
    ``InsightSnapshot.conversations`` (agrégat Meta), ce compte vient des
    messages entrants réels reçus sur le webhook Cloud API."""
    from .models import CtwaReferral

    daily = {}
    qs = (CtwaReferral.objects
          .filter(company=company, ts__date__gte=start_date,
                  ts__date__lte=end_date)
          .exclude(ad_id='')
          .only('ts'))
    for ref in qs:
        if not ref.ts:
            continue
        d = ref.ts.date()
        daily[d] = daily.get(d, 0) + 1
    return daily


def _signed_ca_daily(company, start_date, end_date):
    """CA signé Odoo (MAD) par JOUR sur la fenêtre : ``{configured, daily}``.
    Ne lève JAMAIS (dégradation propre comme le reste du module Odoo) —
    ``configured=False`` si le connecteur n'est pas branché, ``daily={}`` si la
    lecture Odoo échoue."""
    from .odoo_client import is_configured

    if not is_configured():
        return {'configured': False, 'daily': {}}
    try:
        from .odoo_selectors import signed_deals
        deals = signed_deals(since=start_date)
    except Exception:  # noqa: BLE001 — jamais un 500 sur une panne Odoo
        return {'configured': True, 'daily': {}}

    daily = {}
    for deal in deals:
        raw_date = deal.get('date')
        try:
            d = datetime.date.fromisoformat(str(raw_date)[:10])
        except (TypeError, ValueError):
            continue
        if d < start_date or d > end_date:
            continue
        amount = deal.get('amount_mad')
        if amount is None:
            continue
        daily[d] = daily.get(d, Decimal('0')) + Decimal(str(amount))
    return {'configured': True, 'daily': daily}


def dashboard_v2_metrics(company, *, as_of=None,
                         window_days=DASHBOARD_V2_WINDOW_DAYS):
    """ADSDEEP61 — Tuiles du Dashboard v2 (fenêtre glissante, 14 jours par
    défaut, INCLUSIVE ``as_of - (window_days-1) .. as_of``) :

    - ``conversations`` : compte RÉEL de conversations WhatsApp (CTWA,
      ADSDEEP24/25) + sparkline quotidienne.
    - ``mer`` : dépense Meta (devise du COMPTE — ``spend_currency``) et CA
      signé Odoo (``signed_ca_mad``, toujours MAD) rendus CÔTE À CÔTE avec
      leur propre sparkline — AUCUNE conversion, AUCUN ratio inter-devises
      fabriqué ici (dd-treasury règle #7 ; ``mer_ratio`` reste ``None`` si les
      deux devises diffèrent, seul cas où un blended MER a un sens réel).

    Toutes les valeurs viennent de miroirs/instantanés déjà persistés — rien
    n'est inventé, un tenant sans historique reçoit des zéros explicites."""
    from .pacing import load_daily_spend

    as_of = as_of or datetime.date.today()
    start_date = as_of - datetime.timedelta(days=window_days - 1)

    conv_daily = _ctwa_daily_counts(company, start_date, as_of)
    spend_daily_float = load_daily_spend(company, start_date, as_of)
    spend_daily = {d: Decimal(str(v)) for d, v in spend_daily_float.items()}

    signed_ca = _signed_ca_daily(company, start_date, as_of)
    signed_ca_daily = signed_ca['daily']

    from .models import MetaConnection
    conn = MetaConnection.objects.filter(company=company).first()
    spend_currency = (conn.currency if conn else '') or 'MAD'

    total_conversations = sum(conv_daily.values())
    total_spend = sum(spend_daily.values(), Decimal('0'))
    total_signed_ca = sum(signed_ca_daily.values(), Decimal('0'))

    # Un blended MER (CA / dépense) n'a un sens que dans UNE SEULE devise —
    # sinon ce serait diviser des MAD par des USD (conversion silencieuse
    # implicite, interdite). Calculable UNIQUEMENT si le compte Meta est déjà
    # en MAD (aucune conversion requise).
    mer_ratio = None
    if spend_currency == 'MAD' and total_spend > 0:
        mer_ratio = str(total_signed_ca / total_spend)

    return {
        'window_days': window_days,
        'since': start_date.isoformat(),
        'until': as_of.isoformat(),
        'conversations': {
            'total': total_conversations,
            'sparkline': _sparkline(conv_daily, start_date, as_of),
        },
        'mer': {
            # Dépense Meta rendue à 2 décimales (jamais '120.0', elle vient d'un
            # float ``load_daily_spend``) ; le CA signé Odoo est un Decimal exact
            # rendu tel quel (str brut) — contrat des tests dashboard-v2.
            'spend': str(total_spend.quantize(Decimal('0.01'))),
            'spend_currency': spend_currency,
            'signed_ca_mad': str(total_signed_ca),
            'signed_ca_currency': 'MAD',
            'mer_ratio': mer_ratio,
            'odoo_configured': signed_ca['configured'],
            'spend_sparkline': _sparkline(spend_daily, start_date, as_of),
            'signed_ca_sparkline': _sparkline(
                signed_ca_daily, start_date, as_of),
            'note': ("Dépense en devise du compte Meta, CA signé en MAD "
                     "(Odoo) — jamais convertie automatiquement : comparer "
                     "les deux chiffres, ne jamais les diviser l'un par "
                     "l'autre si les devises diffèrent."),
        },
    }


# ── ADSDEEP22 — Cockpit par ad (écran-console quotidien du fondateur) ─────────
COCKPIT_RECENT_DAYS = 7
COCKPIT_MIN_FATIGUE_SAMPLES = 3


def _ad_window_aggregates(company, ad_pks, start_date=None, end_date=None):
    """``{ad_pk: {spend, results, clicks, impressions, frequency, samples}}``
    agrégé sur ``[start_date, end_date]`` (ad-level ``InsightSnapshot``,
    ADSDEEP2) — bornes optionnelles : omises, la requête porte sur TOUT
    l'historique de l'ad (totaux du cockpit). ``frequency`` est une MOYENNE
    (déjà une moyenne journalière côté Meta, cf. ``sum_video_metrics``) ;
    ``samples`` = nombre de jours avec un instantané (plancher d'échantillons
    du détecteur de fatigue ADSDEEP45)."""
    from .models import AdMirror

    if not ad_pks:
        return {}
    ct = ContentType.objects.get_for_model(AdMirror)
    qs = InsightSnapshot.objects.filter(
        company=company, content_type=ct, object_id__in=ad_pks)
    if start_date is not None:
        qs = qs.filter(date__gte=start_date)
    if end_date is not None:
        qs = qs.filter(date__lte=end_date)
    rows = (qs.values('object_id')
            .annotate(spend=Sum('spend'), results=Sum('results'),
                      clicks=Sum('clicks'), impressions=Sum('impressions'),
                      frequency=Avg('frequency'), samples=Count('id')))
    return {r['object_id']: r for r in rows}


def _ad_fatigue_badge(recent, baseline):
    """ADSDEEP45 — Badge de fatigue créative pour UNE ad, dérivé des fenêtres
    récente (7 j) vs référence (7 j précédents) déjà agrégées. Réutilise
    ``anomaly.detect_creative_fatigue`` (détecteur PUR, déjà construit) — aucun
    recalcul de la logique de seuils ici."""
    from .anomaly import detect_creative_fatigue

    recent = recent or {}
    baseline = baseline or {}
    recent_impr = recent.get('impressions') or 0
    baseline_impr = baseline.get('impressions') or 0
    ctr_current = (float(recent.get('clicks') or 0) / recent_impr
                   if recent_impr else None)
    ctr_baseline = (float(baseline.get('clicks') or 0) / baseline_impr
                    if baseline_impr else None)
    recent_results = recent.get('results') or 0
    baseline_results = baseline.get('results') or 0
    cpa_current = (float(recent.get('spend') or 0) / recent_results
                   if recent_results else None)
    cpa_baseline = (float(baseline.get('spend') or 0) / baseline_results
                    if baseline_results else None)
    frequency = recent.get('frequency')
    detection = detect_creative_fatigue(
        frequency=(float(frequency) if frequency is not None else None),
        ctr_current=ctr_current, ctr_baseline=ctr_baseline,
        cpa_current=cpa_current, cpa_baseline=cpa_baseline,
        recent_samples=recent.get('samples') or 0,
        baseline_samples=baseline.get('samples') or 0,
        min_samples=COCKPIT_MIN_FATIGUE_SAMPLES)
    return {
        'fired': detection.fired,
        'insufficient_data': detection.insufficient_data,
        'severity': detection.severity,
        'message_fr': detection.message_fr,
    }


def ads_cockpit_rows(company, *, as_of=None):
    """ADSDEEP22 — Une ligne PAR AD pour le cockpit quotidien du fondateur :
    miniature créatif (référence, pas d'URL persistée — le front résout via
    ``media.resolve``), dépense/résultats agrégés, leads RÉELS (ADSDEEP19),
    conversations WhatsApp réelles (ADSDEEP25), signatures + coût/signature
    Odoo par ad (ADSDEEP20), fréquence, badge de fatigue (ADSDEEP45) et statut
    + badge d'apprentissage HÉRITÉ de l'ad set parent (ADSDEEP32). Combine des
    métriques DÉJÀ construites — aucune logique métier réimplémentée ici."""
    from .models import AdCreativeMirror, AdMirror
    from .odoo_metrics import odoo_signatures_by_ad
    from .serializers import _LEARNING_BADGE, _META_STATUT_FR

    as_of = as_of or datetime.date.today()
    ads = list(AdMirror.objects.filter(company=company)
               .select_related('adset', 'creative_mirror')
               .order_by('-created_at'))
    ad_pks = [a.pk for a in ads]

    totals = _ad_window_aggregates(company, ad_pks, end_date=as_of)
    recent_start = as_of - datetime.timedelta(days=COCKPIT_RECENT_DAYS - 1)
    baseline_end = recent_start - datetime.timedelta(days=1)
    baseline_start = baseline_end - datetime.timedelta(days=COCKPIT_RECENT_DAYS - 1)
    recent_agg = _ad_window_aggregates(company, ad_pks, recent_start, as_of)
    baseline_agg = _ad_window_aggregates(
        company, ad_pks, baseline_start, baseline_end)

    real_leads_by_ad = real_lead_counts(company)['by_ad']
    conv_by_ad = {row['ad_id']: row
                  for row in conversations_per_ad(company)['by_ad']}
    # PUB32 — dernier classement Meta connu PAR AD (diagnostics de qualité/
    # engagement/conversion), visibles au cockpit.
    rankings_by_ad = _latest_rankings_by_ad(company, ad_pks, as_of)
    # PUB35 — dernière lecture d'attribution INCRÉMENTALE connue PAR AD (vide si
    # le compte n'expose pas la colonne — dégradation propre).
    incremental_by_ad = _latest_incremental_by_ad(company, ad_pks, as_of)
    odoo_by_ad = {}
    odoo_configured = False
    try:
        odoo_result = odoo_signatures_by_ad(company)
        odoo_configured = bool(odoo_result.get('configured'))
        odoo_by_ad = {row['ad_id']: row for row in odoo_result.get('ads', [])}
    except Exception:  # noqa: BLE001 — le cockpit ne casse jamais sur Odoo
        pass

    rows = []
    for ad in ads:
        total = totals.get(ad.pk, {})
        spend = total.get('spend') or Decimal('0')
        leads = real_leads_by_ad.get(ad.meta_id, 0)
        cpl = (spend / leads) if leads else None

        conv_row = conv_by_ad.get(ad.meta_id, {})
        odoo_row = odoo_by_ad.get(ad.meta_id)
        signatures = odoo_row['signatures'] if odoo_row else 0
        cost_per_signature = odoo_row['cost_per_signature'] if odoo_row else None

        adset = ad.adset
        learning_status = getattr(adset, 'learning_status', '') or ''
        learning_meta = _LEARNING_BADGE.get(
            learning_status, {'label': 'Inconnu', 'tone': 'neutral'})

        try:
            creative = ad.creative_mirror
        except AdCreativeMirror.DoesNotExist:
            creative = None
        thumbnail_ref = None
        thumbnail_kind = 'image'
        if creative is not None:
            if creative.video_id:
                thumbnail_ref, thumbnail_kind = creative.video_id, 'video'
            elif creative.image_hash:
                thumbnail_ref, thumbnail_kind = creative.image_hash, 'image'

        rows.append({
            'id': ad.id,
            'meta_id': ad.meta_id,
            'nom': ad.name,
            'statut': ad.status,
            'statut_display': _META_STATUT_FR.get(ad.status, ad.status or '—'),
            'learning_badge': {
                'status': learning_status,
                'label': learning_meta['label'],
                'tone': learning_meta['tone'],
            },
            'thumbnail_ref': thumbnail_ref,
            'thumbnail_kind': thumbnail_kind,
            'depense_mad': str(spend),
            'conversations': conv_row.get('conversations', 0),
            'nb_leads': leads,
            'cpl_mad': (str(cpl) if cpl is not None else None),
            'signatures': signatures,
            'cost_per_signature_mad': cost_per_signature,
            'odoo_configured': odoo_configured,
            'frequency': (str(total['frequency'])
                          if total.get('frequency') is not None else None),
            'fatigue': _ad_fatigue_badge(
                recent_agg.get(ad.pk), baseline_agg.get(ad.pk)),
            # PUB32 — diagnostics de classement Meta (proxys négatifs) par ad.
            'classement_qualite': rankings_by_ad.get(ad.pk, {}).get(
                'quality', ''),
            'classement_engagement': rankings_by_ad.get(ad.pk, {}).get(
                'engagement', ''),
            'classement_conversion': rankings_by_ad.get(ad.pk, {}).get(
                'conversion', ''),
            # PUB35 — résultats ATTRIBUÉS (``nb_leads`` ci-dessus) vs
            # INCRÉMENTAUX, côte à côte. Dict vide = colonne non exposée par le
            # compte (dégradation propre — le front affiche « non disponible »).
            'attribution_incrementale': incremental_by_ad.get(ad.pk, {}),
        })
    return rows


def _latest_rankings_by_ad(company, ad_pks, end_date):
    """PUB32 — Dernier diagnostic de classement Meta connu PAR AD : le snapshot
    le plus récent (≤ end_date) portant un ``quality_ranking`` non vide. Renvoie
    ``{ad_pk: {'quality':.., 'engagement':.., 'conversion':..}}`` (une requête)."""
    from django.contrib.contenttypes.models import ContentType

    from .models import AdMirror, InsightSnapshot

    if not ad_pks:
        return {}
    ct = ContentType.objects.get_for_model(AdMirror)
    out = {}
    for row in (InsightSnapshot.objects
                .filter(company=company, content_type=ct,
                        object_id__in=ad_pks, date__lte=end_date)
                .exclude(quality_ranking='')
                .order_by('object_id', '-date')
                .values('object_id', 'quality_ranking',
                        'engagement_rate_ranking', 'conversion_rate_ranking')):
        oid = row['object_id']
        if oid in out:
            continue  # order_by -date : la première vue est la plus récente
        out[oid] = {
            'quality': row['quality_ranking'],
            'engagement': row['engagement_rate_ranking'],
            'conversion': row['conversion_rate_ranking'],
        }
    return out


def _latest_incremental_by_ad(company, ad_pks, end_date):
    """PUB35 — Dernière lecture d'attribution INCRÉMENTALE connue PAR AD : le
    snapshot le plus récent (≤ end_date) dont ``incremental_attribution`` n'est
    pas vide. Renvoie ``{ad_pk: {incremental_conversions: ..}}`` (une requête) ;
    ``{}`` pour un compte qui n'expose pas la colonne (dégradation propre)."""
    from django.contrib.contenttypes.models import ContentType

    from .models import AdMirror, InsightSnapshot

    if not ad_pks:
        return {}
    ct = ContentType.objects.get_for_model(AdMirror)
    out = {}
    for row in (InsightSnapshot.objects
                .filter(company=company, content_type=ct,
                        object_id__in=ad_pks, date__lte=end_date)
                .exclude(incremental_attribution={})
                .order_by('object_id', '-date')
                .values('object_id', 'incremental_attribution')):
        oid = row['object_id']
        if oid in out:
            continue  # order_by -date : la première vue est la plus récente
        out[oid] = row['incremental_attribution'] or {}
    return out
