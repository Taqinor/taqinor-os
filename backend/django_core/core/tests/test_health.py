"""Tests FG397 — page d'état / santé système.

Couvre :
  * check_services renvoie au moins db + cache, db ``ok`` en test ;
  * overall_status agrège (db down → global down) ;
  * l'endpoint status renvoie global/services/incidents (auth requise) ;
  * incidents bornés à la société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import health
from core.models import BackupRun
from core.views import SystemStatusViewSet

User = get_user_model()


class HealthTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.other = Company.objects.create(nom='Autre')
        cls.user = User.objects.create_user(
            username='hl_user', password='x', role_legacy='normal',
            company=cls.company)
        cls.factory = APIRequestFactory()

    def test_check_services_db_ok(self):
        services = health.check_services()
        names = {s['name'] for s in services}
        self.assertIn('database', names)
        self.assertIn('cache', names)
        db = next(s for s in services if s['name'] == 'database')
        self.assertEqual(db['status'], health.STATUS_OK)

    def test_overall_status_down_when_db_down(self):
        services = [
            {'name': 'database', 'status': health.STATUS_DOWN, 'detail': 'x'},
            {'name': 'cache', 'status': health.STATUS_OK, 'detail': ''},
        ]
        self.assertEqual(health.overall_status(services), health.STATUS_DOWN)

    def test_overall_status_ok(self):
        services = [
            {'name': 'database', 'status': health.STATUS_OK, 'detail': ''},
            {'name': 'cache', 'status': health.STATUS_OK, 'detail': ''},
            {'name': 'broker', 'status': health.STATUS_UNKNOWN, 'detail': ''},
        ]
        self.assertEqual(health.overall_status(services), health.STATUS_OK)

    def test_status_endpoint_requires_auth(self):
        req = self.factory.get('/status/')
        resp = SystemStatusViewSet.as_view({'get': 'list'})(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_status_endpoint_shape(self):
        req = self.factory.get('/status/')
        force_authenticate(req, user=self.user)
        resp = SystemStatusViewSet.as_view({'get': 'list'})(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('global', resp.data)
        self.assertIn('services', resp.data)
        self.assertIn('incidents', resp.data)

    def test_incidents_scoped_to_company(self):
        BackupRun.objects.create(
            company=self.other, kind=BackupRun.KIND_RESTORE,
            statut=BackupRun.STATUT_NON_CONFIGURE,
            detail={'message': 'autre société'})
        incidents = health.recent_incidents(company=self.company)
        self.assertEqual(incidents, [])
