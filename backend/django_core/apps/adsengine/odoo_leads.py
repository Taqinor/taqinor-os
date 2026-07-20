"""FIXPUB6 — Leads Odoo attribués PAR ANNONCE (coût-par-lead Odoo).

Variante ADDITIVE des métriques : là où ``odoo_metrics.odoo_signatures_by_ad``
descend les SIGNATURES Odoo au niveau ad (deals signés), ce module descend TOUS
les leads Odoo (``odoo_selectors.all_leads``) au niveau ad — le dénominateur d'un
coût-par-lead (``cpl_odoo``).

ATTRIBUTION D'UN LEAD À UNE ANNONCE — quatre paliers, premier gagnant :
  1. EXACT (téléphone) — le ``phone_norm`` du lead correspond au ``phone_key``
     (QW10) d'un ``MetaLeadMirror`` de la société (ADSDEEP17) → son ``ad_id`` ;
  2. FORMULAIRE (DATAPUB1, LE GROS GAIN) — la plupart des leads Odoo portent le
     NOM d'un formulaire Meta (« TAQINOR FORM-4.0 », « DAZZLEMEDAI-TAQINOR
     FORM-jj/mm »). On regroupe les leads par formulaire (``_form_key``) et on
     apprend l'EMPREINTE de chaque formulaire — l'ensemble des annonces que ses
     leads DÉJÀ placés (téléphone exact ou nom) touchent. Les leads non plaçables
     du même formulaire en héritent : un formulaire servi par UNE annonce →
     rattachement à l'annonce (``formulaire``) ; par PLUSIEURS annonces / une
     campagne → rattachement au niveau CAMPAGNE (``formulaire_campagne``, honnête)
     avec un CPL réparti pondéré par la dépense sur les annonces du formulaire ;
  3. ESTIMATION (nom) — à défaut, un nom encodé non-formulaire (ADSDEEP21) est
     rapproché individuellement du nom d'une annonce miroir ;
  4. ESTIMATION (date) — à défaut, si UNE seule annonce dépensait le jour du lead
     (fenêtre date), on l'y rattache — marqué « estimation ».

Les paliers 2/3/4 sont TOUJOURS étiquetés (``attribution_type`` = ``exact`` /
``formulaire`` / ``estimation`` / ``mixte`` par annonce ; ``formulaire_campagne``
au niveau campagne) — jamais fondus en silence avec l'exact (mêmes garde-fous que
ADSDEEP21). AUCUN lead n'est ignoré en silence : le bilan expose le total, la
répartition par palier et les non-attribués PAR nom de source. Sans configuration
Odoo → NO-OP propre (``configured=False``, aucune ligne). Ne lève JAMAIS
(dégradation propre comme ``odoo_signatures_by_ad``).

Réutilise les sélecteurs/aides déjà construits du même module Odoo
(``_ad_spend_by_meta``, ``_phone_to_ad``, ``_as_date`` d'``odoo_metrics``) — la
dépense ad vient de la MÊME source ``InsightSnapshot`` (ADSDEEP2) que le coût-par-
signature, jamais un deuxième calcul de dépense inventé ici.
"""
from __future__ import annotations

import datetime
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal

from .odoo_client import is_configured as odoo_is_configured
from .odoo_selectors import all_leads as odoo_all_leads
from .odoo_selectors import parse_odoo_lead_name

# Longueur minimale d'un indice de nom pour tenter un rapprochement (évite les
# faux positifs sur des jetons trop courts).
_MIN_HINT_LEN = 3

_CENT = Decimal('0.01')
_TEN_THOUSANDTH = Decimal('0.0001')


def _money_str(value):
    """Décimal monétaire → chaîne à 2 décimales STABLES (``None`` → ``None``).
    Normalise le format du CPL/dépense quelle que soit la profondeur des
    divisions (un CPL réparti divisé par une part fractionnaire ne doit pas
    perdre ses décimales)."""
    if value is None:
        return None
    return str(value.quantize(_CENT, rounding=ROUND_HALF_UP))


def _qty_str(value):
    """Décimal de QUANTITÉ (part de leads fractionnaire) → chaîne à 4 décimales
    (``None`` → ``None``)."""
    if value is None:
        return None
    return str(value.quantize(_TEN_THOUSANDTH, rounding=ROUND_HALF_UP))


