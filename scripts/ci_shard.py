#!/usr/bin/env python3
"""WOW6 / WOW-CI2 — deterministic, DURATION-BALANCED backend-test sharding for CI.

Usage
-----
    python scripts/ci_shard.py <shard_index> <shard_total>   # labels for one shard
    python scripts/ci_shard.py --plan <shard_total>          # human balance table
    python scripts/ci_shard.py --update-timings <log>...     # refresh the timing table

WHY THIS WAS REWRITTEN (18/08/2026, run 32182877239)
----------------------------------------------------
The first version split at APP granularity, round-robin over the sorted app list
(``i % total``). Sorting by name has nothing to do with cost, so the split was
blind: on the 6-way run, ``ci_shard.py 2 6`` handed ONE lane both heavyweights —
``apps.crm`` AND ``apps.ventes`` — plus eleven small apps. That lane was still
running (>9 min of tests) while its siblings had finished in 1 min 44 s to
5 min 48 s. Since wall-clock = setup + the WORST lane, the whole backend gate was
priced by that one accident of alphabetical order.

App granularity could not fix it either: ``apps.ventes`` alone carries ~240 test
modules and is heavier than several entire sibling shards, so no assignment of
whole apps can balance it. Two changes fix that for good:

1. **The unit is a test MODULE, not an app.** Django accepts dotted module labels
   (``apps.ventes.tests.test_pdf``), so a heavy app is spread across lanes
   instead of pinning one. Discovery uses Django's own default pattern
   (``test*.py``, any depth) so the union of the lanes is exactly what an
   unsharded ``test apps authentication core`` would have run — including the
   files that are NOT inside a ``tests/`` package (``apps/ventes/tests_qj9_*.py``)
   and those named ``tests_*.py`` rather than ``test_*.py``.
2. **Placement is LPT (longest-processing-time-first) over MEASURED durations**,
   not round-robin. Units are sorted heaviest-first and each is placed on the
   lane that is currently lightest — the classic greedy makespan heuristic, which
   is provably within 4/3 of optimal and, with units this small, lands much
   closer.

COMPLETENESS IS A TEST, NOT A PROMISE. ``scripts/tests/test_ci_shard.py`` asserts
that the union of every lane equals the full discovered unit set, with no
duplicates and nothing dropped, for several shard totals. A module that silently
fell out of the split would mean tests that no longer run while CI stays green —
the worst possible failure for a gate. That test runs in the ``stage-names`` job.

THE TIMING TABLE — ``scripts/ci_shard_timings.json``
----------------------------------------------------
``{"<dotted label>": <seconds>}``. It is an OPTIMISATION INPUT ONLY: it can never
change WHICH tests run, only which lane they land on. A stale or missing entry
costs balance, never correctness — so it is refreshed manually, on demand, and
never blocks a build.

To refresh it after the suite has grown noticeably, take a green CI run and:

    # one log per backend-tests shard (the ids come from `gh run view <run>`)
    for j in <job-id>...; do \
      gh api repos/Taqinor/taqinor-os/actions/jobs/$j/logs > /tmp/shard-$j.log; done
    python scripts/ci_shard.py --update-timings /tmp/shard-*.log

The parser reads the ``-v 2`` runner output, whose every line carries the runner's
ISO timestamp, and attributes the elapsed wall time between consecutive test lines
to the module that owns the earlier one. Unmeasured modules fall back to a
static weight (their test-method count), which is a decent proxy until measured.
"""
from __future__ import annotations

import argparse
import functools
import json
import os
import re
import sys
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DJANGO_ROOT = os.path.join(REPO_ROOT, "backend", "django_core")
TIMINGS_PATH = os.path.join(REPO_ROOT, "scripts", "ci_shard_timings.json")
# The most recent RAW run, kept beside the planning table so a refresh can take
# max(latest, previous) WITHOUT the value ratcheting upward forever: each refresh
# compares against exactly one prior run, never an accumulated maximum.
RAW_TIMINGS_PATH = os.path.join(REPO_ROOT, "scripts", "ci_shard_timings_raw.json")

# Roots Django is asked to test: every package under apps/, plus the two
# foundation packages that live at the django_core root.
TOP_LEVEL = ("authentication", "core")
# Directories that never carry runnable tests.
SKIP_DIRS = {"__pycache__", "migrations", "node_modules", ".git"}

# Fallback weight for a module absent from the timing table: seconds per test
# method, floored so a module is never weightless. Calibrated on the 18/08 run
# (~27 min of tests over ~2 700 modules).
SECONDS_PER_TEST = 0.55
MIN_UNIT_SECONDS = 0.4

