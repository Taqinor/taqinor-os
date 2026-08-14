"""NTDMO25 — wizard « Créer ma société de démonstration » (3 étapes).

Le coeur testable sans UI : les options additives `--profil`/`--densite` de
`seed_demo_company` (défauts = comportement historique byte-identique) et le
endpoint console fondateur qui les déclenche."""
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from authentication.models import Company, CustomUser


@override_settings(DEBUG=True)
class SeedDemoWizardOptionsTest(TestCase):
    def test_densite_leger_creates_fewer_leads_than_complet(self):
        call_command('seed_demo_company', slug='demo-leger', densite='leger',
                     verbosity=0)
        call_command('seed_demo_company', slug='demo-complet',
                     densite='complet', verbosity=0)
        from apps.crm.models import Lead
        leger = Lead.objects.filter(company__slug='demo-leger').count()
        complet = Lead.objects.filter(company__slug='demo-complet').count()
        self.assertLess(leger, complet)
        self.assertLess(leger, 25)
        self.assertGreaterEqual(complet, 35)

    def test_profil_residentiel_only_residential_devis(self):
        call_command('seed_demo_company', slug='demo-resid',
                     profil='residentiel', densite='leger', verbosity=0)
        from apps.ventes.models import Devis
        modes = set()
        for d in Devis.objects.filter(company__slug='demo-resid'):
            modes.add((d.etude_params or {}).get('mode', 'residentiel'))
        self.assertEqual(modes, {'residentiel'})

    def test_default_options_unchanged(self):
        # Comportement historique byte-identique quand --profil/--densite
        # sont omis (mêmes seuils que le test NTDMO2/3 existant).
        call_command('seed_demo_company', verbosity=0)
        from apps.crm.models import Lead
        self.assertGreaterEqual(
            Lead.objects.filter(company__slug='taqinor-demo-full').count(),
            35)


@override_settings(DEBUG=True)
class DemoWizardEndpointTest(TestCase):
    def setUp(self):
        self.superuser = CustomUser.objects.create_superuser(
            username='fondateur-wizard', email='f@taqinor.local',
            password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.superuser)
        # Le broker Redis existe en CI mais aucun worker ne tourne : sans
        # exécution EN LIGNE (eager), `.delay()` se contente d'empiler la
        # tâche sans jamais la faire tourner — le wizard reste bloqué en
        # 'en_cours' (même patron que apps/publicapi/tests_yapic8_delivery.py).
        from erp_agentique.celery import app as celery_app
        prev = celery_app.conf.task_always_eager
        celery_app.conf.task_always_eager = True
        celery_app.conf.task_eager_propagates = False
        self.addCleanup(
            lambda: setattr(celery_app.conf, 'task_always_eager', prev))

    def test_non_superuser_forbidden(self):
        normal = CustomUser.objects.create(
            username='normal-wizard', email='n@taqinor.local')
        self.client.force_authenticate(normal)
        resp = self.client.post(
            '/api/django/auth/demo-wizard/',
            {'slug': 'demo-wizard-x', 'profil': 'mixte', 'densite': 'leger'},
            format='json')
        self.assertEqual(resp.status_code, 403)

    def test_superuser_triggers_creation(self):
        resp = self.client.post(
            '/api/django/auth/demo-wizard/',
            {'slug': 'demo-wizard-ok', 'profil': 'mixte', 'densite': 'leger'},
            format='json')
        self.assertIn(resp.status_code, (200, 202))
        self.assertTrue(Company.objects.filter(slug='demo-wizard-ok').exists())

    def test_status_endpoint_reports_termine(self):
        self.client.post(
            '/api/django/auth/demo-wizard/',
            {'slug': 'demo-wizard-status', 'profil': 'mixte',
             'densite': 'leger'}, format='json')
        resp = self.client.get(
            '/api/django/auth/demo-wizard/statut/',
            {'slug': 'demo-wizard-status'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], 'termine')
