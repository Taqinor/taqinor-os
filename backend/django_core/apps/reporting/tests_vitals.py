"""VX61 — collecte des Web Vitals réels (INP/LCP/CLS/TTFB) via beacon front."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from .models import VitalMetric
from .vitals import purge_vital_metrics

User = get_user_model()

URL = '/api/django/reporting/vitals/'


class TestVitalsCollect(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='vitals-co', defaults={'nom': 'Vitals Co'})[0]
        self.other = Company.objects.create(slug='vitals-other', nom='Autre')
        self.user = User.objects.create_user(
            username='vitals_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_post_cree_une_ligne_scopee_a_la_societe(self):
        resp = self.api.post(
            URL, {'name': 'LCP', 'value': 1234.5, 'path': '/dashboard'},
            format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(VitalMetric.objects.count(), 1)
        m = VitalMetric.objects.get()
        self.assertEqual(m.name, 'LCP')
        self.assertEqual(m.value, 1234.5)
        self.assertEqual(m.path, '/dashboard')
        # Scoping société posé CÔTÉ SERVEUR depuis l'utilisateur authentifié —
        # jamais lu du corps de requête.
        self.assertEqual(m.company_id, self.company.id)

    def test_anonyme_accepte_avec_company_none(self):
        anon = APIClient()
        resp = anon.post(
            URL, {'name': 'CLS', 'value': 0.05, 'path': '/'}, format='json')
        self.assertEqual(resp.status_code, 201)
        m = VitalMetric.objects.get()
        self.assertIsNone(m.company_id)

    def test_name_invalide_rejete(self):
        resp = self.api.post(
            URL, {'name': 'BOGUS', 'value': 1, 'path': '/'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(VitalMetric.objects.count(), 0)

    def test_value_invalide_rejete(self):
        resp = self.api.post(
            URL, {'name': 'TTFB', 'value': 'not-a-number', 'path': '/'},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(VitalMetric.objects.count(), 0)

    def test_company_ne_peut_pas_etre_injectee_depuis_le_corps(self):
        # Un utilisateur authentifié qui tenterait de forcer une AUTRE société
        # dans le corps de la requête est ignoré — le scoping ne vient QUE de
        # request.user.company.
        resp = self.api.post(
            URL, {'name': 'INP', 'value': 42, 'path': '/x',
                  'company': self.other.id}, format='json')
        self.assertEqual(resp.status_code, 201)
        m = VitalMetric.objects.get()
        self.assertEqual(m.company_id, self.company.id)


class TestPurgeVitalMetrics(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='vitals-purge-co', defaults={'nom': 'Vitals Purge Co'})[0]

    def test_dry_run_ne_supprime_rien(self):
        from django.utils import timezone
        old = VitalMetric.objects.create(
            company=self.company, name='LCP', value=1.0, path='/old')
        VitalMetric.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=365))
        count = purge_vital_metrics(timezone.now(), apply_=False)
        self.assertEqual(count, 1)
        self.assertEqual(VitalMetric.objects.count(), 1)

    def test_apply_supprime_les_metriques_expirees(self):
        from django.utils import timezone
        old = VitalMetric.objects.create(
            company=self.company, name='LCP', value=1.0, path='/old')
        VitalMetric.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=365))
        recent = VitalMetric.objects.create(
            company=self.company, name='CLS', value=0.01, path='/recent')
        count = purge_vital_metrics(timezone.now(), apply_=True)
        self.assertEqual(count, 1)
        remaining = list(VitalMetric.objects.values_list('pk', flat=True))
        self.assertEqual(remaining, [recent.pk])
