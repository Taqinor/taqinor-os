#!/usr/bin/env python3
"""WOW-CI4 — duration-balanced lane lists for the frontend Vitest suite.

Usage
-----
    python scripts/ci_frontend_shard.py <lane_index> <lane_total>   # lane's files
    python scripts/ci_frontend_shard.py --plan <lane_total>         # balance table
    python scripts/ci_frontend_shard.py --update-timings <log>...    # refresh table

WHY (run 32206663106). The Vitest layer was sharded with Vitest's own
``--shard=i/n``. That splits the FILE LIST, not the WORK: it hands each lane an
equal COUNT of files. Measured consequence on that run — three lanes that should
have been identical came in at **6 min 23 s / 4 min 49 s / 3 min 47 s**, a 2 min 36 s
spread, because a jsdom test file's cost ranges over two orders of magnitude
(a pure-render assertion versus a full page with axe). Counting files is exactly
the blind split that `scripts/ci_shard.py` already replaced on the backend side.

So the frontend gets the same treatment: measured per-file durations
(``scripts/ci_vitest_timings.json``), LPT placement (imported from ci_shard — one
implementation of the heuristic, not two), and explicit per-lane file lists handed
to Vitest through ``VITEST_INCLUDE`` (read by ``frontend/vitest.config.js``).
``VITEST_INCLUDE`` rather than CLI arguments on purpose: Vitest treats positional
arguments as substring FILTERS, so a path that happens to be a prefix of another
would silently pull in extra files, and ~260 arguments per lane is a fragile
command line. An explicit ``include`` list is exact.

COMPLETENESS IS A TEST. ``scripts/tests/test_ci_frontend_shard.py`` asserts the
union of the lanes equals the full glob, with no duplicates, for several lane
totals — a file that fell out of the split would stop being tested while every
required check stayed green.

Refreshing the table: take a green run and, for each vitest lane job,

    gh api repos/Taqinor/taqinor-os/actions/jobs/<job-id>/logs > /tmp/vitest-<n>.log
    python scripts/ci_frontend_shard.py --update-timings /tmp/vitest-*.log

Like the backend table, the planning weight is the MAX of the last two measured
runs (one raw run is kept beside it), so a single noisy sample cannot
under-weight a lane twice in a row.
"""
from __future__ import annotations

import argparse
import functools
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ci_shard import assign  # noqa: E402  (shared LPT — never reimplemented here)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(REPO_ROOT, "frontend")
VITEST_CONFIG = os.path.join(FRONTEND, "vitest.config.js")
TIMINGS_PATH = os.path.join(REPO_ROOT, "scripts", "ci_vitest_timings.json")
RAW_TIMINGS_PATH = os.path.join(REPO_ROOT, "scripts", "ci_vitest_timings_raw.json")

# Must stay identical to `test.include` in frontend/vitest.config.js. The guard
# test asserts the pattern still appears there, so the two cannot drift apart.
INCLUDE_SUFFIX = ".test.jsx"
INCLUDE_ROOT = "src"
INCLUDE_PATTERN = "src/**/*.test.jsx"

SKIP_DIRS = {"node_modules", "__pycache__", ".git", "dist", "build", "coverage"}

# Fallback for a file with no measurement: rough cost proxy from how many cases
# it declares. Calibrated on the 19/08 run (~13 min over ~790 files).
SECONDS_PER_CASE = 0.9
MIN_FILE_SECONDS = 0.3

_CASE_RE = re.compile(r"^\s*(?:it|test)\s*(?:\.\w+)?\s*\(", re.MULTILINE)
# Vitest default reporter, one line per file. Duration is ms or s, and the line
# may carry extra segments (skipped counts, a leading tick/cross).
_VITEST_FILE_RE = re.compile(
    r"(src/[\w./-]*?\.test\.jsx)\s*\((?:\d+)\s+tests?[^)]*\)\s*(?:\d+\s*tests?\s*)?"
    r"(?:\|[^0-9]*\d+\s*\w+\s*)?(\d+(?:\.\d+)?)\s*(ms|s)\b"
)
_TS_PREFIX = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z\s?")


@functools.lru_cache(maxsize=None)
def _discover_cached(frontend: str) -> tuple:
    root = os.path.join(frontend, INCLUDE_ROOT)
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name.endswith(INCLUDE_SUFFIX):
                rel = os.path.relpath(os.path.join(dirpath, name), frontend)
                found.append(rel.replace(os.sep, "/"))
    return tuple(sorted(found))


def discover_files(frontend: str = FRONTEND) -> list[str]:
    """Every Vitest test file, path relative to `frontend/`."""
    return list(_discover_cached(frontend))


