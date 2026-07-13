"""Tests YDATA20 — scripts/check_migration_safety.py.

Pure stdlib (unittest), no Django. Run:
    python -m unittest scripts.tests.test_check_migration_safety -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_migration_safety as cms  # noqa: E402


def _check(src, model_names=frozenset()):
    with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8") as fh:
        fh.write(src)
        path = Path(fh.name)
    try:
        return {code for code, _msg in cms.check_file(path, model_names)}
    finally:
        path.unlink()


ADDFIELD_UNIQUE_ONESHOT = '''
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = []
    operations = [
        migrations.AddField(
            model_name='devis',
            name='reference',
            field=models.CharField(max_length=20, unique=True),
        ),
    ]
'''

ADDFIELD_NOT_NULL_ONESHOT = '''
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = []
    operations = [
        migrations.AddField(
            model_name='devis',
            name='statut',
            field=models.CharField(max_length=20, null=False, default='x'),
        ),
    ]
'''

UNIQUE_ON_NEW_TABLE_OK = '''
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = []
    operations = [
        migrations.CreateModel(name='Widget', fields=[]),
        migrations.AddField(
            model_name='widget',
            name='reference',
            field=models.CharField(max_length=20, unique=True),
        ),
    ]
'''

INDEX_NAME_DRIFT = '''
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = []
    operations = [
        migrations.AddIndex(
            model_name='devis',
            index=models.Index(fields=['company'], name='handwritten_idx'),
        ),
    ]
'''

INDEX_NAME_IN_MODELS_OK = INDEX_NAME_DRIFT  # same, but name is declared

INDEX_HASH_NAME_OK = '''
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = []
    operations = [
        migrations.AddIndex(
            model_name='devis',
            index=models.Index(fields=['company'], name='ventes_devis_9a1b2c_idx'),
        ),
    ]
'''


class TestMigrationSafety(unittest.TestCase):
    def test_addfield_unique_oneshot_flagged(self):
        self.assertIn("ADDFIELD_UNIQUE_ONESHOT", _check(ADDFIELD_UNIQUE_ONESHOT))

    def test_addfield_not_null_oneshot_flagged(self):
        self.assertIn("ADDFIELD_NOT_NULL_ONESHOT",
                      _check(ADDFIELD_NOT_NULL_ONESHOT))

    def test_unique_on_new_table_ok(self):
        self.assertNotIn("ADDFIELD_UNIQUE_ONESHOT",
                         _check(UNIQUE_ON_NEW_TABLE_OK))

    def test_index_name_drift_flagged(self):
        self.assertIn("INDEX_NAME_DRIFT", _check(INDEX_NAME_DRIFT))

    def test_index_name_declared_in_models_ok(self):
        self.assertNotIn(
            "INDEX_NAME_DRIFT",
            _check(INDEX_NAME_IN_MODELS_OK, model_names={"handwritten_idx"}))

    def test_index_hash_name_ok(self):
        self.assertNotIn("INDEX_NAME_DRIFT", _check(INDEX_HASH_NAME_OK))


if __name__ == "__main__":
    unittest.main()
