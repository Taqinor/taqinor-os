"""CI guard: no app may have both `<app>/tests.py` and `<app>/tests/` (ERR-QAH-CRM-TESTS-MASQUES).

WHY. In Python, a package always wins over a module of the same name on
``sys.path`` — ``apps/crm/tests/`` silently shadowed ``apps/crm/tests.py`` for
every import of ``apps.crm.tests`` (CALX106, 21/09/2026): the 61 tests in the
module never ran again, in CI or locally, with the build staying green the
whole time. `scripts/ci_shard.py` discovers *files* on disk (it does not
import them), so its label list looked complete while the runtime import
masked one of the two labels — the exact silent-gate failure this guard is
built to make loud instead.

This walks every Django app under ``backend/django_core/apps/`` (plus the
top-level dirs `ci_shard.TOP_LEVEL` covers) and fails if any owns BOTH a
``tests.py`` module and a ``tests/`` package at the same directory level.
The fix is always to flatten the package into sibling ``tests_*.py`` files
(the crm app's own convention) and delete the package — never to rename or
delete ``tests.py``.
"""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DJANGO_ROOT = os.path.join(REPO_ROOT, "backend", "django_core")

sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
import ci_shard  # noqa: E402


def find_shadowed_apps(django_root: str = DJANGO_ROOT) -> list[str]:
    """Return sorted dotted-app names that own both `tests.py` and `tests/`."""
    offenders = []
    roots = []
    apps_dir = os.path.join(django_root, "apps")
    if os.path.isdir(apps_dir):
        for name in sorted(os.listdir(apps_dir)):
            pkg = os.path.join(apps_dir, name)
            if os.path.isdir(pkg) and os.path.exists(
                os.path.join(pkg, "__init__.py")
            ):
                roots.append(("apps.%s" % name, pkg))
    for top in ci_shard.TOP_LEVEL:
        top_dir = os.path.join(django_root, top)
        if os.path.isdir(top_dir):
            roots.append((top, top_dir))

    for dotted, base in roots:
        module = os.path.join(base, "tests.py")
        package = os.path.join(base, "tests")
        if os.path.isfile(module) and os.path.isdir(package):
            offenders.append(dotted)
    return sorted(offenders)


def main() -> int:
    offenders = find_shadowed_apps()
    if not offenders:
        print("OK: aucune app ne porte a la fois tests.py et tests/.")
        return 0
    print("ECHEC: tests.py masque par un paquet tests/ du meme nom "
          "(le paquet gagne a l'import, le module devient injoignable) :")
    for dotted in offenders:
        print("  - %s (tests.py masque par %s/tests/)" % (dotted, dotted))
    print(
        "\nCorrectif : aplatir chaque fichier de tests/ en "
        "<app>/tests_<nom>.py (convention crm) et supprimer le paquet "
        "tests/ — jamais renommer ou supprimer tests.py."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