LEADS_ATTRIBUTION_NOTE = (
    "Leads Odoo attribués : palier EXACT par téléphone (MetaLeadMirror), puis "
    "FORMULAIRE (empreinte du formulaire Meta — annonce unique ou campagne), puis "
    "ESTIMATION par nom de lead encodé (ADSDEEP21), puis ESTIMATION par fenêtre "
    "date. Les paliers non-exacts ne sont jamais fondus avec l'exact (voir "
    "attribution_type / tiers) ; aucun lead n'est ignoré en silence (voir "
    "unattributed_by_source)."
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


# ── DATAPUB1 — Attribution PAR FORMULAIRE (empreinte du formulaire Meta) ──────
# Un nom de lead Odoo qui porte le jeton « form » EST un nom de formulaire Meta
# (« TAQINOR FORM-4.0 »). C'est la clé de regroupement de l'attribution par
# formulaire : la plupart des leads du fondateur portent ce nom, pas un numéro.
_FORM_TOKEN = 'form'


def _form_key(source_name):
    """Clé de FORMULAIRE stable pour un nom de lead Odoo, ou None.

    Réutilise ``parse_odoo_lead_name`` (ADSDEEP21) : clé = ``campaign_hint``
    (segments non-date, la DATE du lead retirée pour qu'un même formulaire servi
    plusieurs jours se regroupe), en minuscules. On ne retient QUE les noms de
    FORMULAIRE (jeton « form » présent) : un vrai nom de personne (« Sara »)
    n'est jamais traité comme un formulaire."""
    parsed = parse_odoo_lead_name(source_name)
    if parsed is None:
        return None
    key = (parsed.get('campaign_hint') or '').strip().lower()
    if not key or _FORM_TOKEN not in key.split():
        return None
    return key


def _ad_to_campaign(company):
    """``{ad_meta_id: campaign_meta_id}`` de la société, résolu depuis DEUX
    sources concordantes : (1) ``MetaLeadMirror`` (ad_id → campaign_id, la
    jointure Meta directe ADSDEEP17), puis (2) la chaîne miroir
    ``AdMirror.adset.campaign`` en repli. Première source non vide gagne."""
    from .models import AdMirror, MetaLeadMirror

    mapping = {}
    for m in (MetaLeadMirror.objects.filter(company=company)
              .exclude(ad_id='').exclude(campaign_id='')
              .values('ad_id', 'campaign_id')):
        mapping.setdefault(m['ad_id'], m['campaign_id'])
    for ad in (AdMirror.objects.filter(company=company).exclude(meta_id='')
               .select_related('adset', 'adset__campaign')):
        if ad.meta_id in mapping:
            continue
        adset = ad.adset
        camp = getattr(adset, 'campaign', None) if adset is not None else None
        if camp is not None and camp.meta_id:
            mapping[ad.meta_id] = camp.meta_id
    return mapping


def _campaign_names(company):
    """``{campaign_meta_id: nom}`` des campagnes miroir de la société."""
    from .models import AdCampaignMirror

    return {c.meta_id: (c.name or '')
            for c in (AdCampaignMirror.objects.filter(company=company)
                      .exclude(meta_id='').only('meta_id', 'name'))}


def _dominant_campaign(ads, ad_to_campaign):
    """Parmi les campagnes des ``ads`` d'un formulaire, renvoie
    ``(campaign_id, [ads de cette campagne])`` de la campagne portant le PLUS
    d'annonces du formulaire (départage déterministe par campaign_id), ou None
    si AUCUNE annonce n'a de campagne résolvable (le palier formulaire est alors
    sauté, l'attribution retombe sur les paliers nom/date)."""
    by_camp = {}
    for ad_id in ads:
        cid = ad_to_campaign.get(ad_id)
        if cid:
            by_camp.setdefault(cid, []).append(ad_id)
    if not by_camp:
        return None
    best = max(by_camp, key=lambda c: (len(by_camp[c]), c))
    return best, sorted(by_camp[best])


def _add_ad(buckets, ad_id, tier, lead_id):
    """Incrémente le compteur ``tier`` (exact/formulaire/estimes) d'une annonce
    et note l'``id`` de lead."""
    bucket = buckets.setdefault(
        ad_id, {'exact': 0, 'formulaire': 0, 'estimes': 0, 'lead_ids': []})
    bucket[tier] += 1
    if lead_id is not None:
        bucket['lead_ids'].append(lead_id)


def _ad_row(ad_id, bucket, spend_by_ad, name_by_meta):
    """Ligne PAR AD : total = exact + formulaire + estimes ; ``cpl_odoo`` =
    dépense ad ÷ total ; ``attribution_type`` = le palier unique présent, ou
    ``mixte`` si plusieurs."""
    total = bucket['exact'] + bucket['formulaire'] + bucket['estimes']
    spend = spend_by_ad.get(ad_id)
    cpl = (spend / total) if (spend is not None and total) else None
    non_zero = [name for count, name in (
        (bucket['exact'], 'exact'),
        (bucket['formulaire'], 'formulaire'),
        (bucket['estimes'], 'estimation')) if count]
    attr_type = non_zero[0] if len(non_zero) == 1 else 'mixte'
    return {
        'ad_id': ad_id,
        'ad_name': name_by_meta.get(ad_id, ''),
        'leads_odoo': total,
        'leads_exact': bucket['exact'],
        'leads_formulaire': bucket['formulaire'],
        'leads_estimes': bucket['estimes'],
        'attribution_type': attr_type,
        'lead_ids': bucket['lead_ids'],
        'spend': _money_str(spend),
        'cpl_odoo': _money_str(cpl),
    }


def _campaign_row(campaign_id, bucket, spend_by_ad, campaign_names):
    """Ligne PAR CAMPAGNE (palier ``formulaire_campagne``) : leads du formulaire
    rattachés à la campagne, dépense = somme des annonces du formulaire, CPL =
    dépense campagne ÷ leads. ``per_ad`` répartit les leads PONDÉRÉS par la
    dépense (le CPL par annonce égale alors le CPL campagne — répartition
    honnête, jamais un CPL par annonce inventé)."""
    ad_ids = sorted(bucket['ad_ids'])
    total_leads = bucket['leads']
    total_spend = Decimal('0')
    has_spend = False
    for ad_id in ad_ids:
        s = spend_by_ad.get(ad_id)
        if s is not None:
            total_spend += s
            has_spend = True
    cpl = (total_spend / total_leads) if (total_leads and total_spend) else None
    per_ad = []
    for ad_id in ad_ids:
        s = spend_by_ad.get(ad_id)
        if s is not None and total_spend > 0 and total_leads:
            share = total_leads * (s / total_spend)
            ad_cpl = (s / share) if share else None
        else:
            share = ad_cpl = None
        per_ad.append({
            'ad_id': ad_id,
            'spend': _money_str(s),
            'leads_share': _qty_str(share),
            'cpl_odoo': _money_str(ad_cpl),
        })
    return {
        'campaign_id': campaign_id,
        'campaign_name': campaign_names.get(campaign_id, ''),
        'leads_odoo': total_leads,
        'ad_ids': ad_ids,
        'lead_ids': bucket['lead_ids'],
        'attribution_type': 'formulaire_campagne',
        'spend': (_money_str(total_spend) if has_spend else None),
        'cpl_odoo': _money_str(cpl),
        'per_ad': per_ad,
    }


def odoo_leads_by_ad(company, since=None, client=None):
    """DATAPUB1/FIXPUB6 — Leads Odoo attribués (annonce OU campagne) + CPL Odoo.

    Renvoie ::

        {
          'configured': bool,
          'ads': [ {ad_id, ad_name, leads_odoo, leads_exact, leads_formulaire,
                    leads_estimes, attribution_type, lead_ids, spend, cpl_odoo} ],
          'campaigns': [ {campaign_id, campaign_name, leads_odoo, ad_ids,
                          lead_ids, attribution_type, spend, cpl_odoo, per_ad} ],
          'attributed': int, 'unattributed': int, 'total': int,
          'tiers': {telephone, formulaire, formulaire_campagne, nom, date},
          'unattributed_by_source': [ {source_name, count}, ... desc ],
          'note': str,
          'odoo_error': str,   # seulement si la lecture Odoo échoue
        }

    Attribution premier-gagnant : téléphone EXACT → FORMULAIRE (empreinte) → nom
    → fenêtre date. ``cpl_odoo`` = dépense (InsightSnapshot ADSDEEP2, bornée
    ``since``) ÷ leads. Ne lève JAMAIS (dégradation propre)."""
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
    ad_to_campaign = _ad_to_campaign(company)

    # ── Passe 1 — EMPREINTE de chaque formulaire : l'ensemble des annonces que
    # ses leads DÉJÀ placés (téléphone exact ou nom) touchent. Les leads non
    # plaçables du même formulaire en hériteront (palier formulaire).
    form_footprint = {}   # form_key → set(ad_id)
    per_lead = []         # (lead, exact_ad, name_ad, form_key)
    for lead in leads:
        phone = lead.get('phone_norm') or ''
        exact_ad = phone_to_ad.get(phone) if phone else None
        parsed = parse_odoo_lead_name(lead.get('source_name'))
        name_ad = name_match(parsed) if parsed is not None else None
        fkey = _form_key(lead.get('source_name'))
        if fkey:
            footprint = form_footprint.setdefault(fkey, set())
            if exact_ad:
                footprint.add(exact_ad)
            if name_ad:
                footprint.add(name_ad)
        per_lead.append((lead, exact_ad, name_ad, fkey))

    # ── Passe 2 — attribution premier-gagnant.
    ad_buckets = {}       # ad_id → {exact, formulaire, estimes, lead_ids}
    camp_buckets = {}     # campaign_id → {leads, ad_ids:set, lead_ids}
    tiers = {'telephone': 0, 'formulaire': 0, 'formulaire_campagne': 0,
             'nom': 0, 'date': 0}
    unattributed_sources = Counter()
    attributed = unattributed = 0

    for lead, exact_ad, name_ad, fkey in per_lead:
        lead_id = lead.get('lead_id')
        # 1 — téléphone EXACT.
        if exact_ad:
            _add_ad(ad_buckets, exact_ad, 'exact', lead_id)
            tiers['telephone'] += 1
            attributed += 1
            continue
        # 2 — FORMULAIRE (empreinte des leads placés du même formulaire).
        placed = False
        if fkey and form_footprint.get(fkey):
            ads = form_footprint[fkey]
            if len(ads) == 1:
                _add_ad(ad_buckets, next(iter(ads)), 'formulaire', lead_id)
                tiers['formulaire'] += 1
                attributed += 1
                placed = True
            else:
                dominant = _dominant_campaign(ads, ad_to_campaign)
                if dominant is not None:
                    camp_id, camp_ads = dominant
                    cb = camp_buckets.setdefault(
                        camp_id, {'leads': 0, 'ad_ids': set(), 'lead_ids': []})
                    cb['leads'] += 1
                    cb['ad_ids'].update(camp_ads)
                    if lead_id is not None:
                        cb['lead_ids'].append(lead_id)
                    tiers['formulaire_campagne'] += 1
                    attributed += 1
                    placed = True
        if placed:
            continue
        # 3 — NOM (estimation individuelle, ADSDEEP21).
        if name_ad:
            _add_ad(ad_buckets, name_ad, 'estimes', lead_id)
            tiers['nom'] += 1
            attributed += 1
            continue
        # 4 — fenêtre DATE : une SEULE annonce active ce jour-là.
        day = _lead_day(lead.get('date'))
        ads_on_day = date_to_ads.get(day) if day is not None else None
        if ads_on_day and len(ads_on_day) == 1:
            _add_ad(ad_buckets, next(iter(ads_on_day)), 'estimes', lead_id)
            tiers['date'] += 1
            attributed += 1
            continue
        unattributed += 1
        unattributed_sources[(lead.get('source_name') or '').strip()] += 1

    # ── Dépense ad-level (une requête, bornée since) pour annonces + campagnes.
    all_ad_ids = set(ad_buckets)
    for cb in camp_buckets.values():
        all_ad_ids.update(cb['ad_ids'])
    spend_by_ad = _ad_spend_by_meta(company, all_ad_ids, since)
    name_by_meta = {
        a.meta_id: (a.name or '')
        for a in AdMirror.objects.filter(
            company=company, meta_id__in=list(all_ad_ids))
        .only('meta_id', 'name')}
    campaign_names = _campaign_names(company)

    ads = [_ad_row(ad_id, ad_buckets[ad_id], spend_by_ad, name_by_meta)
           for ad_id in sorted(ad_buckets)]
    campaigns = [_campaign_row(cid, camp_buckets[cid], spend_by_ad,
                               campaign_names)
                 for cid in sorted(camp_buckets)]

    result = {
        'configured': odoo_is_configured(),
        'ads': ads,
        'campaigns': campaigns,
        'attributed': attributed,
        'unattributed': unattributed,
        'total': attributed + unattributed,
        'tiers': tiers,
        'unattributed_by_source': [
            {'source_name': src, 'count': count}
            for src, count in unattributed_sources.most_common()],
        'note': LEADS_ATTRIBUTION_NOTE,
    }
    if odoo_error is not None:
        result['odoo_error'] = odoo_error
    return result
