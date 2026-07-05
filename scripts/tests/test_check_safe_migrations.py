"""Tests YOPSB4 — scripts/check_safe_migrations.py.

Pure stdlib (unittest), no Django needed — mirrors the DB-free spirit of the
checker itself. Run with:
    python -m unittest scripts.tests.test_check_safe_migrations -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_safe_migrations as csm  # noqa: E402


NEW_ADDFIELD_NOT_NULL = '''
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = []
    operations = [
        migrations.AddField(
            model_name='devis',
            name='code_interne',
            field=models.CharField(max_length=20, null=False, default='X'),
        ),
    ]
'''

SAFE_ADDFIELD_NULLABLE = '''
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = []
    operations = [
        migrations.AddField(
            model_name='devis',
            name='code_interne',
            field=models.CharField(max_length=20, null=True, blank=True),
        ),
    ]
'''

NEW_ADDINDEX_ON_EXISTING_MODEL = '''
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = []
    operations = [
        migrations.AddIndex(
            model_name='devis',
            index=models.Index(fields=['statut'], name='devis_statut_idx'),
        ),
    ]
'''

SAFE_ADDINDEX_ON_NEW_MODEL = '''
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='Widget',
            fields=[
                ('id', models.AutoField(primary_key=True)),
            ],
        ),
        migrations.AddIndex(
            model_name='widget',
            index=models.Index(fields=['id'], name='widget_id_idx'),
        ),
    ]
'''

SAFE_ADDINDEX_ATOMIC_FALSE = '''
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False
    dependencies = []
    operations = [
        migrations.AddIndex(
            model_name='devis',
            index=models.Index(fields=['statut'], name='devis_statut_idx'),
        ),
    ]
'''

NEW_RENAME_FIELD = '''
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = []
    operations = [
        migrations.RenameField(
            model_name='devis', old_name='old_ref', new_name='new_ref'),
    ]
'''


class CheckSafeMigrationsTests(unittest.TestCase):
    def _write_and_check(self, source):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "0099_test_migration.py"
            path.write_text(source, encoding="utf-8")
            return csm.check_file(path)

    def test_addfield_not_null_with_default_is_flagged(self):
        findings = self._write_and_check(NEW_ADDFIELD_NOT_NULL)
        codes = [c for c, _ in findings]
        self.assertIn("ADDFIELD_NOT_NULL_WITH_DEFAULT", codes)

    def test_addfield_nullable_is_not_flagged(self):
        findings = self._write_and_check(SAFE_ADDFIELD_NULLABLE)
        codes = [c for c, _ in findings]
        self.assertNotIn("ADDFIELD_NOT_NULL_WITH_DEFAULT", codes)

    def test_addindex_on_existing_model_is_flagged(self):
        findings = self._write_and_check(NEW_ADDINDEX_ON_EXISTING_MODEL)
        codes = [c for c, _ in findings]
        self.assertIn("ADDINDEX_NOT_CONCURRENT", codes)

    def test_addindex_on_brand_new_model_is_not_flagged(self):
        findings = self._write_and_check(SAFE_ADDINDEX_ON_NEW_MODEL)
        codes = [c for c, _ in findings]
        self.assertNotIn("ADDINDEX_NOT_CONCURRENT", codes)

    def test_addindex_with_atomic_false_is_not_flagged(self):
        findings = self._write_and_check(SAFE_ADDINDEX_ATOMIC_FALSE)
        codes = [c for c, _ in findings]
        self.assertNotIn("ADDINDEX_NOT_CONCURRENT", codes)

    def test_rename_field_is_flagged(self):
        findings = self._write_and_check(NEW_RENAME_FIELD)
        codes = [c for c, _ in findings]
        self.assertIn("RENAMEFIELD", codes)

    def test_allowlisted_migration_is_exempt_end_to_end(self):
        """A migration with a real finding, listed in the allowlist, must
        not fail main()'s overall exit code."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp)
            django_core = fake_root / "backend" / "django_core"
            app_migrations = django_core / "apps" / "demoapp" / "migrations"
            app_migrations.mkdir(parents=True)
            (app_migrations / "__init__.py").write_text("", encoding="utf-8")
            bad_path = app_migrations / "0001_bad.py"
            bad_path.write_text(NEW_RENAME_FIELD, encoding="utf-8")

            allow_path = fake_root / "scripts" / "safe_migrations_allow.txt"
            allow_path.parent.mkdir(parents=True, exist_ok=True)
            rel = "backend/django_core/apps/demoapp/migrations/0001_bad.py"
            allow_path.write_text(rel + "\n", encoding="utf-8")

            import importlib
            orig_root = csm.ROOT
            orig_django_core = csm.DJANGO_CORE
            orig_apps_dir = csm.APPS_DIR
            orig_allow = csm.ALLOWLIST_PATH
            orig_mig_roots = csm.MIGRATION_ROOTS
            try:
                csm.ROOT = fake_root
                csm.DJANGO_CORE = django_core
                csm.APPS_DIR = django_core / "apps"
                csm.ALLOWLIST_PATH = allow_path
                csm.MIGRATION_ROOTS = [
                    django_core / "core" / "migrations",
                    django_core / "authentication" / "migrations",
                ]
                exit_code = csm.main([])
                self.assertEqual(exit_code, 0)

                # Now remove from the allowlist: the SAME migration must now
                # fail (exit code 1) — proves a new/un-allowlisted migration
                # with this pattern is actually caught.
                allow_path.write_text("", encoding="utf-8")
                exit_code_after = csm.main([])
                self.assertEqual(exit_code_after, 1)
            finally:
                csm.ROOT = orig_root
                csm.DJANGO_CORE = orig_django_core
                csm.APPS_DIR = orig_apps_dir
                csm.ALLOWLIST_PATH = orig_allow
                csm.MIGRATION_ROOTS = orig_mig_roots
                importlib.reload(csm)


if __name__ == "__main__":
    unittest.main()
