"""Tests FG194 — Ordre de mission (déplacement chantier).

Couvre :
* Création : ``company`` + ``reference`` (préfixe OM) posées CÔTÉ SERVEUR.
* FK ``employe`` d'une autre société refusé.
* Action ``emettre`` (idempotente, 404 autre tenant).
* Action ``pdf`` (200 application/pdf, scopée société, 404 autre tenant).
* Filtres + isolation + permission (rôle normal 403).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import DossierEmploye, OrdreMission

User = get_user_model()

URL = '/api/django/rh/ordres-mission/'


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


class OrdreMissionTests(TestCase):
    def setUp(self):
        self.co_a = make_company('om-a', 'A')
        self.co_b = make_company('om-b', 'B')
        self.user_a = make_user(self.co_a, 'om-user-a')
        self.user_b = make_user(self.co_b, 'om-user-b')
        self.emp_a = make_employe(self.co_a, 'OA1')
        self.emp_b = make_employe(self.co_b, 'OB1')

    def test_create_reference_et_company_cote_serveur(self):
        resp = auth(self.user_a).post(URL, {
            'employe': self.emp_a.id,
            'destination': 'Chantier Agadir',
            'motif': 'Pose panneaux.',
            'date_depart': '2026-07-01',
            'date_retour': '2026-07-03',
            'moyen_transport': 'Camionnette',
            'per_diem': '150.00',
            # reference ignorée même si fournie
            'reference': 'HACK-1',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        om = OrdreMission.objects.get(id=resp.data['id'])
        self.assertEqual(om.company, self.co_a)
        self.assertTrue(om.reference.startswith('OM-'))
        self.assertNotEqual(om.reference, 'HACK-1')
        self.assertEqual(om.per_diem, Decimal('150.00'))

    def test_employe_autre_societe_refuse(self):
        resp = auth(self.user_a).post(URL, {
            'employe': self.emp_b.id, 'destination': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_emettre_idempotent_et_404(self):
        om = OrdreMission.objects.create(
            company=self.co_a, reference='OM-202607-0001',
            employe=self.emp_a, destination='X')
        api = auth(self.user_a)
        r1 = api.post(f'{URL}{om.id}/emettre/')
        self.assertEqual(r1.status_code, 200, r1.data)
        self.assertEqual(r1.data['statut'], OrdreMission.Statut.EMIS)
        r2 = api.post(f'{URL}{om.id}/emettre/')
        self.assertEqual(r2.status_code, 200)
        r3 = auth(self.user_b).post(f'{URL}{om.id}/emettre/')
        self.assertEqual(r3.status_code, 404)

    def test_pdf_genere(self):
        om = OrdreMission.objects.create(
            company=self.co_a, reference='OM-202607-0002',
            employe=self.emp_a, destination='Chantier Fès',
            motif='Maintenance', per_diem=Decimal('200'))
        resp = auth(self.user_a).get(f'{URL}{om.id}/pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content[:4] == b'%PDF')

    def test_pdf_autre_tenant_404(self):
        om = OrdreMission.objects.create(
            company=self.co_a, reference='OM-202607-0003',
            employe=self.emp_a, destination='X')
        resp = auth(self.user_b).get(f'{URL}{om.id}/pdf/')
        self.assertEqual(resp.status_code, 404)

    def test_filtres_et_isolation(self):
        OrdreMission.objects.create(
            company=self.co_a, reference='OM-202607-0004',
            employe=self.emp_a, destination='X',
            statut=OrdreMission.Statut.EMIS)
        api = auth(self.user_a)
        self.assertEqual(len(rows(api.get(f'{URL}?statut=emis'))), 1)
        self.assertEqual(
            len(rows(api.get(f'{URL}?employe={self.emp_a.id}'))), 1)
        self.assertEqual(len(rows(auth(self.user_b).get(URL))), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'om-normal', role='normal')
        self.assertEqual(auth(normal).get(URL).status_code, 403)
