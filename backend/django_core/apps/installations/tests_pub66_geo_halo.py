"""PUB66 — fresh_installation_geo_seeds : chantiers récents AVEC GPS
exploitable, la base du halo géographique publicitaire — AUCUNE donnée
client renvoyée (id/référence/coordonnées seulement)."""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.installations.selectors import fresh_installation_geo_seeds


class FreshInstallationGeoSeedsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PUB66 Co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='PUB66')

    def _installation(self, ref, *, gps_lat=None, gps_lng=None):
        return Installation.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            gps_lat=gps_lat, gps_lng=gps_lng)

    def test_installation_without_gps_excluded(self):
        self._installation('CHT-PUB66-01')
        self.assertEqual(fresh_installation_geo_seeds(self.company), [])

    def test_installation_with_gps_included(self):
        self._installation(
            'CHT-PUB66-02', gps_lat='33.573100', gps_lng='-7.589800')
        rows = fresh_installation_geo_seeds(self.company)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['reference'], 'CHT-PUB66-02')
        self.assertNotIn('client', rows[0])
        self.assertNotIn('nom', rows[0])

    def test_old_installation_excluded_by_freshness_window(self):
        inst = self._installation(
            'CHT-PUB66-03', gps_lat='34.020000', gps_lng='-6.841600')
        old_date = timezone.now() - datetime.timedelta(days=30)
        Installation.objects.filter(pk=inst.pk).update(date_creation=old_date)
        self.assertEqual(fresh_installation_geo_seeds(self.company, days=14), [])

    def test_other_company_excluded(self):
        other = Company.objects.create(nom='PUB66 Other Co')
        other_client = Client.objects.create(company=other, nom='Autre')
        Installation.objects.create(
            company=other, reference='CHT-PUB66-OTHER', client=other_client,
            gps_lat='31.629500', gps_lng='-8.008900')
        self.assertEqual(fresh_installation_geo_seeds(self.company), [])
