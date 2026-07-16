"""ADSENG-ODOO — Coût-par-signature adossé aux VRAIES signatures Odoo.

Variante ADDITIVE de ``metrics.py`` (qui, lui, reste INTACT et calcule le coût
contre le CRM de l'ERP). Ici le dénominateur « signatures » vient d'Odoo — là où
vivent les deals réellement signés du fondateur — tandis que le numérateur
« dépense Meta » reste la MÊME source que la métrique historique :
``InsightSnapshot.spend`` des miroirs de campagne, scopé société.

    coût-par-signature = dépense Meta (société, période) ÷ signatures Odoo

TRAÇABILITÉ : on renvoie le nombre + les composants + la LISTE des deals signés
(jamais un chiffre boîte-noire). JAMAIS de division par zéro : 0 signature →
``cost_per_signature = None`` (la dépense et ``signatures=0`` restent renvoyés).

ATTRIBUTION PAR CAMPAGNE (best-effort) : on rapproche le ``phone_norm`` d'un deal
signé Odoo des téléphones des leads Meta que l'ERP a capturés (webhook Lead Ads
ADSENG1 → ``crm.reconciliation_lead_rows``, clé ``phone_key`` QW10 — la MÊME
normalisation) et on attribue la signature à la campagne de ce lead
(``meta_campaign_id`` sinon ``utm_campaign``).

[GAP] L'attribution par campagne NE fonctionne QUE pour les deals dont le
téléphone correspond à un lead Meta DONT l'ERP a capturé la campagne
(``meta_campaign_id``/``utm_campaign`` renseigné). Odoo n'a AUCUN champ campagne
Meta structuré sur le lead — donc un deal Odoo sans lead Meta correspondant dans
l'ERP reste « non attribué » et n'est comptabilisé qu'au niveau TOTAL. Le
téléphone est la seule clé de jointure possible (pas de champ campagne partagé).
"""
from __future__ import annotations

from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum

from .models import AdCampaignMirror, InsightSnapshot
from .odoo_client import is_configured as odoo_is_configured
from .odoo_selectors import signed_deals as odoo_signed_deals

# Note de limitation reprise à l'identique dans les réponses (front + diagnostic).
ATTRIBUTION_GAP_NOTE = (
    "Attribution par campagne limitée aux deals dont le téléphone correspond à "
    "un lead Meta capturé par l'ERP (Odoo n'a pas de champ campagne Meta). Les "
    "autres deals restent au niveau TOTAL."
)


def _as_date(since):
    """``since`` (date/datetime/str) → ``datetime.date`` pour filtrer
    ``InsightSnapshot.date`` (DateField), ou None si illisible (pas de filtre)."""
    import datetime as _dt
    if since is None:
        return None
    if isinstance(since, _dt.datetime):
        return since.date()
    if isinstance(since, _dt.date):
        return since
    try:
        return _dt.date.fromisoformat(str(since)[:10])
    except ValueError:
        return None


def _company_meta_spend(company, since=None):
    """Dépense Meta cumulée de la société : somme ``InsightSnapshot.spend`` des
    miroirs de CAMPAGNE (MÊME source que la métrique historique
    ``metrics._campaign_spend_map``), optionnellement bornée ``date >= since``."""
    ct = ContentType.objects.get_for_model(AdCampaignMirror)
    qs = InsightSnapshot.objects.filter(company=company, content_type=ct)
    since_date = _as_date(since)
    if since_date is not None:
        qs = qs.filter(date__gte=since_date)
    return qs.aggregate(s=Sum('spend'))['s'] or Decimal('0')


def _campaign_spend_by_pk(company, campaign_pks, since=None):
    """``{campaign_pk: Decimal}`` de dépense par miroir de campagne (bornée
    société + ``date >= since``). Vide si aucun pk."""
    if not campaign_pks:
        return {}
    ct = ContentType.objects.get_for_model(AdCampaignMirror)
    qs = InsightSnapshot.objects.filter(
        company=company, content_type=ct, object_id__in=list(campaign_pks))
    since_date = _as_date(since)
    if since_date is not None:
        qs = qs.filter(date__gte=since_date)
    rows = qs.values('object_id').annotate(spend=Sum('spend'))
    return {r['object_id']: (r['spend'] or Decimal('0')) for r in rows}


def _phone_to_campaign(company):
    """Carte ``{phone_key: campaign_key}`` des leads Meta capturés par l'ERP.

    Lue via ``apps.crm.selectors.reconciliation_lead_rows`` (jamais un import de
    ``apps.crm.models``). ``campaign_key`` = ``meta_campaign_id`` sinon
    ``utm_campaign``. Le premier lead vu pour un téléphone gagne (déterministe)."""
    from apps.crm.selectors import reconciliation_lead_rows

    mapping = {}
    for row in reconciliation_lead_rows(company):
        phone = row.get('phone_key')
        key = row.get('meta_campaign_id') or row.get('utm_campaign')
        if phone and key and phone not in mapping:
            mapping[phone] = key
    return mapping


def _campaign_pk_lookup(company):
    """``({meta_id: pk}, {name: pk})`` des miroirs de campagne de la société,
    pour rattacher la dépense d'une campagne à sa clé d'attribution."""
    by_meta, by_name = {}, {}
    for camp in AdCampaignMirror.objects.filter(company=company).only(
            'id', 'meta_id', 'name'):
        if camp.meta_id:
            by_meta.setdefault(camp.meta_id, camp.pk)
        if camp.name:
            by_name.setdefault(camp.name, camp.pk)
    return by_meta, by_name


