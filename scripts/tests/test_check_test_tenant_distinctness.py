"""Tests for scripts/check_test_tenant_distinctness.py.

Pure stdlib (unittest), no Django/DB needed. Run with:
    python -m unittest scripts.tests.test_check_test_tenant_distinctness -v

Each fixture below is a miniature test module; the guard must decide whether
its "second tenant" is a real second row.
"""
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_test_tenant_distinctness as guard  # noqa: E402


HEADER = "from authentication.models import Company\n\n\n"

FIXED_HELPER = """\
def make_company(slug='co', nom='Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company
"""

COUNTER_HELPER = """\
import itertools
_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'co-{n}', defaults={'nom': nom or f'Co {n}'})
    return company
"""


def run(source: str, module: str = "apps.x.tests.test_x",
        rel: str = "apps/x/tests/test_x.py") -> list[str]:
    """Analyse one in-memory module and return the guard's failures."""
    tree = ast.parse(source)
    collector = guard._HelperCollector(source.splitlines())
    collector.visit(tree)
    guard._add_wrapper_helpers(collector)
    registry = {module: collector.helpers} if collector.helpers else {}
    return guard.violations_for(tree, module, registry, rel)


class DetectsVacuousIsolation(unittest.TestCase):
    """The bug this guard exists for: a second tenant that is the first one."""

    def test_second_call_with_defaults_is_the_same_row(self):
        failures = run(HEADER + FIXED_HELPER + """

class T:
    def setUp(self):
        self.company = make_company()

    def test_no_leak(self):
        other = make_company()
        assert other != self.company
""")
        self.assertEqual(len(failures), 1, failures)
        self.assertIn("test_no_leak", failures[0])
        self.assertIn("slug='co'", failures[0])

    def test_changing_only_nom_still_hits_the_same_slug(self):
        failures = run(HEADER + FIXED_HELPER + """

class T:
    def setUp(self):
        self.company = make_company()

    def test_no_leak(self):
        other = make_company(nom='Autre')
        assert other != self.company
""")
        self.assertEqual(len(failures), 1, failures)

    def test_inline_get_or_create_colliding_with_the_helper(self):
        failures = run(HEADER + FIXED_HELPER + """

class T:
    def setUp(self):
        self.company = make_company()

    def test_no_leak(self):
        other, _ = Company.objects.get_or_create(
            slug='co', defaults={'nom': 'X'})
""")
        self.assertEqual(len(failures), 1, failures)

    def test_create_without_slug_derives_it_from_nom(self):
        """``Company.save()`` slugifies ``nom`` — 'Co' collides with 'co'."""
        failures = run(HEADER + FIXED_HELPER + """

class T:
    def setUp(self):
        self.company = make_company()

    def test_no_leak(self):
        other = Company.objects.create(nom='Co')
""")
        self.assertEqual(len(failures), 1, failures)

    def test_collision_inherited_from_a_base_class_setup(self):
        failures = run(HEADER + FIXED_HELPER + """

class Base:
    def setUp(self):
        self.company = make_company()


class T(Base):
    def test_no_leak(self):
        other = make_company()
""")
        self.assertEqual(len(failures), 1, failures)

    def test_collision_hidden_behind_a_wrapper_helper(self):
        failures = run(HEADER + FIXED_HELPER + """

def make_tenant():
    return make_company()


class T:
    def setUp(self):
        self.company = make_company()

    def test_no_leak(self):
        other = make_tenant()
""")
        self.assertEqual(len(failures), 1, failures)

    def test_reused_user_keeps_the_first_company(self):
        """``get_or_create(username=...)`` with ``company`` only in defaults."""
        failures = run("""\
from django.contrib.auth import get_user_model

User = get_user_model()


def make_user(company, username='u1'):
    return User.objects.get_or_create(
        username=username, defaults={'company': company})[0]


class T:
    def setUp(self):
        self.user = make_user(self.company_a)

    def test_no_leak(self):
        intruder = make_user(self.company_b)
""")
        self.assertEqual(len(failures), 1, failures)
        self.assertIn("username='u1'", failures[0])


class AcceptsGenuineIsolation(unittest.TestCase):
    """No false positives on tests that really do build two tenants."""

    def test_explicit_distinct_slug(self):
        self.assertEqual(run(HEADER + FIXED_HELPER + """

class T:
    def setUp(self):
        self.company = make_company()

    def test_no_leak(self):
        other = make_company(slug='really-other')
"""), [])

    def test_counter_backed_helper_is_never_flagged(self):
        self.assertEqual(run(HEADER + COUNTER_HELPER + """

class T:
    def setUp(self):
        self.company = make_company()

    def test_no_leak(self):
        other = make_company()
"""), [])

    def test_same_helper_in_two_different_tests_is_fine(self):
        """Each test runs in its own rolled-back transaction."""
        self.assertEqual(run(HEADER + FIXED_HELPER + """

class T:
    def test_one(self):
        company = make_company()

    def test_two(self):
        company = make_company()
"""), [])

    def test_helper_used_once_per_test(self):
        self.assertEqual(run(HEADER + FIXED_HELPER + """

class T:
    def setUp(self):
        self.company = make_company()

    def test_something(self):
        assert self.company is not None
"""), [])


class Slugify(unittest.TestCase):
    def test_matches_django_for_the_cases_we_resolve(self):
        self.assertEqual(guard.slugify("Test PDF Co"), "test-pdf-co")
        # Django transliterates accents before slugifying.
        self.assertEqual(guard.slugify("Société A"), "societe-a")
        self.assertEqual(guard.slugify("A  B"), "a-b")

    def test_agrees_with_django_when_django_is_importable(self):
        try:
            from django.utils.text import slugify as django_slugify
        except ImportError:                       # pragma: no cover
            self.skipTest("Django not installed on the host")
        for value in ("Test PDF Co", "Société A", "A  B", "Chat Co",
                      "Co", "WIR165 Co", "Éé-Àà"):
            self.assertEqual(guard.slugify(value), django_slugify(value),
                             f"divergence on {value!r}")


class RepositoryIsClean(unittest.TestCase):
    """The guard must be GREEN on the tree it ships with."""

    def test_no_vacuous_isolation_in_the_backend(self):
        files = list(guard._iter_python_files())
        if not files:                      # backend absent (docs-only checkout)
            self.skipTest("backend/django_core not present")
        registry, trees = guard.build_registry(files)
        failures: list[str] = []
        for path, tree in trees.items():
            if not guard.is_test_file(path):
                continue
            rel = path.relative_to(guard.BACKEND_ROOT).as_posix()
            failures += guard.violations_for(
                tree, guard._module_name(path), registry, rel)
        self.assertEqual(failures, [], "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
