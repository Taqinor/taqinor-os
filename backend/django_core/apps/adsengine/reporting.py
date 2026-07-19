"""ADSENG33 — Drill-downs de reporting au-delà du dashboard ENG23 (dd-attribution
part d).

Trois vues + export CSV, chacune scopée société et lisant le CRM UNIQUEMENT via
``apps.crm.selectors`` (jamais un import de ``apps.crm.models``) :

  * **table par variante** (§5.1) — dépense / conversions / CPL / CPL-qualifié /
    coût-par-signature PAR AD, avec les ids de leads derrière chaque chiffre
    (traçabilité Northbeam). C'EST la fonction de récompense du bandit rendue
    visible → mêmes nombres qu'``attribution.variant_attribution`` consomme, pas
    une approximation. Réutilise ADSENG6 (fichier disjoint, aucune duplication) ;
  * **entonnoir par campagne** (§5.2) — NEW→CONTACTED→QUOTE_SENT→FOLLOW_UP→SIGNED
    (cumulatif « a atteint au moins »), avec COLD + perdu montrés À CÔTÉ
    (« Perdu » n'est pas une étape — règle #2) ;
  * **cohortes de signature** (§5.3) — leads par SEMAINE de création → fraction
    signée à J+1/2/4/8/12 semaines (lag = ``Devis.date_acceptation`` −
    ``Lead.date_creation``). À faible volume, une TABLE (jamais une courbe
    lissée sur des effectifs à un chiffre) ; une cohorte dont la fenêtre n'est pas
    écoulée est marquée INCOMPLÈTE (jamais un zéro final trompeur).

Les clés d'étape viennent de ``STAGES.py`` via le sélecteur (jamais en dur —
règle #2). Aucune migration, aucun champ.
"""
from __future__ import annotations

import csv
import datetime
import io
import statistics
from decimal import Decimal, ROUND_HALF_UP

from . import allocation

# PUB88 — un bras est un « gagnant confirmé » quand sa probabilité d'être le
# meilleur atteint le seuil de maturité de phase (dd-science-core §4 : P ≥ 80 %).
CONFIRMED_WINNER_PROB = allocation.PHASE_ADVANCE_PROB  # 0.80

# Buckets de lag par défaut (semaines) pour les cohortes de signature (§5.3).
DEFAULT_LAG_WEEKS = (1, 2, 4, 8, 12)

# Clé d'affichage des leads non attribués à une campagne (jamais silencieux).
UNATTRIBUTED_KEY = '(non attribué)'


