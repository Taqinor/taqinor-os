"""ADSENG14 — Catalogue FIXE de règles du Gardien (style ``STAGES.py``).

Source de vérité UNIQUE des SHAPES de règles : conditions AND/OR (JSON),
fenêtres temporelles, action par défaut, sévérité, cadence, et paramètres
éditables whitelistés. **Pas de rule-builder libre** (leçon Revealbot « expertise
média non fournie », dd-guardian §A6/A7) : le fondateur choisit un template du
catalogue et n'en ajuste QUE les paramètres autorisés — jamais la logique.

Ce module ÉTOFFE ``rules.py`` (ADSENG4, qui ne porte que la métadonnée sévérité +
libellé + action) : il ajoute la couche DSL (conditions/fenêtres/action) que le
moteur d'évaluation (``rules_engine.py``, ADSENG15) consomme. Il RÉUTILISE les
constantes de sévérité + cooldown de ``rules.py`` (une seule source de sévérité).

Invariant structurel : ``dry_run`` par défaut True pour toute règle nouvellement
seedée — une règle en simulation ne joue JAMAIS rien (elle se contente de
PROPOSER une action préfixée « [Simulation] »). Voir ``rules_engine`` pour
l'application de cet invariant côté évaluation.

Module PLAIN : aucun import de modèle au niveau module (les helpers de seed
importent les modèles LOCALEMENT — évite tout cycle et garde le catalogue
importable partout, y compris migrations/scripts).
"""
from __future__ import annotations

from .rules import (
    DEFAULT_COOLDOWN_HOURS, SEVERITY_CRITICAL, SEVERITY_INFO, SEVERITY_WARNING,
)

# ── Cadences d'évaluation (dd-guardian §A9 — JAMAIS sub-horaire) ──────────────
# La boucle critique tourne toutes les 6 h ; les règles d'optimisation une fois
# par jour (après la synchro ENG6) ; les règles de tendance une fois par semaine
# (rythme du brief du lundi ENG11). Aucune cadence n'est sub-horaire (les rate
# limits Meta scalent avec le spend et pénalisent les petits comptes).
CADENCE_CRITICAL = 'critical'   # toutes les 6 h — sécurité (argent brûlé, ad KO)
CADENCE_DAILY = 'daily'         # quotidien — optimisation (données fraîches)
CADENCE_WEEKLY = 'weekly'       # hebdomadaire — tendance (rotation, backlog)

CADENCES = (CADENCE_CRITICAL, CADENCE_DAILY, CADENCE_WEEKLY)


