"""ENG10 — Service coût-par-signature (l'héro-métrique du moteur).

Blend déterministe : ``InsightSnapshot.spend`` (côté Meta, réconcilié avec les
miroirs) × leads CRM SIGNÉS attribués par ``utm_campaign`` (côté ERP). Le coût
par signature = dépense de la campagne ÷ nombre de signatures attribuées.

TRAÇABILITÉ (pattern Northbeam, exigence #7 de la recherche UX) : chaque chiffre
est accompagné de la LISTE des ids de leads qui le composent — jamais un chiffre
« boîte noire ». Le front peut donc rendre chaque nombre cliquable jusqu'au lead
réel.

FRONTIÈRE CROSS-APP : le CRM est lu UNIQUEMENT via ``apps.crm.selectors``
(``signed_leads_for_campaigns``) — jamais un import de ``apps.crm.models``
(contrat import-linter ENG20). Le stade « SIGNED » vient de ``STAGES.py`` (via le
sélecteur), jamais codé en dur ici.

ATTRIBUTION : la clé d'attribution d'une campagne est son ``name`` — convention
« Launch Kit » (le moteur nomme la campagne ET estampille la MÊME valeur dans
l'``utm_campaign`` des liens ; domaines 11-13 de la recherche). Le service reste
déterministe et testable sur fixtures.
"""
from __future__ import annotations

from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum

from .models import AdCampaignMirror, InsightSnapshot


def _campaign_spend_map(company, campaigns):
    """Dépense cumulée (``InsightSnapshot.spend``) par miroir de campagne.

    Renvoie ``{campaign_pk: Decimal}`` — réconcilie avec les miroirs (une seule
    source : les instantanés rattachés à la campagne par FK générique)."""
    if not campaigns:
        return {}
    ct = ContentType.objects.get_for_model(AdCampaignMirror)
    rows = (InsightSnapshot.objects
            .filter(company=company, content_type=ct,
                    object_id__in=[c.pk for c in campaigns])
            .values('object_id')
            .annotate(spend=Sum('spend')))
    return {r['object_id']: (r['spend'] or Decimal('0')) for r in rows}


def cost_per_signature(company):
    """ENG10 — Métriques coût-par-signature PAR campagne, avec traçabilité.

    Renvoie une liste de dicts (ordonnée par ``meta_id``) ::

        {
          'campaign_meta_id': str,
          'campaign_name': str,
          'attribution_key': str,       # valeur utm_campaign attendue (= name)
          'spend': str,                 # Decimal sérialisé (dépense cumulée)
          'signed_count': int,          # nombre de signatures attribuées
          'cost_per_signature': str|None,  # spend/signed_count, None si 0 signé
          'signed_lead_ids': [int, ...],   # traçabilité — leads réels
        }

    Le CRM est lu via ``apps.crm.selectors.signed_leads_for_campaigns`` (jamais
    d'import de models). La dépense se réconcilie avec les miroirs.
    """
    from apps.crm.selectors import signed_leads_for_campaigns

    campaigns = list(
        AdCampaignMirror.objects.filter(company=company).order_by('meta_id'))
    spend_map = _campaign_spend_map(company, campaigns)

    # Clé d'attribution = nom de campagne (convention utm_campaign = name).
    attribution_keys = [c.name for c in campaigns if c.name]
    signed = signed_leads_for_campaigns(company, attribution_keys)

    results = []
    for camp in campaigns:
        key = camp.name or ''
        spend = spend_map.get(camp.pk, Decimal('0'))
        bucket = signed.get(key, {'signed_count': 0, 'signed_lead_ids': []})
        count = bucket['signed_count']
        cps = (spend / count) if count else None
        results.append({
            'campaign_meta_id': camp.meta_id,
            'campaign_name': camp.name,
            'attribution_key': key,
            'spend': str(spend),
            'signed_count': count,
            'cost_per_signature': (str(cps) if cps is not None else None),
            'signed_lead_ids': list(bucket['signed_lead_ids']),
        })
    return results


def cost_per_signature_summary(company):
    """Agrégat société : dépense totale, signatures totales, coût-par-signature
    global + le détail par campagne. La dépense totale se réconcilie avec la
    somme des instantanés des miroirs de campagne."""
    per_campaign = cost_per_signature(company)
    total_spend = sum((Decimal(row['spend']) for row in per_campaign),
                      Decimal('0'))
    # ENGFIX4 — total signatures = nombre de leads DISTINCTS (union des ids), et
    # NON la somme des compteurs par campagne : deux miroirs de MÊME nom
    # partagent la même clé d'attribution → le même bucket signé, donc chaque
    # lead serait compté deux fois par une simple somme (gonflement du total,
    # écrasement du coût-par-signature héros). La dépense, elle, reste sommée
    # (chaque miroir porte sa propre dépense, clée par pk distinct).
    distinct_signed_ids = set()
    for row in per_campaign:
        distinct_signed_ids.update(row['signed_lead_ids'])
    total_signed = len(distinct_signed_ids)
    global_cps = (total_spend / total_signed) if total_signed else None
    return {
        'total_spend': str(total_spend),
        'total_signed': total_signed,
        'cost_per_signature': (str(global_cps) if global_cps is not None
                               else None),
        'campagnes': per_campaign,
    }
