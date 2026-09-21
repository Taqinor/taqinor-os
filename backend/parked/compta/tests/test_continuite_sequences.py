"""Tests XACC29 — Rapport de continuité des séquences (gap detection).

Couvre : une séquence avec un trou le liste (journal/plage/manquants),
séquences continues → rapport vide, cross-company isolé, l'export CSV.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors
from apps.crm.models import Client
from apps.ventes.models import Facture

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


def make_facture(company, client, reference):
    return Facture.objects.create(
        reference=reference, company=company, client=client,
        statut=Facture.Statut.EMISE, type_facture=Facture.TypeFacture.COMPLETE,
        taux_tva=Decimal('20'), montant_ht=Decimal('100'),
        montant_tva=Decimal('20'), montant_ttc=Decimal('120'))


class ContinuiteSequencesSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc29-svc', 'XACC29 Svc')
        self.client_obj = Client.objects.create(
            company=self.co, nom='Client Séquence')

    def test_sequence_avec_trou_listee(self):
        make_facture(self.co, self.client_obj, 'FAC-202606-0001')
        make_facture(self.co, self.client_obj, 'FAC-202606-0002')
        make_facture(self.co, self.client_obj, 'FAC-202606-0005')
        rapport = selectors.trous_sequences(self.co)
        entree = next(e for e in rapport if e['source'] == 'factures')
        self.assertEqual(entree['plage'], [1, 5])
        self.assertEqual(entree['manquants'], [3, 4])

    def test_sequence_continue_rapport_vide(self):
        make_facture(self.co, self.client_obj, 'FAC-202606-0001')
        make_facture(self.co, self.client_obj, 'FAC-202606-0002')
        make_facture(self.co, self.client_obj, 'FAC-202606-0003')
        rapport = selectors.trous_sequences(self.co)
        self.assertEqual(
            [e for e in rapport if e['source'] == 'factures'], [])

    def test_facture_annulee_exclue(self):
        make_facture(self.co, self.client_obj, 'FAC-202606-0001')
        f2 = make_facture(self.co, self.client_obj, 'FAC-202606-0002')
        f2.statut = Facture.Statut.ANNULEE
        f2.save(update_fields=['statut'])
        make_facture(self.co, self.client_obj, 'FAC-202606-0003')
        rapport = selectors.trous_sequences(self.co)
        # L'annulée est exclue du contrôle -> seuls 1 et 3 existent -> trou en 2.
        entree = next(e for e in rapport if e['source'] == 'factures')
        self.assertEqual(entree['manquants'], [2])


class ContinuiteSequencesApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('xacc29-a', 'XACC29 A')
        self.co_b = make_company('xacc29-b', 'XACC29 B')
        self.user_a = make_user(self.co_a, 'xacc29-user-a')
        self.client_a = Client.objects.create(company=self.co_a, nom='Client A')
        self.client_b = Client.objects.create(company=self.co_b, nom='Client B')

    def test_cross_company_isole(self):
        make_facture(self.co_a, self.client_a, 'FAC-202606-0001')
        make_facture(self.co_a, self.client_a, 'FAC-202606-0003')
        make_facture(self.co_b, self.client_b, 'FAC-202606-0001')
        make_facture(self.co_b, self.client_b, 'FAC-202606-0002')
        resp = auth(self.user_a).get(
            '/api/django/compta/etats/continuite-sequences/')
        self.assertEqual(resp.status_code, 200)
        entree = next(e for e in resp.data if e['source'] == 'factures')
        self.assertEqual(entree['manquants'], [2])

    def test_export_csv(self):
        make_facture(self.co_a, self.client_a, 'FAC-202606-0001')
        make_facture(self.co_a, self.client_a, 'FAC-202606-0003')
        resp = auth(self.user_a).get(
            '/api/django/compta/etats/continuite-sequences/?export=csv')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn(b'factures', resp.content)

    def test_refuse_role_normal(self):
        normal = make_user(self.co_a, 'xacc29-normal', role='normal')
        resp = auth(normal).get(
            '/api/django/compta/etats/continuite-sequences/')
        self.assertEqual(resp.status_code, 403)