def load_timings(path: str = TIMINGS_PATH) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {k: float(v) for k, v in data.items() if isinstance(v, (int, float))}


@functools.lru_cache(maxsize=None)
def _case_count(rel: str, frontend: str) -> int:
    try:
        with open(os.path.join(frontend, rel), encoding="utf-8", errors="replace") as fh:
            return max(1, len(_CASE_RE.findall(fh.read())))
    except OSError:
        return 1


def weigh(files, timings, frontend: str = FRONTEND) -> dict:
    """Measured seconds where known (used as-is), else a per-case estimate."""
    weights = {}
    for rel in files:
        measured = timings.get(rel)
        if measured:
            weights[rel] = float(measured)
        else:
            weights[rel] = max(MIN_FILE_SECONDS,
                               _case_count(rel, frontend) * SECONDS_PER_CASE)
    return weights


def plan(total: int, frontend: str = FRONTEND):
    files = discover_files(frontend)
    weights = weigh(files, load_timings(), frontend)
    return files, weights, assign(files, total, weights)


def parse_log_durations(lines) -> dict:
    """Per-file seconds from Vitest's default reporter output."""
    out: dict = defaultdict(float)
    for raw in lines:
        line = _TS_PREFIX.sub("", raw.rstrip("\n"))
        for path, value, unit in _VITEST_FILE_RE.findall(line):
            secs = float(value) / 1000.0 if unit == "ms" else float(value)
            out[path] = max(out[path], secs)
    return dict(out)


def update_timings(log_paths, out_path: str = TIMINGS_PATH,
                   raw_path: str = RAW_TIMINGS_PATH) -> int:
    measured: dict = defaultdict(float)
    for path in log_paths:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                for rel, secs in parse_log_durations(fh).items():
                    measured[rel] = max(measured[rel], secs)
        except OSError as exc:
            sys.stderr.write(f"ci_frontend_shard: log illisible {path} ({exc})\n")
            return 2
    if not measured:
        sys.stderr.write(
            "ci_frontend_shard: aucune duree par fichier reconnue. Le rapporteur "
            "Vitest par defaut imprime `src/x/Y.test.jsx (N tests) 123ms` — "
            "verifiez que les journaux viennent bien des lanes vitest.\n"
        )
        return 2

    previous = load_timings(raw_path)
    weights = {k: max(measured.get(k, 0.0), previous.get(k, 0.0))
               for k in set(measured) | set(previous)}
    if previous:
        drifted = [k for k in set(measured) & set(previous)
                   if previous[k] >= 1.0
                   and abs(measured[k] - previous[k]) / previous[k] > 0.20]
        print(f"ci_frontend_shard: {len(drifted)} fichier(s) au-dela de 20 % "
              "d'ecart entre les deux runs (poids = max des deux).")

    for path, table in ((raw_path, measured), (out_path, weights)):
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({k: max(0.01, round(v, 2)) for k, v in sorted(table.items())},
                      fh, indent=1, sort_keys=True)
            fh.write("\n")
    print(f"ci_frontend_shard: {len(weights)} fichier(s) -> {out_path}")
    return 0


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", nargs="?", type=int)
    parser.add_argument("total", nargs="?", type=int)
    parser.add_argument("--plan", type=int, metavar="TOTAL")
    parser.add_argument("--update-timings", nargs="+", metavar="LOG")
    args = parser.parse_args(argv[1:])

    if args.update_timings:
        return update_timings(args.update_timings)

    if args.plan:
        files, weights, lanes = plan(args.plan)
        total_w = sum(weights.values())
        print(f"{len(files)} fichiers, cout total estime {total_w / 60:.1f} min")
        loads = []
        for i, lane in enumerate(lanes):
            load = sum(weights[f] for f in lane)
            loads.append(load)
            print(f"  lane {i}: {len(lane):4d} fichiers  {load / 60:5.2f} min")
        ideal = total_w / len(lanes)
        print(f"  pire lane {max(loads) / 60:.2f} min / ideal {ideal / 60:.2f} min "
              f"(desequilibre {max(loads) / ideal:.2f}x)")
        return 0

    if args.index is None or args.total is None:
        parser.print_usage(sys.stderr)
        return 2
    if not (0 <= args.index < args.total):
        sys.stderr.write("lane_index must be in [0, lane_total)\n")
        return 2
    _files, _w, lanes = plan(args.total)
    # Comma-separated: consumed by `test.include` in frontend/vitest.config.js.
    sys.stdout.write(",".join(lanes[args.index]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
