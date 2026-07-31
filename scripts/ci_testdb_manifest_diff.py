#!/usr/bin/env python3
"""WOW8 — decide whether a RESTORED (cached) pre-migrated database may be
delta-migrated, or must be dropped and rebuilt CLEAN.

Called by ``.github/actions/backend-env/action.yml``. This file holds the whole
decision so it can be unit-tested (``scripts/tests/test_ci_testdb_manifest_diff.py``);
the action itself only reads the exit code and echoes the verdict.

    python scripts/ci_testdb_manifest_diff.py OLD_MANIFEST CUR_MANIFEST
      exit 0 -> DELTA    the cached dump may be delta-migrated
      exit 1 -> REBUILD  a recorded migration is no longer present unchanged
      exit 2 -> REBUILD  the input is unusable (missing/empty/malformed/duplicated)

A manifest is ``sha256sum`` output over every ``*/migrations/*.py`` file, one
``"<sha256>  <path>"`` line each, written next to the dump that those files
produced.


WHY THE GUARD EXISTS (the correctness crux — do not weaken)
-----------------------------------------------------------
``manage.py migrate`` decides what to run from the recorded migration NAMES in
``django_migrations``, never from schema CONTENT. So if a migration that the
restored dump already records as applied has since been EDITED IN PLACE,
``migrate`` skips it, the schema stays stale, ``migrate`` still exits 0, the
tests run green against the wrong schema, and the poisoned dump is re-cached.
A false green is far more expensive than a slow build. Hence: delta-migrate
ONLY when every migration file recorded in the dump is still present, at the
same path, byte-identical. Anything else -> clean rebuild.


THE RULE (unchanged from the inline ``comm -23`` this replaces)
---------------------------------------------------------------
REBUILD iff some ``"<sha>  <path>"`` line of the OLD manifest is not present in
the CURRENT manifest. Paths are unique within a manifest (``find`` lists each
file once, and a duplicate path is rejected as unusable), so line-set
difference and "path maps to a different hash, or is gone" are the same
predicate — this helper is behaviourally identical to the shell it replaces,
with one deliberate tightening: an EMPTY or MALFORMED old manifest now forces a
rebuild instead of silently green-lighting a delta (``comm -23`` against an
empty file produces no output, i.e. the old shell read a truncated manifest as
"nothing changed" — a latent false-green hole).

What this helper adds is DIAGNOSIS: it names and classifies the files that
forced the rebuild (edited in place / renumbered / deleted), so a future
engineer reads the log and knows in seconds why they paid ~70 minutes.


WHY A RENUMBER (RENAME) IS *NOT* GIVEN A FAST PATH
--------------------------------------------------
Renumbering is routine here (8 parallel lanes collide on migration numbers) and
looks like it should be free: same operations, different filename. It is not,
and the reason is structural rather than a limitation of this script.

Definitions: ``D`` = the restored dump, ``A`` = the migration set recorded
applied in ``D``.

1. **Every cached dump is a CONSISTENT, SINGLE-LEAF tree.** A dump is only ever
   written after ``manage.py migrate`` succeeded, and ``migrate`` (Django 5.1,
   ``core/management/commands/migrate.py`` lines 121/125) calls
   ``loader.check_consistent_history()`` — raises ``InconsistentMigrationHistory``
   if any applied migration has an unapplied dependency — and
   ``loader.detect_conflicts()`` — hard ``CommandError`` on multiple leaf nodes
   in an app. So ``A`` can never contain two competing leaves.

2. **A renumber re-chains behind a migration that is NOT in ``A``.** Migration
   ``m`` is renumbered precisely because a sister lane's migration ``n`` took its
   number; to keep one leaf, ``m``'s ``dependencies`` are rewritten from its old
   parent to ``n`` (verified: every one of the 17 renames in this repo's history
   rewrites ``dependencies``; none is byte-identical). Could ``n`` already be in
   ``A``? No — by (1) ``D`` cannot hold both ``m`` (chained on the old parent)
   and ``n`` (chained on the same old parent): that is exactly the two-leaf state
   ``migrate`` refuses, so it could never have been dumped. For a renamed BLOCK
   (a shift such as 0055->0056->0057->0058) the tail links land inside ``A``, but
   the HEAD of the block always points at the colliding new migration, outside
   ``A``.

3. **Therefore a delta over a renumber is a dependency INVERSION**: the renamed
   migration's DDL physically ran BEFORE the migration it now declares itself to
   depend on. Its operations cannot be re-ordered after the fact, and a clean
   build would run them the other way round. Same operation set, different order,
   which can genuinely diverge (two ``AlterField`` on one column end at different
   values; any ``RunPython`` data migration is order-sensitive by construction).
   That divergence is exactly the stale schema this guard exists to prevent.

4. Renaming the ``django_migrations`` row and letting ``migrate`` sort it out
   does NOT rescue it either: Django's own ``check_consistent_history`` (1) sees
   the renamed migration applied before its unapplied dependency and aborts, so
   the run falls through to the clean rebuild anyway — the same ~70 minutes, plus
   a wasted restore.

Consequence: a rename fast path would be dead code in the file that gates every
merge. The only rename that IS provably safe — byte-identical content, i.e.
``dependencies`` unchanged — has occurred 0 times in this repo's history (it
would require renumbering an app's leaf migration into a gap without re-chaining
it, which resolves no collision), so it is not special-cased either; it is
reported in the log and rebuilt like everything else.

THE REAL LEVER is upstream of this file: a renumber only becomes visible here
when the PRE-rename file was itself in the restored dump. Renumber the migration
being folded IN (never one already pushed green), or stop advancing the cache
from mid-wave branch pushes, and the renumber shows up as a pure ADDITION —
which already takes the fast delta path today.


FAIL-SAFE POLICY
----------------
Ambiguous, malformed, unreadable, empty or duplicated input is never resolved by
guessing: it exits non-zero and the caller rebuilds clean.
"""
from __future__ import annotations

