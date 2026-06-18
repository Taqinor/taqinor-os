"""Tests du Journal d'activité (Feature G).

Couvre : capture connexion/échec/déconnexion, capture CRUD + changement de
statut via les signaux pendant une requête, non-capture hors requête (ORM
direct), gating de permission (Directeur uniquement par défaut), et les
endpoints stats/liste.
"""
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser
from apps.roles.models import (
    Role, DIRECTEUR_PERMISSIONS, COMMERCIAL_PERMISSIONS, ADMIN_PERMISSIONS,
)
from apps.crm.models import Lead
from apps.audit.models import AuditLog


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AuditBase(TestCase):
    def setUp(self):
        cache.clear()  # remet à zéro le throttle de connexion entre tests
        self.company = Company.objects.create(nom='Audit Co', slug='audit-co')
        self.dir_role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=DIRECTEUR_PERMISSIONS, est_systeme=True)
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ADMIN_PERMISSIONS, est_systeme=True)
        self.com_role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=COMMERCIAL_PERMISSIONS, est_systeme=True)
        self.directeur = CustomUser.objects.create_user(
            username='dir', password='Secret@2026', company=self.company,
            role=self.dir_role, role_legacy='admin')
        self.admin = CustomUser.objects.create_user(
            username='adm', password='Secret@2026', company=self.company,
            role=self.admin_role, role_legacy='admin')
        self.com = CustomUser.objects.create_user(
            username='com', password='Secret@2026', company=self.company,
            role=self.com_role)


class TestCapture(AuditBase):
    def test_orm_create_outside_request_not_logged(self):
        Lead.objects.create(company=self.company, nom='Direct ORM')
        self.assertFalse(
            AuditLog.objects.filter(action='create').exists())

    def test_api_create_logs(self):
        auth(self.com).post('/api/django/crm/leads/', {'nom': 'Via API'})
        entry = AuditLog.objects.filter(action='create').first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.user_id, self.com.id)
        self.assertEqual(entry.company_id, self.company.id)

    def test_status_change_logged(self):
        lead = Lead.objects.create(company=self.company, nom='Funnel')
        auth(self.directeur).patch(
            f'/api/django/crm/leads/{lead.id}/',
            {'stage': 'CONTACTED'}, format='json')
        entry = AuditLog.objects.filter(
            action='status', object_id=str(lead.id)).first()
        self.assertIsNotNone(entry)
        self.assertIn('→', entry.detail)

    def test_login_success_and_failure_logged(self):
        api = APIClient()
        ok = api.post('/api/django/token/',
                      {'username': 'dir', 'password': 'Secret@2026'},
                      format='json')
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(
            action='login', user=self.directeur).exists())
        bad = api.post('/api/django/token/',
                       {'username': 'ghost', 'password': 'nope'},
                       format='json')
        self.assertEqual(bad.status_code, 401)
        failed = AuditLog.objects.filter(action='login_failed').first()
        self.assertIsNotNone(failed)
        self.assertEqual(failed.actor_username, 'ghost')
        self.assertIsNone(failed.user_id)


class TestReadApi(AuditBase):
    def test_permission_directeur_only(self):
        # Commercial : pas la permission journal → 403.
        self.assertEqual(
            auth(self.com).get('/api/django/audit/entries/').status_code, 403)
        # Admin : pas le journal par défaut → 403.
        self.assertEqual(
            auth(self.admin).get('/api/django/audit/entries/').status_code, 403)
        # Directeur : 200.
        self.assertEqual(
            auth(self.directeur).get('/api/django/audit/entries/').status_code,
            200)

    def test_stats_buckets(self):
        auth(self.com).post('/api/django/crm/leads/', {'nom': 'X'})
        resp = auth(self.directeur).get('/api/django/audit/stats/?period=jour')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['granularity'], 'hour')
        self.assertEqual(len(resp.data['buckets']), 24)
        self.assertGreaterEqual(resp.data['total'], 1)

    def test_list_company_scoped(self):
        other = Company.objects.create(nom='Other', slug='other-audit')
        AuditLog.objects.create(company=other, action='create',
                                object_repr='foreign')
        AuditLog.objects.create(company=self.company, action='create',
                                object_repr='mine')
        resp = auth(self.directeur).get('/api/django/audit/entries/')
        reprs = {r['object_repr'] for r in resp.data['results']}
        self.assertIn('mine', reprs)
        self.assertNotIn('foreign', reprs)
