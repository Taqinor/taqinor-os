"""Orchestration inter-app de l'app reporting.

VX61 — `WebVitalMetric` grossit vite (une ligne par métrique par
navigation) : purge programmée via le registre partagé YOPSB10
(`core.retention`), enregistrée dans `ReportingConfig.ready()`. Fenêtre par
défaut 30 jours (bien plus court que les 180 j CRM — ce ne sont que des
mesures de performance agrégées, pas des données métier), founder-override
via `WEB_VITALS_RETENTION_DAYS` (settings/.env, même patron que
`apps/crm/services.py`). 0/négatif désactive la purge (conservation
illimitée, comportement actuel inchangé).
"""
from decimal import Decimal

from django.utils import timezone

DEFAULT_WEB_VITALS_RETENTION_DAYS = 30


def build_leaderboard(signed_devis, kwc_by_devis, leads_by_owner):
    """WIR82 — calcul UNIQUE du classement commercial.

    Source partagée consommée à la fois par
    ``reporting.commercial.commercial_dashboard`` (leaderboard inline) et par
    ``reporting.insights.sales_leaderboard`` (export xlsx) — au lieu de deux
    calculs quasi identiques divergents.

    Arguments :
      - ``signed_devis`` : itérable de Devis signés (statut ACCEPTE), avec
        ``lead``/``lead__owner``/``created_by`` select_related.
      - ``kwc_by_devis`` : dict {devis_id: Decimal(kWc installé)}.
      - ``leads_by_owner`` : dict {owner_id (0 si aucun): nb de leads} pour le
        taux de victoire individuel.

    Retourne la liste de lignes triée par CA HT décroissant (mêmes clés et
    formats qu'avant l'extraction : chaînes pour les décimaux).
    """
    # QX2 — CA sur le HT REMISÉ de l'option acceptée (chaîne canonique QX1),
    # jamais le HT brut : le classement/CA reflète le vrai revenu signé.
    from apps.ventes.utils.options import option_totaux

    agg = {}
    for d in signed_devis:
        if d.lead_id and d.lead and d.lead.owner_id:
            owner = d.lead.owner
        else:
            owner = d.created_by
        uid = owner.id if owner else 0
        slot = agg.setdefault(uid, {
            'commercial': (getattr(owner, 'username', '') if owner else '') or '—',
            'ca_ht': Decimal('0'),
            'nb_devis': 0,
            'kwc': Decimal('0'),
        })
        slot['ca_ht'] += Decimal(str(option_totaux(d)['ht']))
        slot['nb_devis'] += 1
        slot['kwc'] += kwc_by_devis.get(d.id, Decimal('0'))

    rows = []
    for uid, slot in agg.items():
        total_leads = leads_by_owner.get(uid, 0)
        win_rate = (
            round(slot['nb_devis'] / total_leads * 100, 1)
            if total_leads else None
        )
        avg_deal = (
            round(float(slot['ca_ht']) / slot['nb_devis'], 2)
            if slot['nb_devis'] else 0
        )
        rows.append({
            'commercial': slot['commercial'],
            'ca_ht': str(slot['ca_ht']),
            'nb_devis_signes': slot['nb_devis'],
            'avg_deal_ht': str(avg_deal),
            'kwc': str(slot['kwc']),
            'win_rate_pct': win_rate,
        })

    rows.sort(key=lambda r: float(r['ca_ht']), reverse=True)
    return rows


def _retention_days(setting_name, default_days):
    from django.conf import settings
    value = getattr(settings, setting_name, None)
    if value is None:
        return default_days
    try:
        return int(value)
    except (TypeError, ValueError):
        return default_days


def purge_web_vitals(now, apply_) -> int:
    """VX61 — purge les `WebVitalMetric` au-delà de la fenêtre de
    rétention. Contrat `core.retention` : `apply_=False` (dry-run) ne
    supprime rien, renvoie le compte qui SERAIT supprimé."""
    from .models import WebVitalMetric

    days = _retention_days(
        'WEB_VITALS_RETENTION_DAYS', DEFAULT_WEB_VITALS_RETENTION_DAYS)
    if days <= 0:
        return 0
    cutoff = (now or timezone.now()) - timezone.timedelta(days=days)
    qs = WebVitalMetric.objects.filter(created_at__lt=cutoff)
    count = qs.count()
    if apply_ and count:
        qs.delete()
    return count
