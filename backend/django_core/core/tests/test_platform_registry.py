"""Tests ARC28 — collecteur du registre plateforme (``core.platform``).

Couvre :
  * la découverte GÉNÉRIQUE des manifestes ``apps/<x>/platform.py`` (les deux
    pilotes crm + contrats sont bien collectés) ;
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
        """Les deux pilotes crm + contrats sont collectés génériquement."""
        self.assertIn('crm', self.manifests)
        self.assertIn('contrats', self.manifests)

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

    def test_contrats_manifest_is_asymmetric(self):
        """Contrats a le chatter (ARC8), la recherche (ARC29), les champs
        perso (ARC31), les actions agent LECTURE (ARC33), l'import (ARC32)
        et l'automation de statut (ARC34) câblés — seule la surface KPI
        reste VIDE : le collecteur tolère un manifeste partiel/asymétrique."""
        contrats = self.manifests['contrats']
        self.assertEqual(contrats['record_targets'], ['contrats.contrat'])
        # ARC29 — trou comblé : Contrat est désormais cherchable.
        self.assertEqual(contrats['searchable_models'], ['contrats.contrat'])
        # ARC31 — cible customfieldable déclarée au manifeste (source du
        # registre customfields, plus un register() dans ready()).
        self.assertEqual(contrats['customfield_models'], ['contrat'])
        # ARC33 — actions agent LECTURE seule désormais déclarées.
        self.assertEqual(
            contrats['agent_actions_module'], 'apps.contrats.agent_actions')
        # ARC32 — trou comblé : Contrat est désormais une cible d'import.
        self.assertEqual(contrats['import_specs'], ['contrats'])
        # ARC34 — trou comblé : statut Contrat automatisable (RECORD_STATE_CHANGE).
        self.assertEqual(
            contrats['automation_state_fields'],
            [{'model': 'contrats.contrat', 'field': 'statut'}])
        # Surface DÉLIBÉRÉMENT vide (asymétrie préservée) : le collecteur
        # tolère un manifeste où seules certaines surfaces sont câblées.
        self.assertEqual(contrats['kpi_providers'], [])

    def test_aggregators_flatten_across_manifests(self):
        """Les agrégateurs aplatissent bien les surfaces (via manifests fournis)."""
        searchable = platform.searchable_models(manifests=self.manifests)
        self.assertIn('crm.lead', searchable)
        self.assertIn('crm.client', searchable)
        # ARC29 — trou comblé : Contrat est désormais cherchable.
        self.assertIn('contrats.contrat', searchable)

        targets = platform.record_targets(manifests=self.manifests)
        self.assertIn('crm.lead', targets)
        self.assertIn('contrats.contrat', targets)

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
        self.assertIn('contrats', visibles)

    def test_none_company_returns_all(self):
        visibles = platform.platform_manifests_for_company(None)
        self.assertIn('crm', visibles)

    def test_disabled_module_disappears_from_registry(self):
        """crm OFF pour la société → absent du registre gaté."""
        ModuleToggle.objects.create(
            company=self.company, module='crm', actif=False)
        visibles = platform.platform_manifests_for_company(self.company)
        self.assertNotIn('crm', visibles)
        # contrats reste visible (pas désactivé).
        self.assertIn('contrats', visibles)

    def test_disabled_module_disappears_from_every_surface(self):
        """crm OFF → ses modèles quittent recherche, chatter, agent, etc."""
        ModuleToggle.objects.create(
            company=self.company, module='crm', actif=False)
        # Recherche : plus de crm.lead.
        self.assertNotIn(
            'crm.lead', platform.searchable_models(self.company))
        # Chatter/records : plus de crm.lead ; contrats.contrat reste.
        targets = platform.record_targets(self.company)
        self.assertNotIn('crm.lead', targets)
        self.assertIn('contrats.contrat', targets)
        # Actions agent : plus le module CRM.
        self.assertNotIn(
            'apps.crm.agent_actions',
            platform.agent_actions_modules(self.company))
        # Automatisation : plus le couple lead/relance_date.
        self.assertNotIn(
            {'model': 'crm.lead', 'field': 'relance_date'},
            platform.automation_state_fields(self.company))
