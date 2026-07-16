"""ADSENG20 — Moteur de PACING mensuel (dd-treasury §a).

Couche de FONCTIONS PURES au-dessus des ``InsightSnapshot`` déjà collectés
(ENG5) + la ``GuardrailConfig`` (enveloppe mensuelle). Aucune écriture de
modèle, aucune table nouvelle : l'état est DÉRIVÉ à chaque lecture
(dd-treasury §A4). Ce module ne touche JAMAIS Meta et ne change jamais un
statut.

INVARIANT « plafond jamais dépassé » (dd-treasury §A1) : calibré sur le flex
quotidien Meta RÉEL — **1,25×** (source primaire directe :
developers.facebook.com/docs/marketing-api/bidding/overview/budgets/ —
« up to 25% more than your daily budget may be spent », exemple 10→12,50).
PAS 2× : le « 2× » folklorique confond le flex par défaut avec la feature
opt-in « Ad Set Budget Sharing » (hors périmètre à 2-4 ad sets). Le
multiplicateur est une CONSTANTE de sécurité codée en dur — jamais un réglage
par société (même raisonnement que la règle PAUSED-only).

G4 (garde-fou anti-compounding) — la variation hebdomadaire d'un budget se
mesure contre une VRAIE LIGNE DE BASE À 7 JOURS glissante
(``weekly_baseline_budget_mad``), jamais contre la transition de la veille :
N petits pas quotidiens successifs (chacun dans la bande) ne peuvent alors
JAMAIS composer au-delà de la limite hebdomadaire sur une fenêtre de 7 jours.
Sans ancre à 7 jours (budget jamais changé il y a > 7 j via le moteur), on
retombe HONNÊTEMENT sur le plafond par-transition — documenté comme le repli.
"""
from __future__ import annotations

import calendar
import dataclasses
import datetime

# ── Constantes de sécurité (dd-treasury §a) ──────────────────────────────
# Flex quotidien Meta par défaut (source primaire — voir docstring module).
META_DAILY_FLEX_MULTIPLIER = 1.25
# Démarrage à froid : saisonnalité jour-de-semaine seulement après 4 semaines.
COLD_START_DAYS = 28
# Fenêtre glissante des moyennes par jour-de-semaine.
SEASONALITY_TRAILING_WEEKS = 8
# Fenêtre du run-rate (« si le rythme du jour continue »).
RUN_RATE_TRAILING_DAYS = 7
# Fenêtre de la ligne de base hebdomadaire (G4).
WEEKLY_BASELINE_DAYS = 7

# ── États de pacing (5 valeurs, dd-treasury §A3) — chaînes ALIGNÉES sur
# ``PacingState.State`` (motif ``rules.SEVERITY_*`` : littéraux partagés,
# jamais un import croisé models ↔ pacing). ──
STATE_ON_TRACK = 'on_track'
STATE_UNDER_PACING = 'under_pacing'
STATE_OVER_PACING = 'over_pacing'
STATE_BREACH_IMMINENT = 'breach_imminent'
STATE_PAUSED_FOR_MONTH = 'paused_for_month'
PACING_STATES = frozenset({
    STATE_ON_TRACK, STATE_UNDER_PACING, STATE_OVER_PACING,
    STATE_BREACH_IMMINENT, STATE_PAUSED_FOR_MONTH,
})

# ── Kinds trésorerie ``EngineAction`` (chaînes canoniques — dd-treasury
# §A4/§B4). Définis ICI (module socle sans dépendance de modèle) pour une
# SOURCE UNIQUE : ``services`` (ADSENG22) et ``budget_applier`` (ADSENG21)
# les IMPORTENT — jamais un littéral dupliqué. Ce ne sont PAS des valeurs du
# modèle ``EngineAction.Kind`` (aucun changement de modèle/migration) :
# ``kind`` est un CharField et ``propose_action`` stocke la chaîne brute.
KIND_PAUSE_FOR_MONTH = 'pause_for_month'
KIND_INCREASE_PACE = 'increase_pace'
KIND_REBALANCE_ADSET_BUDGET = 'rebalance_adset_budget'
KIND_ENABLE_CBO = 'enable_cbo'
# Kinds qui MODIFIENT un budget ad set (base de la ligne hebdo G4).
BUDGET_CHANGE_KINDS = frozenset({
    KIND_INCREASE_PACE, KIND_REBALANCE_ADSET_BUDGET,
})


@dataclasses.dataclass
class PacingResult:
    """Résultat de pacing DÉRIVÉ (jamais persisté par ce module).

    Les champs correspondent 1:1 à ``PacingState`` pour un upsert trivial par
    l'appelant (la tâche quotidienne ENG6), mais ce module n'écrit rien."""

    period_start: datetime.date
    days_in_month: int
    days_elapsed: int
    days_remaining: int
    monthly_ceiling: float | None
    spend_to_date: float
    expected_spend_to_date: float
    forecast_spend: float
    pacing_ratio: float
    state: str


