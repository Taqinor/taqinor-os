"""ADSENG9 — Échelle des récompenses + détecteur de divergence CRM/proxy.

dd-science-core §2.7 : le bandit tourne sur une **récompense proxy** fréquente et
bon marché — ``conversation démarrée / impression`` (métrique Meta
``onsite_conversion.messaging_conversation_started_7d``) — parce que les rungs
« argent » (lead qualifié, signature) sont statistiquement sombres à ce volume
(§1.4) et ne peuvent JAMAIS piloter un bandit.

Mais la vérité CRM peut **véto** (jamais piloter en autonome). Une fois par
semaine, ce module compare le **classement proxy** des bras au **classement du
coût CRM** (coût-par-lead-qualifié, via ``attribution.py`` = ADSENG6, en lecture
seule à travers les sélecteurs CRM). Si les deux classements divergent de PLUS
d'une position — un écart d'une seule position = bruit (§2.7) — ET qu'au moins
10 leads qualifiés se sont accumulés, le moteur **N'AGIT PAS** : il lève une
``EngineAction`` propose-only (``auto=False``, ``status='proposee'``) portant les
deux classements et une raison FR. En dessous de ce seuil de preuve, le proxy
règne et le chiffre CRM n'est que du contexte. Convergence ⇒ rien.

Le cœur (``evaluate_divergence``) est **pur** (aucune I/O, testable sans base) ;
seul ``run_divergence_check`` lit la base et propose l'action.
"""
from __future__ import annotations

from decimal import Decimal

# Métrique de récompense proxy (Meta) — VÉRIFIÉE (dd-science-core §2.2/§7).
PROXY_METRIC_KEY = 'onsite_conversion.messaging_conversation_started_7d'

# Seuils du gardien de divergence (dd-science-core §2.7 / §7).
MIN_QUALIFIED_FOR_DIVERGENCE = 10   # « ≥ ~10 leads qualifiés cumulés »
MAX_RANK_GAP_NOISE = 1              # « un écart d'une seule position = bruit »

# Fenêtre glissante du proxy (jours) — GrowthBook « daily or longer » (§2.2/§7).
DEFAULT_WINDOW_DAYS = 28


def proxy_reward(impressions, conversions):
    """Récompense proxy autonome = conversations démarrées / impression.

    Le taux composite CTR × opt-in en un seul nombre (§2.2) : la métrique la
    moins chère qui reflète encore la qualité créative. 0 impression ⇒ 0 (jamais
    de division par zéro, jamais un taux fabriqué). Fonction pure.
    """
    imp = int(impressions)
    if imp <= 0:
        return 0.0
    return max(int(conversions), 0) / imp


def _rank_labels(arms, *, sort_key):
    """Ordonne les libellés du meilleur au pire selon ``sort_key`` (déterministe :
    ``sort_key`` intègre un bris d'égalité par libellé). Renvoie la liste des
    libellés et le dict ``label -> position`` (0 = meilleur)."""
    ordered = sorted(arms, key=sort_key)
    labels = [a['label'] for a in ordered]
    positions = {label: i for i, label in enumerate(labels)}
    return labels, positions


def evaluate_divergence(arms, *, min_qualified=MIN_QUALIFIED_FOR_DIVERGENCE,
                        max_rank_gap=MAX_RANK_GAP_NOISE):
    """Cœur PUR du détecteur (dd-science-core §2.7).

    ``arms`` : liste de dicts, un par bras vivant ::

        {'label': str, 'proxy': float, 'crm_cost': float|None, 'qualified': int}

    - ``proxy`` : récompense proxy (plus haut = meilleur) ;
    - ``crm_cost`` : coût-par-lead-qualifié CRM (plus BAS = meilleur) ; ``None``
      si aucun lead qualifié attribué (classé en dernier, jamais « coût zéro ») ;
    - ``qualified`` : nombre de leads qualifiés attribués au bras.

    Renvoie un dict décision ::

        {'diverged': bool, 'max_rank_gap': int, 'qualified_total': int,
         'proxy_ranking': [labels best→worst], 'crm_ranking': [...],
         'proxy_best': label|None, 'crm_best': label|None, 'reason_fr': str}

    ``diverged`` est vrai UNIQUEMENT si l'écart de classement max dépasse
    ``max_rank_gap`` (donc ≥ 2 positions) ET que ``qualified_total`` atteint
    ``min_qualified``. Aucune I/O, aucun effet de bord. Le moteur qui reçoit
    ``diverged=True`` PROPOSE (jamais n'applique).
    """
    qualified_total = sum(max(int(a.get('qualified', 0)), 0) for a in arms)

    # Moins de 2 bras : pas de classement possible ⇒ jamais de divergence.
    if len(arms) < 2:
        proxy_ranking = [a['label'] for a in arms]
        return {
            'diverged': False,
            'max_rank_gap': 0,
            'qualified_total': qualified_total,
            'proxy_ranking': proxy_ranking,
            'crm_ranking': list(proxy_ranking),
            'proxy_best': proxy_ranking[0] if proxy_ranking else None,
            'crm_best': proxy_ranking[0] if proxy_ranking else None,
            'reason_fr': '',
        }

    # Classement proxy : récompense décroissante (meilleur = plus haute).
    proxy_ranking, proxy_pos = _rank_labels(
        arms, sort_key=lambda a: (-float(a.get('proxy', 0.0)), a['label']))
    # Classement CRM : coût croissant (meilleur = moins cher) ; None en dernier.
    crm_ranking, crm_pos = _rank_labels(
        arms, sort_key=lambda a: (a.get('crm_cost') is None,
                                  float(a['crm_cost'])
                                  if a.get('crm_cost') is not None else 0.0,
                                  a['label']))

    max_gap = max(abs(proxy_pos[label] - crm_pos[label])
                  for label in proxy_pos)

    diverged = (max_gap > max_rank_gap
                and qualified_total >= min_qualified)

    proxy_best = proxy_ranking[0]
    crm_best = crm_ranking[0]
    reason_fr = ''
    if diverged:
        reason_fr = (
            f"Divergence CRM/proxy : le proxy favorise « {proxy_best} » mais le "
            f"coût CRM favorise « {crm_best} » (écart de {max_gap} positions sur "
            f"{qualified_total} leads qualifiés) — le moteur ne réalloue PAS "
            f"seul, une approbation humaine est requise.")

    return {
        'diverged': diverged,
        'max_rank_gap': max_gap,
        'qualified_total': qualified_total,
        'proxy_ranking': proxy_ranking,
        'crm_ranking': crm_ranking,
        'proxy_best': proxy_best,
        'crm_best': crm_best,
        'reason_fr': reason_fr,
    }


