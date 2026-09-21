"""Tests de la géolocalisation des idées liées à un chantier (NTIDE55).

Couvre : ``selectors.idees_geolocalisees`` (lecture du GPS via
``apps.installations.selectors.installation_gps_map`` — jamais un import
direct d'``Installation``), une idée liée à un chantier SANS GPS est
absente, brouillons/masquées exclues, isolation multi-société, endpoint
``GET /api/django/innovation/idees/geolocalisation/`` (palier admin seul).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import selectors
from apps.innovation.models import Idee
from apps.installations.models_installation import Installation

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class IdeesGeolocaliseesSelectorTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide55-a', 'A')
        self.co_b = make_company('innov-ntide55-b', 'B')

    def test_idee_liee_a_chantier_avec_gps(self):
        chantier = Installation.objects.create(
            company=self.co_a, reference='INST-1',
            gps_lat=33.573110, gps_lng=-7.589843)
        Idee.objects.create(
            company=self.co_a, titre='Idée géolocalisée',
            linked_type=Idee.LinkedType.CHANTIER, linked_id=chantier.id)
        data = selectors.idees_geolocalisees(self.co_a)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['titre'], 'Idée géolocalisée')
        self.assertEqual(float(data[0]['gps_lat']), 33.573110)

    def test_idee_liee_sans_gps_absente(self):
        chantier = Installation.objects.create(
            company=self.co_a, reference='INST-2')
        Idee.objects.create(
            company=self.co_a, titre='Sans GPS',
            linked_type=Idee.LinkedType.CHANTIER, linked_id=chantier.id)
        self.assertEqual(selectors.idees_geolocalisees(self.co_a), [])

    def test_idee_non_liee_a_chantier_absente(self):
        Idee.objects.create(
            company=self.co_a, titre='Idée simple',
            linked_type=Idee.LinkedType.DEVIS, linked_id=42)
        self.assertEqual(selectors.idees_geolocalisees(self.co_a), [])

    def test_draft_excluded(self):
        chantier = Installation.objects.create(
            company=self.co_a, reference='INST-3', gps_lat=1, gps_lng=1)
        Idee.objects.create(
            company=self.co_a, titre='Brouillon', draft=True,
            linked_type=Idee.LinkedType.CHANTIER, linked_id=chantier.id)
        self.assertEqual(selectors.idees_geolocalisees(self.co_a), [])

    def test_archived_excluded(self):
        chantier = Installation.objects.create(
            company=self.co_a, reference='INST-4', gps_lat=1, gps_lng=1)
        Idee.objects.create(
            company=self.co_a, titre='Masquée', archived=True,
            linked_type=Idee.LinkedType.CHANTIER, linked_id=chantier.id)
        self.assertEqual(selectors.idees_geolocalisees(self.co_a), [])

    def test_isolated_per_company(self):
        chantier_b = Installation.objects.create(
            company=self.co_b, reference='INST-B', gps_lat=1, gps_lng=1)
        Idee.objects.create(
            company=self.co_b, titre='Chez B',
            linked_type=Idee.LinkedType.CHANTIER, linked_id=chantier_b.id)
        self.assertEqual(selectors.idees_geolocalisees(self.co_a), [])


class GeolocalisationApiTests(TestCase):
    BASE = '/api/django/innovation/idees/geolocalisation/'

    def setUp(self):
        self.co_a = make_company('innov-ntide55-api-a', 'A')
        self.admin_a = make_user(self.co_a, 'ntide55-api-admin', role='admin')
        self.normal_a = make_user(self.co_a, 'ntide55-api-normal')

    def test_admin_can_view(self):
        chantier = Installation.objects.create(
            company=self.co_a, reference='INST-5', gps_lat=1, gps_lng=1)
        Idee.objects.create(
            company=self.co_a, titre='X',
            linked_type=Idee.LinkedType.CHANTIER, linked_id=chantier.id)
        resp = auth(self.admin_a).get(self.BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['results']), 1)

    def test_normal_role_refused(self):
        resp = auth(self.normal_a).get(self.BASE)
        self.assertEqual(resp.status_code, 403)
