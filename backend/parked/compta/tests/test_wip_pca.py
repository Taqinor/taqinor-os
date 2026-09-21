"""Tests FG147 — Produits constatés d'avance & travaux en cours (WIP).

Couvre : le constat PCA (7121 / 4491) et WIP (3134 / 7132) avec écriture OD
équilibrée, la reprise (extourne inversée + idempotence), la pose
``company`` / ``reference`` côté serveur, l'isolation multi-société et le gate
de rôle. Tout est additif et scopé société.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    EcritureComptable, LigneEcriture, TravauxEnCours,
)

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


def _lignes_numeros(ecriture_id):
    lignes = LigneEcriture.objects.filter(ecriture_id=ecriture_id)
    debit = sum((line.debit for line in lignes), Decimal('0'))
    credit = sum((line.credit for line in lignes), Decimal('0'))
    return debit, credit, {line.compte.numero for line in lignes}


class RegularisationServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('fg147-svc', 'FG147 Svc')
        self.user = make_user(self.co, 'fg147-svc-user')

    def test_wip_constate_ecriture_equilibree(self):
        reg = services.constater_regularisation(
            self.co, nature=TravauxEnCours.Nature.WIP,
            montant=Decimal('30000'), date_arrete=date(2026, 3, 31),
            user=self.user)
        self.assertTrue(reg.reference.startswith('REG-'))
        self.assertIsNotNone(reg.ecriture_id)
        debit, credit, numeros = _lignes_numeros(reg.ecriture_id)
        self.assertEqual(debit, credit)
        self.assertEqual(debit, Decimal('30000'))
        self.assertIn('3134', numeros)
        self.assertIn('7132', numeros)

    def test_pca_constate_comptes(self):
        reg = services.constater_regularisation(
            self.co, nature=TravauxEnCours.Nature.PCA,
            montant=Decimal('10000'), date_arrete=date(2026, 3, 31),
            user=self.user)
        _, _, numeros = _lignes_numeros(reg.ecriture_id)
        self.assertIn('7121', numeros)
        self.assertIn('4491', numeros)

    def test_poster_false_ne_passe_pas_ecriture(self):
        reg = services.constater_regularisation(
            self.co, nature=TravauxEnCours.Nature.WIP,
            montant=Decimal('10000'), date_arrete=date(2026, 3, 31),
            poster=False, user=self.user)
        self.assertIsNone(reg.ecriture_id)

    def test_reprise_inverse_et_idempotente(self):
        reg = services.constater_regularisation(
            self.co, nature=TravauxEnCours.Nature.WIP,
            montant=Decimal('20000'), date_arrete=date(2026, 3, 31),
            user=self.user)
        services.reprendre_regularisation(
            reg, date_reprise=date(2026, 4, 1), user=self.user)
        reg.refresh_from_db()
        self.assertEqual(reg.statut, TravauxEnCours.Statut.REPRIS)
        self.assertIsNotNone(reg.ecriture_reprise_id)
        # L'extourne inverse : 3134 maintenant au crédit.
        lignes = LigneEcriture.objects.filter(
            ecriture_id=reg.ecriture_reprise_id)
        l3134 = [x for x in lignes if x.compte.numero == '3134'][0]
        self.assertEqual(l3134.credit, Decimal('20000'))
        # Idempotent : deuxième reprise ne crée pas d'écriture.
        ec_avant = EcritureComptable.objects.filter(company=self.co).count()
        services.reprendre_regularisation(reg, user=self.user)
        self.assertEqual(
            EcritureComptable.objects.filter(company=self.co).count(),
            ec_avant)


class RegularisationApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('fg147-a', 'FG147 A')
        self.co_b = make_company('fg147-b', 'FG147 B')
        self.user_a = make_user(self.co_a, 'fg147-user-a')
        self.user_b = make_user(self.co_b, 'fg147-user-b')

    def test_create_pose_company_serveur(self):
        resp = auth(self.user_a).post(
            '/api/django/compta/travaux-en-cours/',
            {'nature': 'wip', 'montant': '5000',
             'date_arrete': '2026-03-31', 'company': self.co_b.id},
            format='json')
        self.assertEqual(resp.status_code, 201)
        reg = TravauxEnCours.objects.get(id=resp.data['id'])
        self.assertEqual(reg.company_id, self.co_a.id)

    def test_isolation_liste(self):
        services.constater_regularisation(
            self.co_a, nature=TravauxEnCours.Nature.WIP,
            montant=Decimal('1000'), date_arrete=date(2026, 1, 1),
            user=self.user_a)
        resp_b = auth(self.user_b).get(
            '/api/django/compta/travaux-en-cours/')
        results = resp_b.data.get('results', resp_b.data)
        self.assertEqual(len(results), 0)

    def test_refuse_role_normal(self):
        normal = make_user(self.co_a, 'fg147-normal', role='normal')
        resp = auth(normal).post(
            '/api/django/compta/travaux-en-cours/',
            {'nature': 'wip', 'montant': '1000',
             'date_arrete': '2026-01-01'},
            format='json')
        self.assertEqual(resp.status_code, 403)
