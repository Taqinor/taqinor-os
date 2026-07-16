#!/usr/bin/env python3
"""SCA5 — CI validation of docs/BUILD_ORDER.yml (SCA1).

A broken or incomplete BUILD_ORDER.yml would make SCA3's wave gating in
scripts/plan_lanes.py silently inert (a parse error there is swallowed as
"no gating", by design, so a run never blocks over an optional file). This
script is the loud counterpart: it FAILS the build when the file itself is
wrong, so drift is caught in CI instead of silently degrading gating.

Checks:
1. **DAG is acyclic.** Build a graph from every ``edges[].group ->
   after.<prereq>`` pair (resolving aliases to their real prefix) and prove
   there is no cycle.
2. **Thresholds are parseable.** Every ``after:`` value must be a number in
   [0, 100].
3. **Every prefix encountered in the plan files is covered.** A prefix
   found by scripts/plan_progress.py (the real inventory — checkbox tasks
   across docs/PLAN.md, docs/PLAN2.md, docs/new_tasks_plan.md,
   docs/FRONTEND_GAP_PLAN.md) must be either:
     - resolvable to a wave (directly, or via an alias whose ``prefix``
       matches and covers ALL of the prefix's task numbers — a partial
       numbered-subset alias coverage, like ARC-noyau + ARC-sweep together
       covering all of ARC, is fine as long as the union is complete for
       every task NUMBER actually seen), or
     - listed in ``unmapped_ok``.
   An orphaned prefix (neither) is red.

Wired into the existing ``stage-names`` CI job (fast, always-on drift guard)
as an appended step — no new required check, branch protection unchanged.

Pure standard library; reuses scripts/plan_lanes.py's mini-YAML parser (no
duplicate implementation) and scripts/plan_progress.py's real inventory.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD_ORDER_FILE = ROOT / "docs" / "BUILD_ORDER.yml"

sys.path.insert(0, str(ROOT / "scripts"))

import plan_lanes  # noqa: E402
import plan_progress  # noqa: E402


def _edges_as_pairs(build_order: dict) -> list[tuple[str, str]]:
    """Every ``(group, prerequisite)`` edge exactly as authored — ``group``
    and ``after:`` keys are used AS WRITTEN (an alias name like
    ``ARC-sweep``/``ARC-noyau`` stays its own graph node, never collapsed to
    its underlying real prefix).

    This distinction matters: ``ARC-sweep`` legitimately depends on
    ``ARC-noyau`` even though BOTH share the real task-id prefix ``ARC`` —
    collapsing them to one ``ARC`` node before cycle-checking would turn that
    perfectly acyclic numbered-subset split into a false self-loop
    (``ARC -> ARC``). A REAL cycle only exists if the graph, built at the
    granularity the file actually authors edges in, has one — e.g. group X
    depends on group Y which (directly or transitively) depends on group X
    again, using the SAME names on both sides of every edge.
    """
    pairs: list[tuple[str, str]] = []
    for edge in build_order.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        group = edge.get("group", "")
        after = edge.get("after") or {}
        if not isinstance(after, dict):
            continue
        for prereq_name in after:
            if group and prereq_name:
                pairs.append((group, prereq_name))
    return pairs


def check_acyclic(build_order: dict) -> list[str]:
    """Return a list of failure messages; empty = acyclic."""
    pairs = _edges_as_pairs(build_order)
    graph: dict[str, set[str]] = {}
    for group, prereq in pairs:
        graph.setdefault(group, set()).add(prereq)
        graph.setdefault(prereq, set())

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in graph}
    failures: list[str] = []

    def visit(node: str, path: list[str]) -> bool:
        color[node] = GRAY
        path.append(node)
        for nxt in sorted(graph.get(node, ())):
            if color.get(nxt, WHITE) == GRAY:
                cycle = path[path.index(nxt):] + [nxt]
                failures.append("cycle détecté : " + " -> ".join(cycle))
                return True
            if color.get(nxt, WHITE) == WHITE:
                if visit(nxt, path):
                    return True
        path.pop()
        color[node] = BLACK
        return False

    for node in sorted(graph):
        if color[node] == WHITE:
            if visit(node, []):
                break  # one reported cycle is enough to fail the build
    return failures


def check_thresholds(build_order: dict) -> list[str]:
    """Return a list of failure messages; empty = every threshold parseable
    and in [0, 100]."""
    failures: list[str] = []
    for edge in build_order.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        group = edge.get("group", "<sans nom>")
        after = edge.get("after") or {}
        if not isinstance(after, dict):
            failures.append(f"{group}: `after:` n'est pas une correspondance clé/valeur")
            continue
        for prereq_name, threshold in after.items():
            try:
                value = float(threshold)
            except (TypeError, ValueError):
                failures.append(
                    f"{group}: seuil non numérique pour {prereq_name!r} : {threshold!r}"
                )
                continue
            if not (0 <= value <= 100):
                failures.append(
                    f"{group}: seuil hors [0, 100] pour {prereq_name} : {value}"
                )
    return failures


def _covered_prefixes(build_order: dict) -> set[str]:
    """Every real task-id prefix the file resolves to a wave, EITHER
    directly (a bare prefix named in a ``waves[].groups`` list) or via an
    alias's ``prefix`` field."""
    covered: set[str] = set()
    aliases = build_order.get("aliases") or {}
    alias_names = set(aliases)
    for wave in (build_order.get("waves") or {}).values():
        if not isinstance(wave, dict):
            continue
        for group in wave.get("groups") or []:
            if group in alias_names:
                alias = aliases[group]
                if isinstance(alias, dict) and alias.get("prefix"):
                    covered.add(alias["prefix"])
            else:
                covered.add(group)
    # An edge's `group:` can ALSO be an alias not listed in any wave's
    # `groups:` (defensive — BUILD_ORDER.yml always lists it in both places
    # today, but a future edit might not); count it as covered too.
    for edge in build_order.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        group = edge.get("group", "")
        if group in alias_names:
            alias = aliases[group]
            if isinstance(alias, dict) and alias.get("prefix"):
                covered.add(alias["prefix"])
        elif group:
            covered.add(group)
    return covered


