"""Tests QHSE15 — Grille d'audit + critères pondérés.

Couvre :

* ``GrilleAudit.poids_total`` somme les poids des critères ;
* l'API pose ``company`` côté serveur (création grille + critère) ;
* isolation entre sociétés et palier Administrateur/Responsable ;
* un critère rattaché à une grille d'une autre société est refusé (400) ;
* le filtre ``?grille=`` borne les critères ; un poids < 1 est rejeté.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import CritereAudit, GrilleAudit

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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class GrilleAuditModelTests(TestCase):
    def setUp(self):
        self.co = make_company('qhse15-mdl', 'Mdl')

    def test_poids_total(self):
        grille = GrilleAudit.objects.create(company=self.co, nom='Fin chantier')
        self.assertEqual(grille.poids_total(), 0)
        CritereAudit.objects.create(
            company=self.co, grille=grille, intitule='Câblage', poids=3)
        CritereAudit.objects.create(
            company=self.co, grille=grille, intitule='EPI', poids=2)
        self.assertEqual(grille.poids_total(), 5)


class GrilleAuditApiTests(TestCase):
    GRILLES = '/api/django/qhse/grilles-audit/'
    CRITERES = '/api/django/qhse/criteres-audit/'

    def setUp(self):
        self.co = make_company('qhse15-api', 'Api')
        self.user = make_user(self.co, 'qhse15-api')

    def test_create_grille_forces_company(self):
        resp = auth(self.user).post(
            self.GRILLES,
            {'nom': 'Audit sécurité', 'type_audit': 'securite'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        grille = GrilleAudit.objects.get(id=resp.data['id'])
        self.assertEqual(grille.company, self.co)
        self.assertEqual(resp.data['type_audit_display'], 'Sécurité')

    def test_create_critere_forces_company(self):
        grille = GrilleAudit.objects.create(company=self.co, nom='G')
        resp = auth(self.user).post(
            self.CRITERES,
            {'grille': grille.id, 'intitule': 'Propreté', 'poids': 4},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        crit = CritereAudit.objects.get(id=resp.data['id'])
        self.assertEqual(crit.company, self.co)
        self.assertEqual(crit.poids, 4)

    def test_critere_other_company_grille_refused(self):
        other = make_company('qhse15-api-b', 'B')
        other_grille = GrilleAudit.objects.create(company=other, nom='B')
        resp = auth(self.user).post(
            self.CRITERES,
            {'grille': other_grille.id, 'intitule': 'X'},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_poids_below_one_refused(self):
        grille = GrilleAudit.objects.create(company=self.co, nom='G')
        resp = auth(self.user).post(
            self.CRITERES,
            {'grille': grille.id, 'intitule': 'X', 'poids': 0},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_filter_by_grille(self):
        g1 = GrilleAudit.objects.create(company=self.co, nom='G1')
        g2 = GrilleAudit.objects.create(company=self.co, nom='G2')
        CritereAudit.objects.create(
            company=self.co, grille=g1, intitule='A')
        CritereAudit.objects.create(
            company=self.co, grille=g2, intitule='B')
        resp = auth(self.user).get(f'{self.CRITERES}?grille={g1.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)

    def test_list_isolation(self):
        other = make_company('qhse15-iso-b', 'B')
        GrilleAudit.objects.create(company=other, nom='Autre')
        resp = auth(self.user).get(self.GRILLES)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co, 'qhse15-normal', role='normal')
        resp = auth(normal).get(self.GRILLES)
        self.assertEqual(resp.status_code, 403)
