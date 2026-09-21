"""Tests de la classification facturable + type d'activité (XPRJ2).

Couvre : ``Timesheet`` porte ``facturable``/``type_activite``/
``taux_facturation`` ; la synthèse des temps (``synthese_temps_projet``)
ventile facturable/non-facturable et par type d'activité ; ``cout``/
``cout_horaire`` INTERNES restent absents de toute sortie client.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import Projet, RessourceProfil, Timesheet

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


class TimesheetFacturableFieldsTests(TestCase):
    BASE = '/api/django/gestion-projet/timesheets/'

    def setUp(self):
        self.co = make_company('gp-fact-a', 'A')
        self.user = make_user(self.co, 'fact-a')
        self.projet = Projet.objects.create(company=self.co, code='P-F', nom='A')
        self.res = RessourceProfil.objects.create(
            company=self.co, nom='R', cout_horaire=Decimal('100'))

    def test_creation_avec_facturable_et_activite(self):
        api = auth(self.user)
        resp = api.post(self.BASE, {
            'projet': self.projet.id,
            'ressource': self.res.id,
            'date': '2026-06-01',
            'heures': '3',
            'facturable': False,
            'type_activite': 'admin',
            'taux_facturation': '250',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['facturable'], False)
        self.assertEqual(resp.data['type_activite'], 'admin')
        self.assertEqual(resp.data['taux_facturation'], '250.00')

    def test_defaut_facturable_true(self):
        api = auth(self.user)
        resp = api.post(self.BASE, {
            'projet': self.projet.id,
            'ressource': self.res.id,
            'date': '2026-06-02',
            'heures': '2',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['facturable'], True)
        self.assertEqual(resp.data['type_activite'], 'pose')

    def test_cout_interne_jamais_expose_champ_supplementaire(self):
        # cout reste présent (déjà interne géré ailleurs) mais aucun champ
        # cout_horaire de la ressource ne fuite dans la sortie timesheet.
        api = auth(self.user)
        resp = api.post(self.BASE, {
            'projet': self.projet.id,
            'ressource': self.res.id,
            'date': '2026-06-03',
            'heures': '2',
        }, format='json')
        self.assertNotIn('cout_horaire', resp.data)


class SyntheseTempsVentileeTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-fact-syn', 'S')
        self.projet = Projet.objects.create(company=self.co, code='P-FS', nom='S')
        self.r1 = RessourceProfil.objects.create(
            company=self.co, nom='R1', cout_horaire=Decimal('100'))
        Timesheet.objects.create(
            company=self.co, projet=self.projet, ressource=self.r1,
            date=date(2026, 6, 1), heures=Decimal('4'), cout=Decimal('400'),
            facturable=True, type_activite=Timesheet.TypeActivite.POSE)
        Timesheet.objects.create(
            company=self.co, projet=self.projet, ressource=self.r1,
            date=date(2026, 6, 2), heures=Decimal('2'), cout=Decimal('200'),
            facturable=False, type_activite=Timesheet.TypeActivite.ADMIN)
        Timesheet.objects.create(
            company=self.co, projet=self.projet, ressource=self.r1,
            date=date(2026, 6, 3), heures=Decimal('1'), cout=Decimal('100'),
            facturable=True, type_activite=Timesheet.TypeActivite.ETUDE)

    def test_ventilation_facturable_non_facturable(self):
        data = selectors.synthese_temps_projet(self.projet)
        self.assertEqual(data['heures_facturables'], Decimal('5'))
        self.assertEqual(data['heures_non_facturables'], Decimal('2'))
        self.assertEqual(data['total_heures'], Decimal('7'))

    def test_ventilation_par_activite(self):
        data = selectors.synthese_temps_projet(self.projet)
        par_type = {a['type_activite']: a for a in data['par_activite']}
        self.assertEqual(par_type['pose']['heures'], Decimal('4'))
        self.assertEqual(par_type['admin']['heures'], Decimal('2'))
        self.assertEqual(par_type['admin']['heures_facturables'], Decimal('0'))
        self.assertEqual(par_type['etude']['heures'], Decimal('1'))

    def test_par_ressource_ventile_facturable(self):
        data = selectors.synthese_temps_projet(self.projet)
        r = data['par_ressource'][0]
        self.assertEqual(r['heures_facturables'], Decimal('5'))
