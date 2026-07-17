"""ENG5 — Synchronisation idempotente des miroirs publicitaires.

Upsert par ``(company, meta_id)`` : deux exécutions sur les MÊMES payloads
laissent EXACTEMENT le même état (aucun doublon, aucun champ métier divergent).
``created_via_engine`` n'est JAMAIS écrasé par une re-synchro depuis Meta (un
objet né du moteur reste marqué comme tel). Aucune importation d'app métier —
les miroirs vivent tous dans ``adsengine`` (FK même app autorisée).
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib.contenttypes.models import ContentType

from .models import (
    AdCampaignMirror, AdCreativeMirror, AdMirror, AdSetMirror, InsightSnapshot,
)


def _to_decimal(value):
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _to_int(value):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _budget_of(payload):
    return _to_decimal(
        payload.get('daily_budget') or payload.get('lifetime_budget'))


def sync_campaigns(company, payloads, *, created_via_engine=False):
    """Upsert les miroirs de campagne depuis des payloads Meta. Idempotent."""
    mirrors = []
    for p in payloads or []:
        mid = str(p.get('id') or '').strip()
        if not mid:
            continue
        fields = {
            'name': p.get('name', '') or '',
            'status': p.get('status', '') or '',
            'objective': p.get('objective', '') or '',
            'budget': _budget_of(p),
        }
        obj, created = AdCampaignMirror.objects.get_or_create(
            company=company, meta_id=mid,
            defaults={**fields, 'created_via_engine': created_via_engine})
        if not created:
            # created_via_engine délibérément PRÉSERVÉ (jamais réécrit).
            for key, value in fields.items():
                setattr(obj, key, value)
            obj.save()
        mirrors.append(obj)
    return mirrors


def sync_adsets(company, payloads, *, created_via_engine=False):
    """Upsert les miroirs d'ad set ; résout le miroir de campagne parent par
    ``campaign_id`` (null si pas encore synchronisé). Idempotent."""
    mirrors = []
    for p in payloads or []:
        mid = str(p.get('id') or '').strip()
        if not mid:
            continue
        campaign = None
        camp_mid = str(p.get('campaign_id') or '').strip()
        if camp_mid:
            campaign = AdCampaignMirror.objects.filter(
                company=company, meta_id=camp_mid).first()
        fields = {
            'name': p.get('name', '') or '',
            'status': p.get('status', '') or '',
            'budget': _budget_of(p),
            'campaign': campaign,
        }
        obj, created = AdSetMirror.objects.get_or_create(
            company=company, meta_id=mid,
            defaults={**fields, 'created_via_engine': created_via_engine})
        if not created:
            for key, value in fields.items():
                setattr(obj, key, value)
            obj.save()
        mirrors.append(obj)
    return mirrors


def sync_ads(company, payloads, *, created_via_engine=False):
    """Upsert les miroirs d'ad ; résout l'ad set parent par ``adset_id``.
    Idempotent."""
    mirrors = []
    for p in payloads or []:
        mid = str(p.get('id') or '').strip()
        if not mid:
            continue
        adset = None
        adset_mid = str(p.get('adset_id') or '').strip()
        if adset_mid:
            adset = AdSetMirror.objects.filter(
                company=company, meta_id=adset_mid).first()
        fields = {
            'name': p.get('name', '') or '',
            'status': p.get('status', '') or '',
            'adset': adset,
        }
        obj, created = AdMirror.objects.get_or_create(
            company=company, meta_id=mid,
            defaults={**fields, 'created_via_engine': created_via_engine})
        if not created:
            for key, value in fields.items():
                setattr(obj, key, value)
            obj.save()
        mirrors.append(obj)
    return mirrors


def _extract_creative_fields(creative):
    """ADSDEEP11 — Aplati un nœud ``creative{…}`` Meta en champs de miroir.

    Lit d'abord les champs directs (``body``/``title``/…) puis retombe sur
    ``object_story_spec`` (link_data/video_data — dossier creative §1) pour le
    texte/CTA/média. Tolère un payload partiel/incomplet (asset_feed_spec)."""
    creative = creative or {}
    oss = creative.get('object_story_spec') or {}
    link_data = oss.get('link_data') or {}
    video_data = oss.get('video_data') or {}
    afs = creative.get('asset_feed_spec') or {}

    body = (creative.get('body') or link_data.get('message')
            or video_data.get('message') or '')
    title = (creative.get('title') or link_data.get('name')
             or video_data.get('title') or '')
    description = (creative.get('description')
                   or link_data.get('description') or '')
    cta = (creative.get('call_to_action_type')
           or (link_data.get('call_to_action') or {}).get('type')
           or (video_data.get('call_to_action') or {}).get('type') or '')
    link_url = (link_data.get('link')
                or (link_data.get('call_to_action') or {})
                .get('value', {}).get('link') or '')
    image_hash = (link_data.get('image_hash')
                  or (oss.get('photo_data') or {}).get('image_hash') or '')
    video_id = (creative.get('video_id') or video_data.get('video_id') or '')
    return {
        'creative_meta_id': str(creative.get('id') or ''),
        'body': body or '',
        'title': (title or '')[:255],
        'description': description or '',
        'cta_type': (cta or '')[:64],
        'link_url': link_url or '',
        'image_hash': (image_hash or '')[:128],
        'video_id': (video_id or '')[:64],
        'instagram_permalink_url': creative.get(
            'instagram_permalink_url') or '',
        'effective_object_story_id': (creative.get(
            'effective_object_story_id') or '')[:128],
        'asset_feed_spec': afs if isinstance(afs, dict) else {},
    }


def sync_ad_creative(company, ad_mirror, creative_payload):
    """ADSDEEP11 — Upsert idempotent du miroir de créatif d'une ad (OneToOne).

    ``creative_payload`` est le nœud ``creative`` retourné par
    ``GET /<ad>?fields=creative{…}``. Company dérivée de l'ad. Renvoie
    ``(mirror, created)``."""
    from django.utils import timezone

    fields = _extract_creative_fields(creative_payload)
    fields['fetched_at'] = timezone.now()
    return AdCreativeMirror.objects.update_or_create(
        company=company, ad=ad_mirror, defaults=fields)


def resolve_results(objective, normalized_row):
    """ADSDEEP6 — Nombre de « résultats » HOMOGÈNE d'une campagne selon son
    objectif : une campagne CTWA compte des conversations, une campagne
    OUTCOME_LEADS compte des leads, etc. (mapping ``metrics``). Repli sur le
    ``results`` brut Meta si la métrique dédiée est absente. Renvoie ``None`` si
    rien n'est disponible."""
    from .metrics import result_metric_for_objective

    metric = result_metric_for_objective(objective)['metric']
    value = (normalized_row or {}).get(metric)
    if value is None:
        value = (normalized_row or {}).get('results')
    return value


