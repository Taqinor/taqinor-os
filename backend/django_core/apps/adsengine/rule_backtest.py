"""PUB91 — Backtest d'une règle sur l'historique RÉEL (dry-run avant armement).

Avant d'armer une règle, on la rejoue sur les snapshots RÉELS de la société
(« qu'aurait-elle fait sur votre dernier trimestre ? ») : jour par jour, on
évalue la CONDITION de la règle *comme si on était ce jour-là* et on liste les
actions qu'elle **AURAIT proposées**. Rien n'est jamais exécuté ni persisté —
c'est un pur dry-run historique, bien plus convaincant que le simulateur
synthétique existant (``simulator.py``), qui reste INCHANGÉ.

Point-clé (honnêteté du backtest) : on RÉUTILISE les évaluateurs RÉELS du moteur
(``rules_engine._EVALUATORS``) — jamais une ré-implémentation de la logique de
condition qui divergerait. Les évaluateurs ne PERSISTENT rien (ils renvoient des
``findings`` ; c'est ``evaluate_company`` → ``_act_on_finding`` qui crée les
``EngineAction``, et on ne l'appelle JAMAIS ici). La fenêtre de snapshots est
bornée « as-of » (``rules_engine._as_of_date``), donc aucune donnée future ne
fuite dans le rejeu d'un jour passé (pas de lookahead bias).
"""
from __future__ import annotations

import datetime
import logging

logger = logging.getLogger(__name__)

DEFAULT_BACKTEST_DAYS = 90   # « votre dernier trimestre »
MAX_BACKTEST_DAYS = 180


def _as_of_datetime(day):
    """Datetime aware à la FIN du jour ``day`` (borne as-of du rejeu)."""
    from django.utils import timezone
    naive = datetime.datetime.combine(day, datetime.time(23, 59))
    if timezone.is_aware(timezone.now()):
        return timezone.make_aware(naive)
    return naive


def backtest_rule(policy, *, now=None, days=DEFAULT_BACKTEST_DAYS, config=None):
    """PUB91 — Rejoue ``policy`` sur ``days`` jours d'historique réel (dry-run).

    Renvoie ::

        {'supported': bool, 'reason': str,
         'template_key', 'label_fr', 'range': {'debut', 'fin'},
         'proposals': [{'date', 'target_type', 'target_meta_id', 'action_kind',
                        'condition_fr', 'computed'}, …],
         'summary': {'days', 'would_propose', 'distinct_targets', 'action_kind'}}

    ``supported`` est faux (avec ``reason`` FR) quand le template est inconnu ou
    son évaluateur n'est pas câblé — jamais un backtest faux/silencieux. AUCUNE
    ``EngineAction`` n'est créée : les propositions sont hypothétiques.
    """
    from django.utils import timezone

    from . import rule_templates, rules_engine
    from .models import GuardrailConfig

    now = now or timezone.now()
    days = max(1, min(int(days), MAX_BACKTEST_DAYS))

    template = rule_templates.get_template(policy.template_key)
    if template is None:
        return {'supported': False, 'reason': 'Template de règle inconnu.',
                'proposals': [], 'summary': _empty_summary(days)}
    evaluator = rules_engine._EVALUATORS.get(policy.template_key)
    if evaluator is None:
        return {
            'supported': False,
            'reason': ('Backtest indisponible pour ce type de règle '
                       '(évaluateur non câblé).'),
            'template_key': policy.template_key,
            'label_fr': template.get('label_fr'),
            'proposals': [], 'summary': _empty_summary(days)}

    if config is None:
        config = GuardrailConfig.objects.filter(company=policy.company).first()

    action_spec = template.get('action') or {}
    action_kind = action_spec.get('kind')  # None = règle alerte-seule

    end_date = rules_engine._as_of_date(now)
    start_date = end_date - datetime.timedelta(days=days - 1)

    proposals = []
    day = start_date
    while day <= end_date:
        as_of = _as_of_datetime(day)
        try:
            findings = evaluator(
                policy.company, policy, template, now=as_of,
                config=config) or []
        except Exception:  # noqa: BLE001 — un jour en échec n'arrête pas le rejeu
            logger.warning(
                'rule_backtest: échec rejeu règle=%s jour=%s',
                policy.template_key, day, exc_info=True)
            findings = []
        for f in findings:
            if not f.get('fired'):
                continue
            proposals.append({
                'date': day.isoformat(),
                'target_type': f.get('target_type'),
                'target_meta_id': f.get('target_meta_id'),
                'action_kind': action_kind,
                'condition_fr': rules_engine._condition_fr(template, f),
                'computed': f.get('computed', {}),
            })
        day += datetime.timedelta(days=1)

    return {
        'supported': True,
        'reason': '',
        'template_key': policy.template_key,
        'label_fr': template.get('label_fr'),
        'range': {'debut': start_date.isoformat(), 'fin': end_date.isoformat()},
        'proposals': proposals,
        'summary': {
            'days': days,
            'would_propose': len(proposals),
            'distinct_targets': len({
                p['target_meta_id'] for p in proposals
                if p['target_meta_id']}),
            'action_kind': action_kind,
        },
    }


def _empty_summary(days):
    return {'days': days, 'would_propose': 0, 'distinct_targets': 0,
            'action_kind': None}