def _q2(value):
    """Arrondi monétaire 2 décimales (str), ou None si ``value`` est None (0.00
    reste 0.00 — jamais écrasé en None ; le None vient d'un dénominateur nul,
    géré par l'appelant)."""
    if value is None:
        return None
    return str(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


# ── §5.1 — Table par variante ────────────────────────────────────────────────
def variant_table(company, *, qualifying_stage=None):
    """ADSENG33 — Table par variante (§5.1). Réutilise
    ``attribution.variant_attribution`` (ADSENG6) et ajoute le coût-par-lead
    (dépense ÷ leads attribués). Renvoie ``{'variants': [...], 'unresolved':
    {...}, 'organic_excluded_count': int}`` — chaque variante porte les ids de
    leads (lien cliquable) et JAMAIS un coût zéro fabriqué (None quand le
    dénominateur est nul)."""
    from .attribution import variant_attribution

    data = variant_attribution(company, qualifying_stage=qualifying_stage)
    variants = []
    for v in data['variants']:
        spend = Decimal(v['spend'])
        cost_per_lead = _q2(spend / v['leads']) if v['leads'] else None
        variants.append({
            'meta_id': v['meta_id'],
            'name': v['name'],
            'spend': v['spend'],
            'leads': v['leads'],                    # conversions attribuées
            'qualified': v['qualified'],
            'signed': v['signed'],
            'cost_per_lead': cost_per_lead,
            'cost_per_qualified_lead': v['cost_per_qualified_lead'],
            'cost_per_signature': v['cost_per_signature'],
            'lead_ids': v['lead_ids'],
            'signed_lead_ids': v['signed_lead_ids'],
            # PUB28 — taux de junk PAR AD (signal qualité manquant au veto de
            # divergence — voir crm.MotifPerte.est_junk).
            'junk': v['junk'],
            'junk_rate': v['junk_rate'],
            # PUB37 — taux de no-show PAR AD (RDV terrain honorés vs fantômes).
            'appointments': v['appointments'],
            'no_show': v['no_show'],
            'no_show_rate': v['no_show_rate'],
        })
    return {
        'variants': variants,
        'unresolved': data['unresolved'],
        'organic_excluded_count': data['organic_excluded_count'],
    }


# ── §5.2 — Entonnoir par campagne ────────────────────────────────────────────
def _campaign_key(row):
    return row['meta_campaign_id'] or row['utm_campaign'] or UNATTRIBUTED_KEY


def campaign_funnel(company, *, date_start=None, date_end=None):
    """ADSENG33 — Entonnoir par campagne (§5.2). Comptes CUMULATIFS « a atteint
    au moins l'étape X » sur l'entonnoir NEW→SIGNED ; COLD et perdu comptés À
    CÔTÉ (jamais dans l'entonnoir). Renvoie une liste ordonnée ::

        [{'campaign_key', 'total', 'cold', 'perdu',
          'funnel': [{'stage', 'reached'}, ...]}, ...]

    Les clés d'étape viennent de STAGES.py (via le sélecteur)."""
    from apps.crm.selectors import pipeline_stage_order, reporting_lead_rows

    order = pipeline_stage_order()
    funnel = order['funnel']          # NEW..SIGNED (hors COLD)
    cold = order['cold']
    rank = {s: i for i, s in enumerate(funnel)}

    rows = reporting_lead_rows(
        company, date_start=date_start, date_end=date_end)

    campaigns = {}
    for r in rows:
        key = _campaign_key(r)
        slot = campaigns.setdefault(key, {
            'reached': [0] * len(funnel), 'cold': 0, 'perdu': 0, 'total': 0})
        slot['total'] += 1
        if r['perdu']:
            slot['perdu'] += 1
            continue                   # perdu : à côté, jamais dans l'entonnoir.
        if r['stage'] == cold:
            slot['cold'] += 1
            continue                   # COLD : à côté.
        if r['stage'] in rank:
            for i in range(rank[r['stage']] + 1):
                slot['reached'][i] += 1

    result = []
    for key in sorted(campaigns):
        slot = campaigns[key]
        result.append({
            'campaign_key': key,
            'total': slot['total'],
            'cold': slot['cold'],
            'perdu': slot['perdu'],
            'funnel': [
                {'stage': funnel[i], 'reached': slot['reached'][i]}
                for i in range(len(funnel))
            ],
        })
    return result


# ── PUB36 — Entonnoir de décrochage par étape, PAR VARIANTE (ad) ─────────────
def variant_funnel(company, *, ad_ids=None):
    """PUB36 — À quelle étape STAGES.py chaque VARIANTE (ad) perd ses leads
    (jamais CONTACTED = ciblage ; meurt à QUOTE_SENT = prix/closing). Réutilise
    ``attribution.variant_stage_funnel`` (ADSENG6 fichier disjoint, aucune
    duplication de la jointure d'ad) — même contrat de forme que
    ``campaign_funnel`` (§5.2) mais résolu par ad plutôt que par campagne.
    Étapes lues via ``pipeline_stage_order()`` (règle #2, jamais en dur)."""
    from .attribution import variant_stage_funnel
    return variant_stage_funnel(company, ad_ids=ad_ids)


# ── §5.3 — Cohortes de signature (leads par semaine → lag) ───────────────────
def signature_cohorts(company, *, date_start=None, date_end=None, today=None,
                      lag_weeks=DEFAULT_LAG_WEEKS):
    """ADSENG33 — Cohortes de signature (§5.3). Groupe les leads par SEMAINE de
    création (lundi) et compte, pour chaque bucket de lag, combien ont signé dans
    ce délai (lag = ``signature_date`` − ``created_date``). Une cohorte dont la
    fenêtre n'est pas écoulée (``today`` − semaine < lag) est marquée
    ``complete=False`` — jamais un zéro final trompeur. Renvoie ::

        [{'cohort_week', 'total_leads', 'signed_total',
          'lag_buckets': [{'lag_weeks', 'signed', 'complete'}, ...]}, ...]
    """
    from apps.crm.selectors import reporting_lead_rows

    today = today or datetime.date.today()
    rows = reporting_lead_rows(
        company, date_start=date_start, date_end=date_end)

    cohorts = {}
    for r in rows:
        cd = r['created_date']
        if cd is None:
            continue
        week_start = cd - datetime.timedelta(days=cd.weekday())  # lundi
        slot = cohorts.setdefault(week_start, {
            'total': 0, 'signed_total': 0,
            'signed': {w: 0 for w in lag_weeks}})
        slot['total'] += 1
        sd = r['signature_date']
        if sd is not None:
            slot['signed_total'] += 1
            lag_days = (sd - cd).days
            for w in lag_weeks:
                if lag_days <= w * 7:
                    slot['signed'][w] += 1

    result = []
    for week_start in sorted(cohorts):
        slot = cohorts[week_start]
        elapsed_days = (today - week_start).days
        result.append({
            'cohort_week': week_start.isoformat(),
            'total_leads': slot['total'],
            'signed_total': slot['signed_total'],
            'lag_buckets': [
                {'lag_weeks': w, 'signed': slot['signed'][w],
                 'complete': elapsed_days >= w * 7}
                for w in lag_weeks
            ],
        })
    return result


# ── §5.4 — Export CSV (table par variante + table de réconciliation) ─────────
def _csv_string(header, rows):
    """Sérialise (header, rows) en CSV — pas de dépendance lourde (§5.4 : un CSV
    simple suffit, jamais une génération Excel serveur)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def variant_table_csv(company, *, qualifying_stage=None):
    """CSV de la table par variante — mêmes colonnes que l'affichage (§5.4)."""
    table = variant_table(company, qualifying_stage=qualifying_stage)
    header = [
        'meta_id', 'name', 'spend', 'leads', 'qualified', 'signed',
        'cost_per_lead', 'cost_per_qualified_lead', 'cost_per_signature',
        'junk', 'junk_rate', 'appointments', 'no_show', 'no_show_rate',
    ]
    rows = [
        [v['meta_id'], v['name'], v['spend'], v['leads'], v['qualified'],
         v['signed'], v['cost_per_lead'] or '',
         v['cost_per_qualified_lead'] or '', v['cost_per_signature'] or '',
         v['junk'], v['junk_rate'] if v['junk_rate'] is not None else '',
         v['appointments'], v['no_show'],
         v['no_show_rate'] if v['no_show_rate'] is not None else '']
        for v in table['variants']
    ]
    return _csv_string(header, rows)


# ── ADSDEEP47 — Leaderboard créatif (hook/angle/format, spend-weighted) + nuage
# hook rate × dépense en quadrants FR (barre Motion, benchmark concurrent §2).
# Les tags viennent du parser de noms ADSDEEP46 (``AdMirror.hook_tag`` /
# ``angle_tag`` / ``format_tag``) ; le hook rate dérivé vient de
# ``metrics.ad_video_metrics_for_window`` (ADSDEEP44). Période sélectionnable
# (défaut : 30 jours glissants). ────────────────────────────────────────────
LEADERBOARD_DIMENSIONS = {
    'hook': 'hook_tag', 'angle': 'angle_tag', 'format': 'format_tag',
}

QUADRANT_HIDDEN_GEM = 'pepites_cachees'
QUADRANT_MONEY_PIT = 'gouffres'
QUADRANT_CONFIRMED_WINNER = 'gagnants_confirmes'
QUADRANT_WATCH = 'a_surveiller'
QUADRANT_LABELS_FR = {
    QUADRANT_HIDDEN_GEM: 'Pépites cachées',
    QUADRANT_MONEY_PIT: 'Gouffres à budget',
    QUADRANT_CONFIRMED_WINNER: 'Gagnants confirmés',
    QUADRANT_WATCH: 'À surveiller',
}

DEFAULT_LEADERBOARD_PERIOD_DAYS = 30


def _default_period(date_start, date_end):
    """Période par défaut : 30 jours glissants se terminant aujourd'hui — la
    même convention que le reste du module (jamais une fenêtre implicite
    « depuis toujours »)."""
    end = date_end or datetime.date.today()
    start = date_start or (
        end - datetime.timedelta(days=DEFAULT_LEADERBOARD_PERIOD_DAYS - 1))
    return start, end


def _ad_window_rows(company, *, date_start, date_end):
    """Une ligne par ``AdMirror`` de la société AYANT au moins un instantané sur
    la période : dépense/résultats cumulés + le bundle vidéo dérivé COMPLET
    (ADSDEEP44 — hook/hold rate, ratio 15s/6s, courbe de rétention, temps de
    visionnage moyen ; PUB8 : avant cette tâche, seul ``hook_rate`` survivait
    ici, le reste étant calculé puis JETÉ). Company-scopé. Un ad sans
    instantané sur la période est simplement absent (jamais une ligne à zéro
    fabriquée)."""
    from django.contrib.contenttypes.models import ContentType

    from . import metrics as metrics_mod
    from .models import AdMirror, InsightSnapshot

    ct = ContentType.objects.get_for_model(AdMirror)
    rows = []
    for ad in AdMirror.objects.filter(company=company):
        snaps = list(InsightSnapshot.objects.filter(
            company=company, content_type=ct, object_id=ad.pk,
            date__gte=date_start, date__lte=date_end))
        if not snaps:
            continue
        spend = sum(
            (s.spend for s in snaps if s.spend is not None), Decimal('0'))
        results = sum((s.results or 0) for s in snaps)
        video = metrics_mod.ad_video_metrics_for_window(snaps)
        rows.append({
            'ad_meta_id': ad.meta_id, 'name': ad.name,
            'hook_tag': ad.hook_tag, 'angle_tag': ad.angle_tag,
            'format_tag': ad.format_tag,
            'spend': spend, 'results': results,
            'hook_rate': video['hook_rate'],
            # PUB8 — bundle complet conservé (plus jamais jeté).
            'hold_rate': video['hold_rate'],
            'ratio_15s_to_6s': video['ratio_15s_to_6s'],
            'retention': video['retention'],
            'watch_time_avg_s': video['watch_time_avg_s'],
        })
    return rows


def creative_leaderboard(company, *, dimension='hook', date_start=None,
                         date_end=None):
    """ADSDEEP47 — Classement SPEND-WEIGHTED par ``dimension`` (hook/angle/
    format). Un ad SANS tag pour cette dimension est exclu du classement
    (jamais regroupé sous un tag inventé) — compté séparément dans
    ``untagged_count``. Le hook rate moyen du groupe est pondéré par la
    dépense ; un ad sans hook rate calculable (pas de données vidéo) ne
    participe qu'à spend/résultats, jamais à la moyenne pondérée (jamais un 0
    fabriqué diluant la moyenne)."""
    date_start, date_end = _default_period(date_start, date_end)
    field = LEADERBOARD_DIMENSIONS.get(dimension, 'hook_tag')
    rows = _ad_window_rows(company, date_start=date_start, date_end=date_end)

    groups = {}
    untagged = 0
    for row in rows:
        tag = row.get(field) or ''
        if not tag:
            untagged += 1
            continue
        g = groups.setdefault(tag, {
            'tag': tag, 'spend': Decimal('0'), 'results': 0, 'ad_count': 0,
            '_hook_weighted_sum': 0.0, '_hook_weight': Decimal('0')})
        g['spend'] += row['spend']
        g['results'] += row['results']
        g['ad_count'] += 1
        if row['hook_rate'] is not None and row['spend'] > 0:
            g['_hook_weighted_sum'] += row['hook_rate'] * float(row['spend'])
            g['_hook_weight'] += row['spend']

    result = []
    for tag, g in groups.items():
        hook_rate_weighted = (
            g['_hook_weighted_sum'] / float(g['_hook_weight'])
            if g['_hook_weight'] > 0 else None)
        cost_per_result = (
            _q2(g['spend'] / g['results']) if g['results'] else None)
        result.append({
            'tag': tag, 'spend': str(g['spend']), 'results': g['results'],
            'cost_per_result': cost_per_result, 'ad_count': g['ad_count'],
            'hook_rate_weighted': (
                round(hook_rate_weighted, 4)
                if hook_rate_weighted is not None else None),
        })
    result.sort(key=lambda r: Decimal(r['spend']), reverse=True)
    return {
        'dimension': dimension,
        'periode': {'debut': date_start.isoformat(),
                    'fin': date_end.isoformat()},
        'classement': result, 'untagged_count': untagged,
    }


def _round4_or_none(value):
    return round(value, 4) if value is not None else None


def creative_scatter(company, *, date_start=None, date_end=None):
    """ADSDEEP47 — Nuage de points hook rate × dépense, classé en 4 quadrants
    FR autour de la MÉDIANE (hook rate, dépense) des ads du lot — jamais un
    seuil absolu (un petit compte SMB n'a pas la même échelle qu'un gros).
    Seuls les ads avec un hook rate CALCULABLE (données vidéo présentes) et
    une dépense > 0 entrent dans le nuage (jamais un point fabriqué à 0).

    PUB8 — chaque point porte aussi le reste du bundle vidéo dérivé
    (``hold_rate``/``ratio_15s_to_6s``/``retention``/``watch_time_avg_s``,
    ``metrics.derived_ad_video_metrics``) — c'est la seule surface reporting
    PAR AD (le leaderboard groupe par tag) : la courbe de rétention par ad
    vidéo (ReportsScreen onglet Créatifs + drill cockpit) se lit ici."""
    date_start, date_end = _default_period(date_start, date_end)
    rows = _ad_window_rows(company, date_start=date_start, date_end=date_end)
    plottable = [
        r for r in rows if r['hook_rate'] is not None and r['spend'] > 0]
    periode = {'debut': date_start.isoformat(), 'fin': date_end.isoformat()}
    if not plottable:
        return {'periode': periode, 'points': [],
                'median_hook_rate': None, 'median_spend': None}

    hook_rates = [r['hook_rate'] for r in plottable]
    spends = [float(r['spend']) for r in plottable]
    med_hook = statistics.median(hook_rates)
    med_spend = statistics.median(spends)

    points = []
    for r in plottable:
        spend_f = float(r['spend'])
        high_hook = r['hook_rate'] >= med_hook
        high_spend = spend_f >= med_spend
        if high_hook and not high_spend:
            quadrant = QUADRANT_HIDDEN_GEM
        elif not high_hook and high_spend:
            quadrant = QUADRANT_MONEY_PIT
        elif high_hook and high_spend:
            quadrant = QUADRANT_CONFIRMED_WINNER
        else:
            quadrant = QUADRANT_WATCH
        retention = r.get('retention') or {}
        points.append({
            'ad_meta_id': r['ad_meta_id'], 'name': r['name'],
            'hook_tag': r['hook_tag'], 'angle_tag': r['angle_tag'],
            'format_tag': r['format_tag'], 'spend': str(r['spend']),
            'hook_rate': round(r['hook_rate'], 4), 'quadrant': quadrant,
            'quadrant_label_fr': QUADRANT_LABELS_FR[quadrant],
            # PUB8 — reste du bundle vidéo (null-safe par clé, jamais un 0
            # fabriqué pour un point manquant).
            'hold_rate': _round4_or_none(r.get('hold_rate')),
            'ratio_15s_to_6s': _round4_or_none(r.get('ratio_15s_to_6s')),
            'retention': {k: _round4_or_none(v) for k, v in retention.items()},
            'watch_time_avg_s': (
                round(r['watch_time_avg_s'], 1)
                if r.get('watch_time_avg_s') is not None else None),
        })
    return {
        'periode': periode, 'points': points,
        'median_hook_rate': round(med_hook, 4),
        'median_spend': round(med_spend, 2),
    }


# ── PUB81 — ROI par LANE de fabrique créative ─────────────────────────────
def factory_lane_roi(company, *, date_start=None, date_end=None):
    """PUB81 — ``CreativeAsset.cost_cents`` est peuplé par chaque adaptateur
    (zapcap/fal/templated/elevenlabs/json2video/chantier/ugc… via
    ``source_lane``) et n'était lu NULLE PART : coût-par-résultat PAR LANE de
    fabrique, quelle filière de production rapporte. Un asset sans lane
    (``source_lane=''``, ex. upload manuel direct) est groupé sous
    ``'manuel'``. Le coût est compté UNE FOIS par asset distinct de la lane
    (coût de production sunk, indépendant du nombre d'ads qui le réutilisent) ;
    les résultats sont sommés sur TOUTES les ads nées des assets de la lane,
    sur la période (défaut 30 jours glissants, comme le leaderboard créatif
    ADSDEEP47). Jointure : ``CreativeAsset`` → ``ExperimentArm.ad_id`` →
    ``AdMirror`` → ``InsightSnapshot``. Company-scopé ; jamais un coût-par-
    résultat fabriqué (``None`` quand aucun résultat)."""
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Sum

    from .models import AdMirror, CreativeAsset, ExperimentArm, InsightSnapshot

    date_start, date_end = _default_period(date_start, date_end)
    periode = {'debut': date_start.isoformat(), 'fin': date_end.isoformat()}

    assets = list(CreativeAsset.objects.filter(company=company)
                  .only('id', 'source_lane', 'cost_cents'))
    if not assets:
        return {'lanes': [], 'periode': periode}
    asset_by_id = {a.id: a for a in assets}

    arms = list(ExperimentArm.objects
                .filter(company=company, creative_asset_id__in=asset_by_id)
                .exclude(ad_id=''))
    ad_meta_ids = {arm.ad_id for arm in arms}
    ad_by_meta = {
        a.meta_id: a for a in
        AdMirror.objects.filter(company=company, meta_id__in=ad_meta_ids)
    } if ad_meta_ids else {}

    results_by_pk = {}
    if ad_by_meta:
        ct = ContentType.objects.get_for_model(AdMirror)
        ad_pks = [a.pk for a in ad_by_meta.values()]
        qs = (InsightSnapshot.objects
              .filter(company=company, content_type=ct, object_id__in=ad_pks,
                      date__gte=date_start, date__lte=date_end)
              .values('object_id')
              .annotate(results=Sum('results'), spend=Sum('spend')))
        results_by_pk = {row['object_id']: row for row in qs}

    lanes = {}
    for arm in arms:
        asset = asset_by_id.get(arm.creative_asset_id)
        ad = ad_by_meta.get(arm.ad_id)
        if asset is None or ad is None:
            continue
        lane_key = asset.source_lane or 'manuel'
        slot = lanes.setdefault(lane_key, {
            'asset_ids': set(), 'results': 0, 'spend': Decimal('0')})
        slot['asset_ids'].add(asset.id)
        agg = results_by_pk.get(ad.pk) or {}
        slot['results'] += agg.get('results') or 0
        slot['spend'] += agg.get('spend') or Decimal('0')

    rows = []
    for lane_key, slot in lanes.items():
        cost_cents_total = sum(
            asset_by_id[aid].cost_cents for aid in slot['asset_ids'])
        results = slot['results']
        cost_per_result_centimes = (
            round(cost_cents_total / results, 2) if results else None)
        rows.append({
            'lane': lane_key,
            'assets_count': len(slot['asset_ids']),
            'cost_cents_total': cost_cents_total,
            'results': results,
            'spend_mad': str(slot['spend']),
            'cost_per_result_centimes': cost_per_result_centimes,
        })
    # Meilleur ROI (coût-par-résultat le plus bas) d'abord ; lanes sans
    # résultat mesurable en fin de liste (jamais un zéro fabriqué en tête).
    rows.sort(key=lambda r: (r['cost_per_result_centimes'] is None,
                             r['cost_per_result_centimes'] or 0))
    return {'lanes': rows, 'periode': periode}


# ── PUB62 — Carte chaleur ville : CPL, coût-par-signature, ticket moyen ──────

def _normalize_place_fr(value):
    return (value or '').strip().lower()


def city_heatmap(company, *, date_start=None, date_end=None):
    """PUB62 — Carte chaleur ville : CPL, coût-par-signature ET ticket moyen
    SIGNÉ par ville (une ville chère en CPL mais à gros tickets industriels
    peut gagner). Croise le breakdown RÉGION Meta (``InsightBreakdown``,
    ADSDEEP7, synchronisé au niveau CAMPAGNE) avec les villes RÉELLES
    saisies sur les leads (``apps.crm.selectors.leads_ville_rows``) et le
    total TTC des devis ACCEPTÉS qui leur sont liés
    (``apps.ventes.selectors.devis_accepted_totals_by_lead``) — jamais un
    import des modèles crm/ventes.

    Le rapprochement ville↔région Meta est TEXTUEL (une région Meta MA type
    « Casablanca-Settat » contient généralement le nom de ville usuel) —
    correspondance dans les deux sens, insensible à la casse ; une ville sans
    correspondance de région n'a simplement pas de CPL/coût-par-signature
    (jamais un chiffre à 0 fabriqué). Une ville SANS AUCUNE donnée
    n'apparaît PAS dans la table (règle checked-facts : les villes sans
    données sont OMISES, jamais un « 0 »).

    Renvoie ``{'periode': {...}|None, 'villes': [{'ville', 'region_meta',
    'spend', 'leads', 'cpl', 'signed', 'cout_par_signature',
    'ticket_moyen_ttc'}, ...]}`` — triable côté appelant sur les 3
    métriques."""
    from decimal import Decimal

    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Sum

    from apps.crm.selectors import leads_ville_rows
    from apps.ventes.selectors import devis_accepted_totals_by_lead
    from .models import AdCampaignMirror, InsightBreakdown

    ct = ContentType.objects.get_for_model(AdCampaignMirror)
    qs = InsightBreakdown.objects.filter(
        company=company, content_type=ct,
        dimension=InsightBreakdown.Dimension.REGION)
    if date_start is not None:
        qs = qs.filter(date__gte=date_start)
    if date_end is not None:
        qs = qs.filter(date__lte=date_end)
    regions = [
        {'key': r['key'], 'spend': r['spend'] or Decimal('0')}
        for r in qs.values('key').annotate(spend=Sum('spend'))
        if r['key']
    ]

    lead_rows = leads_ville_rows(company)
    signed_lead_ids = [r['id'] for r in lead_rows if r['signed']]
    totals_by_lead = devis_accepted_totals_by_lead(company, signed_lead_ids)

    cities = {}
    for row in lead_rows:
        slot = cities.setdefault(row['ville'], {
            'leads': 0, 'signed': 0, 'signed_total': Decimal('0')})
        slot['leads'] += 1
        if row['signed']:
            slot['signed'] += 1
            slot['signed_total'] += totals_by_lead.get(row['id'], Decimal('0'))

    result = []
    for ville, slot in cities.items():
        norm = _normalize_place_fr(ville)
        matched_region, spend = None, None
        for region in regions:
            rnorm = _normalize_place_fr(region['key'])
            if norm and rnorm and (norm in rnorm or rnorm in norm):
                matched_region, spend = region['key'], region['spend']
                break
        leads = slot['leads']
        signed = slot['signed']
        result.append({
            'ville': ville,
            'region_meta': matched_region,
            'spend': _q2(spend) if spend is not None else None,
            'leads': leads,
            'cpl': (_q2(spend / leads)
                    if spend is not None and leads else None),
            'signed': signed,
            'cout_par_signature': (_q2(spend / signed)
                                   if spend is not None and signed else None),
            'ticket_moyen_ttc': (_q2(slot['signed_total'] / signed)
                                 if signed else None),
        })
    result.sort(key=lambda r: r['ville'])

    periode = None
    if date_start is not None or date_end is not None:
        periode = {
            'debut': date_start.isoformat() if date_start else None,
            'fin': date_end.isoformat() if date_end else None,
        }
    return {'periode': periode, 'villes': result}


# ── PUB64 — Calculateur recyclage COLD (aide à la décision, pas une action) ──

MIN_COLD_RECYCLING_LEADS = 1  # au moins un lead COLD exploitable pour parler


def _company_spend_window(company, date_start, date_end):
    """Dépense totale de la société (``InsightSnapshot``, niveau CAMPAGNE —
    évite tout double-comptage avec les instantanés ad set/ad enfants) sur
    ``[date_start, date_end]``. Même primitif ``ContentType`` que
    ``attribution``/``metrics`` (jamais réimplémenté à un autre niveau)."""
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Sum

    from .models import AdCampaignMirror, InsightSnapshot

    ct = ContentType.objects.get_for_model(AdCampaignMirror)
    total = (InsightSnapshot.objects
             .filter(company=company, content_type=ct,
                     date__gte=date_start, date__lte=date_end)
             .aggregate(total=Sum('spend'))['total'])
    return total or Decimal('0')


def cold_recycling_report(company, *, date_start=None, date_end=None):
    """PUB64 — Calculateur d'aide à la décision GO/NO-GO « réactiver un lead
    COLD vs acheter un lead neuf », basé sur les taux de conversion
    HISTORIQUES réels par âge-au-COLD
    (``apps.crm.selectors.cold_reactivation_by_age_bucket``) et le CAC
    COURANT par mode marché (dépense société sur la fenêtre ÷ leads Meta
    NEUFS de ce mode, ``apps.crm.selectors.new_leads_by_mode_meta``). UN
    CALCULATEUR D'AIDE À LA DÉCISION, PAS UNE NURTURE — aucune action n'est
    déclenchée ici.

    Fenêtre par défaut : 90 jours glissants. Données insuffisantes (aucun
    historique COLD exploitable, ou aucun lead Meta neuf sur la fenêtre) → le
    dit CLAIREMENT (``avertissement``) et s'abstient de toute conclusion
    chiffrée fausse."""
    from apps.crm.selectors import (
        cold_reactivation_by_age_bucket, new_leads_by_mode_meta,
    )

    date_start, date_end = _default_period(date_start, date_end)
    spend = _company_spend_window(company, date_start, date_end)
    leads_by_mode = new_leads_by_mode_meta(
        company, date_start=date_start, date_end=date_end)

    cac_par_mode = []
    for mode, count in sorted(leads_by_mode.items()):
        cac_par_mode.append({
            'mode_installation': mode or '(non renseigné)',
            'leads_neufs_meta': count,
            'cac_actuel': _q2(spend / count) if count else None,
        })

    buckets = cold_reactivation_by_age_bucket(company)
    has_cold_data = sum(b['total'] for b in buckets) >= MIN_COLD_RECYCLING_LEADS
    donnees_suffisantes = has_cold_data and bool(cac_par_mode)

    return {
        'periode': {'debut': date_start.isoformat(),
                    'fin': date_end.isoformat()},
        'depense_totale': _q2(spend),
        'cac_par_mode': cac_par_mode,
        'reconversion_par_age_cold': buckets,
        'donnees_suffisantes': donnees_suffisantes,
        'avertissement': (
            None if donnees_suffisantes else
            "Historique de leads COLD ou dépense/leads Meta neufs "
            "insuffisants sur la période pour un calcul fiable — "
            "abstention (aucune conclusion chiffrée)."),
    }


# ── PUB67 — Saisonnalité pilotée par l'historique RÉEL (recommandation seule) ─

MIN_MONTHS_COVERAGE_SEASONALITY = 12


def seasonality_report(company):
    """PUB67 — Rapport « votre saisonnalité » : vélocité de signature RÉELLE
    mois-par-mois PAR MODE MARCHÉ (``apps.ventes.selectors.
    signature_velocity_by_month_and_mode`` + ``pacing.
    monthly_signature_shares``, RÉUTILISÉ) → RECOMMANDATION de réallocation
    budgétaire saisonnière. Distinct du calendrier fixe générique PUB78 —
    ici c'est la donnée Taqinor RÉELLE. RECOMMANDATION SEULE, jamais une
    action automatique.

    <``MIN_MONTHS_COVERAGE_SEASONALITY`` mois-calendaires distincts de
    données → le dit EXPLICITEMENT et s'abstient de toute recommandation
    (jamais un signal saisonnier fabriqué sur un historique trop court)."""
    from . import pacing
    from apps.ventes.selectors import signature_velocity_by_month_and_mode

    data = signature_velocity_by_month_and_mode(company)
    if data['mois_couverts'] < MIN_MONTHS_COVERAGE_SEASONALITY:
        return {
            'donnees_suffisantes': False,
            'mois_couverts': data['mois_couverts'],
            'seuil_requis': MIN_MONTHS_COVERAGE_SEASONALITY,
            'avertissement': (
                f"Seulement {data['mois_couverts']} mois-calendaires "
                f"distincts de devis signés — "
                f"{MIN_MONTHS_COVERAGE_SEASONALITY} requis pour un cycle "
                f"annuel complet. Abstention (aucune recommandation)."),
            'par_mode': [],
        }

    par_mode = []
    for mode, months in sorted(data['par_mode'].items()):
        total = sum(months.values())
        if total == 0:
            continue
        shares = pacing.monthly_signature_shares(months)
        pic = max(shares, key=shares.get)
        creux = min(shares, key=shares.get)
        par_mode.append({
            'mode_installation': mode,
            'total_signatures': total,
            'repartition_mensuelle': {m: round(s, 4)
                                      for m, s in shares.items()},
            'mois_pic': pic,
            'mois_creux': creux,
            'recommandation_fr': (
                f"{mode} : pic historique en mois {pic} "
                f"({shares[pic] * 100:.0f} % des signatures), creux en "
                f"mois {creux} ({shares[creux] * 100:.0f} %) — envisager "
                f"de réallouer le budget vers le mois {pic} à l'approche "
                f"de la saison (recommandation seule, aucune action "
                f"automatique)."),
        })
    return {
        'donnees_suffisantes': True,
        'mois_couverts': data['mois_couverts'],
        'seuil_requis': MIN_MONTHS_COVERAGE_SEASONALITY,
        'avertissement': None,
        'par_mode': par_mode,
    }


# ── PUB68 — SLA première réponse : médiane par ad ────────────────────────────

def response_time_by_ad(company):
    """PUB68 — Temps de première réponse MÉDIAN par ad (minutes) — la donnée
    la plus documentée du marché (répondre <1 min ≈ ×4-5 conversion),
    jusqu'ici jamais mesurée par l'ERP. Réutilise ``selectors.
    leads_response_time_by_ad_rows`` (fichier disjoint, résolution d'ad
    ADSENG6). Un ad sans lead contacté résolu est ABSENT (jamais une
    médiane sur 0 valeur). Renvoie une liste triée par médiane croissante
    (le plus réactif d'abord) ``[{'meta_id', 'name',
    'median_response_minutes', 'sample_size'}, ...]``."""
    import statistics

    from .selectors import leads_response_time_by_ad_rows

    by_ad = {}
    for row in leads_response_time_by_ad_rows(company):
        slot = by_ad.setdefault(
            row['meta_id'], {'name': row['name'], 'times': []})
        slot['times'].append(row['response_minutes'])

    result = [
        {'meta_id': meta_id, 'name': slot['name'],
         'median_response_minutes': round(
             statistics.median(slot['times']), 1),
         'sample_size': len(slot['times'])}
        for meta_id, slot in by_ad.items()
    ]
    result.sort(key=lambda r: r['median_response_minutes'])
    return result


# ── PUB88 — Livre de compte de l'exploration (exploration vs exploitation) ────
# Le plancher d'exploration (20 %) est de l'argent RÉEL : on rend visible, en
# ligne mensuelle, « MAD dépensés à explorer vs sur le gagnant confirmé » pour
# que le coût d'apprentissage devienne pilotable. Lecture des ALLOCATIONS
# loggées (``DecisionLog.allocations`` : budget_mad + prob_best par bras) — la
# source de vérité de ce que le moteur a dirigé, jamais une ré-estimation.
def classify_allocation(budget_map, prob_map, *,
                        confirm_threshold=CONFIRMED_WINNER_PROB):
    """Répartit le budget d'UNE décision en (exploration, exploitation). Pure.

    ``budget_map`` : ``{label: mad}`` (``allocations.budget_mad``). ``prob_map`` :
    ``{label: P(meilleur)}`` (``allocations.prob_best``). Exploitation = budget
    dirigé vers un bras dont ``P(meilleur) ≥ confirm_threshold`` (gagnant
    confirmé) ; exploration = tout le reste (plancher + budget sur les bras non
    confirmés). Sans gagnant confirmé, 100 % est de l'exploration. Renvoie
    ``(exploration_mad, exploitation_mad)``.
    """
    exploration = 0.0
    exploitation = 0.0
    for label, mad in (budget_map or {}).items():
        try:
            amount = float(mad)
        except (TypeError, ValueError):
            continue
        prob = 0.0
        try:
            prob = float((prob_map or {}).get(label, 0.0))
        except (TypeError, ValueError):
            prob = 0.0
        if prob >= confirm_threshold:
            exploitation += amount
        else:
            exploration += amount
    return (exploration, exploitation)


def _month_key(dt):
    """Clé mensuelle ``YYYY-MM`` d'un datetime aware/naïf (jamais une exception)."""
    return f'{dt.year:04d}-{dt.month:02d}'


def exploration_ledger(company, *, date_start=None, date_end=None,
                       confirm_threshold=CONFIRMED_WINNER_PROB):
    """PUB88 — Livre de compte MENSUEL exploration vs exploitation (society-scopé).

    Lit chaque ``DecisionLog`` de la société (allocations loggées), classe son
    budget via :func:`classify_allocation`, et agrège par mois de décision.
    Renvoie une liste ordonnée du plus ancien au plus récent ::

        [{'mois', 'exploration_mad', 'exploitation_mad', 'total_mad',
          'exploration_pct', 'decisions'}, …]

    ``exploration_pct`` est None quand le total du mois est nul (jamais un 0 %
    trompeur). Les montants sont arrondis au centime.
    """
    from .models import DecisionLog

    qs = DecisionLog.objects.filter(company=company)
    if date_start is not None:
        qs = qs.filter(created_at__date__gte=date_start)
    if date_end is not None:
        qs = qs.filter(created_at__date__lte=date_end)

    months = {}
    for log in qs:
        allocations = log.allocations or {}
        budget_map = allocations.get('budget_mad') or {}
        prob_map = allocations.get('prob_best') or {}
        expl, exploit = classify_allocation(
            budget_map, prob_map, confirm_threshold=confirm_threshold)
        key = _month_key(log.created_at)
        slot = months.setdefault(
            key, {'exploration': 0.0, 'exploitation': 0.0, 'decisions': 0})
        slot['exploration'] += expl
        slot['exploitation'] += exploit
        slot['decisions'] += 1

    result = []
    for key in sorted(months):
        slot = months[key]
        total = slot['exploration'] + slot['exploitation']
        result.append({
            'mois': key,
            'exploration_mad': round(slot['exploration'], 2),
            'exploitation_mad': round(slot['exploitation'], 2),
            'total_mad': round(total, 2),
            'exploration_pct': (round(slot['exploration'] / total * 100, 1)
                                if total > 0 else None),
            'decisions': slot['decisions'],
        })
    return result


def reconciliation_csv(company, *, day=None):
    """CSV de la table de réconciliation (§5.4). Réutilise
    ``reconciliation.reconcile`` (ADSENG31, fichier disjoint) — jamais un schéma
    d'export dédié."""
    from .reconciliation import reconcile

    contract = reconcile(company, date=day)
    header = [
        'campaign_meta_id', 'campaign_name', 'meta_leads', 'erp_leads',
        'delta_leads', 'ratio', 'status', 'cause_fr',
    ]
    rows = [
        [c['campaign_meta_id'], c['campaign_name'], c['meta_leads'],
         c['erp_leads'], c['delta_leads'], c['ratio'], c['status'],
         c['cause_fr']]
        for c in contract['campaigns']
    ]
    return _csv_string(header, rows)


# ── PUB77 — Performance créative COMPARABLE PAR LANGUE (fr / darija / amazigh) ─
#
# Deux variantes FR/Darija du même hook étaient indistinguables : on splite la
# performance des ``CreativeAsset`` par ``language``. La perf vient du champ
# ``perf`` de l'asset (remontée d'insights : impressions/spend/résultats). Un
# asset sans langue renseignée est compté À PART (``untagged_count``) — jamais
# regroupé sous une langue fabriquée (règle checked-facts-only).

def _perf_num(perf, *keys):
    """Nombre (float) lu au mieux dans le dict ``perf`` (0.0 si absent)."""
    for key in keys:
        val = (perf or {}).get(key)
        if val not in (None, ''):
            try:
                return float(val)
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def _perf_money(perf, *keys):
    """Montant Decimal lu au mieux dans ``perf`` (0 si absent) — SANS passer par
    ``float`` (un ``float(100)`` → ``Decimal('100.0')`` traînerait un « .0 »
    parasite sur les entiers ; la dépense doit rester un Decimal propre)."""
    for key in keys:
        val = (perf or {}).get(key)
        if val not in (None, ''):
            try:
                return Decimal(str(val))
            except (ArithmeticError, TypeError, ValueError):
                return Decimal('0')
    return Decimal('0')


def language_leaderboard(company):
    """PUB77 — Classement de la performance créative PAR LANGUE.

    Groupe les ``CreativeAsset`` de la société par ``language`` (fr / ar-ma /
    amazigh) et agrège leur perf (dépense / résultats / impressions). Renvoie
    ``{classement: [...], untagged_count}`` — un asset sans langue est compté
    séparément, jamais rangé sous une langue inventée. Le coût-par-résultat est
    ``None`` sans résultat (jamais un 0 trompeur). Lecture seule, company-scopé."""
    from .models import CreativeAsset

    labels = dict(CreativeAsset.Language.choices)
    groups = {}
    untagged = 0
    for asset in CreativeAsset.objects.filter(company=company):
        lang = asset.language or ''
        if not lang:
            untagged += 1
            continue
        g = groups.setdefault(lang, {
            'language': lang, 'language_label': labels.get(lang, lang),
            'spend': Decimal('0'), 'results': 0, 'impressions': 0,
            'asset_count': 0})
        perf = asset.perf or {}
        g['spend'] += _perf_money(perf, 'spend', 'depense')
        g['results'] += int(_perf_num(perf, 'results', 'resultats'))
        g['impressions'] += int(_perf_num(perf, 'impressions'))
        g['asset_count'] += 1

    classement = []
    for lang, g in groups.items():
        cost_per_result = (
            _q2(g['spend'] / g['results']) if g['results'] else None)
        classement.append({
            'language': lang, 'language_label': g['language_label'],
            'spend': str(g['spend']), 'results': g['results'],
            'impressions': g['impressions'], 'asset_count': g['asset_count'],
            'cost_per_result': cost_per_result,
        })
    classement.sort(key=lambda r: Decimal(r['spend']), reverse=True)
    return {'classement': classement, 'untagged_count': untagged}


# ── PUB82 — Rétention par SCÈNE de script (beat ↔ percentile vidéo) ───────────
#
# Les percentiles de rétention Meta (p25/p50/p75/p100) disent « à quel % du film
# l'audience chute » ; en les reliant aux *beats* PERSISTÉS du script
# (``CreativeAsset.script_beats``) on répond « à quelle SCÈNE » (« la chute
# arrive à la scène du prix »). Beats répartis uniformément sur la durée.

RETENTION_PERCENTILES = (25, 50, 75, 100)


def _beat_index_at_percentile(percentile, n_beats):
    """Index de la scène jouée au repère ``percentile`` % (beats uniformes)."""
    if n_beats <= 0:
        return None
    idx = int(percentile / 100.0 * n_beats)
    return min(n_beats - 1, idx)


def script_beat_retention(asset):
    """PUB82 — Mapping beat↔percentile de rétention pour un asset vidéo.

    Renvoie ``{beat_count, mapping: [{percentile, retention, beat_index,
    beat_text, fact_key}]}`` — chaque percentile pointe la SCÈNE jouée à ce
    repère + la valeur de rétention (``asset.perf['retention']``, ou ``None`` si
    non mesurée : jamais un chiffre fabriqué). ``beat_count == 0`` (aucun beat
    persisté) → mapping vide."""
    beats = list(asset.script_beats or [])
    n = len(beats)
    retention = (asset.perf or {}).get('retention') or {}
    mapping = []
    for p in RETENTION_PERCENTILES:
        idx = _beat_index_at_percentile(p, n)
        beat = beats[idx] if idx is not None else None
        beat_text = ''
        fact_key = None
        if isinstance(beat, dict):
            beat_text = beat.get('text', '') or ''
            fact_key = beat.get('fact_key')
        elif beat is not None:
            beat_text = str(beat)
        mapping.append({
            'percentile': p,
            'retention': retention.get(f'p{p}'),
            'beat_index': idx,
            'beat_text': beat_text,
            'fact_key': fact_key,
        })
    return {'beat_count': n, 'mapping': mapping}
