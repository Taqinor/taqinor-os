"""Tests QHSE36 — Déchet + BordereauSuiviDechet (BSD, loi 28-00).

Couvre :
* CRUD ``Dechet`` scopé société (``company`` posée côté serveur ; ``dangereux``
  dérivé de la catégorie) ;
* BSD : création réservée aux déchets DANGEREUX (loi 28-00 — 400 sinon),
  ``company``/``reference`` posées côté serveur ;
* transitions ``enlever`` / ``traiter`` + garde-fous ;
* filtres, rôle, isolation société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import BordereauSuiviDechet, Dechet

User = get_user_model()

DECHET_URL = '/api/django/qhse/dechets/'
BSD_URL = '/api/django/qhse/bordereaux-dechets/'


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


def make_dechet(company, libelle='Batterie HS', categorie='dangereux'):
    return Dechet.objects.create(
        company=company, libelle=libelle, categorie=categorie)


class DechetApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-dechet', 'CoDechet')
        self.user = make_user(self.company, 'dechet-resp')
        self.client_api = auth_client(self.user)

    def test_creation_company_serveur(self):
        other = make_company('co-dechet-2', 'CoDechet2')
        resp = self.client_api.post(
            DECHET_URL,
            {'libelle': 'Chutes de câble', 'categorie': 'non_dangereux',
             'company': other.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        dechet = Dechet.objects.get(id=resp.data['id'])
        self.assertEqual(dechet.company, self.company)
        self.assertFalse(resp.data['dangereux'])

    def test_dangereux_derive(self):
        resp = self.client_api.post(
            DECHET_URL,
            {'libelle': 'Huile usagée', 'categorie': 'dangereux'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['dangereux'])

    def test_filtre_categorie(self):
        make_dechet(self.company, 'Batterie', 'dangereux')
        make_dechet(self.company, 'Carton', 'non_dangereux')
        resp = self.client_api.get(DECHET_URL, {'categorie': 'dangereux'})
        cats = [r['categorie'] for r in rows(resp)]
        self.assertEqual(cats, ['dangereux'])


class BordereauSuiviDechetApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-bsd', 'CoBsd')
        self.other_company = make_company('co-bsd-2', 'CoBsd2')
        self.user = make_user(self.company, 'bsd-resp')
        self.client_api = auth_client(self.user)
        self.other_user = make_user(self.other_company, 'bsd-resp-2')
        self.other_client = auth_client(self.other_user)
        self.dechet_dang = make_dechet(self.company, 'Batterie', 'dangereux')
        self.dechet_nd = make_dechet(self.company, 'Carton', 'non_dangereux')

    def test_creation_bsd_dangereux(self):
        resp = self.client_api.post(
            BSD_URL,
            {'dechet': self.dechet_dang.id, 'quantite': '12.500',
             'chantier_id': 5},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        bsd = BordereauSuiviDechet.objects.get(id=resp.data['id'])
        self.assertEqual(bsd.company, self.company)
        self.assertEqual(bsd.statut, 'emis')
        self.assertTrue(bsd.reference.startswith('BSD-'))

    def test_creation_bsd_non_dangereux_refusee(self):
        resp = self.client_api.post(
            BSD_URL, {'dechet': self.dechet_nd.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(BordereauSuiviDechet.objects.count(), 0)

    def test_dechet_autre_societe_refuse(self):
        autre_dechet = make_dechet(self.other_company, 'X', 'dangereux')
        resp = self.client_api.post(
            BSD_URL, {'dechet': autre_dechet.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_enlever_puis_traiter(self):
        bsd = BordereauSuiviDechet.objects.create(
            company=self.company, dechet=self.dechet_dang,
            reference='BSD-202606-0001', statut='emis')
        r1 = self.client_api.post(
            f'{BSD_URL}{bsd.id}/enlever/', {}, format='json')
        self.assertEqual(r1.status_code, 200, r1.data)
        bsd.refresh_from_db()
        self.assertEqual(bsd.statut, 'enleve')
        self.assertIsNotNone(bsd.date_enlevement)
        r2 = self.client_api.post(
            f'{BSD_URL}{bsd.id}/traiter/', {}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        bsd.refresh_from_db()
        self.assertEqual(bsd.statut, 'traite')
        self.assertIsNotNone(bsd.date_traitement)

    def test_traiter_refuse_si_deja_traite(self):
        bsd = BordereauSuiviDechet.objects.create(
            company=self.company, dechet=self.dechet_dang,
            reference='BSD-202606-0001', statut='traite')
        resp = self.client_api.post(
            f'{BSD_URL}{bsd.id}/traiter/', {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'bsd-normal', role='normal')
        resp = auth_client(normal).get(BSD_URL)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_societe_detail_404(self):
        bsd = BordereauSuiviDechet.objects.create(
            company=self.company, dechet=self.dechet_dang,
            reference='BSD-202606-0001')
        resp = self.other_client.get(f'{BSD_URL}{bsd.id}/')
        self.assertEqual(resp.status_code, 404)
