"""SOL14 — un KPI dont le module est éteint DÉGRADE proprement.

Ce qu'il ne doit surtout pas faire : appeler le sélecteur d'une app coupée, ou
rendre un 0 qui se lirait comme une vraie mesure. `valeur=None` ⇒ aucun
franchissement, aucune notification, tuile absente de l'écran.
"""
from django.test import TestCase

from apps.reporting.kpi_alertes import (
    KPI_MODULE, evaluate_kpi_alerte, kpi_disponible, kpis_disponibles,
)
from apps.reporting.models import KpiAlerte
from authentication.models import Company
from core import modules as modules_infra
from core.models import ModuleToggle


class TableKpiModuleTests(TestCase):
    def test_chaque_module_cite_existe(self):
        manifests = modules_infra.collect_manifests()
        inconnus = sorted({
            m for m in KPI_MODULE.values() if m not in manifests})
        self.assertEqual(inconnus, [], f'modules inconnus : {inconnus}')

    def test_les_kpi_transverses_ne_sont_pas_mappes(self):
        for kpi in (KpiAlerte.Kpi.DSO, KpiAlerte.Kpi.ENCOURS_ECHU_TOTAL,
                    KpiAlerte.Kpi.VALEUR_STOCK_TOTALE):
            self.assertNotIn(kpi, KPI_MODULE, kpi)


class DisponibiliteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='KPI SOL14', slug='sol14-kpi')

    def test_tout_disponible_par_defaut(self):
        self.assertEqual(
            sorted(kpis_disponibles(self.company)),
            sorted(v for v, _ in KpiAlerte.Kpi.choices))

    def test_module_eteint_retire_son_kpi(self):
        ModuleToggle.objects.create(
            company=self.company, module='douane', actif=False)
        self.assertFalse(
            kpi_disponible(self.company, KpiAlerte.Kpi.DELAI_MOYEN_DEDOUANEMENT))
        self.assertNotIn(
            KpiAlerte.Kpi.DELAI_MOYEN_DEDOUANEMENT,
            kpis_disponibles(self.company))
        # Les KPI transverses restent proposés.
        self.assertIn(KpiAlerte.Kpi.DSO, kpis_disponibles(self.company))

    def test_evaluation_degrade_sans_notifier(self):
        ModuleToggle.objects.create(
            company=self.company, module='scm', actif=False)
        alerte = KpiAlerte.objects.create(
            company=self.company, kpi=KpiAlerte.Kpi.TAUX_SERVICE_SCM,
            operateur=KpiAlerte.Operateur.INF, seuil=95)
        valeur, franchi, notifie = evaluate_kpi_alerte(alerte)
        self.assertIsNone(valeur)
        self.assertFalse(franchi)
        self.assertFalse(notifie)
        alerte.refresh_from_db()
        self.assertFalse(alerte.deja_notifie)
