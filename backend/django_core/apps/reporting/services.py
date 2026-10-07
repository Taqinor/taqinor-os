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


def q_lead_gagne():
    """AANA21 / D-AANA-1 — filtre ORM d'un lead GAGNÉ : étape SIGNED (clé lue
    dans ``apps.crm.stages``, jamais un littéral) ET non perdu."""
    from django.db.models import Q

    from apps.crm import stages
    return Q(stage=stages.SIGNED, perdu=False)


def est_lead_gagne(lead):
    """AANA21 / D-AANA-1 — un lead ``perdu=True`` n'est JAMAIS gagné, même à
    l'étape SIGNED (règle de ``crm/kpis.py``)."""
    from apps.crm import stages
    return lead.stage == stages.SIGNED and not getattr(lead, 'perdu', False)


def _leads_gagnes(leads):
    """AANA21 — LE calcul unique des leads gagnés du reporting.

    Accepte un QuerySet de ``Lead`` (renvoie un QuerySet filtré) ou un
    itérable de leads déjà chargés (renvoie une liste). Funnel, rapports
    planifiés, cohortes, gain/perte par source et classement passent par ici
    (ou par ``q_lead_gagne`` / ``est_lead_gagne``) — jamais un recalcul local.
    """
    from django.db.models import QuerySet
    if isinstance(leads, QuerySet):
        return leads.filter(q_lead_gagne())
    return [le for le in leads if est_lead_gagne(le)]


def taux_gain(leads):
    """AANA21 / D-AANA-1 — LE taux de gain du reporting : leads gagnés (SIGNED
    non perdus) ÷ leads NON perdus, en %, 1 décimale ; ``None`` sans lead non
    perdu. ``leads`` = itérable de leads déjà chargés."""
    leads = list(leads)
    actifs = [le for le in leads if not getattr(le, 'perdu', False)]
    if not actifs:
        return None
    return round(len(_leads_gagnes(actifs)) / len(actifs) * 100, 1)


def build_leaderboard(signed_devis, kwc_by_devis, leads):
    """WIR82 — calcul UNIQUE du classement commercial.

    Source partagée consommée à la fois par
    ``reporting.commercial.commercial_dashboard`` (leaderboard inline) et par
    ``reporting.insights.sales_leaderboard`` (export xlsx) — au lieu de deux
    calculs quasi identiques divergents.

    Arguments :
      - ``signed_devis`` : itérable de Devis signés (statut ACCEPTE), avec
        ``lead``/``lead__owner``/``created_by`` select_related.
      - ``kwc_by_devis`` : dict {devis_id: Decimal(kWc installé)}.
      - ``leads`` : itérable des leads de la fenêtre (``owner_id``,
        ``stage``, ``perdu``) — AANA21 : le taux de victoire individuel est
        LE taux de gain partagé (``taux_gain`` : gagnés ÷ non perdus).

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

    # AANA21 — leads groupés par propriétaire, propriétaire absent = clé 0
    # (même clé que les devis ci-dessus).
    leads_by_owner = {}
    for le in leads:
        leads_by_owner.setdefault(le.owner_id or 0, []).append(le)

    rows = []
    for uid, slot in agg.items():
        win_rate = taux_gain(leads_by_owner.get(uid, []))
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
