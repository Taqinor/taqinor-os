"""Sélecteurs LECTURE SEULE du moteur publicitaire exposés aux AUTRES apps.

Point d'entrée cross-app sanctionné (convention selectors.py) : une app externe
(ex. ``apps.crm`` sur le chemin d'attribution Lead Ads, ADSENG1) lit les miroirs
adsengine à travers ces fonctions plutôt qu'en important ``apps.adsengine.models``
directement. Symétrique de ``apps.crm.selectors`` que ce module (adsengine) lit
pour l'attribution (ADSENG6). Lecture seule ; toujours borné à la société.
"""
from __future__ import annotations

# Version de l'API Marketing utilisée par le repli de résolution paresseux
# (aligné sur ``meta_client.GRAPH_VERSION`` — v25, la version courante ; jamais
# la v19 expirée). Défini en littéral local pour ne PAS importer ``meta_client``
# (et sa dépendance httpx) sur le chemin crm.
_GRAPH_VERSION = 'v25.0'


def _fetch_ad_lineage(ad_id, access_token):  # pragma: no cover - réseau
    """Récupère la lignée (nom d'ad set / campagne + ids) d'une ad Meta.

    Isolé en fonction module pour rester simulable en test (monkeypatch) — jamais
    un vrai appel réseau en test. Renvoie le dict brut du Graph API ou lève sur
    échec (capté par l'appelant, best-effort).
    """
    import json
    import urllib.parse
    import urllib.request

    fields = 'name,adset{id,name},campaign{id,name}'
    qs = urllib.parse.urlencode({'fields': fields, 'access_token': access_token})
    url = f'https://graph.facebook.com/{_GRAPH_VERSION}/{ad_id}?{qs}'
    with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
        return json.loads(resp.read().decode('utf-8'))


def resolve_meta_ad_names(company, *, ad_id='', adgroup_id='', access_token=''):
    """ADSENG1 — Résout les NOMS lisibles (campagne / ad set) + l'id de campagne
    d'un lead Lead Ads à partir de ses identifiants Meta natifs.

    Ordre de résolution (premier gagnant, jamais d'appel réseau si les miroirs
    suffisent) :
      1. miroirs ENG5 (``AdMirror`` → ``AdSetMirror`` → ``AdCampaignMirror``,
         upsertés par la synchro) — source de vérité locale, gratuite ;
      2. repli PARESSEUX via le Graph API (``_fetch_ad_lineage``) UNIQUEMENT si
         un nom manque encore ET qu'un ``access_token`` est fourni — best-effort,
         ne lève jamais.

    Renvoie ``{'campaign_name', 'adset_name', 'campaign_id'}`` (chaînes, jamais
    None). Scopé société : ne lit jamais un miroir d'une autre société.
    """
    from .models import AdMirror, AdSetMirror

    result = {'campaign_name': '', 'adset_name': '', 'campaign_id': ''}
    ad_id = str(ad_id or '')
    adgroup_id = str(adgroup_id or '')

    # ── 1) Résolution locale via les miroirs ────────────────────────────────
    adset_mirror = None
    if ad_id:
        ad_mirror = (AdMirror.objects
                     .filter(company=company, meta_id=ad_id)
                     .select_related('adset', 'adset__campaign')
                     .first())
        if ad_mirror is not None and ad_mirror.adset_id:
            adset_mirror = ad_mirror.adset
    if adset_mirror is None and adgroup_id:
        adset_mirror = (AdSetMirror.objects
                        .filter(company=company, meta_id=adgroup_id)
                        .select_related('campaign')
                        .first())
    if adset_mirror is not None:
        result['adset_name'] = adset_mirror.name or ''
        campaign_mirror = adset_mirror.campaign
        if campaign_mirror is not None:
            result['campaign_name'] = campaign_mirror.name or ''
            result['campaign_id'] = campaign_mirror.meta_id or ''

    # Résolution directe de la campagne par le miroir d'ad set orphelin
    # (adgroup connu mais pas de FK campagne) laissée vide — le repli API
    # ci-dessous peut la compléter.

    # ── 2) Repli paresseux via le Graph API (best-effort) ───────────────────
    if not result['campaign_name'] and ad_id and access_token:
        try:
            data = _fetch_ad_lineage(ad_id, access_token)
        except Exception:  # noqa: BLE001 — la résolution ne casse jamais la
            # création du lead ; sans nom résolu, seuls les ids stables restent.
            data = None
        if isinstance(data, dict):
            adset = data.get('adset') or {}
            campaign = data.get('campaign') or {}
            if not result['adset_name']:
                result['adset_name'] = str(adset.get('name') or '')
            if not result['campaign_name']:
                result['campaign_name'] = str(campaign.get('name') or '')
            if not result['campaign_id']:
                result['campaign_id'] = str(campaign.get('id') or '')

    return result


