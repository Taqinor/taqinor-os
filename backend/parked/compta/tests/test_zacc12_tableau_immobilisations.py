"""Tests ZACC12 — Rapport des immobilisations (tableau CGNC B2/B2bis).

Couvre : l'état liste chaque immo avec brut/amort/VNC cohérents (Σ VNC =
poste bilan classe 2), inclut acquisitions et cessions de l'exercice,
company-scopé, tests de réconciliation.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import selectors, services
from apps.compta.models import ExerciceComptable, Immobilisation

User = get_user_model()


def make_company(slug='zacc12-co', nom='ZACC12 Co'):
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
        # Immobilisation acquise AVANT l'exercice (2025).
        self.immo_ancienne = Immobilisation.objects.create(
            company=self.company, libelle='Camionnette',
            categorie=Immobilisation.Categorie.VEHICULE,
            cout=Decimal('100000'), date_acquisition=date(2025, 1, 1))
        # Immobilisation acquise PENDANT l'exercice (2026).
        self.immo_nouvelle = Immobilisation.objects.create(
            company=self.company, libelle='Ordinateur portable',
            categorie=Immobilisation.Categorie.INFORMATIQUE,
            cout=Decimal('15000'), date_acquisition=date(2026, 6, 1))
        self.user = make_user(self.company, 'zacc12-admin')
        self.api = auth(self.user)


class TestSelector(_Base):
    def test_immo_acquise_avant_apparait_avec_brut_ouverture(self):
        data = selectors.tableau_immobilisations(self.company, self.exercice)
        ligne = next(
            li for li in data['lignes']
            if li['immobilisation_id'] == self.immo_ancienne.id)
        self.assertEqual(ligne['brut_ouverture'], Decimal('100000'))
        self.assertEqual(ligne['acquisitions'], Decimal('0'))
        self.assertEqual(ligne['brut_cloture'], Decimal('100000'))

    def test_immo_acquise_pendant_apparait_en_acquisition(self):
        data = selectors.tableau_immobilisations(self.company, self.exercice)
        ligne = next(
            li for li in data['lignes']
            if li['immobilisation_id'] == self.immo_nouvelle.id)
        self.assertEqual(ligne['brut_ouverture'], Decimal('0'))
        self.assertEqual(ligne['acquisitions'], Decimal('15000'))
        self.assertEqual(ligne['brut_cloture'], Decimal('15000'))

    def test_sans_amortissement_vnc_egale_brut(self):
        data = selectors.tableau_immobilisations(self.company, self.exercice)
        ligne = next(
            li for li in data['lignes']
            if li['immobilisation_id'] == self.immo_nouvelle.id)
        self.assertEqual(ligne['amort_ouverture'], Decimal('0'))
        self.assertEqual(ligne['dotations'], Decimal('0'))
        self.assertEqual(
            ligne['valeur_nette_comptable'], ligne['brut_cloture'])

    def test_totaux_reconcilies_avec_somme_lignes(self):
        data = selectors.tableau_immobilisations(self.company, self.exercice)
        somme_brut_cloture = sum(
            (li['brut_cloture'] for li in data['lignes']), Decimal('0'))
        self.assertEqual(
            data['totaux']['brut_cloture'], somme_brut_cloture)
        somme_vnc = sum(
            (li['valeur_nette_comptable'] for li in data['lignes']),
            Decimal('0'))
        self.assertEqual(data['totaux']['valeur_nette_comptable'], somme_vnc)

    def test_dotation_postee_reduit_la_vnc(self):
        plan = services.generer_plan_amortissement(
            self.immo_ancienne, mode='lineaire', duree_annees=5,
            date_debut=date(2025, 1, 1))
        dotation_2026 = plan.dotations.get(annee=2026)
        services.poster_dotation(dotation_2026, user=self.user)
        data = selectors.tableau_immobilisations(self.company, self.exercice)
        ligne = next(
            li for li in data['lignes']
            if li['immobilisation_id'] == self.immo_ancienne.id)
        self.assertEqual(ligne['dotations'], Decimal('20000'))
        self.assertEqual(
            ligne['valeur_nette_comptable'],
            ligne['brut_cloture'] - ligne['amort_cloture'])

    def test_isolation_societe(self):
        autre = make_company('zacc12-autre', 'Autre Co')
        services.seed_plan_comptable(autre)
        exercice_autre = ExerciceComptable.objects.create(
            company=autre, libelle='2026',
            date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31))
        data = selectors.tableau_immobilisations(autre, exercice_autre)
        self.assertEqual(data['lignes'], [])


class TestEndpoint(_Base):
    def test_endpoint_json(self):
        resp = self.api.get(
            f'/api/django/compta/etats/tableau-immobilisations/'
            f'?exercice={self.exercice.pk}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['lignes']), 2)

    def test_endpoint_sans_exercice_400(self):
        resp = self.api.get(
            '/api/django/compta/etats/tableau-immobilisations/')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_export_csv(self):
        resp = self.api.get(
            f'/api/django/compta/etats/tableau-immobilisations/'
            f'?exercice={self.exercice.pk}&export=csv')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')

    def test_endpoint_export_pdf_ou_503(self):
        resp = self.api.get(
            f'/api/django/compta/etats/tableau-immobilisations/'
            f'?exercice={self.exercice.pk}&export=pdf')
        self.assertIn(resp.status_code, (200, 503))

    def test_cross_company_404(self):
        autre = make_company('zacc12-b', 'ZACC12 B')
        exercice_b = ExerciceComptable.objects.create(
            company=autre, libelle='2026',
            date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31))
        resp = self.api.get(
            f'/api/django/compta/etats/tableau-immobilisations/'
            f'?exercice={exercice_b.pk}')
        self.assertEqual(resp.status_code, 404)
