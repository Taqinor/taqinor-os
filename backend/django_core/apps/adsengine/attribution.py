"""ADSENG6 — Jointure d'attribution PAR VARIANTE (le delta ENG10→ADSENG).

ENG10 (``metrics.py``) mesure le coût-par-signature au niveau CAMPAGNE
(``utm_campaign``). Ce module descend au niveau AD / VARIANTE — le vrai signal de
récompense du bandit (P1) — sans rien changer à ENG10 (fichier disjoint).

Chemin de jointure (dd-attribution §a/§e) ::

    adsengine.AdMirror (meta_id, name)
            │  clé stable = meta_ad_id (ADSENG1) ; sinon utm_content
            ▼
    crm.Lead  (via apps.crm.selectors UNIQUEMENT — jamais un import des modèles)
            │  → qualifié ? signé ? (stades depuis STAGES.py, côté crm)
            ▼
    adsengine.InsightSnapshot (dépense par ad)
            │
            ▼
    coût-par-lead-qualifié + coût-par-signature PAR BRAS

Échelle de résolution (dd-attribution §2.4, premier gagnant, jamais silencieuse) :
  1. ``meta_ad_id`` présent et connu → variante exacte (confiance haute) ;
  1b. ``utm_content == 'ad-<meta_ad_id>'`` (convention ADSENG1) → variante exacte ;
  2. ``utm_content`` == nom d'un ``AdMirror`` → variante fuzzy (confiance moyenne) ;
  3/4. lead Meta avec utm mais sans correspondance ad → bucket « non résolu »
       (jamais fondu dans « organique ») ;
  5. sinon → organique, EXCLU du dénominateur des variantes (jamais compté à
     coût zéro — ce qui ferait paraître chaque ad infiniment efficace).
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def _q2(value):
    """Arrondi monétaire à 2 décimales (str), ou None si dénominateur nul."""
    return str(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _rate(numerator, denominator):
    """PUB28/PUB37 — taux ``numerator / denominator`` arrondi à 4 décimales
    (fraction 0..1, ex. 0.25 = 25 %), ou None si le dénominateur est nul
    (jamais un taux zéro fabriqué — même discipline que ``cost_per_signature``)."""
    if not denominator:
        return None
    return float(
        (Decimal(numerator) / Decimal(denominator))
        .quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))


def _resolve_ad_id(row, by_meta, name_to_meta):
    """Applique l'échelle de résolution à une ligne de lead. Renvoie le
    ``meta_id`` de l'ad attribuée, ou None si non résolue au niveau variante."""
    # Tier 1 — clé stable meta_ad_id (ADSENG1).
    meta_ad_id = row.get('meta_ad_id') or ''
    if meta_ad_id and meta_ad_id in by_meta:
        return meta_ad_id
    utm_content = row.get('utm_content') or ''
    if utm_content:
        # Tier 1b — convention ADSENG1 'ad-<meta_ad_id>'.
        if utm_content.startswith('ad-'):
            candidate = utm_content[3:]
            if candidate in by_meta:
                return candidate
        # Tier 2 — utm_content == nom d'un AdMirror (fuzzy, affichage).
        if utm_content in name_to_meta:
            return name_to_meta[utm_content]
    return None