# ── Catalogue fixe (8 templates, PLAN ADSENG14) ──────────────────────────────
# Chaque entrée :
#   * ``label_fr``          — libellé UI (français).
#   * ``severity``          — 🔴/🟠/🔵 (aligné ``rules.SEVERITY_*``).
#   * ``cadence``           — CADENCE_* (à quelle boucle beat la règle appartient).
#   * ``scope``             — 'account'|'campaign'|'adset'|'ad' (granularité cible).
#   * ``detector``          — nom du détecteur d'anomalie (``anomaly.py``) OU None
#                             (règle non basée sur un détecteur — évaluée à part).
#   * ``action``            — None (alerte seule) OU
#                             {'kind': <EngineAction.Kind value>,
#                              'requires_capability': <champ GuardrailConfig|None>}.
#                             ``kind`` None/absent = alerte seule (rien à approuver).
#                             ``requires_capability`` None = toujours approbation
#                             humaine (jamais d'auto), même en mode auto.
#   * ``conditions``        — DSL AND/OR (dd-guardian §A6), instancié avec ``params``.
#   * ``editable_params``   — whitelist des clés de params ajustables.
#   * ``default_params``    — valeurs par défaut (conservatrices, dd-guardian §b).
RULE_TEMPLATES = {
    # 1) Stop-loss — coût par lead au-dessus d'un plafond dur.
    'stop_loss_cpl': {
        'label_fr': 'Stop-loss — coût par lead au plafond',
        'severity': SEVERITY_CRITICAL,
        'cadence': CADENCE_DAILY,
        'scope': 'campaign',
        'detector': None,
        'action': {'kind': 'pause', 'requires_capability': None},
        'conditions': {
            'logic': 'all',
            'conditions': [{
                'field': 'cost_per_lead_mad',
                'scope': 'campaign',
                'operator': 'gt',
                'value_param': 'threshold_mad',
                'window': {'type': 'trailing_days', 'param': 'window_days'},
                'min_samples_param': 'min_samples',
                'on_insufficient_data': 'alert_info',
            }],
        },
        'editable_params': ['threshold_mad', 'window_days', 'min_samples'],
        'default_params': {
            'threshold_mad': 250, 'window_days': 7, 'min_samples': 5},
    },
    # 2) Revive — une campagne en pause redevient performante : le moteur
    #    N'ACTIVE JAMAIS (règle permanente #3) ; il INFORME seulement, le
    #    fondateur réactive à la main dans Meta.
    'revive': {
        'label_fr': 'Revive — campagne en pause redevenue performante',
        'severity': SEVERITY_INFO,
        'cadence': CADENCE_WEEKLY,
        'scope': 'adset',
        'detector': None,
        'action': None,  # alerte seule — le moteur n'active jamais rien.
        'conditions': {
            'logic': 'all',
            'conditions': [{
                'field': 'leads_count',
                'scope': 'adset',
                'operator': 'gte',
                'value_param': 'min_leads',
                'window': {'type': 'trailing_days', 'param': 'window_days'},
                'min_samples_param': 'min_leads',
                'on_insufficient_data': 'skip',
            }],
        },
        'editable_params': ['min_leads', 'window_days'],
        'default_params': {'min_leads': 1, 'window_days': 7},
    },
    # 3) Fatigue créative — fréquence en fuite (réutilise la clé ADSENG4).
    'frequency_high': {
        'label_fr': 'Fatigue créative — fréquence élevée',
        'severity': SEVERITY_WARNING,
        'cadence': CADENCE_DAILY,
        'scope': 'adset',
        'detector': 'frequency_runaway',
        'action': {'kind': 'rotate_creative',
                   'requires_capability': 'auto_rotate_creative'},
        'conditions': {
            'logic': 'any',
            'conditions': [{
                'field': 'frequency',
                'scope': 'adset',
                'operator': 'gt',
                'value_param': 'frequency_max',
                'window': {'type': 'trailing_days', 'param': 'window_days'},
                'min_samples_param': 'min_samples',
                'on_insufficient_data': 'alert_info',
            }],
        },
        'editable_params': ['frequency_max', 'window_days', 'min_samples'],
        'default_params': {
            'frequency_max': 3.0, 'window_days': 7, 'min_samples': 3},
    },
    # 4) Zéro diffusion malgré dépense (réutilise la clé ADSENG4).
    'zero_delivery': {
        'label_fr': 'Zéro diffusion malgré dépense',
        'severity': SEVERITY_CRITICAL,
        'cadence': CADENCE_CRITICAL,
        'scope': 'campaign',
        'detector': 'zero_delivery',
        # Pause PROPOSÉE, jamais auto : un humain doit vérifier le compte Meta
        # (paiement / révision / restriction) — dd-guardian §B3.
        'action': {'kind': 'pause', 'requires_capability': None},
        'conditions': {
            'logic': 'all',
            'conditions': [{
                'field': 'impressions',
                'scope': 'campaign',
                'operator': 'eq',
                'value_param': 'zero',
                'window': {'type': 'trailing_hours', 'param': 'hours'},
                'min_samples_param': None,
                'on_insufficient_data': 'alert_info',
            }],
        },
        'editable_params': ['hours', 'min_spend_mad'],
        'default_params': {'hours': 48, 'min_spend_mad': 20},
    },
    # 5) Dépassement d'enveloppe budgétaire (pacing) — réutilise la clé ADSENG4.
    #    La MATH de pacing atterrit avec ADSENG20 (pacing.py) ; ici le template
    #    existe (catalogue fixe) et lira l'état de pacing une fois câblé.
    'budget_pacing_breach': {
        'label_fr': "Dépassement d'enveloppe budgétaire (pacing)",
        'severity': SEVERITY_CRITICAL,
        'cadence': CADENCE_DAILY,
        'scope': 'account',
        'detector': None,
        'action': {'kind': 'pause', 'requires_capability': None},
        'conditions': {
            'logic': 'all',
            'conditions': [{
                'field': 'pacing_ratio',
                'scope': 'account',
                'operator': 'gt',
                'value_param': 'max_ratio',
                'window': {'type': 'month_to_date'},
                'min_samples_param': None,
                'on_insufficient_data': 'skip',
            }],
        },
        'editable_params': ['max_ratio'],
        'default_params': {'max_ratio': 1.0},
    },
    # 6) Bande CPL — coût/lead hors de sa bande ±2× (dd-guardian §B2).
    'cpl_band': {
        'label_fr': 'Bande CPL — coût par lead hors de sa bande',
        'severity': SEVERITY_WARNING,
        'cadence': CADENCE_DAILY,
        'scope': 'campaign',
        'detector': 'cpl_band',
        'action': None,  # alerte seule (le fondateur décide de l'ajustement).
        'conditions': {
            'logic': 'any',
            'conditions': [{
                'field': 'cost_per_lead_mad',
                'scope': 'campaign',
                'operator': 'outside_band',
                'value_param': 'band',
                'window': {'type': 'trailing_days', 'param': 'window_days'},
                'min_samples_param': 'min_samples',
                'on_insufficient_data': 'alert_info',
            }],
        },
        'editable_params': [
            'band_low_mult', 'band_high_mult', 'window_days', 'min_samples'],
        'default_params': {
            'band_low_mult': 0.5, 'band_high_mult': 2.0,
            'window_days': 14, 'min_samples': 5},
    },
    # 7) Backlog créatif bas — moins de N assets prêts (fatigue à venir).
    'low_backlog': {
        'label_fr': 'Backlog créatif bas',
        'severity': SEVERITY_INFO,
        'cadence': CADENCE_WEEKLY,
        'scope': 'account',
        'detector': None,
        'action': None,  # alerte seule (produire de nouvelles créations).
        'conditions': {
            'logic': 'all',
            'conditions': [{
                'field': 'backlog_ready_count',
                'scope': 'account',
                'operator': 'lt',
                'value_param': 'min_backlog',
                'window': {'type': 'snapshot'},
                'min_samples_param': None,
                'on_insufficient_data': 'skip',
            }],
        },
        'editable_params': ['min_backlog'],
        'default_params': {'min_backlog': 3},
    },
    # 8) Divergence de réconciliation — le classement CRM diverge du proxy
    #    (dd-science-core §c / ADSENG9). Alerte seule : le moteur N'AGIT PAS sur
    #    une divergence, il la SIGNALE.
    'recon_divergence': {
        'label_fr': 'Divergence de réconciliation (CRM vs proxy)',
        'severity': SEVERITY_WARNING,
        'cadence': CADENCE_WEEKLY,
        'scope': 'account',
        'detector': None,
        'action': None,  # alerte seule (jamais d'action auto sur une divergence).
        'conditions': {
            'logic': 'all',
            'conditions': [{
                'field': 'rank_divergence',
                'scope': 'account',
                'operator': 'gt',
                'value_param': 'max_rank_gap',
                'window': {'type': 'snapshot'},
                'min_samples_param': 'min_qualified_leads',
                'on_insufficient_data': 'skip',
            }],
        },
        'editable_params': ['max_rank_gap', 'min_qualified_leads'],
        'default_params': {'max_rank_gap': 1, 'min_qualified_leads': 10},
    },
}


