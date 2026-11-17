"""Throw-away implementation of design-s2-moteur.md section 3 (pace) as WRITTEN, plus
optional rule variants (Rules flags) used for the before/after comparisons.
Synthetic data only."""
import math, statistics, datetime as dt
from dataclasses import dataclass

DEFAULT_NB = 5
DEFAULT_MIN = 240
HORIZON = 28
N_WIN = 9
MIN_HIST = 5


@dataclass
class Rules:
    # --- variants (False/None = design as written) ---
    weekend_floor: bool = False      # non-working day enters window only if nb >= median of working days
    target_floor: int = 0            # minimum displayed target (0 = as written)
    max_drop: int = 0                # 0 = no limit on day-to-day fall (as written)
    small_cap: float = 0.0           # share of target that tasks <=10 min may fill (0 = no cap)
    imp_min_est: int = 0             # important task counts for the pairing only if estimate >= this (0 = any)
    tenir_rebase_on_alert: bool = False
    pousser_median_plus1: bool = False  # cible = max(ceil(P60), median+1) (still guarded)
    small_ratio: bool = False        # small (<=10 min) done tasks count at most (big tasks + 1)
    floor_frac28: float = 0.0        # target >= round(frac * median of non-missing days of last 28 d)
    rise_cap: int = 1                # max rise per day (as written = 1)
    tenir_min_days: int = 5          # non-missing days needed before R is frozen (as written = 5)
    tenir_mean10: bool = False       # R and drift from mean of last N days instead of median of 9 / 5
    rise_every: int = 0              # POUSSER may rise by +1 at most once every N calendar days (0 = off)
    n_win: int = 9                   # POUSSER window size (as written = 9)
    tenir_win: int = 10              # N for the mean variant
    tenir_real: bool = False         # keep R as a float (band centred on the unrounded mean)


def percentile_lineaire(vals, p):
    s = sorted(vals)
    n = len(s)
    if n == 0:
        return None
    pos = p * (n - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    return s[lo] + (pos - lo) * (s[hi] - s[lo])


def round_half_up(x):
    return int(math.floor(x + 0.5))


@dataclass
class Stat:
    date: dt.date
    nb: int = 0
    nb_imp: int = 0
    nb_small: int = 0        # done tasks with estimate <= 10 min
    minutes: float = 0.0
    plan: bool = False
    touched: bool = False
    off: bool = False
    working: bool = True
    imp_open: int = 0


def est_jour_manquant(st, est_ouvre, off_declare):
    """Section 3 'Missing day' as written."""
    if off_declare:
        return True
    if st is None:
        return True
    if st.nb == 0 and not st.plan and not st.touched:
        return True
    if (not est_ouvre) and st.nb == 0:
        return True
    return False


def effective_count(st, target, rules):
    """Count used for the pace / success. Variant small_cap: tasks <=10 min fill at most
    small_cap*target of the count."""
    if rules.small_ratio:
        big = st.nb - st.nb_small
        return big + min(st.nb_small, big + 1)
    if rules.small_cap and target:
        cap = math.ceil(rules.small_cap * target)
        return st.nb - max(0, st.nb_small - cap)
    return st.nb


def fenetre_non_manquante(stats, today, rules, n=None, horizon=HORIZON):
    n = n or rules.n_win
    """Returns (counts9 chronological, nonmissing_in_horizon, list of Stat)."""
    nm = []
    for k in range(1, horizon + 1):
        d = today - dt.timedelta(days=k)
        st = stats.get(d)
        ouvre = st.working if st else (d.weekday() < 5)
        off = st.off if st else False
        if not est_jour_manquant(st, ouvre, off):
            nm.append(st)
    nm.reverse()  # chronological
    if rules.weekend_floor:
        wk = [s.nb for s in nm if s.working]
        med = statistics.median(wk) if wk else 0
        nm = [s for s in nm if s.working or s.nb >= med]
    return nm[-n:], len(nm), nm


def cible_pousser(c9, cible_hier, rules, c28=None):
    if not c9:
        return None
    t = math.ceil(percentile_lineaire(c9, 0.6))
    if rules.pousser_median_plus1:
        t = max(t, round_half_up(statistics.median(c9)) + 1)
    t = min(t, max(c9))
    if cible_hier is not None:
        t = min(t, cible_hier + rules.rise_cap)
        if rules.max_drop:
            t = max(t, cible_hier - rules.max_drop)
    t = max(t, rules.target_floor)
    if rules.floor_frac28 and c28:
        t = max(t, round_half_up(rules.floor_frac28 * statistics.median(c28)))
    return t


def reference_tenir(c9):
    return round_half_up(statistics.median(c9))


def bande_tenir(R):
    b = max(1, round(0.2 * R))   # python round = banker's; see ambiguity note
    return R - b, R + b


def derive_tenir(R, c5):
    lo, hi = bande_tenir(R)
    m = statistics.median(c5)
    return 'sous' if m < lo else ('au-dessus' if m > hi else 'dans')


def jour_atteint(nb, cible, nb_imp_faites, nb_imp_ouvertes):
    return nb >= cible and (nb_imp_faites >= 1 or nb_imp_ouvertes == 0)