# ── Primitives calendaires ────────────────────────────────────────────────
def days_in_month(year, month):
    return calendar.monthrange(year, month)[1]


def month_period_start(any_date):
    return any_date.replace(day=1)


def resolve_monthly_ceiling(config, period_start):
    """Enveloppe mensuelle effective (MAD). Si ``monthly_budget_ceiling_mad``
    est absent, dérivée du plafond quotidien × jours du mois (dd-treasury §A4)
    — aucun compte n'est jamais « non plafonné » par omission. ``config``
    None → None (l'appelant traite alors le pacing comme non évaluable)."""
    if config is None:
        return None
    explicit = getattr(config, 'monthly_budget_ceiling_mad', None)
    if explicit:
        return float(explicit)
    daily = getattr(config, 'daily_budget_ceiling_mad', None)
    if not daily:
        return None
    return float(daily) * days_in_month(period_start.year, period_start.month)


# ── Courbes cibles (linéaire + saisonnalité jour-de-semaine, §A2) ─────────
def naive_expected_spend(monthly_ceiling, days_elapsed, dim):
    """Courbe cible LINÉAIRE (repli, toujours calculable)."""
    if not monthly_ceiling or dim <= 0:
        return 0.0
    frac = max(0, min(days_elapsed, dim)) / dim
    return float(monthly_ceiling) * frac


def weekday_shares(daily_spend):
    """Parts par jour-de-semaine (0=lundi … 6=dimanche), normalisées à 1,0.

    ``daily_spend`` : dict ``date -> spend``. Démarrage à froid (< 28 jours
    d'historique) → parts uniformes 1/7 (plancher honnête, dd-treasury §A2).
    Sinon : moyenne de dépense par jour-de-semaine / somme des 7 moyennes."""
    uniform = {d: 1.0 / 7.0 for d in range(7)}
    if len(daily_spend) < COLD_START_DAYS:
        return uniform
    sums = {d: 0.0 for d in range(7)}
    counts = {d: 0 for d in range(7)}
    for day, spend in daily_spend.items():
        wd = day.weekday()
        sums[wd] += float(spend or 0)
        counts[wd] += 1
    means = {d: (sums[d] / counts[d]) if counts[d] else 0.0 for d in range(7)}
    total = sum(means.values())
    if total <= 0:
        return uniform
    return {d: means[d] / total for d in range(7)}


def seasonality_expected_spend(monthly_ceiling, period_start, days_elapsed,
                               shares):
    """Dépense attendue à date, pondérée par la saisonnalité jour-de-semaine.

    NOTE de correction : le dossier écrit « ceiling × Σ(weekday_share pour
    chaque jour écoulé) », mais ``weekday_share`` somme à 1,0 sur UNE
    semaine — l'appliquer tel quel sur ~30 jours dépasserait le plafond
    (~4,3×). On normalise donc sur les jours du MOIS : chaque jour porte le
    poids de son jour-de-semaine, la somme des poids du mois = dénominateur —
    la courbe atterrit EXACTEMENT au plafond en fin de mois (invariant)."""
    if not monthly_ceiling:
        return 0.0
    dim = days_in_month(period_start.year, period_start.month)
    month_days = [
        period_start + datetime.timedelta(days=i) for i in range(dim)]
    weights = [shares.get(d.weekday(), 0.0) for d in month_days]
    total = sum(weights)
    if total <= 0:
        return 0.0
    elapsed = max(0, min(days_elapsed, dim))
    elapsed_weight = sum(weights[:elapsed])
    return float(monthly_ceiling) * elapsed_weight / total


# ── Ratio + prévision run-rate (dd-treasury §A2) ──────────────────────────
def pacing_ratio(actual_spend, expected_spend):
    """``actual / expected`` — ``expected`` plancher à 1 MAD (jour 1, ÷0)."""
    denom = max(float(expected_spend or 0), 1.0)
    return float(actual_spend or 0) / denom


def trailing_run_rate(daily_spend, as_of, days=RUN_RATE_TRAILING_DAYS):
    """Moyenne de dépense sur les ``days`` derniers jours (glissante)."""
    if days <= 0:
        return 0.0
    window = [as_of - datetime.timedelta(days=i) for i in range(days)]
    vals = [float(daily_spend.get(d, 0) or 0) for d in window]
    return sum(vals) / days


def forecast_spend(spend_to_date, run_rate, days_remaining):
    """Prévision fin-de-mois « si le rythme du jour continue » (distincte de
    la courbe cible : « on va dépasser si rien ne change ? »)."""
    return float(spend_to_date or 0) + float(run_rate) * max(0, days_remaining)


