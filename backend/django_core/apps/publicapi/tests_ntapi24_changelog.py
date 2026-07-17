"""NTAPI24 — changelog API dédié, réutilise/étend FG399 (`core.ChangelogEntry`).

`GET /api/public/changelog/` : une entrée « breaking v2 » apparaît dans le
fil et le endpoint JSON, filtrable par ``?version=``.
"""
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import ChangelogEntry


class Ntapi24ChangelogTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.breaking = ChangelogEntry.objects.create(
            titre='Breaking v2', corps='Changement cassant.', version='v2',
            categorie=ChangelogEntry.CAT_CORRECTIF, breaking=True,
            publie=True, publie_le=self.now)
        self.feature = ChangelogEntry.objects.create(
            titre='Nouvelle ressource', corps='...', version='v1',
            categorie=ChangelogEntry.CAT_NOUVEAUTE, breaking=False,
            publie=True, publie_le=self.now)
        self.unpublished = ChangelogEntry.objects.create(
            titre='Brouillon', corps='...', version='v2',
            categorie=ChangelogEntry.CAT_NOUVEAUTE, breaking=False,
            publie=False)

    def test_breaking_entry_appears_in_feed(self):
        resp = APIClient().get('/api/public/changelog/')
        self.assertEqual(resp.status_code, 200)
        titres = [row['titre'] for row in resp.data['results']]
        self.assertIn('Breaking v2', titres)
        breaking_row = next(
            r for r in resp.data['results'] if r['titre'] == 'Breaking v2')
        self.assertEqual(breaking_row['type'], 'breaking')
        self.assertTrue(breaking_row['breaking'])

    def test_unpublished_entry_never_appears(self):
        resp = APIClient().get('/api/public/changelog/')
        titres = [row['titre'] for row in resp.data['results']]
        self.assertNotIn('Brouillon', titres)

    def test_filterable_by_version(self):
        resp = APIClient().get('/api/public/changelog/', {'version': 'v2'})
        self.assertEqual(resp.status_code, 200)
        versions = {row['version'] for row in resp.data['results']}
        self.assertEqual(versions, {'v2'})
        titres = [row['titre'] for row in resp.data['results']]
        self.assertIn('Breaking v2', titres)
        self.assertNotIn('Nouvelle ressource', titres)

    def test_no_authentication_required(self):
        # Document de découverte global, comme openapi.json (NTAPI20).
        resp = APIClient().get('/api/public/changelog/')
        self.assertEqual(resp.status_code, 200)
