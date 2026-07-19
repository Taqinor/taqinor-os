"""PUB86 — Registre de qualité des décisions (regret réalisé).

Personne ne répond honnêtement à « l'IA aide-t-elle vraiment ? ». Ce module
compare chaque décision d'allocation loggée (les ``DecisionLog`` + leur
conséquence RÉELLE dans ``ArmDailyStat``) au bras **réellement meilleur a
posteriori**, et chiffre en MAD le *regret réalisé* — les « MAD laissés sur la
table » en ayant fait tourner des bras inférieurs plutôt que le champion.

Définition (honnête, en MAD, calculable sur les seules données réalisées) :

  * pour chaque bras, le coût-par-conversion RÉALISÉ ``cpc_i = dépense_i /
    conversions_i`` ;
  * le champion a posteriori = le bras au ``cpc`` le plus BAS (le plus efficient
    en MAD) parmi ceux ayant au moins une conversion ;
  * le gaspillage d'un bras ``= max(0, dépense_i − conversions_i · cpc_champion)``
    — exactement les MAD payés en trop pour les conversions de ce bras par rapport
    au tarif du champion. Nul pour le champion, ≥ 0 pour les autres ;
  * le regret total = la somme des gaspillages.

**Honnêteté statistique (le point qui compte le plus, régime bas-volume §0).**
Le ``cpc`` du champion repose sur un COMPTAGE de conversions souvent minuscule
(3-5/mois) : un point-estimate y serait mensonger. On borne donc le regret par un
INTERVALLE de confiance, via la CI de Poisson EXACTE du comptage du champion
(``mde.poisson_ci``, réutilisée — jamais réimplémentée) : plus de conversions
plausibles ⇒ champion moins cher ⇒ regret plus haut, et inversement. Sous le
plancher de conversions, ``insufficient_data`` est vrai et l'appelant AFFICHE
l'intervalle plutôt qu'un chiffre faussement précis.

Le cœur (:func:`realized_regret`) est **pur** : zéro I/O, entièrement testable
sur des agrégats synthétiques. La couche modèle (:func:`experiment_regret`,
:func:`regret_registry`) lit ``ArmDailyStat``/``DecisionLog`` society-scopé.
"""
from __future__ import annotations

from decimal import Decimal

from . import mde

# Sous ce nombre de conversions sur le bras champion, son cpc n'est pas fiable :
# on marque ``insufficient_data`` et on s'appuie sur l'intervalle (jamais un
# point-estimate sec) — cohérent avec le plancher d'échantillons du gardien.
DEFAULT_MIN_CONVERSIONS = 5
DEFAULT_CONFIDENCE = 0.95


def _clean_arms(arms):
    """Normalise les agrégats de bras en ``(label, spend, conversions)`` sûrs.

    ``spend`` en float ≥ 0, ``conversions`` en int ≥ 0. Fonction pure.
    """
    out = []
    for i, a in enumerate(arms or []):
        label = str(a.get('label', f'arm-{i}'))
        try:
            spend = max(float(a.get('spend', 0) or 0), 0.0)
        except (TypeError, ValueError):
            spend = 0.0
        try:
            conv = max(int(a.get('conversions', 0) or 0), 0)
        except (TypeError, ValueError):
            conv = 0
        out.append({'label': label, 'spend': spend, 'conversions': conv})
    return out


def _regret_at_cpc(arms, cpc_ref):
    """Somme des gaspillages ``max(0, dépense_i − conversions_i·cpc_ref)``. Pure."""
    total = 0.0
    for a in arms:
        total += max(0.0, a['spend'] - a['conversions'] * cpc_ref)
    return total