_TEST_DEF_RE = re.compile(r"^\s+(?:async\s+)?def\s+test", re.MULTILINE)
# A Django -v 2 result line: "name (dotted.path.Class.name) ... ok"
_RESULT_RE = re.compile(r"^\S*\s*\(([\w.]+)\)\s*\.\.\.")
_TS_RE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d+Z)\s?(.*)$")


def _dotted(path: str) -> str:
    """`backend/django_core/apps/x/tests/test_y.py` -> `apps.x.tests.test_y`."""
    rel = os.path.relpath(path, DJANGO_ROOT).replace(os.sep, "/")
    return rel[:-3].replace("/", ".")


def _walk_tests(base: str):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            # Django's default discovery pattern is `test*.py` — that matches
            # `test_x.py`, `tests.py` AND `tests_x.py`. Keep it identical here,
            # or the shards would run a different set than an unsharded run.
            if name.startswith("test") and name.endswith(".py"):
                yield os.path.join(dirpath, name)


@functools.lru_cache(maxsize=None)
def _discover_cached(repo_root: str) -> tuple:
    return tuple(_discover(repo_root))


def discover_units(repo_root: str = REPO_ROOT) -> list[str]:
    """Sorted dotted labels of every discoverable test MODULE (memoised)."""
    return list(_discover_cached(repo_root))


def _discover(repo_root: str) -> list[str]:
    django_root = os.path.join(repo_root, "backend", "django_core")
    global DJANGO_ROOT
    previous, DJANGO_ROOT = DJANGO_ROOT, django_root
    try:
        units: list[str] = []
        apps_dir = os.path.join(django_root, "apps")
        if os.path.isdir(apps_dir):
            for name in sorted(os.listdir(apps_dir)):
                pkg = os.path.join(apps_dir, name)
                if not os.path.isdir(pkg):
                    continue
                if not os.path.exists(os.path.join(pkg, "__init__.py")):
                    continue
                units += [_dotted(p) for p in _walk_tests(pkg)]
        for top in TOP_LEVEL:
            top_dir = os.path.join(django_root, top)
            if os.path.isdir(top_dir):
                units += [_dotted(p) for p in _walk_tests(top_dir)]
        return sorted(set(units))
    finally:
        DJANGO_ROOT = previous


def load_timings(path: str = TIMINGS_PATH) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {k: float(v) for k, v in data.items() if isinstance(v, (int, float))}


@functools.lru_cache(maxsize=None)
def _static_test_count(unit: str, repo_root: str) -> int:
    """How many test methods the module declares (cheap regex, no import)."""
    path = os.path.join(repo_root, "backend", "django_core", *unit.split(".")) + ".py"
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return max(1, len(_TEST_DEF_RE.findall(fh.read())))
    except OSError:
        return 1


def app_of(unit: str) -> str:
    """`apps.ventes.tests.test_pdf` -> `apps.ventes`; `core.tests.x` -> `core`."""
    parts = unit.split(".")
    return ".".join(parts[:2]) if parts[0] == "apps" and len(parts) > 1 else parts[0]