# ── PUB68 — SLA première réponse : résolution d'ad pour le temps de réponse ──

def leads_response_time_by_ad_rows(company):
    """PUB68 — Lignes brutes (temps de première réponse + ad résolu) pour le
    calcul de la médiane PAR AD (``reporting.response_time_by_ad``). Résout
    l'ad via la MÊME échelle qu'``attribution.variant_attribution``
    (ADSENG6, ``attribution._resolve_ad_id`` — RÉUTILISÉE, jamais
    réimplémentée) ; le CRM est lu UNIQUEMENT via
    ``apps.crm.selectors.leads_response_time_rows`` (jamais un import
    d'``apps.crm.models``). Un lead non résolu à une ad est ABSENT. Renvoie
    ``[{'meta_id', 'name', 'response_minutes'}, ...]``."""
    from apps.crm.selectors import leads_response_time_rows

    from .attribution import _resolve_ad_id
    from .models import AdMirror

    ads = list(AdMirror.objects.filter(company=company))
    by_meta = {a.meta_id: a for a in ads}
    name_to_meta = {}
    for a in ads:
        if a.name:
            name_to_meta.setdefault(a.name, a.meta_id)

    rows = []
    for row in leads_response_time_rows(company):
        meta_id = _resolve_ad_id(row, by_meta, name_to_meta)
        if meta_id is None:
            continue
        rows.append({
            'meta_id': meta_id, 'name': by_meta[meta_id].name or '',
            'response_minutes': row['response_minutes'],
        })
    return rows


# ── PUB99 — KPIs pub FÉDÉRÉS vers le dashboard central reporting (ARC28) ──────
def kpi_publicite(company):
    """PUB99 — Tuiles KPI publicitaires fédérées (contrat ``core.platform``).

    Renvoie une liste de tuiles ``{'id', 'label', 'valeur', 'unite'}`` calculées
    sur les 7 derniers jours : dépense totale (niveau campagne, comme la
    réconciliation) et leads Meta (miroirs). Bornée à la société. Aucune donnée
    ⇒ tuiles à zéro (jamais d'erreur : ``reporting`` ignore un provider qui lève,
    mais on ne lève jamais)."""
    import datetime

    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Sum

    from .models import AdCampaignMirror, InsightSnapshot, MetaLeadMirror

    today = datetime.date.today()
    since = today - datetime.timedelta(days=6)
    ct = ContentType.objects.get_for_model(AdCampaignMirror)
    spend = (InsightSnapshot.objects
             .filter(company=company, content_type=ct,
                     date__gte=since, date__lte=today)
             .aggregate(s=Sum('spend'))['s']) or 0
    leads = MetaLeadMirror.objects.filter(
        company=company, created_at__date__gte=since).count()
    return [
        {'id': 'adsengine_spend_7j', 'label': 'Dépense pub (7 j)',
         'valeur': float(spend), 'unite': 'MAD'},
        {'id': 'adsengine_leads_7j', 'label': 'Leads Meta (7 j)',
         'valeur': int(leads), 'unite': 'leads'},
    ]
