"""PUB49 — Annotations de courbe (notes de décision épinglées à une date).

Prouve : CRUD company-scopé (``company`` posée côté serveur, jamais lue du
corps), isolation multi-tenant, et une note posée est bien exposée (le rendu en
surimpression est côté front — lane console).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine.models import Annotation

User = get_user_model()

BASE = '/api/django/adsengine/annotations/'


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


def rows(resp):
    data = resp.data
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


class AnnotationCrudTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Ann Co', slug='ann-co')
        self.user = make_user(
            self.company, 'ann_mgr',
            ['adsengine_view', 'adsengine_manage'])

    def test_create_forces_company_server_side(self):
        other = Company.objects.create(nom='Ann B', slug='ann-b')
        resp = auth(self.user).post(BASE, {
            'date': '2026-03-01',
            'texte': 'Budget baissé ici — Ramadan',
            'portee': 'dashboard',
            'company': other.id,  # tentative d'injection — ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ann = Annotation.objects.get(id=resp.data['id'])
        self.assertEqual(ann.company_id, self.company.id)
        self.assertEqual(ann.texte, 'Budget baissé ici — Ramadan')
        self.assertEqual(ann.portee, 'dashboard')

    def test_default_portee_is_globale(self):
        resp = auth(self.user).post(BASE, {
            'date': '2026-03-01', 'texte': 'Note'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['portee'], 'globale')

    def test_list_returns_posted_annotation(self):
        Annotation.objects.create(
            company=self.company, date='2026-03-01', texte='Ramadan',
            portee=Annotation.Portee.REPORTING)
        listing = auth(self.user).get(BASE)
        self.assertEqual(listing.status_code, 200)
        data = rows(listing)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['texte'], 'Ramadan')

    def test_delete_annotation(self):
        ann = Annotation.objects.create(
            company=self.company, date='2026-03-01', texte='X')
        resp = auth(self.user).delete(f'{BASE}{ann.id}/')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Annotation.objects.filter(id=ann.id).exists())

    def test_tenant_isolation(self):
        Annotation.objects.create(
            company=self.company, date='2026-03-01', texte='A only')
        other = Company.objects.create(nom='Ann C', slug='ann-c')
        user_b = make_user(
            other, 'ann_b', ['adsengine_view', 'adsengine_manage'])
        listing = auth(user_b).get(BASE)
        self.assertEqual(rows(listing), [])
