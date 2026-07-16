"""Tests des paramètres Campagnes innovation (NTIDE7 — tab Paramètres → Avancé).

Couvre : singleton par société (créé au premier GET), PATCH partiel, audit
via ``SettingsAuditLog`` (section ``innovation``), accès réservé au palier
admin/responsable, isolation multi-société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation.models import InnovationSettings

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class InnovationSettingsTests(TestCase):
    BASE = '/api/django/innovation/parametres/'

    def setUp(self):
        self.co_a = make_company('innov-set-a', 'A')
        self.co_b = make_company('innov-set-b', 'B')
        self.admin_a = make_user(self.co_a, 'innov-set-admin', role='admin')
        self.normal_a = make_user(self.co_a, 'innov-set-normal', role='normal')

    def test_get_creates_default_singleton(self):
        resp = auth(self.admin_a).get(self.BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['campagnes_activees'])
        self.assertEqual(InnovationSettings.objects.filter(company=self.co_a).count(), 1)

    def test_get_is_idempotent(self):
        auth(self.admin_a).get(self.BASE)
        auth(self.admin_a).get(self.BASE)
        self.assertEqual(InnovationSettings.objects.filter(company=self.co_a).count(), 1)

    def test_patch_updates_fields(self):
        resp = auth(self.admin_a).patch(
            self.BASE,
            {
                'campagnes_activees': True,
                'segment_defaut': 'Commercial',
                'message_relance': 'Vos idées comptent !',
            },
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        obj = InnovationSettings.objects.get(company=self.co_a)
        self.assertTrue(obj.campagnes_activees)
        self.assertEqual(obj.segment_defaut, 'Commercial')
        self.assertEqual(obj.message_relance, 'Vos idées comptent !')

    def test_patch_logs_settings_audit(self):
        from apps.parametres.models_audit import SettingsAuditLog

        auth(self.admin_a).patch(
            self.BASE, {'campagnes_activees': True}, format='json')
        entry = SettingsAuditLog.objects.get(
            company=self.co_a, section='innovation', field='campagnes_activees')
        self.assertEqual(entry.old_value, 'False')
        self.assertEqual(entry.new_value, 'True')
        self.assertEqual(entry.user, self.admin_a)

    def test_patch_no_change_writes_no_audit(self):
        from apps.parametres.models_audit import SettingsAuditLog

        auth(self.admin_a).patch(
            self.BASE, {'campagnes_activees': False}, format='json')
        self.assertEqual(
            SettingsAuditLog.objects.filter(
                company=self.co_a, section='innovation').count(), 0)

    def test_normal_role_refused(self):
        resp = auth(self.normal_a).get(self.BASE)
        self.assertEqual(resp.status_code, 403)

    def test_settings_isolated_per_company(self):
        InnovationSettings.objects.create(
            company=self.co_b, campagnes_activees=True)
        resp = auth(self.admin_a).get(self.BASE)
        self.assertFalse(resp.data['campagnes_activees'])