def upsert_insight(company, target, *, date, spend=None, results=None,
                   frequency=None, cpl=None, impressions=None, reach=None,
                   clicks=None, link_clicks=None, conversations=None,
                   leads_count=None, video_metrics=None):
    """Upsert un ``InsightSnapshot`` daté sur un miroir (FK générique).

    Clé idempotente : ``(company, content_type, object_id, date)`` — un même
    jour re-synchronisé met à jour la ligne existante au lieu d'en créer une
    nouvelle.

    ADSDEEP1 — les colonnes typées additionnelles (impressions/reach/clicks/
    link_clicks/conversations/leads_count/video_metrics) sont écrites quand la
    synchro les fournit ; un appelant ancien (4 arguments) laisse ces colonnes
    NULL sans jamais écraser une valeur existante par un None fourni
    explicitement (les rows historiques restent intacts).
    """
    ct = ContentType.objects.get_for_model(target)
    defaults = {
        'spend': _to_decimal(spend),
        'results': _to_int(results),
        'frequency': _to_decimal(frequency),
        'cpl': _to_decimal(cpl),
    }
    # Colonnes ADSDEEP1 : n'écrire que ce qui est réellement fourni (None laissé
    # de côté pour ne jamais annuler une valeur déjà en base sur un re-sync
    # partiel). ``video_metrics`` a un défaut {} en base : ne l'écrire que si
    # non-None.
    for name, value in (
            ('impressions', _to_int(impressions)),
            ('reach', _to_int(reach)),
            ('clicks', _to_int(clicks)),
            ('link_clicks', _to_int(link_clicks)),
            ('conversations', _to_int(conversations)),
            ('leads_count', _to_int(leads_count))):
        if value is not None:
            defaults[name] = value
    if video_metrics is not None:
        defaults['video_metrics'] = video_metrics
    obj, _ = InsightSnapshot.objects.update_or_create(
        company=company, content_type=ct, object_id=target.pk, date=date,
        defaults=defaults)
    return obj
