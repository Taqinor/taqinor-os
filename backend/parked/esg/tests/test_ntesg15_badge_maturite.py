"""NTESG15 — Badge de maturité ESG interne (auto-évalué, jamais un label
externe).

Critère d'acceptation : le score se recalcule correctement quand les
composantes changent, le disclaimer est toujours visible à côté du score.
"""
from django.test import TestCase

from testkit.base import TenantAPITestCase
from testkit.factories import CompanyFactory

from apps.esg.management.commands.seed_catalogue_esg import (
    seed_catalogue_esg_for_company,
)
from apps.esg.models import CatalogueIndicateurESG, ObjectifESGTrajectoire
from apps.esg.selectors import DISCLAIMER_BADGE_MATURITE, badge_maturite_esg


class BadgeMaturiteEsgTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()

    def test_no_company_returns_zero_score_with_disclaimer(self):
        data = badge_maturite_esg(None)
        self.assertEqual(data['score'], 0.0)
        self.assertEqual(data['disclaimer'], DISCLAIMER_BADGE_MATURITE)

    def test_empty_company_returns_zero_score(self):
        data = badge_maturite_esg(self.company)
        self.assertEqual(data['score'], 0.0)
        self.assertEqual(data['disclaimer'], DISCLAIMER_BADGE_MATURITE)

    def test_score_increases_with_catalogue_coverage(self):
        from apps.qhse.models import IndicateurESG

        seed_catalogue_esg_for_company(self.company)
        premier = CatalogueIndicateurESG.objects.filter(
            company=self.company).first()
        IndicateurESG.objects.create(
            company=self.company, code=premier.code,
            libelle=premier.libelle, pilier=premier.pilier, valeur=1,
            annee=2026)
        data = badge_maturite_esg(self.company)
        self.assertGreater(data['score'], 0.0)
        self.assertTrue(data['composantes']['couverture_catalogue']['disponible'])

    def test_atteinte_cible_only_counts_indicateurs_with_cible(self):
        from apps.qhse.models import IndicateurESG

        IndicateurESG.objects.create(
            company=self.company, code='E1', libelle='Sans cible',
            pilier=IndicateurESG.Pilier.ENVIRONNEMENT, valeur=10, annee=2026)
        IndicateurESG.objects.create(
            company=self.company, code='E2', libelle='Avec cible atteinte',
            pilier=IndicateurESG.Pilier.ENVIRONNEMENT, valeur=5, cible=10,
            tendance_souhaitee=IndicateurESG.Tendance.BAISSE_FAVORABLE,
            annee=2026)
        data = badge_maturite_esg(self.company)
        composante = data['composantes']['atteinte_cibles']
        self.assertTrue(composante['disponible'])
        # Un seul indicateur (E2) a une cible renseignée -> 100 % atteint.
        self.assertEqual(composante['valeur_pct'], 100.0)

    def test_trajectoire_component_counts_catalogue_codes_with_active_objectif(self):
        seed_catalogue_esg_for_company(self.company)
        premier = CatalogueIndicateurESG.objects.filter(
            company=self.company).first()
        ObjectifESGTrajectoire.objects.create(
            company=self.company, indicateur_code=premier.code,
            valeur_reference=100, annee_reference=2024,
            valeur_cible=50, annee_cible=2028)
        data = badge_maturite_esg(self.company)
        composante = data['composantes']['trajectoires_actives']
        self.assertTrue(composante['disponible'])
        self.assertGreater(composante['valeur_pct'], 0.0)

    def test_inactive_objectif_not_counted(self):
        seed_catalogue_esg_for_company(self.company)
        premier = CatalogueIndicateurESG.objects.filter(
            company=self.company).first()
        ObjectifESGTrajectoire.objects.create(
            company=self.company, indicateur_code=premier.code,
            valeur_reference=100, annee_reference=2024,
            valeur_cible=50, annee_cible=2028, actif=False)
        data = badge_maturite_esg(self.company)
        self.assertEqual(
            data['composantes']['trajectoires_actives']['valeur_pct'], 0.0)


class BadgeMaturiteEsgApiTests(TenantAPITestCase):
    BASE = '/api/django/esg/catalogue-esg/'

    def test_badge_maturite_endpoint_scoped_to_company(self):
        r = self.client_as().get(f'{self.BASE}badge-maturite/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('score', r.data)
        self.assertIn('disclaimer', r.data)
