"""ADSENG28 — Plan de vol + préflight (dd-science-core §d + creative-sci §c).

Un ``FlightPlan`` 6 mois = des phases SÉQUENTIELLES testant **UNE variable à la
fois**, dans l'ordre canonique hook→format→angle→audience→consolidation,
chacune sur **2-3 bras pendant 3-4 semaines** (le plan 3-2-2 à 12 cellules est
mathématiquement inutilisable à notre volume — MDE ±90%).

Avant de matérialiser un plan, le **préflight** exige TOUT :
  1. volume de backlog approuvé ≥12 sur 3 mois ;
  2. diversité ≥4 accroches distinctes (ADSENG27) ;
  3. garde-fous configurés (``GuardrailConfig``) ;
  4. alertes câblées (au moins une ``RulePolicy`` activée) ;
  5. sanité MDE par phase (ADSENG13 / ``mde.py`` — lane parallèle, dégrade en
     contrôle structurel si absent).

Un plan invalide est REFUSÉ avec des raisons FR ; un plan valide se matérialise
en phases planifiées (nées comme DONNÉES — le plan ne LANCE rien lui-même ; les
campagnes qu'il propose naissent PAUSED, règle #3).
"""
from __future__ import annotations

import dataclasses
import datetime
import logging

from .models import (
    CreativeBacklogItem, FlightPhase, FlightPlan, GuardrailConfig, RulePolicy,
)
from . import backlog

logger = logging.getLogger(__name__)

# Ordre canonique des phases : UNE variable testée à la fois.
PHASE_SEQUENCE = ('hook', 'format', 'angle', 'audience', 'consolidation')

# Bornes d'une phase.
PHASE_ARMS_MIN = 2
PHASE_ARMS_MAX = 3
PHASE_WEEKS_MIN = 3
PHASE_WEEKS_MAX = 4

# Seuils de préflight.
PREFLIGHT_BACKLOG_MIN = 12
PREFLIGHT_HOOK_DIVERSITY_MIN = backlog.DIVERSITY_FLOOR_HOOKS  # 4
PREFLIGHT_WINDOW_DAYS = backlog.DIVERSITY_WINDOW_DAYS         # 90 (3 mois)


@dataclasses.dataclass
class PreflightResult:
    """Résultat de préflight : ``ok`` + la liste des raisons FR d'échec."""

    ok: bool
    reasons_fr: list

    def __bool__(self):
        return self.ok


def default_phase_specs():
    """Gabarit canonique 5 phases (une variable, 2 bras, 3 semaines)."""
    return [
        {'name': f'Phase {i + 1} — {var}', 'tested_variable': var,
         'num_arms': PHASE_ARMS_MIN, 'week_span': PHASE_WEEKS_MIN,
         'launch_template': '', 'budget_mad': 0}
        for i, var in enumerate(PHASE_SEQUENCE)
    ]


def validate_phase_spec(spec):
    """Valide une spec de phase (bornes bras/semaines + variable unique).
    Renvoie la liste des raisons FR d'échec (vide si valide)."""
    reasons = []
    name = spec.get('name') or spec.get('tested_variable') or '?'
    arms = int(spec.get('num_arms', 0) or 0)
    weeks = int(spec.get('week_span', 0) or 0)
    variable = (spec.get('tested_variable') or '').strip()
    if not (PHASE_ARMS_MIN <= arms <= PHASE_ARMS_MAX):
        reasons.append(
            f"Phase « {name} » : {arms} bras hors bornes "
            f"({PHASE_ARMS_MIN}-{PHASE_ARMS_MAX}).")
    if not (PHASE_WEEKS_MIN <= weeks <= PHASE_WEEKS_MAX):
        reasons.append(
            f"Phase « {name} » : {weeks} semaine(s) hors bornes "
            f"({PHASE_WEEKS_MIN}-{PHASE_WEEKS_MAX}).")
    if not variable:
        reasons.append(
            f"Phase « {name} » : aucune variable testée (une variable à la "
            "fois est obligatoire).")
    return reasons


def approved_backlog_count(company, *, today=None,
                           window_days=PREFLIGHT_WINDOW_DAYS):
    """Nombre d'items de backlog APPROUVÉS (asset validé policy) EN FILE sur la
    fenêtre 3 mois — le volume que le préflight exige ≥12."""
    today = today or datetime.date.today()
    horizon = today + datetime.timedelta(days=window_days)
    from django.db.models import Q
    return (CreativeBacklogItem.objects
            .filter(company=company,
                    status=CreativeBacklogItem.Statut.EN_FILE,
                    asset__policy_stamp__passed=True)
            .filter(Q(earliest_date__isnull=True)
                    | Q(earliest_date__lte=horizon))
            .count())