def weigh(units, timings, repo_root: str = REPO_ROOT) -> dict:
    """Cost per unit, best available source first.

    1. a MEASURED per-module entry (what ``--update-timings`` writes);
    2. else the app's MEASURED total, shared out across its modules in
       proportion to how many test methods each declares — this is what the
       committed table holds today, because the 18/08 run reported per-app
       totals. It captures both effects that matter: how heavy the app is
       (``apps.ventes`` runs at 0.18 s/test, ``apps.ao`` at 0.024 s/test — a 7x
       spread that a flat per-test constant would get badly wrong) and how big
       the module is inside that app;
    3. else a flat per-test-method fallback, for an app nobody has measured yet.

    Weights only decide PLACEMENT. A wrong weight costs balance, never
    correctness: the union of the lanes is asserted complete by
    scripts/tests/test_ci_shard.py whatever the numbers say.
    """
    counts = {u: _static_test_count(u, repo_root) for u in units}
    per_app_counts: dict = defaultdict(int)
    for unit in units:
        per_app_counts[app_of(unit)] += counts[unit]

    weights = {}
    for unit in units:
        measured = timings.get(unit)
        if measured:
            # A MEASURED value is used as-is, with NO floor. The floor exists to
            # stop a static ESTIMATE from reading as weightless; applying it to a
            # measurement would destroy the balance it is meant to protect. Most
            # of the 2 680 modules really do run in hundredths of a second, and
            # flooring them all to the same 0.4 s would make LPT balance module
            # COUNT instead of module TIME — which is the blind split this whole
            # mechanism replaced. (Measured 2026-08-19: the floor inflated an
            # estimated total of 1 457 s to 2 232 s, i.e. 775 s of pure phantom.)
            weights[unit] = float(measured)
            continue
        app = app_of(unit)
        app_total = timings.get(app)
        n_app = per_app_counts.get(app, 0)
        if app_total and n_app:
            share = counts[unit] / n_app
            weights[unit] = max(MIN_UNIT_SECONDS, float(app_total) * share)
        else:
            # UN MODULE NON MESURE COUTE LA MEDIANE, pas une extrapolation par
            # nombre de tests (mesure du 19/08/2026). Ce palier tourne avec
            # `--exclude-tag=pdf --exclude-tag=slow` : 347 des 2 733 modules ne
            # s'executent donc JAMAIS ici et n'ont, par construction, aucune
            # mesure. Les facturer `nb_tests x 0,55 s` gonflait le total estime a
            # 58 min contre 23 min reellement mesurees — LPT equilibrait des
            # fantomes, et le desequilibre affiche a 1,00x etait un mirage. La
            # mediane des modules REELLEMENT mesures est l'estimation neutre :
            # elle ne peut ni dominer une lane ni disparaitre.
            weights[unit] = _fallback_seconds(timings, counts[unit])
    return weights


@functools.lru_cache(maxsize=None)
def _median_measured(frozen_items) -> float:
    values = sorted(v for _k, v in frozen_items if v > 0)
    if not values:
        return 0.0
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2


def _fallback_seconds(timings: dict, n_cases: int) -> float:
    median = _median_measured(tuple(sorted(timings.items()))) if timings else 0.0
    if median > 0:
        return max(MIN_UNIT_SECONDS, median)
    return max(MIN_UNIT_SECONDS, n_cases * SECONDS_PER_TEST)


def assign(units, total: int, weights) -> list[list[str]]:
    """LPT greedy: heaviest unit first onto the currently lightest lane.

    Deterministic: units are ordered by (-weight, label) so equal weights break
    by name, and ties between lanes always resolve to the lowest lane index.
    """
    if total < 1:
        raise ValueError("shard_total must be >= 1")
    lanes: list[list[str]] = [[] for _ in range(total)]
    loads = [0.0] * total
    for unit in sorted(units, key=lambda u: (-weights[u], u)):
        i = min(range(total), key=lambda k: (loads[k], k))
        lanes[i].append(unit)
        loads[i] += weights[unit]
    return [sorted(lane) for lane in lanes]


def plan(total: int, repo_root: str = REPO_ROOT):
    units = discover_units(repo_root)
    weights = weigh(units, load_timings(), repo_root)
    lanes = assign(units, total, weights)
    return units, weights, lanes


# --------------------------------------------------------------------------
# --update-timings: rebuild the table from CI job logs
# --------------------------------------------------------------------------
def parse_log_durations(lines) -> dict:
    """Attribute elapsed wall time between -v 2 result lines to their module."""
    from datetime import datetime

    durations: dict = defaultdict(float)
    prev_module = None
    prev_time = None
    for raw in lines:
        m = _TS_RE.match(raw.rstrip("\n"))
        if not m:
            continue
        stamp, body = m.group(1), m.group(2)
        hit = _RESULT_RE.match(body)
        if not hit:
            continue
        dotted = hit.group(1)
        # "apps.ventes.tests.test_pdf.ClassName.test_method" -> drop the last two
        module = ".".join(dotted.split(".")[:-2]) or dotted
        now = datetime.strptime(stamp[:26] + "Z", "%Y-%m-%dT%H:%M:%S.%fZ")
        if prev_module is not None and prev_time is not None:
            delta = (now - prev_time).total_seconds()
            if 0 <= delta < 600:  # ignore clock jumps / inter-shard gaps
                durations[prev_module] += delta
        prev_module, prev_time = module, now
    return dict(durations)


