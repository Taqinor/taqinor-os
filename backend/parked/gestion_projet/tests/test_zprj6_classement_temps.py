"""Tests du classement de saisie des temps — leaderboard interne (ZPRJ6).

Couvre : classement trié par complétude puis heures ; aucun montant/coût
interne exposé ; isolation tenant ; ressource sans user exclue ; endpoint
``timesheets/classement/``.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import Projet, RessourceProfil, Tache, Timesheet

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


class ClassementTempsSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-z6-sel', 'S')
        self.projet = Projet.objects.create(company=self.co, code='P-Z6', nom='P')
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T', ordre=1)
        self.assidu_user = make_user(self.co, 'z6-assidu')
        self.retard_user = make_user(self.co, 'z6-retard')
        self.assidu = RessourceProfil.objects.create(
            company=self.co, nom='Assidu', actif=True, user=self.assidu_user,
            cout_horaire=Decimal('200'))
        self.retard = RessourceProfil.objects.create(
            company=self.co, nom='Retard', actif=True, user=self.retard_user,
            cout_horaire=Decimal('300'))
        # Assidu saisit tous les jours ouvrés (1-5 juin 2026, 5 jours).
        for jour in range(1, 6):
            Timesheet.objects.create(
                company=self.co, projet=self.projet, tache=self.tache,
                ressource=self.assidu, date=date(2026, 6, jour),
                heures=Decimal('8'))
        # Retard ne saisit qu'un seul jour.
        Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=self.tache,
            ressource=self.retard, date=date(2026, 6, 1),
            heures=Decimal('8'))

    def test_classement_trie_par_completude(self):
        data = selectors.classement_temps(
            self.co, date(2026, 6, 1), date(2026, 6, 5))
        noms = [ln['ressource_nom'] for ln in data['lignes']]
        self.assertEqual(noms[0], 'Assidu')
        self.assertEqual(noms[1], 'Retard')

    def test_completude_et_retard_corrects(self):
        data = selectors.classement_temps(
            self.co, date(2026, 6, 1), date(2026, 6, 5))
        assidu_ligne = next(
            ln for ln in data['lignes'] if ln['ressource_nom'] == 'Assidu')
        retard_ligne = next(
            ln for ln in data['lignes'] if ln['ressource_nom'] == 'Retard')
        self.assertEqual(assidu_ligne['taux_completude_pct'], 100.0)
        self.assertEqual(assidu_ligne['jours_de_retard'], 0)
        self.assertEqual(assidu_ligne['total_heures'], 40.0)
        self.assertEqual(retard_ligne['taux_completude_pct'], 20.0)
        self.assertEqual(retard_ligne['jours_de_retard'], 4)
        self.assertEqual(retard_ligne['total_heures'], 8.0)

    def test_aucun_montant_interne_expose(self):
        data = selectors.classement_temps(
            self.co, date(2026, 6, 1), date(2026, 6, 5))
        for ligne in data['lignes']:
            self.assertNotIn('cout', ligne)
            self.assertNotIn('cout_horaire', ligne)

    def test_ressource_sans_user_exclue(self):
        RessourceProfil.objects.create(
            company=self.co, nom='SansUser', actif=True)
        data = selectors.classement_temps(
            self.co, date(2026, 6, 1), date(2026, 6, 5))
        noms = [ln['ressource_nom'] for ln in data['lignes']]
        self.assertNotIn('SansUser', noms)

    def test_isolation_societe(self):
        co_b = make_company('gp-z6-b', 'B')
        user_b = make_user(co_b, 'z6-b-u')
        RessourceProfil.objects.create(
            company=co_b, nom='AutreSociete', actif=True, user=user_b)
        data = selectors.classement_temps(
            self.co, date(2026, 6, 1), date(2026, 6, 5))
        noms = [ln['ressource_nom'] for ln in data['lignes']]
        self.assertNotIn('AutreSociete', noms)


class ClassementTempsApiTests(TestCase):
    BASE = '/api/django/gestion-projet/timesheets/classement/'

    def setUp(self):
        self.co_a = make_company('gp-z6-api-a', 'A')
        self.co_b = make_company('gp-z6-api-b', 'B')
        self.user_a = make_user(self.co_a, 'z6-api-a')
        self.user_b = make_user(self.co_b, 'z6-api-b')
        self.normal = make_user(self.co_a, 'z6-api-normal', role='normal')

    def test_endpoint_ok(self):
        api = auth(self.user_a)
        resp = api.get(
            self.BASE, {'debut': '2026-06-01', 'fin': '2026-06-05'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('lignes', resp.data)

    def test_dates_manquantes_400(self):
        api = auth(self.user_a)
        resp = api.get(self.BASE)
        self.assertEqual(resp.status_code, 400)

    def test_role_normal_interdit(self):
        api = auth(self.normal)
        resp = api.get(
            self.BASE, {'debut': '2026-06-01', 'fin': '2026-06-05'})
        self.assertEqual(resp.status_code, 403)
