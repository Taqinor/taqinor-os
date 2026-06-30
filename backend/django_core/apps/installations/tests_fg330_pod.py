"""
FG330 — Preuve de livraison (POD).

Couvre :
  * création : société/`created_by` posés serveur ; `horodatage` posé serveur ;
  * une livraison d'une autre société rejetée ;
  * une seule preuve par livraison (OneToOne) ;
  * scope société + barrière de rôle.

Run :
    python manage.py test apps.installations.tests_fg330_pod -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import (
    Installation, Livraison, PreuveLivraison,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg330-co-{n}', defaults={'nom': nom or f'FG330 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg330-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_installation(company, ref='PD1'):
    client = Client.objects.create(
        company=company, nom='Client', prenom='Test',
        email=f'pd-{company.id}-{ref}@example.invalid')
    return Installation.objects.create(
        company=company, reference=ref, client=client,
        statut=Installation.Statut.RECEPTIONNE,
        type_installation='residentiel',
        puissance_installee_kwc=Decimal('6.5'))


def make_livraison(company, ref='LIV-T'):
    inst = make_installation(company, ref=f'I{ref}')
    return Livraison.objects.create(
        company=company, installation=inst, reference=ref)


class TestPreuveLivraison(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.liv = make_livraison(self.company)

    def test_create_sets_company_and_horodatage(self):
        resp = self.api.post(f'{BASE}/preuves-livraison/', {
            'livraison': self.liv.id, 'signataire_nom': 'M. Client',
            'gps_lat': '33.589886', 'gps_lng': '-7.603869', 'company': 999,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        pod = PreuveLivraison.objects.get(id=resp.data['id'])
        self.assertEqual(pod.company_id, self.company.id)
        self.assertEqual(pod.created_by_id, self.user.id)
        self.assertIsNotNone(pod.horodatage)

    def test_livraison_other_company_rejected(self):
        other = make_company()
        liv_other = make_livraison(other, ref='LIV-O')
        resp = self.api.post(f'{BASE}/preuves-livraison/', {
            'livraison': liv_other.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_one_pod_per_livraison(self):
        PreuveLivraison.objects.create(
            company=self.company, livraison=self.liv,
            signataire_nom='Premier')
        resp = self.api.post(f'{BASE}/preuves-livraison/', {
            'livraison': self.liv.id, 'signataire_nom': 'Doublon',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)


class TestScopingAndRoles(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other = make_company()
        self.liv = make_livraison(self.company)

    def test_commercial_cannot_write(self):
        api = auth(make_user(self.company, role='commercial'))
        resp = api.post(f'{BASE}/preuves-livraison/', {
            'livraison': self.liv.id,
        }, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_other_company_cannot_see(self):
        PreuveLivraison.objects.create(
            company=self.company, livraison=self.liv, signataire_nom='X')
        api = auth(make_user(self.other))
        resp = api.get(f'{BASE}/preuves-livraison/')
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 0)