def realized_regret(arms, *, min_conversions=DEFAULT_MIN_CONVERSIONS,
                    confidence=DEFAULT_CONFIDENCE):
    """Regret réalisé (MAD laissés sur la table) d'un lot de bras. Fonction PURE.

    ``arms`` : itérable de dicts ``{'label', 'spend', 'conversions'}`` agrégés sur
    la fenêtre. Renvoie ::

        {'best_label', 'best_cpc', 'total_regret_mad',
         'interval': {'low', 'high'} | None, 'insufficient_data': bool,
         'total_spend', 'total_conversions',
         'per_arm': [{'label', 'spend', 'conversions', 'cpc', 'wasted_mad'}, …]}

    Le champion a posteriori = le bras au coût-par-conversion le plus bas (parmi
    ceux ayant ≥ 1 conversion). Sans aucune conversion, le regret n'est pas
    calculable : ``insufficient_data`` vrai, ``total_regret_mad`` None,
    ``interval`` None. L'intervalle borne le regret par la CI de Poisson du
    comptage du champion (``mde.poisson_ci``).
    """
    clean = _clean_arms(arms)
    total_spend = round(sum(a['spend'] for a in clean), 4)
    total_conv = sum(a['conversions'] for a in clean)

    scored = []
    for a in clean:
        cpc = (a['spend'] / a['conversions']) if a['conversions'] > 0 else None
        scored.append({**a, 'cpc': cpc})

    with_conv = [a for a in scored if a['cpc'] is not None]
    if not with_conv:
        # Aucune conversion nulle part : impossible de nommer un champion.
        return {
            'best_label': None, 'best_cpc': None, 'total_regret_mad': None,
            'interval': None, 'insufficient_data': True,
            'total_spend': total_spend, 'total_conversions': total_conv,
            'per_arm': [
                {'label': a['label'], 'spend': round(a['spend'], 4),
                 'conversions': a['conversions'], 'cpc': None,
                 'wasted_mad': None}
                for a in scored],
        }

    champion = min(with_conv, key=lambda a: a['cpc'])
    best_cpc = champion['cpc']
    best_spend = champion['spend']
    best_conv = champion['conversions']

    total_regret = _regret_at_cpc(scored, best_cpc)

    per_arm = []
    for a in scored:
        wasted = (max(0.0, a['spend'] - a['conversions'] * best_cpc)
                  if a['cpc'] is not None or a['spend'] > 0 else 0.0)
        per_arm.append({
            'label': a['label'], 'spend': round(a['spend'], 4),
            'conversions': a['conversions'],
            'cpc': round(a['cpc'], 4) if a['cpc'] is not None else None,
            'wasted_mad': round(wasted, 4)})

    # Intervalle honnête : CI de Poisson du comptage de conversions du champion.
    # λ haut ⇒ champion moins cher (cpc bas) ⇒ regret HAUT ; λ bas ⇒ regret BAS.
    lam_low, lam_high = mde.poisson_ci(best_conv, confidence=confidence)
    cpc_when_cheaper = (best_spend / lam_high) if lam_high > 0 else best_cpc
    cpc_when_dearer = (best_spend / lam_low) if lam_low > 0 else best_cpc
    regret_high = _regret_at_cpc(scored, cpc_when_cheaper)
    regret_low = _regret_at_cpc(scored, cpc_when_dearer)
    interval = {'low': round(min(regret_low, regret_high), 4),
                'high': round(max(regret_low, regret_high), 4)}

    return {
        'best_label': champion['label'],
        'best_cpc': round(best_cpc, 4),
        'total_regret_mad': round(total_regret, 4),
        'interval': interval,
        'insufficient_data': best_conv < min_conversions,
        'total_spend': total_spend,
        'total_conversions': total_conv,
        'per_arm': per_arm,
    }


# ── Couche modèle (I/O, society-scopé) ────────────────────────────────────────
def _arm_aggregates(experiment, *, date_start=None, date_end=None):
    """Agrège ``ArmDailyStat`` par bras sur la fenêtre (dépense + conversations).

    Renvoie une liste ``[{'label', 'spend', 'conversions'}]`` — un bras sans
    aucune stat sur la fenêtre est inclus à zéro (il a pu être budgété sans
    délivrer : c'est précisément un regret candidat). Company dérivée du bras.
    """
    from .models import ArmDailyStat

    rows = []
    for arm in experiment.arms.all():
        qs = ArmDailyStat.objects.filter(arm=arm)
        if date_start is not None:
            qs = qs.filter(date__gte=date_start)
        if date_end is not None:
            qs = qs.filter(date__lte=date_end)
        spend = Decimal('0')
        conv = 0
        for s in qs:
            spend += (s.spend or Decimal('0'))
            conv += int(s.conversations or 0)
        rows.append({
            'label': arm.label or f'Bras #{arm.pk}',
            'spend': float(spend), 'conversions': conv})
    return rows


