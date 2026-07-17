"""ADSDEEP9 — Tests de l'endpoint breakdowns : 200 + filtres, permission
adsengine_view requise, isolation société (id d'une autre société → 404).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import sync
from apps.adsengine.models import InsightBreakdown

User = get_user_model()
URL = '/api/django/adsengine/breakdowns/'


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class BreakdownsApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='BK Co', slug='bkapi')
        self.viewer = make_user(self.company, 'viewer', ['adsengine_view'])
        self.camp = sync.sync_campaigns(self.company, [{'id': 'c1'}])[0]
        for dim, key in (('age_gender', '25-34/f'), ('region', 'Casablanca')):
            InsightBreakdown.upsert(
                self.company, self.camp, date=datetime.date(2026, 7, 16),
                dimension=dim, key=key, spend='5', impressions=50)

    def test_list_ok(self):
        resp = auth(self.viewer).get(
            URL, {'object_type': 'campaign', 'object_id': self.camp.pk})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 2)

    def test_dimension_filter(self):
        resp = auth(self.viewer).get(URL, {
            'object_type': 'campaign', 'object_id': self.camp.pk,
            'dimension': 'region'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['key'], 'Casablanca')

    def test_requires_view_permission(self):
        nobody = make_user(self.company, 'nobody', [])
        resp = auth(nobody).get(
            URL, {'object_type': 'campaign', 'object_id': self.camp.pk})
        self.assertEqual(resp.status_code, 403)

    def test_missing_params_400(self):
        resp = auth(self.viewer).get(URL, {'object_type': 'campaign'})
        self.assertEqual(resp.status_code, 400)

    def test_cross_company_object_is_404(self):
        other = Company.objects.create(nom='BK B', slug='bkb-api')
        other_camp = sync.sync_campaigns(other, [{'id': 'c1'}])[0]
        # Viewer de company A demande l'objet de company B → 404 (pas de fuite).
        resp = auth(self.viewer).get(
            URL, {'object_type': 'campaign', 'object_id': other_camp.pk})
        self.assertEqual(resp.status_code, 404)
