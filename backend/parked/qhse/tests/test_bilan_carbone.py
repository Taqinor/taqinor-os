"""Tests QHSE39 — BilanCarbone + LigneBilanCarbone (scopes 1/2/3).

Couvre :
* CRUD scopé société (``company`` posée côté serveur) ;
* totaux par scope + total global dérivés des lignes (``tco2e`` = quantité ×
  facteur) ;
* FK ``bilan`` (ligne) validé même-société ;
* filtres, rôle, isolation société.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import BilanCarbone, LigneBilanCarbone

User = get_user_model()

BILAN_URL = '/api/django/qhse/bilans-carbone/'
LIGNE_URL = '/api/django/qhse/lignes-bilan-carbone/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return (data['results']
            if isinstance(data, dict) and 'results' in data else data)


def make_bilan(company, libelle='Bilan 2026', annee=2026):
    return BilanCarbone.objects.create(
        company=company, libelle=libelle, annee=annee)


def make_ligne(company, bilan, scope='scope_1', quantite='100',
               facteur='0.5'):
    return LigneBilanCarbone.objects.create(
        company=company, bilan=bilan, libelle='Source', scope=scope,
        quantite=Decimal(quantite), facteur_emission=Decimal(facteur))


class BilanCarboneModelTests(TestCase):
    def setUp(self):
        self.company = make_company('co-bilan', 'CoBilan')

    def test_tco2e_ligne(self):
        bilan = make_bilan(self.company)
        ligne = make_ligne(self.company, bilan, quantite='100', facteur='0.5')
        self.assertEqual(ligne.tco2e, Decimal('50.000'))

    def test_totaux_par_scope(self):
        bilan = make_bilan(self.company)
        make_ligne(self.company, bilan, scope='scope_1',
                   quantite='100', facteur='0.5')   # 50
        make_ligne(self.company, bilan, scope='scope_2',
                   quantite='200', facteur='0.1')   # 20
        make_ligne(self.company, bilan, scope='scope_3',
                   quantite='10', facteur='1')      # 10
        self.assertEqual(bilan.total_scope_1, Decimal('50.000'))
        self.assertEqual(bilan.total_scope_2, Decimal('20.000'))
        self.assertEqual(bilan.total_scope_3, Decimal('10.000'))
        self.assertEqual(bilan.total_tco2e, Decimal('80.000'))


class BilanCarboneApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-bilan-api', 'CoBilanApi')
        self.other_company = make_company('co-bilan-api-2', 'CoBilanApi2')
        self.user = make_user(self.company, 'bilan-resp')
        self.client_api = auth_client(self.user)
        self.other_user = make_user(self.other_company, 'bilan-resp-2')
        self.other_client = auth_client(self.other_user)

    def test_creation_company_serveur(self):
        resp = self.client_api.post(
            BILAN_URL,
            {'libelle': 'Bilan 2026', 'annee': 2026,
             'company': self.other_company.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        bilan = BilanCarbone.objects.get(id=resp.data['id'])
        self.assertEqual(bilan.company, self.company)

    def test_totaux_exposes(self):
        bilan = make_bilan(self.company)
        make_ligne(self.company, bilan, scope='scope_1',
                   quantite='100', facteur='0.5')
        resp = self.client_api.get(f'{BILAN_URL}{bilan.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total_scope_1'], '50.000')
        self.assertEqual(resp.data['total_tco2e'], '50.000')

    def test_ligne_bilan_meme_societe(self):
        autre_bilan = make_bilan(self.other_company)
        resp = self.client_api.post(
            LIGNE_URL,
            {'bilan': autre_bilan.id, 'libelle': 'X', 'scope': 'scope_1',
             'quantite': '1', 'facteur_emission': '1'},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_ligne_tco2e_expose(self):
        bilan = make_bilan(self.company)
        resp = self.client_api.post(
            LIGNE_URL,
            {'bilan': bilan.id, 'libelle': 'Gasoil', 'scope': 'scope_1',
             'quantite': '1000', 'facteur_emission': '0.0027'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['tco2e'], '2.700')

    def test_filtre_scope(self):
        bilan = make_bilan(self.company)
        make_ligne(self.company, bilan, scope='scope_1')
        make_ligne(self.company, bilan, scope='scope_2')
        resp = self.client_api.get(LIGNE_URL, {'scope': 'scope_2'})
        scopes = [r['scope'] for r in rows(resp)]
        self.assertEqual(scopes, ['scope_2'])

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'bilan-normal', role='normal')
        resp = auth_client(normal).get(BILAN_URL)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_societe_detail_404(self):
        bilan = make_bilan(self.company)
        resp = self.other_client.get(f'{BILAN_URL}{bilan.id}/')
        self.assertEqual(resp.status_code, 404)
