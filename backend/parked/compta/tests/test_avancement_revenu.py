"""Tests FG146 — Reconnaissance du revenu par avancement (% completion).

Couvre : le calcul du % d'avancement (cost-to-cost et saisie), le revenu cumulé
et le delta de période FIGÉS au constat, l'écriture OD de reconnaissance
(3427 / 71xx, équilibrée), l'idempotence cumulative (deux constats successifs ne
double-comptent pas), la pose de ``company`` / ``reference`` / ``%`` côté serveur
(jamais imposables), l'isolation multi-société, le gate de rôle et le sélecteur
de synthèse. Tout est additif et scopé société.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    ContratAvancement, EcritureComptable, LigneEcriture,
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


class ContratAvancementServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('fg146-svc', 'FG146 Svc')
        self.user = make_user(self.co, 'fg146-svc-user')

    def test_creation_pose_reference_et_statut(self):
        c = services.creer_contrat_avancement(
            self.co, revenu_total=Decimal('1000000'),
            cout_total_estime=Decimal('700000'),
            libelle='Chantier A', user=self.user)
        self.assertTrue(c.reference.startswith('CONTRAT-'))
        self.assertEqual(c.statut, ContratAvancement.Statut.EN_COURS)
        self.assertEqual(c.created_by, self.user)

    def test_avancement_cost_to_cost(self):
        # 700 000 estimés, 350 000 engagés → 50 % ; CA 1 000 000 → 500 000.
        c = services.creer_contrat_avancement(
            self.co, revenu_total=Decimal('1000000'),
            cout_total_estime=Decimal('700000'), user=self.user)
        constat = services.constater_avancement(
            c, date_arrete=date(2026, 3, 31),
            cout_engage_cumule=Decimal('350000'), user=self.user)
        self.assertEqual(constat.pourcentage, Decimal('50.00'))
        self.assertEqual(constat.revenu_cumule, Decimal('500000.00'))
        self.assertEqual(constat.revenu_periode, Decimal('500000.00'))

    def test_avancement_saisie_explicite(self):
        c = services.creer_contrat_avancement(
            self.co, revenu_total=Decimal('200000'),
            methode=ContratAvancement.Methode.SAISIE, user=self.user)
        constat = services.constater_avancement(
            c, date_arrete=date(2026, 3, 31), pourcentage=Decimal('25'),
            user=self.user)
        self.assertEqual(constat.pourcentage, Decimal('25.00'))
        self.assertEqual(constat.revenu_cumule, Decimal('50000.00'))

    def test_deux_constats_ne_double_comptent_pas(self):
        c = services.creer_contrat_avancement(
            self.co, revenu_total=Decimal('1000000'),
            cout_total_estime=Decimal('1000000'), user=self.user)
        c1 = services.constater_avancement(
            c, date_arrete=date(2026, 3, 31),
            cout_engage_cumule=Decimal('300000'), user=self.user)
        c2 = services.constater_avancement(
            c, date_arrete=date(2026, 6, 30),
            cout_engage_cumule=Decimal('800000'), user=self.user)
        self.assertEqual(c1.revenu_periode, Decimal('300000.00'))
        self.assertEqual(c2.revenu_cumule, Decimal('800000.00'))
        self.assertEqual(c2.revenu_periode, Decimal('500000.00'))
        c.refresh_from_db()
        self.assertEqual(c.revenu_reconnu, Decimal('800000.00'))

    def test_ecriture_od_equilibree_et_liee(self):
        c = services.creer_contrat_avancement(
            self.co, revenu_total=Decimal('100000'),
            cout_total_estime=Decimal('100000'), user=self.user)
        constat = services.constater_avancement(
            c, date_arrete=date(2026, 3, 31),
            cout_engage_cumule=Decimal('40000'), user=self.user)
        self.assertIsNotNone(constat.ecriture_id)
        ec = EcritureComptable.objects.get(id=constat.ecriture_id)
        lignes = LigneEcriture.objects.filter(ecriture=ec)
        debit = sum((line.debit for line in lignes), Decimal('0'))
        credit = sum((line.credit for line in lignes), Decimal('0'))
        self.assertEqual(debit, credit)
        self.assertEqual(debit, Decimal('40000.00'))
        numeros = {line.compte.numero for line in lignes}
        self.assertIn('3427', numeros)

    def test_poster_false_ne_passe_pas_ecriture(self):
        c = services.creer_contrat_avancement(
            self.co, revenu_total=Decimal('100000'),
            cout_total_estime=Decimal('100000'), user=self.user)
        constat = services.constater_avancement(
            c, date_arrete=date(2026, 3, 31),
            cout_engage_cumule=Decimal('40000'), poster=False,
            user=self.user)
        self.assertIsNone(constat.ecriture_id)

    def test_selecteur_synthese(self):
        c = services.creer_contrat_avancement(
            self.co, revenu_total=Decimal('1000000'),
            cout_total_estime=Decimal('600000'), user=self.user)
        services.constater_avancement(
            c, date_arrete=date(2026, 3, 31),
            cout_engage_cumule=Decimal('300000'), user=self.user)
        data = selectors.avancement_contrat(self.co, c)
        self.assertEqual(data['revenu_reconnu'], Decimal('500000.00'))
        self.assertEqual(data['reste_a_reconnaitre'], Decimal('500000.00'))
        self.assertEqual(data['marge_estimee'], Decimal('400000'))
        self.assertEqual(data['nb_constats'], 1)


class ContratAvancementApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('fg146-a', 'FG146 A')
        self.co_b = make_company('fg146-b', 'FG146 B')
        self.user_a = make_user(self.co_a, 'fg146-user-a')
        self.user_b = make_user(self.co_b, 'fg146-user-b')

    def test_create_pose_company_serveur(self):
        resp = auth(self.user_a).post(
            '/api/django/compta/contrats-avancement/',
            {'revenu_total': '500000', 'cout_total_estime': '300000',
             'libelle': 'Marché X', 'company': self.co_b.id},
            format='json')
        self.assertEqual(resp.status_code, 201)
        c = ContratAvancement.objects.get(id=resp.data['id'])
        self.assertEqual(c.company_id, self.co_a.id)
        self.assertTrue(c.reference.startswith('CONTRAT-'))

    def test_constater_action_calcule_serveur(self):
        c = services.creer_contrat_avancement(
            self.co_a, revenu_total=Decimal('1000000'),
            cout_total_estime=Decimal('1000000'), user=self.user_a)
        resp = auth(self.user_a).post(
            f'/api/django/compta/contrats-avancement/{c.id}/constater/',
            {'date_arrete': '2026-03-31', 'cout_engage_cumule': '250000',
             'pourcentage': '99',           # ignoré (méthode couts).
             'revenu_periode': '999999'},   # tentative d'imposer le revenu.
            format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(
            Decimal(str(resp.data['pourcentage'])), Decimal('25.00'))
        self.assertEqual(
            Decimal(str(resp.data['revenu_periode'])), Decimal('250000.00'))

    def test_avancement_action(self):
        c = services.creer_contrat_avancement(
            self.co_a, revenu_total=Decimal('100000'),
            cout_total_estime=Decimal('100000'), user=self.user_a)
        services.constater_avancement(
            c, date_arrete=date(2026, 3, 31),
            cout_engage_cumule=Decimal('50000'), user=self.user_a)
        resp = auth(self.user_a).get(
            f'/api/django/compta/contrats-avancement/{c.id}/avancement/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            Decimal(str(resp.data['revenu_reconnu'])), Decimal('50000.00'))

    def test_isolation_liste(self):
        services.creer_contrat_avancement(
            self.co_a, revenu_total=Decimal('1'), user=self.user_a)
        resp_b = auth(self.user_b).get(
            '/api/django/compta/contrats-avancement/')
        results = resp_b.data.get('results', resp_b.data)
        self.assertEqual(len(results), 0)

    def test_refuse_role_normal(self):
        normal = make_user(self.co_a, 'fg146-normal', role='normal')
        resp = auth(normal).post(
            '/api/django/compta/contrats-avancement/',
            {'revenu_total': '1000'}, format='json')
        self.assertEqual(resp.status_code, 403)