def update_timings(log_paths, out_path: str = TIMINGS_PATH,
                   raw_path: str = RAW_TIMINGS_PATH) -> int:
    merged: dict = defaultdict(float)
    for path in log_paths:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                for mod, secs in parse_log_durations(fh).items():
                    merged[mod] = max(merged[mod], secs)
        except OSError as exc:
            sys.stderr.write(f"ci_shard: log illisible {path} ({exc})\n")
            return 2
    if not merged:
        sys.stderr.write(
            "ci_shard: aucune durée reconnue dans ces journaux — la suite "
            "tourne-t-elle bien en -v 2 ?\n"
        )
        return 2

    # GARDE DE VARIANCE (round 4). Une seule mesure est BRUITEE : entre deux runs,
    # l'etat du cache de base de test, le bruit du runner et le voisinage dans le
    # meme processus font bouger le cout d'un module. Le round 3 a equilibre sur un
    # seul echantillon et la pire lane est repartie a 1,24x la moyenne. Le poids de
    # planification est donc le MAX des DEUX derniers runs — pessimiste, donc une
    # lane ne peut pas etre sous-estimee deux fois de suite. Borne : on ne garde
    # qu'UN run brut precedent, donc le max ne monte pas indefiniment.
    # Depart du tableau de planification EXISTANT, pas d'une page blanche : une
    # lane qui n'a pas demarre (plafond de creneaux) ou un module simplement non
    # joue ce jour-la n'a AUCUNE mesure dans ces journaux. Repartir de zero
    # supprimerait son poids et le renverrait a l'estimation statique — c'est
    # arrive le 19/08 avec les modules du shard 5, jamais demarre. On conserve
    # donc l'ancien poids pour tout ce que ce run n'a pas mesure.
    previous_raw = load_timings(raw_path)
    weights = dict(load_timings(out_path))
    for key in set(merged) | set(previous_raw):
        weights[key] = max(merged.get(key, 0.0), previous_raw.get(key, 0.0),
                           weights.get(key, 0.0) if key not in merged else 0.0)
    previous = previous_raw

    if previous:
        drifted = [
            (k, previous[k], merged[k])
            for k in set(merged) & set(previous)
            if previous[k] >= 1.0 and abs(merged[k] - previous[k]) / previous[k] > 0.20
        ]
        drifted.sort(key=lambda r: -abs(r[2] - r[1]))
        print(f"ci_shard: {len(drifted)} module(s) au-dela de 20 % d'ecart entre "
              f"les deux runs (poids = max des deux) ; 10 plus gros ecarts :")
        for key, before, after in drifted[:10]:
            print(f"    {key}: {before:.2f}s -> {after:.2f}s")

    with open(raw_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({k: max(0.01, round(v, 2)) for k, v in sorted(merged.items())},
                  fh, indent=1, sort_keys=True)
        fh.write("\n")
    merged = weights
    # Floor AFTER rounding, not before: a module measured at 0.004 s rounds to
    # 0.0, and a 0.0 entry is FALSY — `weigh()` would silently ignore the
    # measurement and fall back to the static estimate, which for a
    # sub-millisecond module over-weighs it by two orders of magnitude. The
    # well-formedness test in scripts/tests/test_ci_shard.py pins this.
    table = {k: max(0.01, round(v, 2)) for k, v in sorted(merged.items()) if v > 0}
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(table, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"ci_shard: {len(table)} module(s) chronometre(s) -> {out_path}")
    return 0


def main(argv):
    parser = argparse.ArgumentParser(add_help=True, description=__doc__)
    parser.add_argument("index", nargs="?", type=int)
    parser.add_argument("total", nargs="?", type=int)
    parser.add_argument("--plan", type=int, metavar="TOTAL",
                        help="print the balance table for TOTAL lanes")
    parser.add_argument("--update-timings", nargs="+", metavar="LOG",
                        help="rebuild scripts/ci_shard_timings.json from CI logs")
    args = parser.parse_args(argv[1:])

    if args.update_timings:
        return update_timings(args.update_timings)

    if args.plan:
        units, weights, lanes = plan(args.plan)
        total_w = sum(weights.values())
        print(f"{len(units)} modules, cout total estime {total_w / 60:.1f} min")
        for i, lane in enumerate(lanes):
            load = sum(weights[u] for u in lane)
            print(f"  lane {i}: {len(lane):4d} modules  {load / 60:5.2f} min")
        loads = [sum(weights[u] for u in lane) for lane in lanes]
        print(f"  pire lane {max(loads) / 60:.2f} min / ideal "
              f"{total_w / len(lanes) / 60:.2f} min "
              f"(desequilibre {max(loads) / (total_w / len(lanes)):.2f}x)")
        return 0

    if args.index is None or args.total is None:
        parser.print_usage(sys.stderr)
        return 2
    if not (0 <= args.index < args.total):
        sys.stderr.write("shard_index must be in [0, shard_total)\n")
        return 2
    _units, _weights, lanes = plan(args.total)
    sys.stdout.write(" ".join(lanes[args.index]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
