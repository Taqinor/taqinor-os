"""GED36 — Quotas de stockage par société.

Couvre :
  * `usage_stockage_octets` somme les tailles des versions de la société ;
  * `quota_octets` lit l'entrée explicite, sinon le défaut settings ;
  * `quota_depasse` / `assert_quota_disponible` (illimité = jamais bloqué) ;
  * un quota fixé est respecté (dépôt simulé qui le dépasserait → bloqué) ;
  * isolation société (l'usage de A n'inclut jamais les versions de B).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from authentication.models import Company
from apps.ged import services
from apps.ged.models import (
    Cabinet, Document, Folder, QuotaDepasseError, QuotaStockage,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class QuotaServiceTests(TestCase):
    def setUp(self):
        self.co_a = make_company('ged36-a', 'Ged36 A')
        self.co_b = make_company('ged36-b', 'Ged36 B')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Docs')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='F')
        self.doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Doc')
        self.cab_b = Cabinet.objects.create(company=self.co_b, nom='Docs')
        self.folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='F')
        self.doc_b = Document.objects.create(
            company=self.co_b, folder=self.folder_b, nom='Doc B')

    def _version(self, doc, company, size):
        services.add_version(
            doc, file_key=f'k/{doc.id}-{size}.bin', company=company,
            filename='f.bin', size=size)

    def test_usage_somme_les_versions(self):
        self._version(self.doc_a, self.co_a, 100)
        self._version(self.doc_a, self.co_a, 250)
        self.assertEqual(services.usage_stockage_octets(self.co_a), 350)

    def test_usage_isole_par_societe(self):
        self._version(self.doc_a, self.co_a, 100)
        self._version(self.doc_b, self.co_b, 999)
        self.assertEqual(services.usage_stockage_octets(self.co_a), 100)

    @override_settings(GED_QUOTA_DEFAUT_OCTETS=0)
    def test_quota_illimite_jamais_depasse(self):
        self._version(self.doc_a, self.co_a, 10 ** 9)
        self.assertEqual(services.quota_octets(self.co_a), 0)
        self.assertFalse(services.quota_depasse(self.co_a))
        # Ne lève jamais en illimité.
        services.assert_quota_disponible(
            self.co_a, octets_supplementaires=10 ** 12)

    def test_quota_explicite_respecte(self):
        QuotaStockage.objects.create(company=self.co_a, quota_octets=1000)
        self._version(self.doc_a, self.co_a, 800)
        self.assertEqual(services.quota_octets(self.co_a), 1000)
        self.assertEqual(services.quota_restant_octets(self.co_a), 200)
        # Un dépôt de 300 dépasserait (800 + 300 > 1000).
        self.assertTrue(
            services.quota_depasse(self.co_a, octets_supplementaires=300))
        with self.assertRaises(QuotaDepasseError):
            services.assert_quota_disponible(
                self.co_a, octets_supplementaires=300)
        # Un dépôt de 100 reste dans le quota.
        self.assertFalse(
            services.quota_depasse(self.co_a, octets_supplementaires=100))

    @override_settings(GED_QUOTA_DEFAUT_OCTETS=500)
    def test_defaut_settings_applique_sans_entree(self):
        self.assertEqual(services.quota_octets(self.co_a), 500)
        self._version(self.doc_a, self.co_a, 600)
        self.assertTrue(services.quota_depasse(self.co_a))
