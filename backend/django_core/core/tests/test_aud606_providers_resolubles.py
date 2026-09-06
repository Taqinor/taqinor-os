"""AUD606 — une surface à CHEMIN DOTTÉ déclarée doit RÉSOUDRE.

``kpi_providers`` et ``agent_actions_module`` ne nomment pas des modèles mais
des callables/modules par chemin dotté. Leurs consommateurs les résolvent en
silence et IGNORENT ce qui ne résout pas : ``reporting.reports.kpi_federes``
saute toute clé sans point (« clé libre héritée ») puis toute
``ImportError``/``AttributeError`` — « jamais un 500 ». Excellent en production,
AVEUGLE en revue : ``apps/crm/platform.py`` a déclaré ``kpi_providers:
['crm_sales_report']`` — sans point — et le hub KPI fédéré n'a jamais affiché la
moindre tuile de funnel commercial sans que rien ne le dise.

Run :
    python manage.py test core.tests.test_aud606_providers_resolubles -v2
"""
from django.test import SimpleTestCase

from core import platform_coverage


class TestProvidersResolubles(SimpleTestCase):
    def test_aucun_chemin_dotte_declare_ne_reste_mort(self):
        findings = platform_coverage.new_providers_drift()
        self.assertEqual(
            findings, set(),
            'Surfaces déclarées mais NON câblées :\n'
            + platform_coverage.format_providers_drift(findings))

    def test_le_funnel_crm_resout_enfin(self):
        from core import platform

        manifests = platform.collect_platform_manifests()
        providers = manifests['crm']['kpi_providers']
        self.assertTrue(providers)
        for dotted in providers:
            with self.subTest(provider=dotted):
                ok, motif = platform_coverage._resout_en_callable(dotted)
                self.assertTrue(ok, motif)


class TestLaGardeNePeutPasEtreVerteParAccident(SimpleTestCase):
    """Une garde qui ne rougit jamais ne garde rien."""

    def test_une_cle_sans_point_est_detectee(self):
        faux = {'bidon': {
            'module': 'bidon', 'record_targets': [], 'searchable_models': [],
            'kpi_providers': ['crm_sales_report'],
            'agent_actions_module': '',
        }}
        self.assertIn(
            ('bidon', 'kpi_providers', 'crm_sales_report'),
            platform_coverage.all_providers_drift(faux))

    def test_un_chemin_introuvable_est_detecte(self):
        faux = {'bidon': {
            'module': 'bidon', 'record_targets': [], 'searchable_models': [],
            'kpi_providers': ['apps.bidon.kpis.fantome'],
            'agent_actions_module': '',
        }}
        self.assertTrue(platform_coverage.all_providers_drift(faux))

    def test_un_module_d_actions_introuvable_est_detecte(self):
        faux = {'bidon': {
            'module': 'bidon', 'record_targets': [], 'searchable_models': [],
            'kpi_providers': [],
            'agent_actions_module': 'apps.bidon.agent_actions',
        }}
        self.assertIn(
            ('bidon', 'agent_actions_module', 'apps.bidon.agent_actions'),
            platform_coverage.all_providers_drift(faux))

    def test_un_manifeste_sain_ne_produit_rien(self):
        faux = {'crm': {
            'module': 'crm', 'record_targets': [], 'searchable_models': [],
            'kpi_providers': ['apps.crm.kpis.kpi_crm'],
            'agent_actions_module': 'apps.crm.agent_actions',
        }}
        self.assertEqual(platform_coverage.all_providers_drift(faux), set())