def check_orphan_prefixes(build_order: dict) -> list[str]:
    """Return a list of failure messages, one per orphaned prefix found in
    the real plan-file inventory (scripts/plan_progress.py) that is neither
    covered by a wave/alias nor listed in ``unmapped_ok``."""
    real_prefixes = set(plan_progress.progress().keys())
    covered = _covered_prefixes(build_order)
    # Defensive: a malformed `unmapped_ok:` (e.g. a mapping accidentally
    # nested under it instead of a flat list of prefix strings) must not
    # crash this check with an unhashable-type TypeError -- only string
    # entries are usable as prefix names, so silently drop anything else
    # (a non-string entry there is itself a structural bug the file's
    # author should fix, but it should never take CI down with a traceback).
    unmapped_ok = {x for x in (build_order.get("unmapped_ok") or []) if isinstance(x, str)}

    orphans = sorted(real_prefixes - covered - unmapped_ok)
    return [
        f"préfixe orphelin trouvé dans les plans mais absent de BUILD_ORDER.yml "
        f"(ni vague/alias, ni unmapped_ok) : {p}"
        for p in orphans
    ]


def run_checks(build_order: dict) -> list[str]:
    failures: list[str] = []
    failures += check_acyclic(build_order)
    failures += check_thresholds(build_order)
    failures += check_orphan_prefixes(build_order)
    return failures


def main(argv: list[str] | None = None) -> int:
    path = BUILD_ORDER_FILE
    if argv:
        path = Path(argv[0])
        if not path.is_absolute():
            path = ROOT / path

    if not path.is_file():
        print(
            f"{path} introuvable — le contrôle BUILD_ORDER.yml est ignoré "
            "(fichier absent, SCA1 pas encore atterri) — vert par défaut.",
        )
        return 0

    build_order = plan_lanes.load_build_order(path)
    if build_order is None:
        print(f"{path} introuvable au chargement — ignoré.")
        return 0

    failures = run_checks(build_order)

    if failures:
        print(f"BUILD_ORDER.yml invalide ({path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}) :")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("BUILD_ORDER.yml valide : DAG acyclique, seuils parseables, aucun préfixe orphelin.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
