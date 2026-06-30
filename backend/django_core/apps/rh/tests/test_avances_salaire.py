"""Tests FG195 — Avances sur salaire (demande/validation/déduction).

Couvre :
* Création : ``company`` posée CÔTÉ SERVEUR ; mois de déduction par défaut =
  mois suivant la demande ; FK employe d'une autre société refusé.
* Actions ``approuver`` / ``refuser`` / ``marquer-deduite`` (idempotentes,
  404 autre tenant, valideur tracé).
* Sélecteur ``avances_a_deduire`` (avances approuvées du mois, scopé société).
* Filtres + isolation + permission (rôle normal 403).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import AvanceSalaire, DossierEmploye

User = get_user_model()

URL = '/api/django/rh/avances-salaire/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule, user=None):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='N', prenom='P', user=user)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class AvanceSalaireTests(TestCase):
    def setUp(self):
        self.co_a = make_company('av-a', 'A')
        self.co_b = make_company('av-b', 'B')
        self.user_a = make_user(self.co_a, 'av-user-a')
        self.user_b = make_user(self.co_b, 'av-user-b')
        self.emp_a = make_employe(self.co_a, 'AV1', user=self.user_a)
        self.emp_b = make_employe(self.co_b, 'AV2')

    def test_create_deduction_mois_suivant(self):
        resp = auth(self.user_a).post(URL, {
            'employe': self.emp_a.id,
            'montant': '1000.00',
            'date_demande': '2026-06-10',
            'motif': 'Imprévu familial.',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        av = AvanceSalaire.objects.get(id=resp.data['id'])
        self.assertEqual(av.company, self.co_a)
        self.assertEqual(av.mois_deduction, 7)
        self.assertEqual(av.annee_deduction, 2026)
        self.assertEqual(av.statut, AvanceSalaire.Statut.DEMANDEE)

    def test_deduction_decembre_passe_janvier(self):
        resp = auth(self.user_a).post(URL, {
            'employe': self.emp_a.id, 'montant': '500',
            'date_demande': '2026-12-15',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        av = AvanceSalaire.objects.get(id=resp.data['id'])
        self.assertEqual(av.mois_deduction, 1)
        self.assertEqual(av.annee_deduction, 2027)

    def test_employe_autre_societe_refuse(self):
        resp = auth(self.user_a).post(URL, {
            'employe': self.emp_b.id, 'montant': '500',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_approuver_trace_valideur_et_404(self):
        av = AvanceSalaire.objects.create(
            company=self.co_a, employe=self.emp_a, montant=Decimal('800'))
        api = auth(self.user_a)
        r1 = api.post(f'{URL}{av.id}/approuver/')
        self.assertEqual(r1.status_code, 200, r1.data)
        self.assertEqual(r1.data['statut'], AvanceSalaire.Statut.APPROUVEE)
        av.refresh_from_db()
        self.assertEqual(av.valideur, self.emp_a)
        r2 = api.post(f'{URL}{av.id}/approuver/')
        self.assertEqual(r2.status_code, 200)
        r3 = auth(self.user_b).post(f'{URL}{av.id}/approuver/')
        self.assertEqual(r3.status_code, 404)

    def test_refuser_et_marquer_deduite(self):
        av = AvanceSalaire.objects.create(
            company=self.co_a, employe=self.emp_a, montant=Decimal('300'))
        api = auth(self.user_a)
        r = api.post(f'{URL}{av.id}/refuser/')
        self.assertEqual(r.data['statut'], AvanceSalaire.Statut.REFUSEE)
        av2 = AvanceSalaire.objects.create(
            company=self.co_a, employe=self.emp_a, montant=Decimal('300'),
            statut=AvanceSalaire.Statut.APPROUVEE)
        r2 = api.post(f'{URL}{av2.id}/marquer-deduite/')
        self.assertEqual(r2.data['statut'], AvanceSalaire.Statut.DEDUITE)

    def test_selecteur_avances_a_deduire(self):
        AvanceSalaire.objects.create(
            company=self.co_a, employe=self.emp_a, montant=Decimal('400'),
            statut=AvanceSalaire.Statut.APPROUVEE,
            annee_deduction=2026, mois_deduction=7)
        # Une avance encore demandée (non approuvée) ne sort pas.
        AvanceSalaire.objects.create(
            company=self.co_a, employe=self.emp_a, montant=Decimal('100'),
            statut=AvanceSalaire.Statut.DEMANDEE,
            annee_deduction=2026, mois_deduction=7)
        # Une avance d'une autre société ne sort pas.
        AvanceSalaire.objects.create(
            company=self.co_b, employe=self.emp_b, montant=Decimal('900'),
            statut=AvanceSalaire.Statut.APPROUVEE,
            annee_deduction=2026, mois_deduction=7)
        res = selectors.avances_a_deduire(self.co_a, 2026, 7)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['montant'], Decimal('400'))

    def test_filtres_et_isolation(self):
        AvanceSalaire.objects.create(
            company=self.co_a, employe=self.emp_a, montant=Decimal('200'),
            statut=AvanceSalaire.Statut.APPROUVEE,
            annee_deduction=2026, mois_deduction=7)
        api = auth(self.user_a)
        self.assertEqual(len(rows(api.get(f'{URL}?statut=approuvee'))), 1)
        self.assertEqual(
            len(rows(api.get(f'{URL}?mois_deduction=7'))), 1)
        self.assertEqual(len(rows(auth(self.user_b).get(URL))), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'av-normal', role='normal')
        self.assertEqual(auth(normal).get(URL).status_code, 403)
