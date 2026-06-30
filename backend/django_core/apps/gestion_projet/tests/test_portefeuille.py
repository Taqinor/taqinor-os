"""Tests du tableau de bord portefeuille (PROJ36).

Agrège, par société, avancement / retards / risques / marge réelle / charge de
chaque projet + totaux. Donnée 100 % INTERNE. Couvre : une ligne par projet ;
totaux ; filtre statut ; scoping société (un autre tenant n'apparaît jamais) ;
accès Administrateur/Responsable (403 pour ``normal``).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import Projet, Tache

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


class PortefeuilleSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-pf-sel', 'S')

    def test_agregation_et_totaux(self):
        p1 = Projet.objects.create(
            company=self.co, code='P1', nom='Un',
            budget_total=Decimal('10000'))
        # Tâche en retard (fin prévue passée, non terminée) + charge.
        hier = date.today() - timedelta(days=5)
        Tache.objects.create(
            company=self.co, projet=p1, libelle='En retard',
            date_fin_prevue=hier, charge_estimee=Decimal('4'),
            avancement_pct=20, ordre=1)
        Projet.objects.create(
            company=self.co, code='P2', nom='Deux',
            budget_total=Decimal('5000'))
        data = selectors.tableau_portefeuille(self.co)
        self.assertEqual(data['nb_projets'], 2)
        self.assertEqual(data['total_charge'], Decimal('4'))
        # Au moins un retard sur P1.
        self.assertGreaterEqual(data['total_retards'], 1)

    def test_filtre_statut(self):
        Projet.objects.create(
            company=self.co, code='PA', nom='A',
            statut=Projet.Statut.EN_COURS)
        Projet.objects.create(
            company=self.co, code='PB', nom='B',
            statut=Projet.Statut.BROUILLON)
        data = selectors.tableau_portefeuille(
            self.co, statut=Projet.Statut.EN_COURS)
        self.assertEqual(data['nb_projets'], 1)
        self.assertEqual(data['projets'][0]['code'], 'PA')


class PortefeuilleApiTests(TestCase):
    BASE = '/api/django/gestion-projet/projets/portefeuille/'

    def setUp(self):
        self.co_a = make_company('gp-pf-a', 'A')
        self.co_b = make_company('gp-pf-b', 'B')
        self.user_a = make_user(self.co_a, 'pf-a')
        Projet.objects.create(company=self.co_a, code='PA', nom='A')
        Projet.objects.create(company=self.co_b, code='PB', nom='B')

    def test_endpoint_scope_societe(self):
        api = auth(self.user_a)
        resp = api.get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['nb_projets'], 1)
        self.assertEqual(resp.data['projets'][0]['code'], 'PA')

    def test_role_normal_interdit(self):
        normal = make_user(self.co_a, 'pf-normal', role='normal')
        api = auth(normal)
        resp = api.get(self.BASE)
        self.assertEqual(resp.status_code, 403)
