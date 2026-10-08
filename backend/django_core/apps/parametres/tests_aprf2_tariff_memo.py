"""APRF2 — ``TariffSettings.get`` mémoïsé pour la durée d'une requête
(``core.request_cache``), invalidé à l'enregistrement (C-APRF-001)."""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.parametres.models_tariff import TariffSettings
from apps.parametres.views_tariff import update_tariff_settings
from authentication.models import Company
from core import request_cache

User = get_user_model()


def _requetes_tarif(ctx):
    return [q for q in ctx.captured_queries
            if 'parametres_tariffsettings' in q['sql']]


class TariffMemoTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APRF2 Co', slug='aprf2-co')
        TariffSettings.get(company=self.company)  # ligne créée hors portée

    def test_dix_lectures_une_requete(self):
        with request_cache.request_scope():
            with CaptureQueriesContext(connection) as ctx:
                for _ in range(10):
                    s = TariffSettings.get(company=self.company)
        self.assertEqual(len(_requetes_tarif(ctx)), 1)
        self.assertEqual(s.company_id, self.company.id)

    def test_hors_portee_une_requete_par_appel(self):
        with CaptureQueriesContext(connection) as ctx:
            for _ in range(3):
                TariffSettings.get(company=self.company)
        self.assertEqual(len(_requetes_tarif(ctx)), 3)

    def test_save_invalide(self):
        with request_cache.request_scope():
            s = TariffSettings.get(company=self.company)
            # Écriture par une AUTRE instance (comme un autre chemin de code).
            autre = TariffSettings.objects.get(pk=s.pk)
            autre.tolerance_kwh = 17
            autre.save()
            relu = TariffSettings.get(company=self.company)
        self.assertEqual(relu.tolerance_kwh, 17)

    def test_patch_version_relue(self):
        admin = User.objects.create_user(
            username='aprf2_admin', password='x', role_legacy='admin',
            company=self.company)
        version_avant = TariffSettings.objects.get(company=self.company).version
        factory = APIRequestFactory()
        with request_cache.request_scope():
            TariffSettings.get(company=self.company)  # mémo chaud
            req = factory.patch(
                '/api/django/parametres/tarification/update/',
                {'tolerance_kwh': 14}, format='json')
            force_authenticate(req, user=admin)
            r = update_tariff_settings(req)
            self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
            relu = TariffSettings.get(company=self.company)
        self.assertEqual(relu.tolerance_kwh, 14)
        self.assertEqual(relu.version, version_avant + 1)
