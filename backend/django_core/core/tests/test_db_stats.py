"""NTPLT19 — collecteur de stats DB : dégradation propre + isolation par section."""
from unittest import mock

from django.test import SimpleTestCase
from django.urls import reverse

from core import db_stats


class DbStatsCollectorTests(SimpleTestCase):
    def test_non_postgres_degrades_without_error(self):
        fake = mock.MagicMock()
        fake.vendor = 'sqlite'
        with mock.patch.object(db_stats, 'connection', fake):
            out = db_stats.collect_db_stats()
        self.assertEqual(out['backend'], 'sqlite')
        self.assertFalse(out['pg_stat_statements'])
        self.assertIn('detail', out)
        self.assertEqual(out['top_queries'], [])

    def test_missing_extension_degrades_per_section(self):
        fake = mock.MagicMock()
        fake.vendor = 'postgresql'
        cursor = fake.cursor.return_value.__enter__.return_value
        cursor.execute.side_effect = Exception("pg_stat_statements absent")
        with mock.patch.object(db_stats, 'connection', fake):
            out = db_stats.collect_db_stats()
        # Aucune exception ne remonte ; chaque section porte son erreur.
        self.assertIn('top_queries_error', out)
        self.assertIn('table_sizes_error', out)
        self.assertFalse(out['pg_stat_statements'])

    def test_url_registered(self):
        self.assertEqual(reverse('db-stats'), '/api/django/core/db-stats/')
