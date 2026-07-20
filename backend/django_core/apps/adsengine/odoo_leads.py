"""FIXPUB6 — Leads Odoo attribués PAR ANNONCE (coût-par-lead Odoo).

Variante ADDITIVE des métriques : là où ``odoo_metrics.odoo_signatures_by_ad``
descend les SIGNATURES Odoo au niveau ad (deals signés), ce module descend TOUS
les leads Odoo (``odoo_selectors.all_leads``) au niveau ad — le dénominateur d'un
coût-par-lead (``cpl_odoo``).

ATTRIBUTION D'UN LEAD À UNE ANNONCE — trois paliers, premier gagnant :
  1. EXACT — le ``phone_norm`` du lead correspond au ``phone_key`` (QW10) d'un
     ``MetaLeadMirror`` de la société (ADSDEEP17) → son ``ad_id`` ;
  2. ESTIMATION (nom) — le nom du lead Odoo, souvent encodé
     (« AGENCE-…FORM-jj/mm/aaaa », ADSDEEP21), est parsé
     (``parse_odoo_lead_name``) puis rapproché du nom d'une annonce miroir ;
  3. ESTIMATION (date) — à défaut, si UNE seule annonce dépensait le jour du lead
     (fenêtre date), on l'y rattache — marqué « estimation ».

Les paliers 2/3 sont TOUJOURS étiquetés estimation (``attribution_type`` =
``exact`` / ``estimation`` / ``mixte`` par annonce) — jamais fondus en silence
avec l'exact (mêmes garde-fous que ADSDEEP21). Sans configuration Odoo → NO-OP
propre (``configured=False``, aucune ligne). Ne lève JAMAIS (dégradation propre
comme ``odoo_signatures_by_ad``).

Réutilise les sélecteurs/aides déjà construits du même module Odoo
(``_ad_spend_by_meta``, ``_phone_to_ad``, ``_as_date`` d'``odoo_metrics``) — la
dépense ad vient de la MÊME source ``InsightSnapshot`` (ADSDEEP2) que le coût-par-
signature, jamais un deuxième calcul de dépense inventé ici.
"""
from __future__ import annotations

import datetime

from .odoo_client import is_configured as odoo_is_configured
from .odoo_selectors import all_leads as odoo_all_leads
from .odoo_selectors import parse_odoo_lead_name

# Longueur minimale d'un indice de nom pour tenter un rapprochement (évite les
# faux positifs sur des jetons trop courts).
_MIN_HINT_LEN = 3

LEADS_ATTRIBUTION_NOTE = (
    "Leads Odoo attribués par annonce : palier EXACT par téléphone "
    "(MetaLeadMirror), puis ESTIMATION par nom de lead encodé (ADSDEEP21), puis "
    "ESTIMATION par fenêtre date. Les estimations ne sont jamais fondues avec "
    "l'exact (voir attribution_type)."
)


def _lead_day(value):
    """``value`` (date Odoo ``YYYY-MM-DD[ HH:MM:SS]``) → ``YYYY-MM-DD`` valide, ou
    None si illisible/absent."""
    if not value:
        return None
    s = str(value)[:10]
    try:
        datetime.date.fromisoformat(s)
    except ValueError:
        return None
    return s


def _name_matcher(company):
    """Construit un matcher ``parsed → ad_id|None`` : rapproche les indices d'un
    nom de lead Odoo parsé (form_hint / source / campaign_hint) du nom d'une
    annonce miroir de la société. Déterministe (annonces triées par création ;
    première correspondance gagne)."""
    from .models import AdMirror

    ads = [(a.meta_id, (a.name or '').lower())
           for a in (AdMirror.objects
                     .filter(company=company)
                     .exclude(meta_id='')
                     .only('meta_id', 'name', 'created_at')
                     .order_by('created_at'))]

    def match(parsed):
        hints = []
        for key in ('form_hint', 'source', 'campaign_hint'):
            val = (parsed.get(key) or '').strip().lower()
            if len(val) >= _MIN_HINT_LEN:
                hints.append(val)
        for meta_id, name_lower in ads:
            if not name_lower:
                continue
            for hint in hints:
                if hint in name_lower:
                    return meta_id
        return None

    return match


def _active_ad_dates(company, since):
    """``{jour_iso: {ad_meta_id, ...}}`` des annonces AYANT dépensé un jour donné
    (``InsightSnapshot.spend > 0`` sur ``AdMirror``, bornée ``date >= since``).
    Une requête ; vide sans miroir d'annonce."""
    from django.contrib.contenttypes.models import ContentType

    from .models import AdMirror, InsightSnapshot
    from .odoo_metrics import _as_date

    pk_to_meta = {a.pk: a.meta_id
                  for a in AdMirror.objects.filter(company=company)
                  .only('id', 'meta_id')}
    if not pk_to_meta:
        return {}
    ct = ContentType.objects.get_for_model(AdMirror)
    qs = InsightSnapshot.objects.filter(
        company=company, content_type=ct,
        object_id__in=list(pk_to_meta), spend__gt=0)
    since_date = _as_date(since)
    if since_date is not None:
        qs = qs.filter(date__gte=since_date)
    out = {}
    for row in qs.values('object_id', 'date'):
        meta = pk_to_meta.get(row['object_id'])
        if meta and row['date'] is not None:
            out.setdefault(row['date'].isoformat(), set()).add(meta)
    return out