def template_keys():
    """Clés du catalogue (ordre stable d'insertion)."""
    return list(RULE_TEMPLATES.keys())


def get_template(template_key):
    """Métadonnées d'un template, ou ``None`` si la clé est inconnue."""
    return RULE_TEMPLATES.get(template_key)


def template_choices():
    """Paires (clé, libellé FR) du catalogue fixe (pour ``choices=``)."""
    return [(k, RULE_TEMPLATES[k]['label_fr']) for k in RULE_TEMPLATES]


def template_severity(template_key):
    """Sévérité d'un template (repli WARNING si clé inconnue)."""
    tpl = RULE_TEMPLATES.get(template_key)
    return tpl['severity'] if tpl else SEVERITY_WARNING


def template_cooldown_hours(template_key):
    """Cooldown par défaut d'un template = cooldown de sa sévérité (6/24/72 h)."""
    sev = template_severity(template_key)
    return DEFAULT_COOLDOWN_HOURS.get(sev, DEFAULT_COOLDOWN_HOURS[
        SEVERITY_WARNING])


def resolve_params(template_key, overrides=None):
    """Fusionne les défauts du template avec les overrides WHITELISTÉS.

    Toute clé d'override HORS ``editable_params`` est IGNORÉE (jamais de
    paramètre arbitraire — catalogue fixe, pas de builder libre). Renvoie un
    nouveau dict (les défauts du catalogue ne sont jamais mutés)."""
    tpl = RULE_TEMPLATES.get(template_key)
    if tpl is None:
        return dict(overrides or {})
    params = dict(tpl['default_params'])
    editable = set(tpl['editable_params'])
    for key, value in (overrides or {}).items():
        if key in editable:
            params[key] = value
    return params