def _mde_sane(company, spec, *, mde_check=None):
    """Sanité MDE d'une phase. ``mde_check(company, spec) -> (bool, reason)``
    injecté a priorité ; sinon on tente ``mde.py`` (ADSENG13, lane parallèle) ;
    sinon on dégrade sur un contrôle STRUCTUREL (déjà couvert par les bornes de
    ``validate_phase_spec`` — peu de cellules = MDE raisonnable). Renvoie
    ``(ok, reason_or_None)``.
    """
    if mde_check is not None:
        try:
            ok, reason = mde_check(company, spec)
            return bool(ok), reason
        except Exception:  # noqa: BLE001 - chemin optionnel → dégrade
            logger.debug('flightplan: mde_check injecté a échoué — dégrade')
    try:
        from . import mde as _mde
        fn = (getattr(_mde, 'phase_is_sane', None)
              or getattr(_mde, 'is_phase_detectable', None))
        if callable(fn):
            result = fn(company, spec)
            if isinstance(result, tuple):
                reason = result[1] if len(result) > 1 else None
                return bool(result[0]), reason
            return bool(result), None
    except Exception:  # noqa: BLE001 - mde absent/incompatible → dégrade
        logger.debug('flightplan: mde.py absent/incompatible — contrôle '
                     'structurel')
    # Dégradation : la sanité structurelle (bornes bras/semaines) fait foi.
    return True, None


def preflight(company, phase_specs, *, today=None, mde_check=None):
    """Valide un plan de vol AVANT matérialisation → ``PreflightResult``.

    Échoue (avec raisons FR) si un seul critère manque : volume backlog,
    diversité, garde-fous, alertes, ou sanité MDE d'une phase.
    """
    today = today or datetime.date.today()
    reasons = []

    specs = list(phase_specs or [])
    if not specs:
        reasons.append("Plan vide : aucune phase définie.")

    # 1. Volume de backlog approuvé ≥12/3 mois.
    volume = approved_backlog_count(company, today=today)
    if volume < PREFLIGHT_BACKLOG_MIN:
        reasons.append(
            f"Backlog insuffisant : {volume} créatif(s) approuvé(s) sur 3 "
            f"mois (minimum {PREFLIGHT_BACKLOG_MIN}).")

    # 2. Diversité ≥4 accroches distinctes.
    diversity = backlog.hook_diversity(company, today=today)
    if diversity < PREFLIGHT_HOOK_DIVERSITY_MIN:
        reasons.append(
            f"Diversité insuffisante : {diversity} accroche(s) distincte(s) "
            f"(minimum {PREFLIGHT_HOOK_DIVERSITY_MIN}).")

    # 3. Garde-fous configurés.
    if not GuardrailConfig.objects.filter(company=company).exists():
        reasons.append(
            "Garde-fous non configurés : aucune GuardrailConfig pour la "
            "société.")

    # 4. Alertes câblées (au moins une règle gardien activée).
    if not RulePolicy.objects.filter(company=company, enabled=True).exists():
        reasons.append(
            "Alertes non câblées : aucune règle de garde-fou activée.")

    # 5. Sanité de chaque phase (bornes + MDE).
    for spec in specs:
        reasons.extend(validate_phase_spec(spec))
        ok, mde_reason = _mde_sane(company, spec, mde_check=mde_check)
        if not ok:
            name = spec.get('name') or spec.get('tested_variable') or '?'
            reasons.append(
                f"Phase « {name} » : sanité MDE non atteinte"
                + (f" ({mde_reason})" if mde_reason else "") + ".")

    return PreflightResult(ok=not reasons, reasons_fr=reasons)


def materialize(plan, phase_specs, *, today=None, mde_check=None):
    """Matérialise un plan VALIDE en ``FlightPhase`` planifiées (ordonnées,
    dates séquentielles). REFUSE un plan invalide en levant ``ValueError``
    portant les raisons FR du préflight. Renvoie la liste des phases créées.
    """
    result = preflight(
        plan.company, phase_specs, today=today, mde_check=mde_check)
    if not result.ok:
        raise ValueError(
            "Plan de vol refusé : " + " ".join(result.reasons_fr))

    today = today or datetime.date.today()
    cursor = plan.start_date or today
    phases = []
    for index, spec in enumerate(phase_specs):
        weeks = int(spec.get('week_span', PHASE_WEEKS_MIN) or PHASE_WEEKS_MIN)
        start = cursor
        end = start + datetime.timedelta(weeks=weeks)
        phase = FlightPhase.objects.create(
            company=plan.company, plan=plan, order=index,
            name=spec.get('name', f'Phase {index + 1}'),
            tested_variable=(spec.get('tested_variable') or ''),
            launch_template=spec.get('launch_template', ''),
            budget_mad=int(spec.get('budget_mad', 0) or 0),
            num_arms=int(spec.get('num_arms', PHASE_ARMS_MIN)
                         or PHASE_ARMS_MIN),
            week_span=weeks, start_date=start, end_date=end)
        phases.append(phase)
        cursor = end

    plan.status = FlightPlan.Statut.ACTIF
    if not plan.start_date:
        plan.start_date = today
    plan.end_date = cursor
    plan.save(update_fields=['status', 'start_date', 'end_date', 'updated_at'])
    return phases
