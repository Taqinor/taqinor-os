"""Tests du clonage de campagne (NTIDE30).

Couvre : la copie créée est TOUJOURS en brouillon (même si l'originale est
active/fermée), même segment/message/tag/cible/dates, nom suffixé
« (copie) », l'originale n'est jamais modifiée, palier Directeur/Admin,
isolation multi-société (404 cross-tenant).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation.models import CampagneInnovation

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role_legacy='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ClonerCampagneTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide30-a', 'A')
        self.co_b = make_company('innov-ntide30-b', 'B')
        self.admin_a = make_user(self.co_a, 'ntide30-admin')
        self.normal_a = make_user(self.co_a, 'ntide30-normal', role_legacy='normal')
        self.camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage', description='Détail',
            statut=CampagneInnovation.Statut.ACTIVE,
            segment=['Technicien'], cible_departement='Pompage',
            message_incitation='Parlez-nous du pompage.', tag_auto='Pompage')

    def test_clone_is_always_draft(self):
        resp = auth(self.admin_a).post(
            f'/api/django/innovation/campagnes/{self.camp.id}/cloner/')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['statut'], CampagneInnovation.Statut.BROUILLON)

    def test_clone_copies_segment_message_tag(self):
        resp = auth(self.admin_a).post(
            f'/api/django/innovation/campagnes/{self.camp.id}/cloner/')
        self.assertEqual(resp.data['segment'], ['Technicien'])
        self.assertEqual(resp.data['message_incitation'], 'Parlez-nous du pompage.')
        self.assertEqual(resp.data['tag_auto'], 'Pompage')
        self.assertEqual(resp.data['cible_departement'], 'Pompage')

    def test_clone_name_suffixed(self):
        resp = auth(self.admin_a).post(
            f'/api/django/innovation/campagnes/{self.camp.id}/cloner/')
        self.assertEqual(resp.data['nom'], 'Pompage (copie)')

    def test_original_untouched(self):
        auth(self.admin_a).post(
            f'/api/django/innovation/campagnes/{self.camp.id}/cloner/')
        self.camp.refresh_from_db()
        self.assertEqual(self.camp.statut, CampagneInnovation.Statut.ACTIVE)
        self.assertEqual(self.camp.nom, 'Pompage')

    def test_creates_a_new_row(self):
        before = CampagneInnovation.objects.filter(company=self.co_a).count()
        auth(self.admin_a).post(
            f'/api/django/innovation/campagnes/{self.camp.id}/cloner/')
        after = CampagneInnovation.objects.filter(company=self.co_a).count()
        self.assertEqual(after, before + 1)

    def test_normal_role_refused(self):
        resp = auth(self.normal_a).post(
            f'/api/django/innovation/campagnes/{self.camp.id}/cloner/')
        self.assertEqual(resp.status_code, 403)

    def test_cross_tenant_404(self):
        user_b = make_user(self.co_b, 'ntide30-b-user')
        resp = auth(user_b).post(
            f'/api/django/innovation/campagnes/{self.camp.id}/cloner/')
        self.assertEqual(resp.status_code, 404)

    def test_admin_can_rename_clone_afterwards(self):
        resp = auth(self.admin_a).post(
            f'/api/django/innovation/campagnes/{self.camp.id}/cloner/')
        clone_id = resp.data['id']
        patch_resp = auth(self.admin_a).patch(
            f'/api/django/innovation/campagnes/{clone_id}/',
            {'nom': 'Pompage v2'}, format='json')
        self.assertEqual(patch_resp.status_code, 200, patch_resp.data)
        self.assertEqual(patch_resp.data['nom'], 'Pompage v2')