def _window_start(now, window_days):
    from datetime import timedelta
    return now - timedelta(days=window_days - 1)


def collect_arm_rewards(company, *, experiment=None, window_days=DEFAULT_WINDOW_DAYS,
                        now=None, qualifying_stage=None):
    """Assemble les données par bras (proxy fenêtré + coût CRM cumulé).

    Lit ``ArmDailyStat`` (même app) sur la fenêtre glissante pour le proxy, et
    ``attribution.variant_attribution`` (ADSENG6 → sélecteurs CRM only) pour le
    coût-par-lead-qualifié cumulé. Renvoie la liste de dicts attendue par
    :func:`evaluate_divergence`. Scopé société.
    """
    from datetime import date
    from django.db.models import Sum

    from . import attribution
    from .models import ArmDailyStat, ExperimentArm

    today = now or date.today()
    start = _window_start(today, window_days)

    arms_qs = ExperimentArm.objects.filter(company=company, is_active=True)
    if experiment is not None:
        arms_qs = arms_qs.filter(experiment=experiment)
    arms = [a for a in arms_qs if a.ad_id]
    if not arms:
        return []

    # Proxy fenêtré par bras.
    stats = (ArmDailyStat.objects
             .filter(company=company, arm__in=arms,
                     date__gte=start, date__lte=today)
             .values('arm')
             .annotate(imp=Sum('impressions'), conv=Sum('conversations')))
    proxy_by_arm = {s['arm']: proxy_reward(s['imp'] or 0, s['conv'] or 0)
                    for s in stats}

    # Coût CRM cumulé par ad (attribution ADSENG6).
    ad_ids = [a.ad_id for a in arms]
    attr = attribution.variant_attribution(
        company, qualifying_stage=qualifying_stage, ad_ids=ad_ids)
    crm_by_meta = {v['meta_id']: v for v in attr['variants']}

    rows = []
    for a in arms:
        variant = crm_by_meta.get(a.ad_id)
        cpql = variant['cost_per_qualified_lead'] if variant else None
        rows.append({
            'label': a.label or a.ad_id or f'arm-{a.pk}',
            'arm_id': a.pk,
            'ad_id': a.ad_id,
            'proxy': proxy_by_arm.get(a.pk, 0.0),
            'crm_cost': float(Decimal(cpql)) if cpql is not None else None,
            'qualified': variant['qualified'] if variant else 0,
        })
    return rows


def run_divergence_check(company, *, experiment=None,
                         window_days=DEFAULT_WINDOW_DAYS, now=None,
                         qualifying_stage=None, create_action=True):
    """Boucle hebdomadaire (I/O) : assemble → évalue → propose (jamais applique).

    En cas de divergence, crée une ``EngineAction`` **propose-only**
    (``kind=rebalance_budget``, ``auto=False``, ``status='proposee'``) portant
    les deux classements et la raison FR. Convergence ⇒ aucune action.
    Renvoie ``(decision, action|None)``.
    """
    from .models import EngineAction

    rows = collect_arm_rewards(
        company, experiment=experiment, window_days=window_days, now=now,
        qualifying_stage=qualifying_stage)
    decision = evaluate_divergence(rows)

    action = None
    if decision['diverged'] and create_action:
        # Propose-only : jamais auto. Company forcée côté serveur ; raison FR
        # non vide (contrainte CHECK ``adseng_action_reason_req``).
        action = EngineAction.objects.create(
            company=company,
            kind=EngineAction.Kind.REBALANCE_BUDGET,
            payload={
                'source': 'rewards.divergence',
                'proxy_ranking': decision['proxy_ranking'],
                'crm_ranking': decision['crm_ranking'],
                'proxy_best': decision['proxy_best'],
                'crm_best': decision['crm_best'],
                'max_rank_gap': decision['max_rank_gap'],
                'qualified_total': decision['qualified_total'],
                'proxy_metric': PROXY_METRIC_KEY,
            },
            reason_fr=decision['reason_fr'],
            status=EngineAction.Statut.PROPOSEE,
            auto=False,
        )
    return decision, action