def would_breach_at_max_flex(spend_to_date, daily_ceiling, monthly_ceiling,
                             flex=META_DAILY_FLEX_MULTIPLIER):
    """Vrai si un SEUL jour au flex maximum (1,25×) pousserait le compte
    au-delà de l'enveloppe mensuelle — le cœur de l'invariant « plafond
    jamais dépassé » (dd-treasury §A1/§A3). Détecte AVANT le franchissement,
    avec le 1,25× confirmé (jamais un 2× deviné)."""
    if not monthly_ceiling or daily_ceiling is None:
        return False
    try:
        worst_tomorrow = float(daily_ceiling) * float(flex)
    except (TypeError, ValueError):
        return False
    return (float(spend_to_date or 0) + worst_tomorrow) > float(
        monthly_ceiling)


def classify_state(*, ratio, forecast, spend_to_date, daily_ceiling,
                   monthly_ceiling, band_pct, already_paused=False):
    """Table d'états à 5 valeurs (dd-treasury §A3). ``breach_imminent`` prime
    sur ``over_pacing`` (l'invariant passe avant la simple dérive)."""
    if already_paused:
        return STATE_PAUSED_FOR_MONTH
    breach = False
    if monthly_ceiling:
        if float(forecast) > float(monthly_ceiling):
            breach = True
        elif would_breach_at_max_flex(spend_to_date, daily_ceiling,
                                      monthly_ceiling):
            breach = True
    if breach:
        return STATE_BREACH_IMMINENT
    band = float(band_pct) / 100.0
    if ratio < (1.0 - band):
        return STATE_UNDER_PACING
    if ratio > (1.0 + band):
        return STATE_OVER_PACING
    return STATE_ON_TRACK


def recommended_action_for_state(state):
    """Kind d'``EngineAction`` recommandé pour un état (dd-treasury §A3), ou
    None (aucune action : ``on_track`` / ``over_pacing`` = ligne de brief
    seule ; ``paused_for_month`` = plus rien avant le 1er du mois suivant).
    PUR — ne propose rien lui-même (c'est la boucle propose→approuve)."""
    if state == STATE_UNDER_PACING:
        return KIND_INCREASE_PACE
    if state == STATE_BREACH_IMMINENT:
        return KIND_PAUSE_FOR_MONTH
    return None


# ── Assemblage ────────────────────────────────────────────────────────────
def compute_pacing(*, period_start, as_of, daily_spend, monthly_ceiling,
                   daily_ceiling, band_pct, already_paused=False):
    """Calcule l'état de pacing d'un mois à partir d'une série
    ``date -> spend``.

    ``daily_spend`` couvre idéalement les 8 semaines glissantes (saisonnalité)
    ET le mois courant ; ``spend_to_date`` n'agrège QUE
    ``period_start..as_of``. Fonction PURE (aucun accès DB) — testable
    exactement."""
    dim = days_in_month(period_start.year, period_start.month)
    days_elapsed = min(max((as_of - period_start).days + 1, 0), dim)
    days_remaining = dim - days_elapsed
    spend_to_date = sum(
        float(v or 0) for d, v in daily_spend.items()
        if period_start <= d <= as_of)

    shares = weekday_shares(daily_spend)
    expected = seasonality_expected_spend(
        monthly_ceiling, period_start, days_elapsed, shares)
    if expected <= 0 and monthly_ceiling:
        expected = naive_expected_spend(monthly_ceiling, days_elapsed, dim)

    run_rate = trailing_run_rate(daily_spend, as_of)
    forecast = forecast_spend(spend_to_date, run_rate, days_remaining)
    ratio = pacing_ratio(spend_to_date, expected)
    state = classify_state(
        ratio=ratio, forecast=forecast, spend_to_date=spend_to_date,
        daily_ceiling=daily_ceiling, monthly_ceiling=monthly_ceiling,
        band_pct=band_pct, already_paused=already_paused)

    return PacingResult(
        period_start=period_start, days_in_month=dim,
        days_elapsed=days_elapsed, days_remaining=days_remaining,
        monthly_ceiling=(float(monthly_ceiling)
                         if monthly_ceiling is not None else None),
        spend_to_date=round(spend_to_date, 2),
        expected_spend_to_date=round(expected, 2),
        forecast_spend=round(forecast, 2),
        pacing_ratio=round(ratio, 4), state=state)


