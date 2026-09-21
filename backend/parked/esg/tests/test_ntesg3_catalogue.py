"""NTESG3 — Référentiel GRI-lite : seed idempotent + calcul de couverture.

Critère d'acceptation : le catalogue seed une fois par société (idempotent),
la couverture calcule un % correct par pilier basé sur les codes
``IndicateurESG`` existants qui matchent.
"""
from django.test import TestCase

from testkit.factories import CompanyFactory

from apps.esg.catalogue_data import GRI_LITE_CATALOGUE
from apps.esg.management.commands.seed_catalogue_esg import (
    seed_catalogue_esg_for_company,
)
from apps.esg.models import CatalogueIndicateurESG
from apps.esg.selectors import couverture_catalogue


class SeedCatalogueEsgTests(TestCase):
    def test_seed_is_idempotent(self):
        company = CompanyFactory()
        created_first = seed_catalogue_esg_for_company(company)
        self.assertEqual(created_first, len(GRI_LITE_CATALOGUE))
        created_second = seed_catalogue_esg_for_company(company)
        self.assertEqual(created_second, 0)
        self.assertEqual(
            CatalogueIndicateurESG.objects.filter(company=company).count(),
            len(GRI_LITE_CATALOGUE))

    def test_seed_scoped_per_company(self):
        co_a = CompanyFactory()
        co_b = CompanyFactory()
        seed_catalogue_esg_for_company(co_a)
        self.assertEqual(
            CatalogueIndicateurESG.objects.filter(company=co_b).count(), 0)


class CouvertureCatalogueTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        seed_catalogue_esg_for_company(self.company)

    def test_couverture_zero_without_indicateurs(self):
        data = couverture_catalogue(self.company)
        self.assertEqual(data['global_pct'], 0.0)
        for pilier in data['piliers'].values():
            self.assertEqual(pilier['couverts'], 0)

    def test_couverture_matches_used_codes(self):
        from apps.qhse.models import IndicateurESG

        IndicateurESG.objects.create(
            company=self.company, code='E1', libelle='Énergie',
            pilier=IndicateurESG.Pilier.ENVIRONNEMENT, valeur=1, annee=2026)
        data = couverture_catalogue(self.company)
        env_total = data['piliers']['environnement']['total']
        self.assertEqual(data['piliers']['environnement']['couverts'], 1)
        self.assertGreater(env_total, 1)
        self.assertGreater(data['global_pct'], 0.0)

    def test_couverture_no_company_returns_empty_without_exception(self):
        data = couverture_catalogue(None)
        self.assertEqual(data, {'piliers': {}, 'global_pct': 0.0})