def variant_attribution(company, *, qualifying_stage=None, ad_ids=None):
    """ADSENG6 — Attribution par variante pour une société.

    Renvoie un dict ::

        {
          'variants': [
            {'meta_id', 'name', 'spend', 'leads', 'qualified', 'signed',
             'cost_per_qualified_lead', 'cost_per_signature',
             'lead_ids', 'signed_lead_ids', 'junk', 'junk_rate',
             'appointments', 'no_show', 'no_show_rate'}, ...
          ],
          'unresolved': {'leads', 'qualified', 'signed', 'junk',
                         'appointments', 'no_show', 'lead_ids'},
          'organic_excluded_count': int,
        }

    ``cost_per_qualified_lead`` / ``cost_per_signature`` = dépense de l'ad ÷
    (leads qualifiés / signés attribués), ou None quand le dénominateur est nul
    (jamais une division par zéro, jamais un coût zéro fabriqué). Chaque chiffre
    porte les ids de leads qui le composent (traçabilité Northbeam). Scopé
    société ; ENG10 (niveau campagne) reste inchangé.
    """
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Sum

    from apps.crm.selectors import attribution_lead_rows, lead_appointment_stats
    from .models import AdMirror, InsightSnapshot

    ad_qs = AdMirror.objects.filter(company=company)
    if ad_ids is not None:
        ad_qs = ad_qs.filter(meta_id__in=[str(a) for a in ad_ids])
    ads = list(ad_qs)
    by_meta = {a.meta_id: a for a in ads}
    # Nom → meta_id (tier 2). En cas de noms dupliqués, le premier vu gagne.
    name_to_meta = {}
    for a in ads:
        if a.name:
            name_to_meta.setdefault(a.name, a.meta_id)

    # Dépense par ad (InsightSnapshot, FK générique sur AdMirror).
    ct = ContentType.objects.get_for_model(AdMirror)
    spend_by_pk = {}
    if ads:
        snaps = (InsightSnapshot.objects
                 .filter(company=company, content_type=ct,
                         object_id__in=[a.pk for a in ads])
                 .values('object_id')
                 .annotate(total=Sum('spend')))
        for s in snaps:
            spend_by_pk[s['object_id']] = s['total'] or Decimal('0')

    def _new_bucket():
        return {'leads': 0, 'qualified': 0, 'signed': 0, 'junk': 0,
                'appointments': 0, 'no_show': 0,
                'lead_ids': [], 'signed_lead_ids': []}

    variants = {m: _new_bucket() for m in by_meta}
    unresolved = {'leads': 0, 'qualified': 0, 'signed': 0, 'junk': 0,
                  'appointments': 0, 'no_show': 0, 'lead_ids': []}
    organic_excluded = 0
    # PUB37 — RDV (Appointment) PAR LEAD, pour le taux de no-show par variante
    # (signal qualité intermédiaire : une annonce qui génère des RDV fantômes
    # coûte cher avant que le coût-par-signature ne le montre).
    appt_stats = lead_appointment_stats(company)

    for row in attribution_lead_rows(company, qualifying_stage=qualifying_stage):
        meta_id = _resolve_ad_id(row, by_meta, name_to_meta)
        appt = appt_stats.get(row['id'])
        if meta_id is not None:
            bucket = variants[meta_id]
            bucket['leads'] += 1
            bucket['lead_ids'].append(row['id'])
            if row['qualified']:
                bucket['qualified'] += 1
            # PUB28 — signal qualité junk, DISTINCT de « non qualifié » (un
            # lead junk est perdu pour une raison qui n'en a jamais fait un
            # vrai prospect — voir MotifPerte.est_junk).
            if row.get('junk'):
                bucket['junk'] += 1
            if row['signed']:
                bucket['signed'] += 1
                bucket['signed_lead_ids'].append(row['id'])
            if appt:
                bucket['appointments'] += appt['total']
                bucket['no_show'] += appt['no_show']
        elif (row.get('utm_content') or row.get('utm_campaign')
              or row.get('is_meta_channel')):
            # A une intention Meta (utm ou canal) mais aucune variante résolue :
            # bucket « non résolu » — JAMAIS fondu dans « organique ».
            unresolved['leads'] += 1
            unresolved['lead_ids'].append(row['id'])
            if row['qualified']:
                unresolved['qualified'] += 1
            if row.get('junk'):
                unresolved['junk'] += 1
            if row['signed']:
                unresolved['signed'] += 1
            if appt:
                unresolved['appointments'] += appt['total']
                unresolved['no_show'] += appt['no_show']
        else:
            # Organique (aucun utm, canal non-Meta) : exclu du dénominateur.
            organic_excluded += 1

    # ADSDEEP20 — signatures Odoo RÉELLES par ad (deal signé → phone_key →
    # MetaLeadMirror → ad_id), avec coût/signature sur la dépense ad réelle.
    # Best-effort + guardé : sans connecteur Odoo configuré, tout reste 0 (aucun
    # appel réseau) — le CRM-signed historique ci-dessus est inchangé.
    odoo_by_ad = {}
    try:
        from .odoo_client import is_configured as _odoo_configured
        if _odoo_configured():
            from .odoo_metrics import odoo_signatures_by_ad
            odoo_res = odoo_signatures_by_ad(company)
            odoo_by_ad = {a['ad_id']: a for a in odoo_res.get('ads', [])}
    except Exception:  # noqa: BLE001 — l'attribution CRM ne dépend jamais d'Odoo
        odoo_by_ad = {}

    variant_rows = []
    for meta_id, bucket in variants.items():
        ad = by_meta[meta_id]
        spend = spend_by_pk.get(ad.pk, Decimal('0'))
        cpql = (_q2(spend / bucket['qualified'])
                if bucket['qualified'] else None)
        cps = (_q2(spend / bucket['signed'])
               if bucket['signed'] else None)
        odoo = odoo_by_ad.get(meta_id, {})
        variant_rows.append({
            'meta_id': meta_id,
            'name': ad.name or '',
            'spend': _q2(spend),
            'leads': bucket['leads'],
            'qualified': bucket['qualified'],
            'signed': bucket['signed'],
            'cost_per_qualified_lead': cpql,
            'cost_per_signature': cps,
            'lead_ids': bucket['lead_ids'],
            'signed_lead_ids': bucket['signed_lead_ids'],
            # PUB28 — signal qualité junk PAR AD (numéro invalide/spam/hors
            # zone/jamais répondu — voir MotifPerte.est_junk), distinct du
            # simple « non qualifié ».
            'junk': bucket['junk'],
            'junk_rate': _rate(bucket['junk'], bucket['leads']),
            # PUB37 — taux de no-show PAR AD (RDV honorés vs fantômes),
            # signal qualité intermédiaire avant le coût-par-signature.
            'appointments': bucket['appointments'],
            'no_show': bucket['no_show'],
            'no_show_rate': _rate(bucket['no_show'], bucket['appointments']),
            # ADSDEEP20 — signatures Odoo par ad (deals traçables).
            'odoo_signed': odoo.get('signatures', 0),
            'odoo_cost_per_signature': odoo.get('cost_per_signature'),
            'odoo_signed_deal_ids': odoo.get('deal_ids', []),
        })
    # Tri par coût-par-signature ascendant (les meilleurs d'abord) ; les ads sans
    # signature en fin de liste.
    variant_rows.sort(
        key=lambda r: (r['cost_per_signature'] is None,
                       Decimal(r['cost_per_signature'])
                       if r['cost_per_signature'] else Decimal('0'),
                       r['meta_id']))

    return {
        'variants': variant_rows,
        'unresolved': unresolved,
        'organic_excluded_count': organic_excluded,
    }