# ── Ligne de base hebdomadaire (G4 — anti-compounding) ────────────────────
def weekly_baseline_budget_mad(company, adset_meta_id, *, as_of=None,
                               lookback_days=WEEKLY_BASELINE_DAYS):
    """G4 — Budget quotidien (MAD) de l'ad set tel qu'il était il y a
    ``lookback_days`` jours : la VRAIE LIGNE DE BASE contre laquelle la
    variation hebdomadaire est mesurée (jamais la transition de la veille).
    C'est l'ancre qui empêche N petits pas quotidiens de composer au-delà de
    la limite hebdo sur une fenêtre glissante de 7 jours.

    = le nouveau budget de la plus RÉCENTE action de changement de budget
    APPLIQUÉE sur cet ad set dont ``applied_at`` <= (as_of − lookback).
    Aucune ancre (budget jamais changé il y a > 7 j via le moteur) → None :
    l'appelant retombe alors sur le plafond par-transition, HONNÊTEMENT
    documenté comme le repli (pas d'ancre = pas de garde hebdo à ce stade)."""
    if not adset_meta_id:
        return None
    as_of = as_of or datetime.date.today()
    cutoff = as_of - datetime.timedelta(days=lookback_days)
    from .models import EngineAction
    action = (EngineAction.objects
              .filter(company=company, kind__in=BUDGET_CHANGE_KINDS,
                      status=EngineAction.Statut.APPLIQUEE,
                      applied_at__date__lte=cutoff,
                      payload__adset_id=str(adset_meta_id))
              .order_by('-applied_at')
              .first())
    if action is None:
        return None
    payload = action.payload or {}
    explicit = payload.get('new_daily_budget_mad')
    if explicit is not None:
        try:
            return float(explicit)
        except (TypeError, ValueError):
            return None
    daily = payload.get('daily_budget')  # centimes
    if daily is None:
        return None
    try:
        return float(daily) / 100.0
    except (TypeError, ValueError):
        return None


def weekly_change_within_baseline(proposed_mad, baseline_mad, max_pct):
    """Vrai si le budget proposé reste dans ±``max_pct`` de la ligne de base à
    7 jours. ``baseline`` None/≤0 → Vrai (aucune ancre : le plafond par-
    transition gouverne — repli G4 documenté). Budgets illisibles → Vrai
    (les autres garde-fous budget tranchent)."""
    if baseline_mad is None:
        return True
    try:
        base = float(baseline_mad)
        prop = float(proposed_mad)
    except (TypeError, ValueError):
        return True
    if base <= 0:
        return True
    change_pct = abs(prop - base) / base * 100.0
    return change_pct <= float(max_pct)


# ── Conveniences adossées à la base (lecture seule) ───────────────────────
def is_paused_for_month(company, period_start):
    """Vrai si une action ``pause_for_month`` a été APPLIQUÉE ce mois-ci."""
    from .models import EngineAction
    dim = days_in_month(period_start.year, period_start.month)
    period_end = period_start + datetime.timedelta(days=dim - 1)
    return (EngineAction.objects
            .filter(company=company, kind=KIND_PAUSE_FOR_MONTH,
                    status=EngineAction.Statut.APPLIQUEE,
                    applied_at__date__gte=period_start,
                    applied_at__date__lte=period_end)
            .exists())


def load_daily_spend(company, start_date, as_of):
    """Somme de dépense par JOUR, au niveau CAMPAGNE uniquement (évite le
    double-comptage : un spend d'ad/adset est déjà agrégé au niveau
    campagne). Renvoie un dict ``date -> float`` sur ``start_date..as_of``."""
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Sum

    from .models import AdCampaignMirror, InsightSnapshot
    ct = ContentType.objects.get_for_model(AdCampaignMirror)
    rows = (InsightSnapshot.objects
            .filter(company=company, content_type=ct,
                    date__gte=start_date, date__lte=as_of)
            .values('date').annotate(total=Sum('spend')))
    return {r['date']: float(r['total'] or 0) for r in rows}


def compute_pacing_for_company(company, *, as_of=None, config=None):
    """Assemble le pacing d'une société pour le mois de ``as_of`` (lecture DB).

    Charge la dépense quotidienne sur (début du mois − 8 semaines) → ``as_of``
    pour la saisonnalité, dérive l'état, et NE PERSISTE RIEN (dd-treasury
    §A4)."""
    as_of = as_of or datetime.date.today()
    period_start = month_period_start(as_of)
    if config is None:
        from .models import GuardrailConfig
        config = GuardrailConfig.objects.filter(company=company).first()
    monthly = resolve_monthly_ceiling(config, period_start)
    daily_ceiling = getattr(config, 'daily_budget_ceiling_mad', None)
    band = getattr(config, 'pacing_band_pct', 15)
    history_start = period_start - datetime.timedelta(
        days=SEASONALITY_TRAILING_WEEKS * 7)
    daily_spend = load_daily_spend(company, history_start, as_of)
    already = is_paused_for_month(company, period_start)
    return compute_pacing(
        period_start=period_start, as_of=as_of, daily_spend=daily_spend,
        monthly_ceiling=monthly, daily_ceiling=daily_ceiling,
        band_pct=band, already_paused=already)
