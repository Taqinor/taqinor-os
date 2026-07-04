"""Tests de la facturation en régie (T&M) depuis les temps approuvés (XPRJ3).

Couvre : action ``projets/<id>/facturer-temps/`` sélectionne les timesheets
APPROUVÉES + facturables + non encore facturées d'une période, groupe par
tâche/type d'activité, crée une ``ventes.Facture`` BROUILLON (numérotée via
``apps/ventes/utils/references.py``), marque les lignes ``facture_id`` ; un
re-run est idempotent (0 ligne re-facturée) ; les timesheets non approuvées
sont exclues ; sans client résolvable → erreur explicite.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.gestion_projet import services
from apps.gestion_projet.models import Projet, RessourceProfil, Tache, Timesheet
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


class FacturerTempsServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-regie-svc', 'S')
        self.client_crm = Client.objects.create(
            company=self.co, nom='Client Régie')
        self.projet = Projet.objects.create(
            company=self.co, code='P-REG', nom='R', client_id=self.client_crm.id)
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Dépannage', ordre=1)
        self.res = RessourceProfil.objects.create(company=self.co, nom='R')
        self.user = make_user(self.co, 'regie-svc')

    def _ts(self, jour, heures, statut=Timesheet.Statut.APPROUVEE,
            facturable=True, taux=Decimal('300'), tache=None):
        return Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=tache or self.tache,
            ressource=self.res, date=jour, heures=heures, statut=statut,
            facturable=facturable, taux_facturation=taux,
            type_activite=Timesheet.TypeActivite.SAV)

    def test_facture_creee_montant_correct(self):
        self._ts(date(2026, 7, 1), Decimal('4'))
        self._ts(date(2026, 7, 2), Decimal('2'))
        resultat = services.facturer_temps_projet(
            self.projet, debut=date(2026, 7, 1), fin=date(2026, 7, 31),
            user=self.user)
        self.assertEqual(resultat['montant_ht'], Decimal('1800.00'))  # 6h*300
        self.assertEqual(resultat['nb_lignes'], 2)
        facture = resultat['facture']
        self.assertEqual(facture.company_id, self.co.id)
        self.assertEqual(facture.client_id, self.client_crm.id)
        self.assertEqual(facture.statut, Facture.Statut.BROUILLON)
        self.assertTrue(facture.reference)

    def test_lignes_marquees_facture_id(self):
        ts1 = self._ts(date(2026, 7, 1), Decimal('4'))
        resultat = services.facturer_temps_projet(
            self.projet, debut=date(2026, 7, 1), fin=date(2026, 7, 31),
            user=self.user)
        ts1.refresh_from_db()
        self.assertEqual(ts1.facture_id, resultat['facture'].id)

    def test_rerun_idempotent_zero_relignes(self):
        self._ts(date(2026, 7, 1), Decimal('4'))
        services.facturer_temps_projet(
            self.projet, debut=date(2026, 7, 1), fin=date(2026, 7, 31),
            user=self.user)
        with self.assertRaises(services.FacturationRegieError):
            services.facturer_temps_projet(
                self.projet, debut=date(2026, 7, 1), fin=date(2026, 7, 31),
                user=self.user)
        # Une seule facture au total.
        self.assertEqual(
            Facture.objects.filter(company=self.co).count(), 1)

    def test_timesheet_non_approuvee_exclue(self):
        self._ts(date(2026, 7, 1), Decimal('4'),
                 statut=Timesheet.Statut.SOUMISE)
        with self.assertRaises(services.FacturationRegieError):
            services.facturer_temps_projet(
                self.projet, debut=date(2026, 7, 1), fin=date(2026, 7, 31),
                user=self.user)

    def test_timesheet_non_facturable_exclue(self):
        self._ts(date(2026, 7, 1), Decimal('4'), facturable=False)
        with self.assertRaises(services.FacturationRegieError):
            services.facturer_temps_projet(
                self.projet, debut=date(2026, 7, 1), fin=date(2026, 7, 31),
                user=self.user)

    def test_sans_client_leve_erreur(self):
        projet_sans_client = Projet.objects.create(
            company=self.co, code='P-NC', nom='NC')
        Timesheet.objects.create(
            company=self.co, projet=projet_sans_client, ressource=self.res,
            date=date(2026, 7, 1), heures=Decimal('4'),
            statut=Timesheet.Statut.APPROUVEE, facturable=True,
            taux_facturation=Decimal('300'))
        with self.assertRaises(services.FacturationRegieError):
            services.facturer_temps_projet(
                projet_sans_client, debut=date(2026, 7, 1),
                fin=date(2026, 7, 31), user=self.user)


class FacturerTempsApiTests(TestCase):
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co = make_company('gp-regie-api', 'A')
        self.client_crm = Client.objects.create(
            company=self.co, nom='Client API')
        self.user = make_user(self.co, 'regie-api')
        self.projet = Projet.objects.create(
            company=self.co, code='P-API', nom='A', client_id=self.client_crm.id)
        self.res = RessourceProfil.objects.create(company=self.co, nom='R')
        Timesheet.objects.create(
            company=self.co, projet=self.projet, ressource=self.res,
            date=date(2026, 8, 5), heures=Decimal('3'),
            statut=Timesheet.Statut.APPROUVEE, facturable=True,
            taux_facturation=Decimal('250'))

    def test_endpoint_cree_facture(self):
        api = auth(self.user)
        resp = api.post(
            f'{self.BASE}{self.projet.id}/facturer-temps/',
            {'debut': '2026-08-01', 'fin': '2026-08-31'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['montant_ht'], '750.00')
        self.assertEqual(resp.data['nb_lignes'], 1)

    def test_endpoint_sans_dates_400(self):
        api = auth(self.user)
        resp = api.post(
            f'{self.BASE}{self.projet.id}/facturer-temps/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_rerun_400(self):
        api = auth(self.user)
        api.post(
            f'{self.BASE}{self.projet.id}/facturer-temps/',
            {'debut': '2026-08-01', 'fin': '2026-08-31'}, format='json')
        resp = api.post(
            f'{self.BASE}{self.projet.id}/facturer-temps/',
            {'debut': '2026-08-01', 'fin': '2026-08-31'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_tenant(self):
        co_b = make_company('gp-regie-b', 'B')
        user_b = make_user(co_b, 'regie-b')
        api = auth(user_b)
        resp = api.post(
            f'{self.BASE}{self.projet.id}/facturer-temps/',
            {'debut': '2026-08-01', 'fin': '2026-08-31'}, format='json')
        self.assertEqual(resp.status_code, 404)
