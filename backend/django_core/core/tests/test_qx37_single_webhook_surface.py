"""QX37 — une seule surface d'abonnement webhook (publicapi).

Le doublon mort ``core.WebhookSubscription`` / ``core.webhooks`` a été supprimé.
Ces tests garantissent qu'il ne réapparaît pas et que la couche vivante
``apps.publicapi`` reste la surface unique.
"""
from django.apps import apps
from django.test import SimpleTestCase


class Qx37DeadWebhookRemovedTests(SimpleTestCase):
    def test_core_webhooksubscription_model_is_gone(self):
        with self.assertRaises(LookupError):
            apps.get_model('core', 'WebhookSubscription')

    def test_core_webhooks_module_is_gone(self):
        with self.assertRaises(ImportError):
            __import__('core.webhooks', fromlist=['dispatch_event'])

    def test_publicapi_remains_the_single_webhook_surface(self):
        # La couche vivante existe toujours. Résolution DYNAMIQUE (importlib) :
        # ``core`` ne doit jamais IMPORTER statiquement ``apps.publicapi``
        # (contrat import-linter « core-foundation-is-a-base-layer »).
        import importlib
        self.assertIsNotNone(apps.get_model('publicapi', 'Webhook'))
        delivery = importlib.import_module('apps.publicapi.delivery')
        self.assertTrue(hasattr(delivery, 'dispatch_event'))
