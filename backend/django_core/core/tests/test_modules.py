"""Tests ODX2 — collecte et validation des manifests de modules.

Couvre :
  * chaque app installée sous ``apps/`` (+ core/authentication) porte un
    ``module_manifest`` collecté ;
  * chaque ``depends`` pointe vers un manifest existant ;
  * pas de clé dupliquée ;
  * pas de cycle ;
  * la validation lève sur graphe invalide (dépendance manquante, cycle).
"""
from django.apps import apps as django_apps
from django.test import TestCase

from core import modules


class ManifestCollectionTests(TestCase):
    def test_collect_returns_full_graph(self):
        manifests = modules.collect_manifests()
        # Un échantillon de clés attendues est présent.
        for key in ('stock', 'crm', 'ventes', 'sav', 'rh', 'compta', 'core'):
            self.assertIn(key, manifests)
        # Chaque entrée normalisée porte les champs attendus.
        for key, m in manifests.items():
            self.assertEqual(m['key'], key)
            self.assertTrue(m['label'])
            self.assertIsInstance(m['depends'], list)
            self.assertIsInstance(m['installable'], bool)
            self.assertIn(m['categorie'], modules.CATEGORIES)

    def test_every_installed_app_has_a_manifest(self):
        # Toute app sous ``apps.`` (+ core/authentication) déclare un manifest.
        manque = []
        for app_config in django_apps.get_app_configs():
            name = app_config.name
            fondation = name in ('core', 'authentication')
            if not (name.startswith('apps.') or fondation):
                continue
            if not getattr(app_config, 'module_manifest', None):
                manque.append(app_config.label)
        self.assertEqual(manque, [], f'apps sans manifest : {manque}')

    def test_dependencies_exist(self):
        manifests = modules.collect_manifests()
        for key, m in manifests.items():
            for dep in m['depends']:
                self.assertIn(
                    dep, manifests,
                    f'« {key} » dépend de « {dep} » sans manifest.')

    def test_no_duplicate_keys(self):
        manifests = modules.collect_manifests()
        keys = [m['key'] for m in manifests.values()]
        self.assertEqual(len(keys), len(set(keys)))

    def test_graph_validates(self):
        # Le graphe réel est valide (pas de cycle, deps existantes).
        modules.valider_graphe()

    def test_foundation_apps_not_installable(self):
        manifests = modules.collect_manifests()
        for key in ('core', 'authentication', 'roles', 'records',
                    'customfields', 'parametres'):
            self.assertFalse(
                manifests[key]['installable'],
                f'« {key} » (fondation) devrait être installable=False.')


class ManifestValidationTests(TestCase):
    def test_missing_dependency_raises(self):
        graphe = {
            'a': {'key': 'a', 'depends': ['manquant'], 'app_label': 'a'},
        }
        with self.assertRaises(modules.ManifestError):
            modules.valider_graphe(graphe)

    def test_cycle_raises(self):
        graphe = {
            'a': {'key': 'a', 'depends': ['b'], 'app_label': 'a'},
            'b': {'key': 'b', 'depends': ['a'], 'app_label': 'b'},
        }
        with self.assertRaises(modules.ManifestError):
            modules.valider_graphe(graphe)

    def test_dependency_closure(self):
        graphe = {
            'a': {'key': 'a', 'depends': ['b'], 'app_label': 'a'},
            'b': {'key': 'b', 'depends': ['c'], 'app_label': 'b'},
            'c': {'key': 'c', 'depends': [], 'app_label': 'c'},
        }
        self.assertEqual(modules.dependency_closure('a', graphe), {'b', 'c'})

    def test_dependents(self):
        graphe = {
            'a': {'key': 'a', 'depends': ['b'], 'app_label': 'a'},
            'b': {'key': 'b', 'depends': [], 'app_label': 'b'},
        }
        self.assertEqual(modules.dependents('b', graphe), {'a'})
