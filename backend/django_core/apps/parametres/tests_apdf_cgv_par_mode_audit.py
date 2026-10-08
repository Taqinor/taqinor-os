"""APDF23 — ``cgv_par_mode`` est journalisé (SettingsAuditLog) et versionné."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.parametres.models import SettingsAuditLog
from apps.parametres.models_documents import DocumentTemplates

User = get_user_model()
URL = '/api/django/parametres/document-templates/update/'


class CgvParModeAuditTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            slug='apdf23', nom='Apdf23 Co')
        self.user = User.objects.create_user(
            username='apdf23_admin', password='x',
            role_legacy='admin', company=self.company)
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION='Bearer %s'
                             % AccessToken.for_user(self.user))

    def _lignes(self):
        return SettingsAuditLog.objects.filter(
            company=self.company, section='documents', field='cgv_par_mode')

    def _patch(self, titre, clause):
        return self.api.patch(URL, {'cgv_par_mode': {
            'industriel': {'titre': titre, 'bullets': [clause]}}},
            format='json')

    def test_patch_journalise_et_versionne(self):
        self.assertEqual(self._patch('T', 'Clause X').status_code, 200)
        tpl = DocumentTemplates.objects.get(company=self.company)
        self.assertEqual(tpl.version, 2)
        self.assertEqual(self._lignes().count(), 1)
        self.assertEqual(self._patch('T2', 'Clause Y').status_code, 200)
        tpl.refresh_from_db()
        self.assertEqual(tpl.version, 3)
        self.assertEqual(self._lignes().count(), 2)
        derniere = self._lignes().order_by('-pk').first()
        self.assertIn('Clause X', derniere.old_value)
        self.assertIn('Clause Y', derniere.new_value)

    def test_patch_identique_sans_ligne(self):
        self._patch('T', 'Clause X')
        avant = SettingsAuditLog.objects.count()
        r = self._patch('T', 'Clause X')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(SettingsAuditLog.objects.count(), avant)
        tpl = DocumentTemplates.objects.get(company=self.company)
        self.assertEqual(tpl.version, 2)
