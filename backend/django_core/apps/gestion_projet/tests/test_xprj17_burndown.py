"""Tests XPRJ17 — burndown du projet.

Couvre : série exacte sur un scénario multi-semaines (charge restante décroît
quand une tâche se termine, ligne idéale linéaire, heures loguées cumulées),
un projet sans charge estimée → réponse vide propre, et ``date_fin_reelle``
posée côté serveur au passage à TERMINE (XPRJ17 s'appuie dessus).
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


class BurndownSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj17', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-X17', nom='Projet X17')

    def test_sans_charge_estimee_reponse_vide(self):
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Sans charge')
        data = selectors.burndown(
            self.projet, date(2026, 1, 1), date(2026, 1, 15))
        self.assertEqual(data['points'], [])
        self.assertEqual(data['charge_totale'], Decimal('0'))

    def test_serie_multi_semaines_charge_decroit(self):
        # Tâche A : 5j, terminée le 8 janvier. Tâche B : 5j, jamais terminée
        # sur la fenêtre.
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='A',
            charge_estimee=Decimal('5'),
            statut=Tache.Statut.TERMINE, date_fin_reelle=date(2026, 1, 8))
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='B',
            charge_estimee=Decimal('5'))
        data = selectors.burndown(
            self.projet, date(2026, 1, 1), date(2026, 1, 15))
        self.assertEqual(data['charge_totale'], Decimal('10'))
        points_par_date = {p['date']: p for p in data['points']}
        # Semaine 1 (2026-01-01) : rien terminé → 10 restant.
        self.assertEqual(
            points_par_date['2026-01-01']['charge_restante'], Decimal('10'))
        # Semaine 2 (2026-01-08) : A pas encore < date, exactement à la date
        # de fin réelle → considérée terminée (date_fin_reelle == courant
        # n'est pas > courant) → seule B (5) reste.
        self.assertEqual(
            points_par_date['2026-01-08']['charge_restante'], Decimal('5'))
        # Semaine 3 (2026-01-15) : toujours 5 (B jamais terminée).
        self.assertEqual(
            points_par_date['2026-01-15']['charge_restante'], Decimal('5'))

    def test_ligne_ideale_lineaire(self):
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='A',
            charge_estimee=Decimal('10'))
        data = selectors.burndown(
            self.projet, date(2026, 1, 1), date(2026, 1, 15))
        points_par_date = {p['date']: p for p in data['points']}
        # Début : idéal = charge totale.
        self.assertEqual(
            points_par_date['2026-01-01']['charge_ideale'],
            Decimal('10.00'))
        # Fin : idéal = 0.
        self.assertEqual(
            points_par_date['2026-01-15']['charge_ideale'],
            Decimal('0.00'))

    def test_heures_loguees_cumulees(self):
        tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='A',
            charge_estimee=Decimal('10'))
        ressource = RessourceProfil.objects.create(company=self.co, nom='R')
        Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=tache,
            ressource=ressource, date=date(2026, 1, 1),
            heures=Decimal('8'))
        Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=tache,
            ressource=ressource, date=date(2026, 1, 8),
            heures=Decimal('8'))
        data = selectors.burndown(
            self.projet, date(2026, 1, 1), date(2026, 1, 15))
        points_par_date = {p['date']: p for p in data['points']}
        self.assertEqual(
            points_par_date['2026-01-01']['heures_loguees_cumulees'],
            Decimal('8'))
        self.assertEqual(
            points_par_date['2026-01-08']['heures_loguees_cumulees'],
            Decimal('16'))
        self.assertEqual(
            points_par_date['2026-01-15']['heures_loguees_cumulees'],
            Decimal('16'))


class BurndownEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj17-api', 'S')
        self.user = make_user(self.co, 'resp-xprj17')
        self.projet = Projet.objects.create(
            company=self.co, code='P-X17B', nom='Projet X17 API')

    def test_endpoint_scope_societe(self):
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='A',
            charge_estimee=Decimal('10'))
        api = auth(self.user)
        resp = api.get(
            f'/api/django/gestion-projet/projets/{self.projet.id}/'
            f'burndown/?debut=2026-01-01&fin=2026-01-15')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.data['points']) > 0)

    def test_endpoint_404_autre_societe(self):
        autre_co = make_company('gp-xprj17-autre', 'Autre')
        autre_user = make_user(autre_co, 'user-autre-x17')
        api = auth(autre_user)
        resp = api.get(
            f'/api/django/gestion-projet/projets/{self.projet.id}/'
            f'burndown/?debut=2026-01-01&fin=2026-01-15')
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_dates_obligatoires(self):
        api = auth(self.user)
        resp = api.get(
            f'/api/django/gestion-projet/projets/{self.projet.id}/'
            f'burndown/')
        self.assertEqual(resp.status_code, 400)


class DateFinReelleTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj17-dfr', 'S')
        self.user = make_user(self.co, 'resp-xprj17-dfr')
        self.projet = Projet.objects.create(
            company=self.co, code='P-X17C', nom='Projet X17 DFR')
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Tâche',
            charge_estimee=Decimal('3'))

    def test_date_fin_reelle_posee_au_passage_termine(self):
        api = auth(self.user)
        resp = api.patch(
            f'/api/django/gestion-projet/taches/{self.tache.id}/',
            {'statut': Tache.Statut.TERMINE}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.tache.refresh_from_db()
        self.assertIsNotNone(self.tache.date_fin_reelle)

    def test_date_fin_reelle_reinitialisee_si_reouverte(self):
        self.tache.statut = Tache.Statut.TERMINE
        self.tache.date_fin_reelle = date(2026, 1, 1)
        self.tache.save()
        api = auth(self.user)
        resp = api.patch(
            f'/api/django/gestion-projet/taches/{self.tache.id}/',
            {'statut': Tache.Statut.EN_COURS}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.tache.refresh_from_db()
        self.assertIsNone(self.tache.date_fin_reelle)

    def test_date_fin_reelle_non_ecrite_par_le_corps(self):
        api = auth(self.user)
        resp = api.patch(
            f'/api/django/gestion-projet/taches/{self.tache.id}/',
            {'date_fin_reelle': '2026-05-01'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.tache.refresh_from_db()
        self.assertIsNone(self.tache.date_fin_reelle)
