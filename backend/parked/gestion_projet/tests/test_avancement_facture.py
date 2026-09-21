"""Tests du suivi avancement vs facturé (PROJ28).

Avancement physique = roll-up pondéré par charge (PROJ9) ; facturé = somme des
``facturation_pct`` des jalons ATTEINTS (bornée à 100). Écart = avancement −
facturé (> 0 sous-facturation, < 0 facturation d'avance).

Couvre : calcul de l'écart ; borne du % facturé à 100 ; montants projetés
(% × budget) ; endpoint ; scoping (404 cross-tenant) ; accès
Administrateur/Responsable (403 pour ``normal``).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import Jalon, Projet, Tache

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


class AvancementFactureSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-avf-sel', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-AVF', nom='Projet',
            budget_total=Decimal('100000'))

    def test_ecart_sous_facturation(self):
        # Avancement : une tâche feuille à 60 % (charge 10) → projet 60 %.
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T',
            avancement_pct=60, charge_estimee=Decimal('10'), ordre=1)
        # Facturé : jalon atteint 30 %.
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='Acompte',
            date_prevue=date(2026, 1, 1), statut=Jalon.Statut.ATTEINT,
            facturation_pct=Decimal('30'))
        data = selectors.avancement_vs_facture(self.projet)
        self.assertEqual(data['avancement_pct'], Decimal('60'))
        self.assertEqual(data['facture_pct'], Decimal('30'))
        self.assertEqual(data['ecart_pct'], Decimal('30'))
        # Montants : 60 % et 30 % de 100000.
        self.assertEqual(data['montant_avancement'], Decimal('60000.00'))
        self.assertEqual(data['montant_facture'], Decimal('30000.00'))

    def test_facture_pct_borne_a_100(self):
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='J1',
            date_prevue=date(2026, 1, 1), statut=Jalon.Statut.ATTEINT,
            facturation_pct=Decimal('70'))
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='J2',
            date_prevue=date(2026, 1, 2), statut=Jalon.Statut.ATTEINT,
            facturation_pct=Decimal('60'))
        data = selectors.avancement_vs_facture(self.projet)
        self.assertEqual(data['facture_pct'], Decimal('100'))


class AvancementFactureApiTests(TestCase):
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co_a = make_company('gp-avf-a', 'A')
        self.co_b = make_company('gp-avf-b', 'B')
        self.user_a = make_user(self.co_a, 'avf-a')
        self.projet = Projet.objects.create(
            company=self.co_a, code='P-A', nom='A',
            budget_total=Decimal('100000'))

    def test_endpoint(self):
        api = auth(self.user_a)
        resp = api.get(f'{self.BASE}{self.projet.id}/avancement-vs-facture/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('avancement_pct', resp.data)
        self.assertIn('ecart_pct', resp.data)

    def test_cross_tenant_404(self):
        autre = Projet.objects.create(company=self.co_b, code='P-B', nom='B')
        api = auth(self.user_a)
        resp = api.get(f'{self.BASE}{autre.id}/avancement-vs-facture/')
        self.assertEqual(resp.status_code, 404)

    def test_role_normal_interdit(self):
        normal = make_user(self.co_a, 'avf-normal', role='normal')
        api = auth(normal)
        resp = api.get(f'{self.BASE}{self.projet.id}/avancement-vs-facture/')
        self.assertEqual(resp.status_code, 403)
