"""Tests FG193 — Primes & indemnités (référentiel + attribution).

Couvre :
* TypePrime : création ``company`` posée CÔTÉ SERVEUR, (company, code) unique.
* PrimeAttribuee : création company posée serveur ; montant par défaut repris
  du type si absent ; FK type_prime/employe d'une autre société refusés ;
  validation mois ; action ``valider`` (idempotente, 404 autre tenant).
* Filtres + isolation + permission (rôle normal 403).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import DossierEmploye, PrimeAttribuee, TypePrime

User = get_user_model()

TYPE_URL = '/api/django/rh/types-prime/'
PRIME_URL = '/api/django/rh/primes-attribuees/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='N', prenom='P')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class TypePrimeTests(TestCase):
    def setUp(self):
        self.co_a = make_company('tp-a', 'A')
        self.user_a = make_user(self.co_a, 'tp-user-a')

    def test_create_company_cote_serveur(self):
        resp = auth(self.user_a).post(TYPE_URL, {
            'code': 'PANIER', 'libelle': 'Panier', 'nature': 'indemnite',
            'montant_defaut': '30.00',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        tp = TypePrime.objects.get(id=resp.data['id'])
        self.assertEqual(tp.company, self.co_a)

    def test_code_unique_par_societe(self):
        TypePrime.objects.create(
            company=self.co_a, code='PANIER', libelle='Panier')
        with self.assertRaises(IntegrityError):
            TypePrime.objects.create(
                company=self.co_a, code='PANIER', libelle='Autre')


class PrimeAttribueeTests(TestCase):
    def setUp(self):
        self.co_a = make_company('pa-a', 'A')
        self.co_b = make_company('pa-b', 'B')
        self.user_a = make_user(self.co_a, 'pa-user-a')
        self.user_b = make_user(self.co_b, 'pa-user-b')
        self.emp_a = make_employe(self.co_a, 'PA1')
        self.emp_b = make_employe(self.co_b, 'PB1')
        self.tp_a = TypePrime.objects.create(
            company=self.co_a, code='RENDEMENT', libelle='Rendement',
            montant_defaut=Decimal('500.00'))
        self.tp_b = TypePrime.objects.create(
            company=self.co_b, code='RENDEMENT', libelle='Rendement')

    def test_create_montant_defaut_repris(self):
        resp = auth(self.user_a).post(PRIME_URL, {
            'type_prime': self.tp_a.id, 'employe': self.emp_a.id,
            'annee': 2026, 'mois': 6,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        prime = PrimeAttribuee.objects.get(id=resp.data['id'])
        self.assertEqual(prime.company, self.co_a)
        self.assertEqual(prime.montant, Decimal('500.00'))

    def test_montant_explicite_respecte(self):
        resp = auth(self.user_a).post(PRIME_URL, {
            'type_prime': self.tp_a.id, 'employe': self.emp_a.id,
            'annee': 2026, 'mois': 6, 'montant': '120.00',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data['montant']), Decimal('120.00'))

    def test_type_prime_autre_societe_refuse(self):
        resp = auth(self.user_a).post(PRIME_URL, {
            'type_prime': self.tp_b.id, 'employe': self.emp_a.id,
            'annee': 2026, 'mois': 6,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_employe_autre_societe_refuse(self):
        resp = auth(self.user_a).post(PRIME_URL, {
            'type_prime': self.tp_a.id, 'employe': self.emp_b.id,
            'annee': 2026, 'mois': 6,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_mois_invalide_refuse(self):
        resp = auth(self.user_a).post(PRIME_URL, {
            'type_prime': self.tp_a.id, 'employe': self.emp_a.id,
            'annee': 2026, 'mois': 0,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_valider_idempotent_et_404(self):
        prime = PrimeAttribuee.objects.create(
            company=self.co_a, type_prime=self.tp_a, employe=self.emp_a,
            annee=2026, mois=6)
        api = auth(self.user_a)
        r1 = api.post(f'{PRIME_URL}{prime.id}/valider/')
        self.assertEqual(r1.status_code, 200, r1.data)
        self.assertEqual(r1.data['statut'], PrimeAttribuee.Statut.VALIDEE)
        r2 = api.post(f'{PRIME_URL}{prime.id}/valider/')
        self.assertEqual(r2.status_code, 200)
        r3 = auth(self.user_b).post(f'{PRIME_URL}{prime.id}/valider/')
        self.assertEqual(r3.status_code, 404)

    def test_filtres_et_isolation(self):
        PrimeAttribuee.objects.create(
            company=self.co_a, type_prime=self.tp_a, employe=self.emp_a,
            annee=2026, mois=6, statut=PrimeAttribuee.Statut.PROPOSEE)
        api = auth(self.user_a)
        self.assertEqual(len(rows(api.get(f'{PRIME_URL}?annee=2026'))), 1)
        self.assertEqual(
            len(rows(api.get(f'{PRIME_URL}?employe={self.emp_a.id}'))), 1)
        self.assertEqual(len(rows(auth(self.user_b).get(PRIME_URL))), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'pa-normal', role='normal')
        self.assertEqual(auth(normal).get(PRIME_URL).status_code, 403)
        self.assertEqual(auth(normal).get(TYPE_URL).status_code, 403)
