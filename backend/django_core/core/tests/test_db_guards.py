"""NTPLT18 — le statement_timeout par défaut est bien posé sur la connexion."""
from django.conf import settings
from django.test import SimpleTestCase


class StatementTimeoutSettingTests(SimpleTestCase):
    def test_statement_timeout_option_present(self):
        """Le réglage statement_timeout est actif dans OPTIONS (défaut 30 s)."""
        opts = settings.DATABASES['default'].get('OPTIONS', {})
        # Le défaut (30 000 ms) est > 0 → l'option doit être présente.
        self.assertIn('options', opts)
        self.assertIn('statement_timeout', opts['options'])

    def test_helper_importable(self):
        from core.db_guards import statement_timeout  # noqa: F401
