"""XPOS18 — Configuration matériel comptoir (imprimante réseau) : scoping."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.pos.models import ConfigMaterielPOS

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


class ConfigMaterielPOSApiTests(TestCase):
    BASE = '/api/django/pos/config-materiel/'

    def setUp(self):
        self.co_a = make_company('xpos18-cfg-a', 'A')
        self.co_b = make_company('xpos18-cfg-b', 'B')
        self.user_a = make_user(self.co_a, 'xpos18-cfg-a-user')
        self.user_b = make_user(self.co_b, 'xpos18-cfg-b-user')

    def test_create_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(
            self.BASE,
            {'imprimante_ip': '10.0.0.10', 'imprimante_active': True},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        config = ConfigMaterielPOS.objects.get(id=resp.data['id'])
        self.assertEqual(config.company_id, self.co_a.id)

    def test_company_isolation(self):
        api_a = auth(self.user_a)
        create_resp = api_a.post(
            self.BASE, {'imprimante_ip': '10.0.0.10'}, format='json')
        config_id = create_resp.data['id']

        api_b = auth(self.user_b)
        detail = api_b.get(f'{self.BASE}{config_id}/')
        self.assertEqual(detail.status_code, 404)

    def test_default_no_op_unless_active(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {'imprimante_ip': '10.0.0.10'}, format='json')
        self.assertFalse(resp.data['imprimante_active'])
