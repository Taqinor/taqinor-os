"""Tests des campagnes multi-segment (NTIDE35).

Décision NTIDE35 : « Lancer chez tous les Techniciens + tous les
Commerciaux » crée UNE campagne unique dont ``segment`` mappe la liste des
rôles — jamais une campagne par segment. Couvre : création d'une campagne
avec un ``segment`` multi-rôle via la route CRUD standard (aucune route
dédiée « bulk » nécessaire), ``users_for_campaign`` cible bien l'UNION des
segments, et ``selectors.segments_disponibles`` (données du multi-select)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import selectors
from apps.innovation.models import CampagneInnovation, ROLES_CIBLABLES
from apps.roles.models import Role

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_role(company, nom):
    role, _ = Role.objects.get_or_create(company=company, nom=nom)
    return role


def make_user(company, username, role=None, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CampagneMultiSegmentCreationTests(TestCase):
    BASE = '/api/django/innovation/campagnes/'

    def setUp(self):
        self.co_a = make_company('innov-ntide35-a', 'A')
        self.admin = make_user(self.co_a, 'ntide35-admin', role_legacy='admin')
        self.role_tech = make_role(self.co_a, 'Technicien')
        self.role_com = make_role(self.co_a, 'Commercial')
        self.tech = make_user(self.co_a, 'ntide35-tech', role=self.role_tech)
        self.com = make_user(self.co_a, 'ntide35-com', role=self.role_com)

    def test_creates_single_campaign_with_multi_role_segment(self):
        resp = auth(self.admin).post(self.BASE, {
            'nom': 'Techniciens + Commerciaux',
            'segment': ['Technicien', 'Commercial'],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            CampagneInnovation.objects.filter(
                company=self.co_a, nom='Techniciens + Commerciaux').count(),
            1)

    def test_users_for_campaign_targets_union_of_segments(self):
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Multi', segment=['Technicien', 'Commercial'])
        cibles = selectors.users_for_campaign(self.co_a, camp)
        self.assertIn(self.tech, cibles)
        self.assertIn(self.com, cibles)


class SegmentsDisponiblesTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide35-seg-a', 'A')
        self.admin = make_user(self.co_a, 'ntide35-seg-admin', role_legacy='admin')

    def test_includes_fallback_roles(self):
        segments = selectors.segments_disponibles(self.co_a)
        for role in ROLES_CIBLABLES:
            self.assertIn(role, segments)

    def test_includes_extra_role_actually_in_use(self):
        role_directeur_adjoint = make_role(self.co_a, 'Directeur Adjoint')
        make_user(self.co_a, 'ntide35-seg-user', role=role_directeur_adjoint)
        segments = selectors.segments_disponibles(self.co_a)
        self.assertIn('Directeur Adjoint', segments)

    def test_endpoint_returns_segments(self):
        resp = auth(self.admin).get(
            '/api/django/innovation/campagnes/segments-disponibles/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('Technicien', resp.data['results'])
