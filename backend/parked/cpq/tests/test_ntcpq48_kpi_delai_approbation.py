"""NTCPQ48 — KPI « Délai moyen d'approbation de remise » au tableau de bord
``reporting`` (hub KPI fédéré ARC40, widget existant — pas un nouvel écran)."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.cpq import platform, selectors
from apps.cpq.models import EtapeApprobationDevis
from core import platform as core_platform
from testkit.factories import CompanyFactory, DevisFactory, UserFactory


class TestKpiDelaiApprobation(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.approbateur = UserFactory(company=self.company)
        self.devis = DevisFactory(company=self.company)

    def _etape_decidee(self, heures):
        etape = EtapeApprobationDevis.objects.create(
            company=self.company, devis=self.devis, niveau=1,
            approbateur=self.approbateur,
            statut=EtapeApprobationDevis.Statut.APPROUVE)
        creation = timezone.now() - timedelta(hours=heures)
        EtapeApprobationDevis.objects.filter(id=etape.id).update(
            date_creation=creation, decision_le=timezone.now())
        return etape

    def test_aucune_etape_decidee_liste_vide(self):
        self.assertEqual(selectors.kpi_delai_approbation(self.company), [])

    def test_moyenne_et_p90_calcules(self):
        self._etape_decidee(2)
        self._etape_decidee(4)
        self._etape_decidee(6)
        stats = selectors.delai_approbation_stats(self.company)
        self.assertEqual(stats['count'], 3)
        self.assertAlmostEqual(stats['moyenne_heures'], 4.0, delta=0.1)
        tuiles = selectors.kpi_delai_approbation(self.company)
        ids = {t['id'] for t in tuiles}
        self.assertEqual(
            ids, {'cpq_delai_moyen_approbation', 'cpq_delai_p90_approbation'})

    def test_filtre_par_approbateur(self):
        autre = UserFactory(company=self.company)
        self._etape_decidee(2)
        etape2 = EtapeApprobationDevis.objects.create(
            company=self.company, devis=self.devis, niveau=2,
            approbateur=autre, statut=EtapeApprobationDevis.Statut.APPROUVE)
        EtapeApprobationDevis.objects.filter(id=etape2.id).update(
            date_creation=timezone.now() - timedelta(hours=10),
            decision_le=timezone.now())
        stats = selectors.delai_approbation_stats(
            self.company, approbateur_id=self.approbateur.id)
        self.assertEqual(stats['count'], 1)

    def test_isolation_multi_tenant(self):
        autre_company = CompanyFactory()
        self._etape_decidee(3)
        self.assertEqual(
            selectors.kpi_delai_approbation(autre_company), [])

    def test_declare_dans_le_manifeste_plateforme(self):
        self.assertIn(
            'apps.cpq.selectors.kpi_delai_approbation',
            platform.PLATFORM['kpi_providers'])
        self.assertIn(
            'apps.cpq.selectors.kpi_delai_approbation',
            core_platform.kpi_providers(manifests={'cpq': platform.PLATFORM}))