import re
import sys

EXIT_DELTA = 0
EXIT_REBUILD = 1
EXIT_UNUSABLE = 2

# GNU sha256sum emits "<64 hex>  <path>" in text mode (the ubuntu-latest runner's
# default) and "<64 hex> *<path>" in binary mode (what a Git-for-Windows shell
# produces). Both are accepted — the hash and the path are exact either way, and
# refusing one of them would silently degrade EVERY run to a ~70-min rebuild.
# Unambiguous: for a text-mode line whose path itself starts with '*', the second
# literal space is consumed by the marker class and the path keeps its '*'.
# A path holding a backslash or a newline is emitted by sha256sum with a leading
# '\' and escapes; such a line does not match and is rejected as unusable (fail
# safe) rather than parsed heuristically.
SHA_LINE = re.compile(r"^([0-9a-f]{64}) [ *](\S.*?)[ \t]*$")
# A real Django migration file: 4-digit number + descriptive stem. Anything else
# in a migrations/ directory (__init__.py, helpers) is never claimed as a rename.
NUMBERED = re.compile(r"^([0-9]{4})_(.+)$")


def parse_manifest(text):
    """Return ``(mapping, error)``; ``mapping`` is ``{path: sha256}``.

    ``error`` is a string on ANY doubt (blank input, malformed line, duplicate
    path) and the caller must then rebuild clean.
    """
    mapping = {}
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip("\r\n")
        if not line.strip():
            continue
        match = SHA_LINE.match(line)
        if match is None:
            return None, "manifest line {0} is not '<sha256>  <path>': {1!r}".format(lineno, line[:120])
        digest, path = match.group(1), match.group(2)
        if "\\" in path:
            return None, "manifest line {0} has an escaped path this guard will not interpret: {1!r}".format(
                lineno, line[:120]
            )
        while path.startswith("./"):
            path = path[2:]
        if not path:
            return None, "manifest line {0} has an empty path".format(lineno)
        if path in mapping:
            return None, "manifest lists {0} twice — cannot tell which hash is current".format(path)
        mapping[path] = digest
    if not mapping:
        return None, "manifest is empty — it records nothing about the dump, so the dump cannot be trusted"
    return mapping, None


def _dirname(path):
    return path.rsplit("/", 1)[0] if "/" in path else ""


def _basename(path):
    return path.rsplit("/", 1)[-1]


def _stem(path):
    """``0090_protect_produit.py`` -> ``protect_produit``; ``None`` if unnumbered."""
    name = _basename(path)
    if not name.endswith(".py"):
        return None
    match = NUMBERED.match(name[:-3])
    return match.group(2) if match else None


