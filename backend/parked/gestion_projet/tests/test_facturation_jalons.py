"""Tests des jalons de facturation liés à l'avancement (PROJ27).

Un jalon est FACTURABLE quand il est ATTEINT et porte un ``facturation_pct`` > 0.
Le montant théorique = ``facturation_pct`` % du ``budget_total`` (interne).
L'écriture de la facture passe par ``ventes.services`` (frontière cross-app) ;
tant qu'aucune entrée dédiée n'y existe, on DÉGRADE en proposition (aucune
facture créée).

Couvre : sélecteur ``jalons_facturables`` (atteint+pct>0) ; refus de facturer un
jalon non atteint / sans pct (400) ; proposition dégradée (facture_creee=False) ;
endpoints ; scoping (404 cross-tenant) ; accès Administrateur/Responsable (403).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors, services
from apps.gestion_projet.models import Jalon, Projet

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


class JalonsFacturablesSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-fj-sel', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-FJ', nom='Projet jalons',
            budget_total=Decimal('100000'))

    def test_facturable_si_atteint_et_pct(self):
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='Acompte',
            date_prevue=date(2026, 1, 1), statut=Jalon.Statut.ATTEINT,
            facturation_pct=Decimal('30'))
        # Jalon atteint mais sans pct → non facturable.
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='Repère',
            date_prevue=date(2026, 1, 2), statut=Jalon.Statut.ATTEINT,
            facturation_pct=Decimal('0'))
        # Jalon avec pct mais pas atteint → non facturable.
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='Solde',
            date_prevue=date(2026, 1, 3), statut=Jalon.Statut.A_VENIR,
            facturation_pct=Decimal('40'))
        data = selectors.jalons_facturables(self.projet)
        facturables = [j for j in data['jalons'] if j['facturable']]
        self.assertEqual(len(facturables), 1)
        self.assertEqual(facturables[0]['libelle'], 'Acompte')
        # Montant = 30 % de 100000 = 30000.00.
        self.assertEqual(facturables[0]['montant'], Decimal('30000.00'))
        self.assertEqual(data['total_pct_facture'], Decimal('30'))


class FacturationServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-fj-svc', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-FJ2', nom='P',
            budget_total=Decimal('50000'))

    def test_refus_jalon_non_atteint(self):
        jalon = Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='J',
            date_prevue=date(2026, 1, 1), statut=Jalon.Statut.A_VENIR,
            facturation_pct=Decimal('20'))
        with self.assertRaises(services.FacturationJalonError):
            services.declencher_facturation_jalon(jalon)

    def test_refus_jalon_sans_pct(self):
        jalon = Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='J',
            date_prevue=date(2026, 1, 1), statut=Jalon.Statut.ATTEINT,
            facturation_pct=Decimal('0'))
        with self.assertRaises(services.FacturationJalonError):
            services.declencher_facturation_jalon(jalon)

    def test_proposition_degradee(self):
        jalon = Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='J',
            date_prevue=date(2026, 1, 1), statut=Jalon.Statut.ATTEINT,
            facturation_pct=Decimal('20'))
        data = services.declencher_facturation_jalon(jalon)
        self.assertFalse(data['facture_creee'])
        self.assertEqual(data['montant'], Decimal('10000.00'))
        self.assertIn('proposition', data['note'].lower())


class FacturationApiTests(TestCase):
    PROJETS = '/api/django/gestion-projet/projets/'
    JALONS = '/api/django/gestion-projet/jalons/'

    def setUp(self):
        self.co_a = make_company('gp-fj-a', 'A')
        self.co_b = make_company('gp-fj-b', 'B')
        self.user_a = make_user(self.co_a, 'fj-a')
        self.projet = Projet.objects.create(
            company=self.co_a, code='P-A', nom='A',
            budget_total=Decimal('100000'))
        self.jalon = Jalon.objects.create(
            company=self.co_a, projet=self.projet, libelle='Acompte',
            date_prevue=date(2026, 1, 1), statut=Jalon.Statut.ATTEINT,
            facturation_pct=Decimal('30'))

    def test_jalons_facturables_endpoint(self):
        api = auth(self.user_a)
        resp = api.get(f'{self.PROJETS}{self.projet.id}/jalons-facturables/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['jalons']), 1)
        self.assertTrue(resp.data['jalons'][0]['facturable'])

    def test_facturer_endpoint(self):
        api = auth(self.user_a)
        resp = api.post(f'{self.JALONS}{self.jalon.id}/facturer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['montant'], '30000.00')
        self.assertFalse(resp.data['facture_creee'])

    def test_facturer_non_atteint_400(self):
        jalon = Jalon.objects.create(
            company=self.co_a, projet=self.projet, libelle='X',
            date_prevue=date(2026, 1, 2), statut=Jalon.Statut.A_VENIR,
            facturation_pct=Decimal('10'))
        api = auth(self.user_a)
        resp = api.post(f'{self.JALONS}{jalon.id}/facturer/')
        self.assertEqual(resp.status_code, 400)

    def test_cross_tenant_404(self):
        autre_p = Projet.objects.create(company=self.co_b, code='P-B', nom='B')
        autre_j = Jalon.objects.create(
            company=self.co_b, projet=autre_p, libelle='J',
            date_prevue=date(2026, 1, 1), statut=Jalon.Statut.ATTEINT,
            facturation_pct=Decimal('10'))
        api = auth(self.user_a)
        resp = api.post(f'{self.JALONS}{autre_j.id}/facturer/')
        self.assertEqual(resp.status_code, 404)

    def test_role_normal_interdit(self):
        normal = make_user(self.co_a, 'fj-normal', role='normal')
        api = auth(normal)
        resp = api.post(f'{self.JALONS}{self.jalon.id}/facturer/')
        self.assertEqual(resp.status_code, 403)
