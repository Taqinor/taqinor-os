"""Tests gestion employés (admin) : poste, avatar, mot de passe.

L'upload réel de la photo passe par MinIO (boto3) — même chemin éprouvé que
le logo d'entreprise. On teste ici la surface API (édition du poste, garde
admin, validation d'upload, réinitialisation de mot de passe), sans dépendre
du conteneur objet pour rester hermétique.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role, ALL_PERMISSIONS

User = get_user_model()


class TestEmployeeAdmin(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Emp Co', slug='emp-co')
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True,
        )
        self.admin = User.objects.create_user(
            username='emp_admin', password='x', role=self.admin_role,
            role_legacy='admin', company=self.company,
        )
        self.employee = User.objects.create_user(
            username='emp_one', password='oldpass', role_legacy='normal',
            company=self.company,
        )
        self.api = APIClient()
        token = str(AccessToken.for_user(self.admin))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_admin_can_edit_poste(self):
        resp = self.api.patch(
            f'/api/django/users/{self.employee.id}/',
            {'poste': 'Commerciale'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.poste, 'Commerciale')
        self.assertEqual(resp.data['poste'], 'Commerciale')

    def test_admin_can_set_new_password(self):
        resp = self.api.patch(
            f'/api/django/users/{self.employee.id}/',
            {'password': 'brandnew123'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.check_password('brandnew123'))
        # Le mot de passe n'est jamais renvoyé en clair.
        self.assertNotIn('password', resp.data)

    def test_avatar_key_not_writable_via_patch(self):
        resp = self.api.patch(
            f'/api/django/users/{self.employee.id}/',
            {'avatar_key': 'avatars/forged.png'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.avatar_key, '')

    def test_avatar_upload_requires_file(self):
        resp = self.api.post(
            f'/api/django/users/{self.employee.id}/avatar/', {}, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_avatar_endpoint_is_admin_only(self):
        commerciale = User.objects.create_user(
            username='emp_comm', password='x', role_legacy='responsable',
            company=self.company,
        )
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(commerciale)}')
        resp = api.post(
            f'/api/django/users/{self.employee.id}/avatar/', {}, format='multipart')
        self.assertEqual(resp.status_code, 403)

    def test_user_serializer_exposes_avatar_url_field(self):
        resp = self.api.get(f'/api/django/users/{self.employee.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('avatar_url', resp.data)
        self.assertIn('poste', resp.data)
