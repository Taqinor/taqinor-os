"""Tests ODX21 — cohérence du registre de modules (garde CI légère).

Verrouille le contrat du registre côté backend (le pendant Python du script
``scripts/check_modules.py`` qui, lui, corrèle aussi le frontend) :

  (a) chaque app installée sous ``apps/`` (+ core/authentication) expose un
      ``module_manifest`` valide (clé non vide) ;
  (b) chaque clé ``depends`` pointe vers un manifest existant ;
  (c) aucune clé dupliquée ;
  (d) le graphe est sans cycle ;
  (e) une clé ``ModuleToggle`` créée en base correspond à une clé de manifest.

Rouge si on ajoute une app sans manifest ; vert sur l'état courant.
"""
from django.apps import apps as django_apps
from django.test import TestCase

from authentication.models import Company
from core import modules
from core.models import ModuleToggle


class ModuleRegistryContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manifests = modules.collect_manifests()

    def test_every_installed_app_declares_a_manifest(self):
        manque = []
        for app_config in django_apps.get_app_configs():
            name = app_config.name
            fondation = name in ('core', 'authentication')
            if not (name.startswith('apps.') or fondation):
                continue
            if not getattr(app_config, 'module_manifest', None):
                manque.append(app_config.label)
        self.assertEqual(manque, [], f'apps sans manifest : {manque}')

    def test_keys_non_empty(self):
        for key, m in self.manifests.items():
            self.assertTrue(key)
            self.assertEqual(m['key'], key)

    def test_dependencies_resolve(self):
        for key, m in self.manifests.items():
            for dep in m['depends']:
                self.assertIn(dep, self.manifests,
                              f'{key} → dépendance inconnue {dep}')

    def test_no_duplicate_keys(self):
        keys = [m['key'] for m in self.manifests.values()]
        self.assertEqual(len(keys), len(set(keys)))

    def test_graph_has_no_cycle(self):
        modules.valider_graphe(self.manifests)

    def test_module_toggle_key_is_a_manifest_key(self):
        company = Company.objects.create(nom='ACME')
        # Une clé de manifest est acceptée et corrélée.
        toggle = ModuleToggle.objects.create(
            company=company, module='flotte', actif=False)
        self.assertIn(toggle.module, self.manifests)
        # Toute clé ModuleToggle présente en base doit être une clé connue.
        for key in ModuleToggle.objects.values_list('module', flat=True):
            self.assertIn(
                key, self.manifests,
                f'ModuleToggle « {key} » ne correspond à aucun manifest.')
