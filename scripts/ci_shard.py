#!/usr/bin/env python3
"""WOW6 — deterministic backend-test sharding for CI.

Usage: ``python scripts/ci_shard.py <shard_index> <shard_total>``

Prints the space-separated Django test labels assigned to ``<shard_index>``
(0-based) when the discoverable test apps are split round-robin across
``<shard_total>`` shards. The split is stable (sorted label list, ``i % total``)
so a given app always lands on the same shard.

NOTE: every shard still builds the FULL test database from all apps' migrations
(Django migrates the whole schema regardless of the test labels) — only the test
EXECUTION is split across shards. The wins come from running each quarter of the
suite on its own free public-repo runner in parallel.
"""
import glob
import os
import sys


def _has_tests(pkg):
    """True if the package carries tests Django would discover.

    Django's default discovery walks a label's package for files matching
    ``test*.py`` at ANY depth — which matches ``tests.py``, files like
    ``tests_role_change.py`` (authentication), and nested packages like
    ``apps/ged/tests/test_ged.py``. Using the exact recursive pattern guarantees
    the shard split covers precisely what an unsharded ``test apps`` run covers —
    no app's tests can be silently dropped.
    """
    return bool(glob.glob(os.path.join(pkg, '**', 'test*.py'), recursive=True))


def discover_labels(repo_root):
    """Sorted Django test labels for every app package that carries tests."""
    dj = os.path.join(repo_root, 'backend', 'django_core')
    labels = []
    apps_dir = os.path.join(dj, 'apps')
    for name in sorted(os.listdir(apps_dir)):
        pkg = os.path.join(apps_dir, name)
        if not os.path.isdir(pkg):
            continue
        if not os.path.exists(os.path.join(pkg, '__init__.py')):
            continue
        if _has_tests(pkg):
            labels.append('apps.' + name)
    # Foundation apps live at the django_core root and carry tests too.
    for top in ('authentication', 'core'):
        top_dir = os.path.join(dj, top)
        if os.path.isdir(top_dir) and _has_tests(top_dir):
            labels.append(top)
    return sorted(labels)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: ci_shard.py <shard_index> <shard_total>\n')
        return 2
    index, total = int(argv[1]), int(argv[2])
    if not (0 <= index < total) or total < 1:
        sys.stderr.write('shard_index must be in [0, shard_total)\n')
        return 2
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    labels = discover_labels(repo_root)
    mine = [lab for i, lab in enumerate(labels) if i % total == index]
    sys.stdout.write(' '.join(mine))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