def experiment_regret(experiment, *, date_start=None, date_end=None,
                      min_conversions=DEFAULT_MIN_CONVERSIONS):
    """Regret réalisé d'UNE expérience + son contexte de décisions loggées.

    Lit les ``ArmDailyStat`` (conséquence réelle des allocations) et compte les
    ``DecisionLog`` de l'expérience sur la fenêtre. Renvoie le dict de
    :func:`realized_regret` enrichi de ``experiment_id`` / ``experiment_name`` /
    ``tested_variable`` / ``decisions_logged``.
    """
    from .models import DecisionLog

    arms = _arm_aggregates(
        experiment, date_start=date_start, date_end=date_end)
    result = realized_regret(arms, min_conversions=min_conversions)

    dl = DecisionLog.objects.filter(experiment=experiment)
    if date_start is not None:
        dl = dl.filter(created_at__date__gte=date_start)
    if date_end is not None:
        dl = dl.filter(created_at__date__lte=date_end)

    result.update({
        'experiment_id': experiment.pk,
        'experiment_name': experiment.name,
        'tested_variable': experiment.tested_variable,
        'tested_variable_label': experiment.get_tested_variable_display(),
        'decisions_logged': dl.count(),
    })
    return result


def regret_registry(company, *, date_start=None, date_end=None,
                    min_conversions=DEFAULT_MIN_CONVERSIONS):
    """PUB86 — Tuile Reporting : regret réalisé cumulé PAR TYPE DE DÉCISION.

    Le « type de décision » est la variable testée de l'expérience
    (hook/visuel/audience/…). Society-scopé. Renvoie ::

        {'total_regret_mad', 'insufficient_data', 'par_type': [...],
         'experiences': [...]}

    ``par_type`` agrège le regret par ``tested_variable`` ; ``insufficient_data``
    (global et par type) est vrai dès qu'une composante repose sur trop peu de
    données — l'UI affiche alors l'intervalle, jamais un chiffre sec.
    """
    from .models import Experiment

    experiences = []
    by_type = {}
    total_regret = 0.0
    any_insufficient = False
    total_low = 0.0
    total_high = 0.0

    for exp in Experiment.objects.filter(company=company):
        r = experiment_regret(
            exp, date_start=date_start, date_end=date_end,
            min_conversions=min_conversions)
        experiences.append(r)
        regret = r['total_regret_mad'] or 0.0
        total_regret += regret
        if r['insufficient_data'] or r['total_regret_mad'] is None:
            any_insufficient = True
        if r['interval'] is not None:
            total_low += r['interval']['low']
            total_high += r['interval']['high']

        slot = by_type.setdefault(r['tested_variable'], {
            'tested_variable': r['tested_variable'],
            'tested_variable_label': r['tested_variable_label'],
            'regret_mad': 0.0, 'experiments': 0, 'insufficient_data': False,
            'interval_low': 0.0, 'interval_high': 0.0})
        slot['regret_mad'] += regret
        slot['experiments'] += 1
        if r['insufficient_data'] or r['total_regret_mad'] is None:
            slot['insufficient_data'] = True
        if r['interval'] is not None:
            slot['interval_low'] += r['interval']['low']
            slot['interval_high'] += r['interval']['high']

    par_type = []
    for slot in by_type.values():
        par_type.append({
            'tested_variable': slot['tested_variable'],
            'tested_variable_label': slot['tested_variable_label'],
            'regret_mad': round(slot['regret_mad'], 4),
            'experiments': slot['experiments'],
            'insufficient_data': slot['insufficient_data'],
            'interval': {'low': round(slot['interval_low'], 4),
                         'high': round(slot['interval_high'], 4)}})
    par_type.sort(key=lambda s: s['regret_mad'], reverse=True)

    return {
        'total_regret_mad': round(total_regret, 4),
        'interval': {'low': round(total_low, 4), 'high': round(total_high, 4)},
        'insufficient_data': any_insufficient,
        'par_type': par_type,
        'experiences': experiences,
    }
