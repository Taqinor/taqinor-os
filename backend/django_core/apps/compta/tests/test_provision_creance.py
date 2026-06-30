"""Tests FG152 — Provisions pour créances douteuses.

Couvre : le calcul de la dotation (base × taux %), l'écriture OD de dotation
(6196 / 3942, équilibrée), la reprise (3942 / 7196 + idempotence), la pose
``company`` / ``reference`` / ``dotation`` côté serveur (jamais imposables),
l'isolation multi-société et le gate de rôle.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import EcritureComptable, LigneEcriture, ProvisionCreance

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


class ProvisionServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('fg152-svc', 'FG152 Svc')
        self.user = make_user(self.co, 'fg152-svc-user')

    def test_dotation_calculee_et_ecriture(self):
        prov = services.enregistrer_provision_creance(
            self.co, date_dotation=date(2026, 6, 30),
            base=Decimal('100000'), taux=Decimal('50'),
            tiers_nom='Client X', anciennete_jours=200, user=self.user)
        self.assertEqual(prov.dotation, Decimal('50000.00'))
        self.assertTrue(prov.reference.startswith('PROV-'))
        self.assertIsNotNone(prov.ecriture_id)
        lignes = LigneEcriture.objects.filter(ecriture_id=prov.ecriture_id)
        debit = sum((x.debit for x in lignes), Decimal('0'))
        credit = sum((x.credit for x in lignes), Decimal('0'))
        self.assertEqual(debit, credit)
        self.assertEqual(debit, Decimal('50000.00'))
        numeros = {x.compte.numero for x in lignes}
        self.assertIn('6196', numeros)
        self.assertIn('3942', numeros)

    def test_reprise_inverse_et_idempotente(self):
        prov = services.enregistrer_provision_creance(
            self.co, date_dotation=date(2026, 6, 30),
            base=Decimal('20000'), taux=Decimal('100'),
            tiers_nom='Client Y', user=self.user)
        services.reprendre_provision_creance(
            prov, date_reprise=date(2026, 12, 31), user=self.user)
        prov.refresh_from_db()
        self.assertEqual(prov.statut, ProvisionCreance.Statut.REPRISE)
        self.assertIsNotNone(prov.ecriture_reprise_id)
        lignes = LigneEcriture.objects.filter(
            ecriture_id=prov.ecriture_reprise_id)
        numeros = {x.compte.numero for x in lignes}
        self.assertIn('7196', numeros)
        ec_avant = EcritureComptable.objects.filter(company=self.co).count()
        services.reprendre_provision_creance(prov, user=self.user)
        self.assertEqual(
            EcritureComptable.objects.filter(company=self.co).count(),
            ec_avant)


class ProvisionApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('fg152-a', 'FG152 A')
        self.co_b = make_company('fg152-b', 'FG152 B')
        self.user_a = make_user(self.co_a, 'fg152-user-a')
        self.user_b = make_user(self.co_b, 'fg152-user-b')

    def test_create_pose_company_et_dotation_serveur(self):
        resp = auth(self.user_a).post(
            '/api/django/compta/provisions-creances/',
            {'date_dotation': '2026-06-30', 'base': '80000', 'taux': '25',
             'tiers_nom': 'Z', 'dotation': '999999',  # tentative d'imposer.
             'company': self.co_b.id},
            format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(
            Decimal(str(resp.data['dotation'])), Decimal('20000.00'))
        prov = ProvisionCreance.objects.get(id=resp.data['id'])
        self.assertEqual(prov.company_id, self.co_a.id)

    def test_action_reprendre(self):
        prov = services.enregistrer_provision_creance(
            self.co_a, date_dotation=date(2026, 6, 30), base=Decimal('1000'),
            taux=Decimal('100'), user=self.user_a)
        resp = auth(self.user_a).post(
            f'/api/django/compta/provisions-creances/{prov.id}/reprendre/',
            {'date_reprise': '2026-12-31'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], ProvisionCreance.Statut.REPRISE)

    def test_isolation_liste(self):
        services.enregistrer_provision_creance(
            self.co_a, date_dotation=date(2026, 6, 30), base=Decimal('1000'),
            taux=Decimal('10'), user=self.user_a)
        resp_b = auth(self.user_b).get(
            '/api/django/compta/provisions-creances/')
        results = resp_b.data.get('results', resp_b.data)
        self.assertEqual(len(results), 0)

    def test_refuse_role_normal(self):
        normal = make_user(self.co_a, 'fg152-normal', role='normal')
        resp = auth(normal).post(
            '/api/django/compta/provisions-creances/',
            {'date_dotation': '2026-06-30', 'base': '1000', 'taux': '10'},
            format='json')
        self.assertEqual(resp.status_code, 403)
