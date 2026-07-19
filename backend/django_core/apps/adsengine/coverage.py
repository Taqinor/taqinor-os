"""PUB80 — Rapport « trous de couverture » (formats Meta + segments).

Deux volets, tous deux 100 % LECTURE (aucune action, aucune écriture) :

  (a) **formats** — ``CreativeAsset.AssetType`` ne modélise que reel/static/
      explainer : carrousel/collection (des formats Meta RÉELS) ne sont
      structurellement JAMAIS produits. Croisé avec l'usage réel (un format
      modélisé mais jamais utilisé par la société est aussi un « trou »,
      distinct du trou structurel) ;
  (b) **segments** — croise ``InsightBreakdown`` (âge×genre / région) avec les
      tags hook/angle (ADSDEEP46, ``AdMirror.hook_tag``/``angle_tag``) : un
      segment à forte dépense (RELATIVE — jamais un seuil absolu, cohérent
      avec ``anomaly.py``/dd-guardian) dont AUCUNE ad qui l'a atteint ne porte
      de tag hook/angle (= aucune créa dédiée, seulement du générique).

Aucune migration, aucun champ — lecture pure des modèles déjà en place.
"""
from __future__ import annotations

import datetime
import statistics
from decimal import Decimal

# Catalogue des formats PUBLICITAIRES Meta pertinents (donnée, pas de logique).
# 'reel'/'static'/'explainer' sont les 3 types MODÉLISÉS
# (``CreativeAsset.AssetType``) ; 'carousel'/'collection' sont des formats
# Meta RÉELS structurellement absents du modèle (PUB80 point a).
META_AD_FORMATS_FR = {
    'reel': 'Reel / vidéo verticale',
    'static': 'Statique (image)',
    'explainer': 'Explainer animé',
    'carousel': 'Carrousel',
    'collection': 'Collection',
}

DEFAULT_COVERAGE_PERIOD_DAYS = 30


def format_coverage(company):
    """PUB80(a) — Audit des formats Meta jamais couverts. Distingue :

      * ``jamais_modelises`` — un format Meta réel qu'``AssetType`` ne
        modélise structurellement PAS (carrousel/collection) ; ce trou existe
        même à zéro donnée (c'est un trou STRUCTUREL, pas un fait mesuré) ;
      * ``modelises_jamais_utilises`` — un type modélisé (reel/static/
        explainer) dont la société n'a POURTANT produit aucun asset ;
      * ``formats_utilises`` — types réellement présents, avec leur compte.

    Company-scopé."""
    from .models import CreativeAsset

    modeled_types = {c[0] for c in CreativeAsset.AssetType.choices}
    counts = {}
    for asset_type in (CreativeAsset.objects.filter(company=company)
                       .exclude(asset_type='')
                       .values_list('asset_type', flat=True)):
        counts[asset_type] = counts.get(asset_type, 0) + 1

    jamais_modelises = [
        {'format': k, 'label_fr': v}
        for k, v in META_AD_FORMATS_FR.items() if k not in modeled_types
    ]
    modelises_jamais_utilises = [
        {'format': k, 'label_fr': META_AD_FORMATS_FR.get(k, k)}
        for k in sorted(modeled_types) if k not in counts
    ]
    formats_utilises = [
        {'format': k, 'label_fr': META_AD_FORMATS_FR.get(k, k), 'count': v}
        for k, v in sorted(counts.items(), key=lambda kv: -kv[1])
    ]

    return {
        'jamais_modelises': jamais_modelises,
        'modelises_jamais_utilises': modelises_jamais_utilises,
        'formats_utilises': formats_utilises,
    }


def _default_period(date_start, date_end):
    end = date_end or datetime.date.today()
    start = date_start or (
        end - datetime.timedelta(days=DEFAULT_COVERAGE_PERIOD_DAYS - 1))
    return start, end


def segment_coverage(company, *, date_start=None, date_end=None,
                     dimensions=('age_gender', 'region')):
    """PUB80(b) — Segments (âge×genre / région) à forte dépense RELATIVE
    (>= médiane des segments observés — jamais un seuil absolu, cohérent avec
    ``anomaly.py``/dd-guardian §B2) dont AUCUNE ad qui les a atteints ne porte
    de tag hook/angle (ADSDEEP46) : dépense sans AUCUNE créa dédiée. Période
    par défaut : 30 jours glissants. Company-scopé, jamais un segment
    fabriqué (absent des données = absent du rapport)."""
    from django.contrib.contenttypes.models import ContentType

    from .models import AdMirror, InsightBreakdown

    date_start, date_end = _default_period(date_start, date_end)
    ads = {a.pk: a for a in AdMirror.objects.filter(company=company)}
    periode = {'debut': date_start.isoformat(), 'fin': date_end.isoformat()}
    if not ads:
        return {'segments_non_couverts': [], 'periode': periode,
                'median_spend': None}

    ct = ContentType.objects.get_for_model(AdMirror)
    qs = (InsightBreakdown.objects
          .filter(company=company, content_type=ct, object_id__in=ads.keys(),
                  dimension__in=dimensions, date__gte=date_start,
                  date__lte=date_end)
          .exclude(spend=None))

    segments = {}
    for row in qs:
        ad = ads.get(row.object_id)
        if ad is None:
            continue
        key = (row.dimension, row.key)
        slot = segments.setdefault(
            key, {'spend': Decimal('0'), 'tagged_spend': Decimal('0')})
        slot['spend'] += row.spend
        if ad.hook_tag or ad.angle_tag:
            slot['tagged_spend'] += row.spend

    if not segments:
        return {'segments_non_couverts': [], 'periode': periode,
                'median_spend': None}

    median_spend = statistics.median(
        float(s['spend']) for s in segments.values())

    gaps = []
    for (dimension, key), slot in segments.items():
        if slot['tagged_spend'] > 0:
            continue  # au moins une ad taguée a atteint ce segment.
        if float(slot['spend']) < median_spend:
            continue  # pas « à forte dépense » (relatif au lot observé).
        gaps.append({
            'dimension': dimension, 'segment': key,
            'spend': str(slot['spend']),
        })
    gaps.sort(key=lambda g: Decimal(g['spend']), reverse=True)

    return {
        'segments_non_couverts': gaps, 'periode': periode,
        'median_spend': round(median_spend, 2),
    }


def coverage_report(company, *, date_start=None, date_end=None):
    """PUB80 — Rapport combiné « trous de couverture » (formats + segments),
    la surface consommée par l'écran reporting."""
    return {
        'formats': format_coverage(company),
        'segments': segment_coverage(
            company, date_start=date_start, date_end=date_end),
    }
