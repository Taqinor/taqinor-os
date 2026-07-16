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
