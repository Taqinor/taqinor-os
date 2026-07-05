"""Tests ZACC3 — Tableau de financement / des flux de trésorerie CGNC
(méthode indirecte).

Couvre : les 3 sections (exploitation/investissement/financement) dont la
somme = variation nette de trésorerie, réconciliée avec la position
d'ouverture à clôture ; exports csv/pdf ; company-scopé.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import selectors, services
from apps.compta.models import ExerciceComptable

User = get_user_model()


def make_company(slug='zacc3-co', nom='ZACC3 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _Base(TestCase):
    def setUp(self):
        self.company = make_company()
        services.seed_plan_comptable(self.company)
        services.seed_journaux(self.company)
        self.exercice = ExerciceComptable.objects.create(
            company=self.company, libelle='2026',
            date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31))
        journal_od = services._journal(
            self.company, services.Journal.Type.OPERATIONS_DIVERSES)
        compte_capital = services.get_compte(self.company, '1111')
        compte_banque = services.get_compte(self.company, '5141')
        # Apport initial en capital -> trésorerie d'ouverture non nulle.
        services.creer_ecriture_od(
            self.company, '2025-06-01', 'Apport capital',
            [
                {'compte': compte_banque, 'debit': Decimal('20000'),
                 'credit': Decimal('0')},
                {'compte': compte_capital, 'debit': Decimal('0'),
                 'credit': Decimal('20000')},
            ], journal=journal_od)
        # Vente encaissée sur l'exercice (résultat + trésorerie).
        compte_ventes = services.get_compte(self.company, '7121')
        services.creer_ecriture_od(
            self.company, '2026-03-10', 'Vente encaissée',
            [
                {'compte': compte_banque, 'debit': Decimal('5000'),
                 'credit': Decimal('0')},
                {'compte': compte_ventes, 'debit': Decimal('0'),
                 'credit': Decimal('5000')},
            ], journal=journal_od)
        self.user = make_user(self.company, 'zacc3-admin')
        self.api = auth(self.user)


class TestSelector(_Base):
    def test_trois_sections_presentes(self):
        data = selectors.tableau_flux_tresorerie(self.company, self.exercice)
        self.assertIn('exploitation', data)
        self.assertIn('investissement', data)
        self.assertIn('financement', data)

    def test_somme_des_flux_egale_variation_nette(self):
        data = selectors.tableau_flux_tresorerie(self.company, self.exercice)
        somme = (data['exploitation']['flux_net']
                 + data['investissement']['flux_net']
                 + data['financement']['flux_net'])
        self.assertEqual(somme, data['variation_nette_tresorerie'])

    def test_reconciliation_ouverture_cloture(self):
        data = selectors.tableau_flux_tresorerie(self.company, self.exercice)
        self.assertTrue(data['reconciliee'])
        self.assertEqual(
            data['tresorerie_ouverture'] + data['variation_nette_tresorerie'],
            data['tresorerie_cloture'])

    def test_flux_exploitation_reflete_le_resultat(self):
        data = selectors.tableau_flux_tresorerie(self.company, self.exercice)
        # Vente de 5000 encaissée directement en banque (pas de créance
        # ouverte) : le résultat net = 5000, la CAF = 5000 (pas de
        # dotation/reprise), le BFR ne bouge pas -> flux exploitation = 5000.
        self.assertEqual(
            data['exploitation']['resultat_net'], Decimal('5000'))
        self.assertEqual(
            data['exploitation']['capacite_autofinancement'], Decimal('5000'))
        self.assertEqual(data['exploitation']['flux_net'], Decimal('5000'))

    def test_variation_tresorerie_correspond_aux_mouvements_bancaires(self):
        data = selectors.tableau_flux_tresorerie(self.company, self.exercice)
        # Seule la vente de 5000 se produit PENDANT l'exercice 2026 (l'apport
        # de capital est daté de 2025, donc dans la trésorerie d'ouverture).
        self.assertEqual(data['variation_nette_tresorerie'], Decimal('5000'))
        self.assertEqual(data['tresorerie_ouverture'], Decimal('20000'))
        self.assertEqual(data['tresorerie_cloture'], Decimal('25000'))

    def test_isolation_societe(self):
        autre = make_company('zacc3-autre', 'Autre Co')
        services.seed_plan_comptable(autre)
        exercice_autre = ExerciceComptable.objects.create(
            company=autre, libelle='2026',
            date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31))
        data = selectors.tableau_flux_tresorerie(autre, exercice_autre)
        self.assertEqual(data['tresorerie_ouverture'], Decimal('0'))
        self.assertEqual(data['tresorerie_cloture'], Decimal('0'))


class TestEndpoint(_Base):
    def test_endpoint_json(self):
        resp = self.api.get(
            f'/api/django/compta/etats/tableau-flux/'
            f'?exercice={self.exercice.pk}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('exploitation', resp.data)

    def test_endpoint_sans_exercice_400(self):
        resp = self.api.get('/api/django/compta/etats/tableau-flux/')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_exercice_inconnu_404(self):
        resp = self.api.get(
            '/api/django/compta/etats/tableau-flux/?exercice=999999')
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_export_csv(self):
        resp = self.api.get(
            f'/api/django/compta/etats/tableau-flux/'
            f'?exercice={self.exercice.pk}&export=csv')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')

    def test_endpoint_export_pdf_ou_503(self):
        resp = self.api.get(
            f'/api/django/compta/etats/tableau-flux/'
            f'?exercice={self.exercice.pk}&export=pdf')
        self.assertIn(resp.status_code, (200, 503))

    def test_cross_company_404(self):
        autre = make_company('zacc3-b', 'ZACC3 B')
        exercice_b = ExerciceComptable.objects.create(
            company=autre, libelle='2026',
            date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31))
        resp = self.api.get(
            f'/api/django/compta/etats/tableau-flux/'
            f'?exercice={exercice_b.pk}')
        self.assertEqual(resp.status_code, 404)
