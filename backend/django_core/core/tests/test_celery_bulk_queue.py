"""NTPLT27 — la 4e queue `bulk` est bien déclarée dans CELERY_TASK_ROUTES."""
from fnmatch import fnmatch

from django.conf import settings
from django.test import SimpleTestCase


class BulkQueueRoutingTests(SimpleTestCase):
    def test_bulk_glob_routes_present(self):
        routes = settings.CELERY_TASK_ROUTES
        bulk_patterns = [k for k, v in routes.items()
                         if v.get('queue') == 'bulk']
        self.assertTrue(bulk_patterns, "Aucune route vers la queue bulk.")
        # Les familles de tâches de masse doivent matcher un motif bulk.
        for name in ('crm.import_leads', 'stock.backfill_mouvements',
                     'core.seed_scale', 'reporting.export_bulk_devis'):
            self.assertTrue(
                any(fnmatch(name, pat) for pat in bulk_patterns),
                f"{name} devrait être routé sur bulk.")

    def test_existing_tasks_not_rerouted_to_bulk(self):
        # Un nom existant type interactif ne doit PAS tomber sur bulk.
        routes = settings.CELERY_TASK_ROUTES
        bulk_patterns = [k for k, v in routes.items()
                         if v.get('queue') == 'bulk']
        self.assertFalse(
            any(fnmatch('ventes.generate_devis_pdf', p) for p in bulk_patterns))