def _attribute_lead(lead, phone_to_ad, name_match, date_to_ads):
    """Attribue UN lead à AU PLUS une annonce. Renvoie ``(ad_id, tier)`` où
    ``tier`` vaut ``'exact'`` / ``'estimation'`` — ``(None, None)`` si aucun
    palier n'aboutit."""
    phone = lead.get('phone_norm') or ''
    if phone and phone in phone_to_ad:
        return phone_to_ad[phone], 'exact'
    # Palier 2 — nom encodé (ADSDEEP21).
    parsed = parse_odoo_lead_name(lead.get('source_name'))
    if parsed is not None:
        ad_id = name_match(parsed)
        if ad_id:
            return ad_id, 'estimation'
    # Palier 3 — fenêtre date : une SEULE annonce active ce jour-là.
    day = _lead_day(lead.get('date'))
    if day is not None:
        ads_on_day = date_to_ads.get(day)
        if ads_on_day and len(ads_on_day) == 1:
            return next(iter(ads_on_day)), 'estimation'
    return None, None


def odoo_leads_by_ad(company, since=None, client=None):
    """FIXPUB6 — Leads Odoo attribués PAR AD + coût-par-lead (``cpl_odoo``).

    Renvoie ::

        {
          'configured': bool,
          'ads': [ {ad_id, ad_name, leads_odoo, leads_exact, leads_estimes,
                    attribution_type, lead_ids, spend, cpl_odoo}, ... ],
          'attributed': int, 'unattributed': int, 'note': str,
          'odoo_error': str,   # seulement si la lecture Odoo échoue
        }

    ``leads_odoo`` = leads exacts + estimés attribués à l'annonce ;
    ``cpl_odoo`` = dépense ad (InsightSnapshot ADSDEEP2, bornée ``since``) ÷
    ``leads_odoo`` (None si 0). Ne lève JAMAIS (dégradation propre)."""
    from .models import AdMirror
    from .odoo_metrics import _ad_spend_by_meta, _phone_to_ad

    odoo_error = None
    try:
        leads = odoo_all_leads(client=client)
    except Exception as exc:  # noqa: BLE001 — dégradation propre (jamais un 500)
        leads = []
        odoo_error = f"{type(exc).__name__}: {exc}"[:300]

    phone_to_ad = _phone_to_ad(company)
    name_match = _name_matcher(company)
    date_to_ads = _active_ad_dates(company, since)

    buckets = {}
    attributed = unattributed = 0
    for lead in leads:
        ad_id, tier = _attribute_lead(
            lead, phone_to_ad, name_match, date_to_ads)
        if ad_id:
            bucket = buckets.setdefault(
                ad_id, {'exact': 0, 'estimes': 0, 'lead_ids': []})
            if tier == 'exact':
                bucket['exact'] += 1
            else:
                bucket['estimes'] += 1
            if lead.get('lead_id') is not None:
                bucket['lead_ids'].append(lead['lead_id'])
            attributed += 1
        else:
            unattributed += 1

    spend_by_ad = _ad_spend_by_meta(company, buckets.keys(), since)
    name_by_meta = {
        a.meta_id: (a.name or '')
        for a in AdMirror.objects.filter(
            company=company, meta_id__in=list(buckets)).only('meta_id', 'name')}

    ads = []
    for ad_id in sorted(buckets):
        bucket = buckets[ad_id]
        total = bucket['exact'] + bucket['estimes']
        spend = spend_by_ad.get(ad_id)
        cpl = (spend / total) if (spend is not None and total) else None
        if bucket['exact'] and bucket['estimes']:
            attr_type = 'mixte'
        elif bucket['exact']:
            attr_type = 'exact'
        else:
            attr_type = 'estimation'
        ads.append({
            'ad_id': ad_id,
            'ad_name': name_by_meta.get(ad_id, ''),
            'leads_odoo': total,
            'leads_exact': bucket['exact'],
            'leads_estimes': bucket['estimes'],
            'attribution_type': attr_type,
            'lead_ids': bucket['lead_ids'],
            'spend': (str(spend) if spend is not None else None),
            'cpl_odoo': (str(cpl) if cpl is not None else None),
        })

    result = {
        'configured': odoo_is_configured(),
        'ads': ads,
        'attributed': attributed,
        'unattributed': unattributed,
        'note': LEADS_ATTRIBUTION_NOTE,
    }
    if odoo_error is not None:
        result['odoo_error'] = odoo_error
    return result
