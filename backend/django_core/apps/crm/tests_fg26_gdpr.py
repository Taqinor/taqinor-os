"""FG26 — outillage RGPD : export d'accès du sujet + anonymisation client."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role, ADMIN_PERMISSIONS, COMMERCIAL_PERMISSIONS
from apps.crm.models import Client

User = get_user_model()


def _company(slug='fg26-co', nom='FG26 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class FG26GdprTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=list(ADMIN_PERMISSIONS), est_systeme=True)
        self.comm_role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS))
        self.admin = User.objects.create_user(
            username='fg26_admin', password='pw', role_legacy='admin',
            role=self.admin_role, company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Jean Soleil',
            email='jean@example.com', telephone='0612345678',
            adresse='1 rue X', cin='AB12345')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def test_data_export_returns_subject_bundle(self):
        r = self.api.get(
            f'/api/django/crm/clients/{self.client_obj.id}/data-export/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['identite']['email'], 'jean@example.com')
        self.assertIn('documents', r.data)

    def test_anonymize_scrubs_pii(self):
        r = self.api.post(
            f'/api/django/crm/clients/{self.client_obj.id}/anonymize/')
        self.assertEqual(r.status_code, 200, r.content)
        self.client_obj.refresh_from_db()
        self.assertTrue(self.client_obj.is_anonymized)
        self.assertIsNone(self.client_obj.email)
        self.assertIsNone(self.client_obj.telephone)
        self.assertIsNone(self.client_obj.cin)
        self.assertNotEqual(self.client_obj.nom, 'Jean Soleil')
        self.assertIsNotNone(self.client_obj.anonymized_at)

    def test_anonymize_idempotent_guard(self):
        self.api.post(
            f'/api/django/crm/clients/{self.client_obj.id}/anonymize/')
        r = self.api.post(
            f'/api/django/crm/clients/{self.client_obj.id}/anonymize/')
        self.assertEqual(r.status_code, 400, r.content)

    def test_anonymize_requires_admin(self):
        comm = User.objects.create_user(
            username='fg26_comm', password='pw', role_legacy='responsable',
            role=self.comm_role, company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(comm)}')
        r = api.post(
            f'/api/django/crm/clients/{self.client_obj.id}/anonymize/')
        self.assertEqual(r.status_code, 403)
