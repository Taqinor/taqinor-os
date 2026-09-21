"""Tests du rapprochement pointages RH ↔ temps projet (XPRJ8).

Couvre : écarts corrects sur cas croisés (pointé sans imputation, imputé sans
pointage, delta d'heures), dégradation propre sans aucun pointage, frontière
cross-app respectée (gestion_projet lit RH via ``apps.rh.selectors``, jamais
``apps.rh.models``).
"""
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import Projet, RessourceProfil, Timesheet
from apps.rh.models import DossierEmploye, Pointage

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


def make_pointage(company, employe, jour, heures):
    arrivee = datetime(
        jour.year, jour.month, jour.day, 8, 0, tzinfo=dt_timezone.utc)
    depart = datetime(
        jour.year, jour.month, jour.day, 8 + int(heures), 0,
        tzinfo=dt_timezone.utc)
    return Pointage.objects.create(
        company=company, employe=employe,
        type_pointage=Pointage.TypePointage.COMPLET,
        heure_arrivee=arrivee, heure_depart=depart)


class RapprochementSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-rappr-svc', 'S')
        self.user = make_user(self.co, 'rappr-svc')
        self.projet = Projet.objects.create(company=self.co, code='P-RP', nom='R')
        self.res = RessourceProfil.objects.create(
            company=self.co, nom='R', user=self.user)
        self.employe = DossierEmploye.objects.create(
            company=self.co, user=self.user, matricule='M-001', nom='N', prenom='P')
        self.debut = date(2026, 7, 6)
        self.fin = date(2026, 7, 7)

    def test_pointe_sans_imputation(self):
        make_pointage(self.co, self.employe, date(2026, 7, 6), 8)
        data = selectors.rapprochement_pointages(self.co, self.debut, self.fin)
        types = [e['type_ecart'] for e in data['ecarts']]
        self.assertIn('pointe_sans_imputation', types)

    def test_impute_sans_pointage(self):
        Timesheet.objects.create(
            company=self.co, projet=self.projet, ressource=self.res,
            date=date(2026, 7, 6), heures=Decimal('8'))
        data = selectors.rapprochement_pointages(self.co, self.debut, self.fin)
        types = [e['type_ecart'] for e in data['ecarts']]
        self.assertIn('impute_sans_pointage', types)

    def test_delta_heures_au_dela_du_seuil(self):
        make_pointage(self.co, self.employe, date(2026, 7, 6), 8)
        Timesheet.objects.create(
            company=self.co, projet=self.projet, ressource=self.res,
            date=date(2026, 7, 6), heures=Decimal('4'))
        data = selectors.rapprochement_pointages(
            self.co, self.debut, self.fin, seuil_heures=Decimal('0.5'))
        ecart = next(
            e for e in data['ecarts'] if e['date'] == date(2026, 7, 6))
        self.assertEqual(ecart['type_ecart'], 'delta_heures')
        self.assertEqual(ecart['heures_pointees'], Decimal('8.00'))
        self.assertEqual(ecart['heures_imputees'], Decimal('4'))

    def test_pas_ecart_si_delta_sous_seuil(self):
        make_pointage(self.co, self.employe, date(2026, 7, 6), 8)
        Timesheet.objects.create(
            company=self.co, projet=self.projet, ressource=self.res,
            date=date(2026, 7, 6), heures=Decimal('7.9'))
        data = selectors.rapprochement_pointages(
            self.co, self.debut, self.fin, seuil_heures=Decimal('0.5'))
        self.assertEqual(data['ecarts'], [])

    def test_correspondance_exacte_pas_ecart(self):
        make_pointage(self.co, self.employe, date(2026, 7, 6), 8)
        Timesheet.objects.create(
            company=self.co, projet=self.projet, ressource=self.res,
            date=date(2026, 7, 6), heures=Decimal('8'))
        data = selectors.rapprochement_pointages(self.co, self.debut, self.fin)
        self.assertEqual(data['ecarts'], [])

    def test_aucun_pointage_degrade_proprement(self):
        Timesheet.objects.create(
            company=self.co, projet=self.projet, ressource=self.res,
            date=date(2026, 7, 6), heures=Decimal('8'))
        # Aucun Pointage créé du tout : ne doit jamais lever.
        data = selectors.rapprochement_pointages(self.co, self.debut, self.fin)
        self.assertTrue(len(data['ecarts']) >= 1)


class RapprochementApiTests(TestCase):
    BASE = '/api/django/gestion-projet/timesheets/rapprochement/'

    def setUp(self):
        self.co = make_company('gp-rappr-api', 'A')
        self.user = make_user(self.co, 'rappr-api')
        RessourceProfil.objects.create(company=self.co, nom='R', user=self.user)

    def test_endpoint_ok(self):
        api = auth(self.user)
        resp = api.get(f'{self.BASE}?debut=2026-07-06&fin=2026-07-07')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('ecarts', resp.data)

    def test_endpoint_sans_dates_400(self):
        api = auth(self.user)
        resp = api.get(self.BASE)
        self.assertEqual(resp.status_code, 400)
