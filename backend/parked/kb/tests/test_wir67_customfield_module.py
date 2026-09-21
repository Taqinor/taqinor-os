"""WIR67 — le module ``kb_article`` est enregistré comme cible customfieldable.

Prouve que :
* le manifeste plateforme KB déclare ``kb_article`` dans ``customfield_models`` ;
* le chargeur central ``customfields.registry`` le voit comme enregistré
  (``is_registered('kb_article')``) après ``register_from_platform_manifests`` ;
* une ``CustomFieldDef`` de module ``kb_article`` passe
  ``CustomFieldDefSerializer.validate_module`` (« Done = une définition
  kb_article passe la validation »).
"""
from django.test import TestCase

from apps.customfields import registry
from apps.customfields.serializers import CustomFieldDefSerializer
from apps.kb.platform import PLATFORM


class Wir67CustomfieldModuleTests(TestCase):
    def test_manifest_declares_kb_article(self):
        self.assertIn('kb_article', PLATFORM['customfield_models'])

    def test_registry_registers_kb_article(self):
        # Idempotent : le chargeur central peut être ré-appelé sans risque.
        registry.register_from_platform_manifests()
        self.assertTrue(registry.is_registered('kb_article'))
        self.assertIn('kb_article', registry.registered_module_keys())

    def test_serializer_accepts_kb_article_module(self):
        registry.register_from_platform_manifests()
        ser = CustomFieldDefSerializer()
        self.assertEqual(ser.validate_module('kb_article'), 'kb_article')