def classify(old, cur):
    """Return ``(offenders, added)``.

    ``offenders`` is the list of ``(kind, old_path, [candidates])`` for every old
    path that is not present unchanged in ``cur`` — the exact set whose emptiness
    decides DELTA vs REBUILD. The kind is DIAGNOSTIC ONLY: it never changes the
    verdict, it only tells the reader what happened.
    """
    added = sorted(set(cur) - set(old))
    # Content index over paths that are NEW in the current tree, so a rename can
    # be recognised by its content hash landing at a different path.
    new_by_hash = {}
    for path in added:
        new_by_hash.setdefault(cur[path], []).append(path)
    # Same-app + same-descriptive-stem index, which is what a RENUMBER looks like
    # once its `dependencies` were rewritten (so the content hash no longer matches).
    new_by_stem = {}
    for path in added:
        stem = _stem(path)
        if stem is not None:
            new_by_stem.setdefault((_dirname(path), stem), []).append(path)

    offenders = []
    for path in sorted(old):
        if cur.get(path) == old[path]:
            continue
        if path in cur:
            offenders.append(("EDITED-IN-PLACE", path, []))
            continue
        stem = _stem(path)
        if stem is not None:
            same_content = new_by_hash.get(old[path], [])
            if same_content:
                offenders.append(("RENAMED", path, list(same_content)))
                continue
            same_stem = new_by_stem.get((_dirname(path), stem), [])
            if same_stem:
                offenders.append(("RENUMBERED+EDITED", path, list(same_stem)))
                continue
        offenders.append(("DELETED", path, []))
    return offenders, added


_KIND_NOTE = {
    "EDITED-IN-PLACE": (
        "its content changed at the same path; the dump records it applied, so a delta would SKIP it -> stale schema"
    ),
    "RENAMED": (
        "byte-identical content moved to a new filename; safe in principle, but see the module docstring — it has "
        "never occurred here and is not special-cased"
    ),
    "RENUMBERED+EDITED": (
        "renumbered AND its content changed (a renumber rewrites `dependencies` to chain behind the colliding "
        "migration, which is NOT in this dump) -> applying it now would be a dependency inversion, so: rebuild"
    ),
    "DELETED": "gone from the tree, and its content is nowhere else; the dump records schema this tree no longer defines",
}


def report(old, cur, offenders, added, out):
    write = out.write
    write("=== testdb cache: can the restored dump be delta-migrated? ===\n")
    write("cached dump manifest: {0} migration files\n".format(len(old)))
    write("current tree:         {0} migration files\n".format(len(cur)))
    if not offenders:
        write(
            "VERDICT: DELTA — every migration recorded in the cached dump is still present, byte-identical, at the "
            "same path. {0} new migration file(s) will be applied on top.\n".format(len(added))
        )
        for path in added[:20]:
            write("  new: {0}\n".format(path))
        if len(added) > 20:
            write("  ... and {0} more\n".format(len(added) - 20))
        return
    write(
        "VERDICT: REBUILD — {0} migration file(s) recorded in the cached dump are no longer present byte-identical "
        "at their original path. `migrate` picks its work from the recorded NAMES in django_migrations, never from "
        "content, so a delta on this dump would silently skip them: stale schema, exit 0, FALSE GREEN.\n".format(
            len(offenders)
        )
    )
    for kind, path, candidates in offenders:
        write("  {0:<18} {1}\n".format(kind, path))
        for candidate in candidates:
            write("  {0:<18}   -> {1}\n".format("", candidate))
        write("  {0:<18}   {1}\n".format("", _KIND_NOTE[kind]))
    write(
        "This costs a full ~850-migration replay (~70 min). It is the CORRECT price: see the module docstring of "
        "scripts/ci_testdb_manifest_diff.py for why a renumber cannot take the fast path, and for the two upstream "
        "changes that make renumbers free (renumber the migration being folded in, not one already pushed green; "
        "and/or stop advancing the cache from mid-wave branch pushes).\n"
    )


def main(argv):
    out = sys.stdout
    if len(argv) != 2:
        out.write("usage: ci_testdb_manifest_diff.py OLD_MANIFEST CUR_MANIFEST\n")
        return EXIT_UNUSABLE
    old_path, cur_path = argv
    manifests = {}
    for label, path in (("cached-dump", old_path), ("current-tree", cur_path)):
        try:
            with open(path, "r", encoding="utf-8", errors="strict") as handle:
                text = handle.read()
        except OSError as exc:
            out.write("VERDICT: REBUILD — cannot read the {0} manifest {1}: {2}\n".format(label, path, exc))
            return EXIT_UNUSABLE
        except UnicodeDecodeError as exc:
            out.write("VERDICT: REBUILD — the {0} manifest {1} is not valid UTF-8: {2}\n".format(label, path, exc))
            return EXIT_UNUSABLE
        mapping, error = parse_manifest(text)
        if error is not None:
            out.write("VERDICT: REBUILD — unusable {0} manifest ({1}): {2}\n".format(label, path, error))
            return EXIT_UNUSABLE
        manifests[label] = mapping
    old, cur = manifests["cached-dump"], manifests["current-tree"]
    offenders, added = classify(old, cur)
    report(old, cur, offenders, added, out)
    return EXIT_REBUILD if offenders else EXIT_DELTA


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