def _public_deal(deal):
    """Deal signé sérialisable (montant Decimal → str)."""
    return {
        'phone_norm': deal['phone_norm'],
        'amount_mad': str(deal['amount_mad']),
        'date': deal['date'],
        'source_name': deal['source_name'],
        'origin': deal['origin'],
        'lead_id': deal['lead_id'],
    }


def _attribute_per_campaign(company, deals, since=None):
    """Attribue chaque deal signé à une campagne Meta par MATCH TÉLÉPHONE.

    Renvoie ``{'campaigns': [...], 'attributed': int, 'unattributed': int}``.
    Chaque campagne : ``{campaign_key, signatures, signed_phones, spend,
    cost_per_signature}`` (spend/coût None si aucun miroir ne correspond)."""
    phone_to_campaign = _phone_to_campaign(company)

    buckets = {}
    attributed = unattributed = 0
    for deal in deals:
        phone = deal.get('phone_norm')
        key = phone_to_campaign.get(phone) if phone else None
        if key:
            bucket = buckets.setdefault(
                key, {'signatures': 0, 'signed_phones': []})
            bucket['signatures'] += 1
            bucket['signed_phones'].append(phone)
            attributed += 1
        else:
            unattributed += 1

    by_meta, by_name = _campaign_pk_lookup(company)
    key_to_pk = {}
    for key in buckets:
        pk = by_meta.get(key) or by_name.get(key)
        if pk:
            key_to_pk[key] = pk
    spend_by_pk = _campaign_spend_by_pk(company, key_to_pk.values(), since)

    campaigns = []
    for key in sorted(buckets):
        bucket = buckets[key]
        pk = key_to_pk.get(key)
        spend = spend_by_pk.get(pk) if pk is not None else None
        count = bucket['signatures']
        cost = (spend / count) if (spend is not None and count) else None
        campaigns.append({
            'campaign_key': key,
            'signatures': count,
            'signed_phones': bucket['signed_phones'],
            'spend': (str(spend) if spend is not None else None),
            'cost_per_signature': (str(cost) if cost is not None else None),
        })
    return {'campaigns': campaigns,
            'attributed': attributed, 'unattributed': unattributed}


def odoo_cost_per_signature(company, since=None, client=None):
    """Coût-par-signature adossé aux signatures Odoo, avec traçabilité.

    Renvoie ::

        {
          'configured': bool,          # connecteur Odoo configuré ?
          'total_spend': str,          # dépense Meta société (Decimal sérialisé)
          'signatures': int,           # nb de deals signés Odoo (0 si non config)
          'cost_per_signature': str|None,  # total_spend / signatures, None si 0
          'signed_deals': [ {...}, ],  # liste traçable des deals signés
          'per_campaign': [ {...}, ],  # attribution best-effort par campagne
          'attribution': {'attributed', 'unattributed', 'note'},
          'odoo_error': str,           # présent SEULEMENT si la lecture Odoo échoue
        }

    Ne lève JAMAIS (ni division par zéro, ni exception de lecture). Sans config
    Odoo → ``configured=False``, ``signatures=0``, ``cost_per_signature=None``.
    Config présente mais lecture Odoo en échec (auth/réseau/DB erronés) →
    ``signatures=0`` + ``odoo_error`` explicite, JAMAIS un 500 (la dépense Meta,
    locale, reste renvoyée dans tous les cas)."""
    # CONTRAT DE LA VUE : JAMAIS un 500. Une fois le connecteur configuré, la
    # lecture Odoo (``odoo_signed_deals`` → JSON-RPC) peut échouer pour une raison
    # EXTERNE (auth refusée, réseau injoignable, DB/login erronés). On dégrade
    # proprement — ``signatures=0`` + ``odoo_error`` explicite — au lieu de laisser
    # l'exception remonter en 500. La dépense Meta (locale) reste toujours servie.
    odoo_error = None
    try:
        deals = odoo_signed_deals(since=since, client=client)
    except Exception as exc:  # noqa: BLE001 — dégradation propre voulue (jamais un 500)
        deals = []
        odoo_error = f"{type(exc).__name__}: {exc}"[:300]
    signatures = len(deals)
    spend = _company_meta_spend(company, since)
    cost = (spend / signatures) if signatures else None
    per_campaign = _attribute_per_campaign(company, deals, since)
    result = {
        'configured': odoo_is_configured(),
        'total_spend': str(spend),
        'signatures': signatures,
        'cost_per_signature': (str(cost) if cost is not None else None),
        'signed_deals': [_public_deal(d) for d in deals],
        'per_campaign': per_campaign['campaigns'],
        'attribution': {
            'attributed': per_campaign['attributed'],
            'unattributed': per_campaign['unattributed'],
            'note': ATTRIBUTION_GAP_NOTE,
        },
    }
    # Présent UNIQUEMENT en cas d'échec de lecture Odoo (diagnostic côté front) —
    # le chemin succès garde EXACTEMENT la même forme qu'avant (zéro régression).
    if odoo_error is not None:
        result['odoo_error'] = odoo_error
    return result