def instantiate_conditions(template_key, overrides=None):
    """DSL de conditions du template + un dict ``params`` résolu.

    Renvoie ``(conditions, params)`` : ``conditions`` est le DSL AND/OR figé du
    catalogue (jamais modifié) ; ``params`` porte les valeurs (défauts +
    overrides whitelistés) que le moteur résout à l'évaluation."""
    tpl = RULE_TEMPLATES.get(template_key)
    if tpl is None:
        return {}, dict(overrides or {})
    return tpl['conditions'], resolve_params(template_key, overrides)


def is_actionable(template_key):
    """Vrai si le template propose une ACTION (pause/rotation), pas une alerte
    seule. Une alerte seule (``action`` None) n'écrit jamais d'``EngineAction``."""
    tpl = RULE_TEMPLATES.get(template_key)
    return bool(tpl and tpl.get('action') and tpl['action'].get('kind'))


def action_kind(template_key):
    """``EngineAction.Kind`` value du template (string) ou ``None`` (alerte seule)."""
    tpl = RULE_TEMPLATES.get(template_key)
    if not (tpl and tpl.get('action')):
        return None
    return tpl['action'].get('kind')


def seed_default_policies(company, *, created_by=None):
    """Seed idempotent des ``RulePolicy`` du catalogue fixe pour ``company``.

    Chaque template devient une ``RulePolicy`` en DÉFAUT SÛR : ``enabled=False``
    + ``dry_run=True`` + ``mode='propose'`` (le fondateur opte par template et
    quitte la simulation explicitement). ``get_or_create`` sur
    ``(company, template_key)`` — deux exécutions ne créent jamais de doublon
    (contrainte unique en base). Renvoie la liste des ``RulePolicy`` créées
    (vide au 2e passage). ``created_by`` (optionnel) posé à la création."""
    from .models import RulePolicy

    created = []
    for key, tpl in RULE_TEMPLATES.items():
        _, was_created = RulePolicy.objects.get_or_create(
            company=company, template_key=key,
            defaults={
                'enabled': False,
                'dry_run': True,
                'mode': RulePolicy.Mode.PROPOSE,
                'conditions': tpl['conditions'],
                'params': dict(tpl['default_params']),
                'cadence_hours': (
                    6 if tpl['cadence'] == CADENCE_CRITICAL else 24),
                'cooldown_hours': 0,  # 0 = défaut de sévérité (voir modèle)
                'created_by': created_by,
            },
        )
        if was_created:
            created.append(_)
    return created
