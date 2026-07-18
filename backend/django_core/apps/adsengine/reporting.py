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
    ]
    rows = [
        [v['meta_id'], v['name'], v['spend'], v['leads'], v['qualified'],
         v['signed'], v['cost_per_lead'] or '',
         v['cost_per_qualified_lead'] or '', v['cost_per_signature'] or '']
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
    la période : dépense/résultats cumulés + hook rate dérivé (ADSDEEP44).
    Company-scopé. Un ad sans instantané sur la période est simplement absent
    (jamais une ligne à zéro fabriquée)."""
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


def creative_scatter(company, *, date_start=None, date_end=None):
    """ADSDEEP47 — Nuage de points hook rate × dépense, classé en 4 quadrants
    FR autour de la MÉDIANE (hook rate, dépense) des ads du lot — jamais un
    seuil absolu (un petit compte SMB n'a pas la même échelle qu'un gros).
    Seuls les ads avec un hook rate CALCULABLE (données vidéo présentes) et
    une dépense > 0 entrent dans le nuage (jamais un point fabriqué à 0)."""
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
        points.append({
            'ad_meta_id': r['ad_meta_id'], 'name': r['name'],
            'hook_tag': r['hook_tag'], 'angle_tag': r['angle_tag'],
            'format_tag': r['format_tag'], 'spend': str(r['spend']),
            'hook_rate': round(r['hook_rate'], 4), 'quadrant': quadrant,
            'quadrant_label_fr': QUADRANT_LABELS_FR[quadrant],
        })
    return {
        'periode': periode, 'points': points,
        'median_hook_rate': round(med_hook, 4),
        'median_spend': round(med_spend, 2),
    }


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
