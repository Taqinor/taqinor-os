"""Tests ARC28 — collecteur du registre plateforme (``core.platform``).

Couvre :
  * la découverte GÉNÉRIQUE des manifestes ``apps/<x>/platform.py`` (les deux
    pilotes crm + sav sont bien collectés) ;
  * l'agrégation par surface (searchable_models, record_targets, etc.) ;
  * le gatage ``ModuleToggle`` : un module désactivé pour la société DISPARAÎT
    du registre ET de toutes les surfaces (étend ODX23) ;
  * la validation d'un manifeste (clé de surface inconnue, entrée automation
    mal formée) sans DB.
"""
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from core import platform
from core.models import ModuleToggle


class PlatformCollectorTests(SimpleTestCase):
    """Collecte + agrégation (sans société — pas de DB requise)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manifests = platform.collect_platform_manifests()

    def test_pilot_manifests_are_discovered(self):
        """Les deux pilotes crm + sav sont collectés génériquement."""
        self.assertIn('crm', self.manifests)
        self.assertIn('sav', self.manifests)

    def test_crm_manifest_shape(self):
        """Le manifeste CRM porte ses surfaces réelles, normalisées."""
        crm = self.manifests['crm']
        self.assertEqual(crm['module'], 'crm')
        self.assertIn('crm.lead', crm['searchable_models'])
        self.assertIn('crm.client', crm['searchable_models'])
        self.assertIn('crm.lead', crm['record_targets'])
        self.assertIn('lead', crm['customfield_models'])
        self.assertIn('leads', crm['import_specs'])
        self.assertEqual(crm['agent_actions_module'], 'apps.crm.agent_actions')
        self.assertIn(
            {'model': 'crm.lead', 'field': 'relance_date'},
            crm['automation_state_fields'])

    def test_sav_manifest_is_asymmetric(self):
        """SAV a la recherche (ARC29), le chatter (ARC30), l'import (ARC32) et
        l'automation de statut (ARC34) câblés, mais NI champs perso, NI actions
        agent, NI KPI : le collecteur tolère un manifeste partiel/asymétrique
        (c'est tout l'intérêt d'un second pilote à côté du CRM complet)."""
        sav = self.manifests['sav']
        # ARC30 — cible chatter/records historique.
        self.assertEqual(sav['record_targets'], ['sav.ticket'])
        # ARC29 — les 3 modèles SAV historiquement cherchables.
        self.assertEqual(
            sav['searchable_models'],
            ['sav.equipement', 'sav.ticket', 'sav.contratmaintenance'])
        # ARC32 — cible d'import du parc SAV.
        self.assertEqual(sav['import_specs'], ['equipements'])
        # ARC34 — statut Ticket automatisable (RECORD_STATE_CHANGE).
        self.assertEqual(
            sav['automation_state_fields'],
            [{'model': 'sav.ticket', 'field': 'statut'}])
        # Surfaces DÉLIBÉRÉMENT vides (asymétrie préservée) : le collecteur
        # tolère un manifeste où seules certaines surfaces sont câblées.
        self.assertEqual(sav['customfield_models'], [])
        self.assertEqual(sav['agent_actions_module'], '')
        self.assertEqual(sav['kpi_providers'], [])

    def test_aggregators_flatten_across_manifests(self):
        """Les agrégateurs aplatissent bien les surfaces (via manifests fournis)."""
        searchable = platform.searchable_models(manifests=self.manifests)
        self.assertIn('crm.lead', searchable)
        self.assertIn('crm.client', searchable)
        # ARC29 — le second pilote (SAV) est aplati dans la même surface.
        self.assertIn('sav.ticket', searchable)

        targets = platform.record_targets(manifests=self.manifests)
        self.assertIn('crm.lead', targets)
        self.assertIn('sav.ticket', targets)

        modules = platform.agent_actions_modules(manifests=self.manifests)
        self.assertIn('apps.crm.agent_actions', modules)


class PlatformValidationTests(SimpleTestCase):
    """Validation d'un manifeste (aucune DB)."""

    def test_unknown_surface_key_is_rejected(self):
        with self.assertRaises(platform.PlatformManifestError):
            platform._normaliser('x', {'surface_bidon': ['a']})

    def test_malformed_automation_entry_is_rejected(self):
        with self.assertRaises(platform.PlatformManifestError):
            platform._normaliser(
                'x', {'automation_state_fields': ['pas-un-dict']})

    def test_list_surfaces_are_deduped(self):
        norm = platform._normaliser(
            'x', {'searchable_models': ['a', 'a', 'b']})
        self.assertEqual(norm['searchable_models'], ['a', 'b'])


class PlatformToggleGatingTests(TestCase):
    """Gatage ModuleToggle : un module OFF disparaît de toutes les surfaces."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')

    def test_enabled_by_default_all_manifests_visible(self):
        """Sans ligne ModuleToggle, tous les manifestes sont visibles (FG391)."""
        visibles = platform.platform_manifests_for_company(self.company)
        self.assertIn('crm', visibles)
        self.assertIn('sav', visibles)

    def test_none_company_returns_all(self):
        visibles = platform.platform_manifests_for_company(None)
        self.assertIn('crm', visibles)

    def test_disabled_module_disappears_from_registry(self):
        """crm OFF pour la société → absent du registre gaté."""
        ModuleToggle.objects.create(
            company=self.company, module='crm', actif=False)
        visibles = platform.platform_manifests_for_company(self.company)
        self.assertNotIn('crm', visibles)
        # sav reste visible (pas désactivé).
        self.assertIn('sav', visibles)

    def test_disabled_module_disappears_from_every_surface(self):
        """crm OFF → ses modèles quittent recherche, chatter, agent, etc."""
        ModuleToggle.objects.create(
            company=self.company, module='crm', actif=False)
        # Recherche : plus de crm.lead.
        self.assertNotIn(
            'crm.lead', platform.searchable_models(self.company))
        # Chatter/records : plus de crm.lead ; sav.ticket reste.
        targets = platform.record_targets(self.company)
        self.assertNotIn('crm.lead', targets)
        self.assertIn('sav.ticket', targets)
        # Actions agent : plus le module CRM.
        self.assertNotIn(
            'apps.crm.agent_actions',
            platform.agent_actions_modules(self.company))
        # Automatisation : plus le couple lead/relance_date.
        self.assertNotIn(
            {'model': 'crm.lead', 'field': 'relance_date'},
            platform.automation_state_fields(self.company))
