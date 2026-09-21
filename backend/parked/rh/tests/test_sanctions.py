"""Tests FG191 — Disciplinaire & sanctions (registre disciplinaire).

Couvre :
* Création : ``company`` posée CÔTÉ SERVEUR (jamais lue du corps), CRUD.
* FK ``employe`` / ``auteur`` d'une autre société refusés.
* Action ``annuler`` (idempotente, scopée société, 404 autre tenant).
* Filtres ``?employe=`` / ``?statut=`` / ``?type_sanction=``.
* Isolation multi-société + permission (rôle normal 403).
* DRF : ``?format=`` réservé ne casse pas la liste.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import DossierEmploye, Sanction

User = get_user_model()

URL = '/api/django/rh/sanctions/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule, nom='Nom', prenom='Prenom'):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom=nom, prenom=prenom)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class SanctionTests(TestCase):
    def setUp(self):
        self.co_a = make_company('sanc-a', 'A')
        self.co_b = make_company('sanc-b', 'B')
        self.user_a = make_user(self.co_a, 'sanc-user-a')
        self.user_b = make_user(self.co_b, 'sanc-user-b')
        self.emp_a = make_employe(self.co_a, 'SA1')
        self.emp_b = make_employe(self.co_b, 'SB1')

    def test_create_company_cote_serveur(self):
        resp = auth(self.user_a).post(URL, {
            'employe': self.emp_a.id,
            'type_sanction': 'avertissement',
            'date_faits': '2026-06-01',
            'date_notification': '2026-06-05',
            'motif': 'Retards répétés.',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        s = Sanction.objects.get(id=resp.data['id'])
        self.assertEqual(s.company, self.co_a)
        self.assertEqual(s.statut, Sanction.Statut.NOTIFIEE)

    def test_mise_a_pied_duree(self):
        resp = auth(self.user_a).post(URL, {
            'employe': self.emp_a.id,
            'type_sanction': 'mise_a_pied',
            'duree_jours': 3,
            'motif': 'Faute grave.',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['duree_jours'], 3)

    def test_employe_autre_societe_refuse(self):
        resp = auth(self.user_a).post(URL, {
            'employe': self.emp_b.id,
            'type_sanction': 'blame',
            'motif': 'x',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_auteur_autre_societe_refuse(self):
        resp = auth(self.user_a).post(URL, {
            'employe': self.emp_a.id,
            'auteur': self.emp_b.id,
            'type_sanction': 'blame',
            'motif': 'x',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_annuler_idempotent(self):
        s = Sanction.objects.create(
            company=self.co_a, employe=self.emp_a,
            type_sanction=Sanction.TypeSanction.AVERTISSEMENT, motif='x')
        api = auth(self.user_a)
        r1 = api.post(f'{URL}{s.id}/annuler/')
        self.assertEqual(r1.status_code, 200, r1.data)
        self.assertEqual(r1.data['statut'], Sanction.Statut.ANNULEE)
        r2 = api.post(f'{URL}{s.id}/annuler/')
        self.assertEqual(r2.status_code, 200)
        s.refresh_from_db()
        self.assertEqual(s.statut, Sanction.Statut.ANNULEE)

    def test_annuler_autre_tenant_404(self):
        s = Sanction.objects.create(
            company=self.co_a, employe=self.emp_a,
            type_sanction=Sanction.TypeSanction.BLAME, motif='x')
        resp = auth(self.user_b).post(f'{URL}{s.id}/annuler/')
        self.assertEqual(resp.status_code, 404)

    def test_filtre_employe_et_statut(self):
        Sanction.objects.create(
            company=self.co_a, employe=self.emp_a,
            type_sanction=Sanction.TypeSanction.BLAME,
            statut=Sanction.Statut.NOTIFIEE, motif='a')
        emp2 = make_employe(self.co_a, 'SA2')
        Sanction.objects.create(
            company=self.co_a, employe=emp2,
            type_sanction=Sanction.TypeSanction.AVERTISSEMENT,
            statut=Sanction.Statut.ANNULEE, motif='b')
        resp = auth(self.user_a).get(f'{URL}?employe={self.emp_a.id}')
        self.assertEqual(len(rows(resp)), 1)
        resp = auth(self.user_a).get(f'{URL}?statut=annulee')
        self.assertEqual(len(rows(resp)), 1)
        resp = auth(self.user_a).get(f'{URL}?type_sanction=blame')
        self.assertEqual(len(rows(resp)), 1)

    def test_isolation(self):
        Sanction.objects.create(
            company=self.co_a, employe=self.emp_a,
            type_sanction=Sanction.TypeSanction.BLAME, motif='x')
        resp = auth(self.user_b).get(URL)
        self.assertEqual(len(rows(resp)), 0)

    def test_permission_role_normal_403(self):
        normal = make_user(self.co_a, 'sanc-normal', role='normal')
        resp = auth(normal).get(URL)
        self.assertEqual(resp.status_code, 403)

    def test_format_reserve_ne_casse_pas(self):
        resp = auth(self.user_a).get(f'{URL}?format=json')
        self.assertEqual(resp.status_code, 200)
