"""Tests XPRJ20 — jours fériés marocains pré-remplis (depuis core/calendar.py).

Couvre : seed idempotent (aucun doublon en re-run), dates issues EXCLUSIVEMENT
de ``core.calendar`` (zéro date en dur côté gestion_projet), message fêtes
mobiles manquantes pour une année sans jeu codé, et l'action/la commande.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet.models import CalendrierProjet, JourFerie, Projet
from apps.gestion_projet.services import seeder_feries_calendrier
from core.calendar import moroccan_holidays

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


class SeederFeriesServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj20', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-X20', nom='Projet X20')
        self.calendrier = CalendrierProjet.objects.create(
            company=self.co, projet=self.projet)

    def test_seed_dates_issues_de_core_calendar(self):
        resultat = seeder_feries_calendrier(self.calendrier, 2026)
        attendues = moroccan_holidays(2026)
        self.assertEqual(set(resultat['crees']), attendues)
        self.assertEqual(
            JourFerie.objects.filter(calendrier=self.calendrier).count(),
            len(attendues))

    def test_idempotence_rerun(self):
        seeder_feries_calendrier(self.calendrier, 2026)
        nb_avant = JourFerie.objects.filter(calendrier=self.calendrier).count()
        resultat2 = seeder_feries_calendrier(self.calendrier, 2026)
        nb_apres = JourFerie.objects.filter(calendrier=self.calendrier).count()
        self.assertEqual(nb_avant, nb_apres)
        self.assertEqual(resultat2['crees'], [])
        self.assertEqual(resultat2['nb_deja_presents'], nb_avant)

    def test_fetes_mobiles_manquantes_annee_non_codee(self):
        resultat = seeder_feries_calendrier(self.calendrier, 2099)
        self.assertTrue(resultat['fetes_mobiles_manquantes'])

    def test_fetes_mobiles_presentes_annee_codee(self):
        resultat = seeder_feries_calendrier(self.calendrier, 2026)
        self.assertFalse(resultat['fetes_mobiles_manquantes'])


class SeedFeriesEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj20-api', 'S')
        self.user = make_user(self.co, 'resp-xprj20')
        self.projet = Projet.objects.create(
            company=self.co, code='P-X20B', nom='Projet X20 API')
        self.calendrier = CalendrierProjet.objects.create(
            company=self.co, projet=self.projet)

    def test_action_seed_feries(self):
        api = auth(self.user)
        resp = api.post(
            f'/api/django/gestion-projet/calendriers/{self.calendrier.id}/'
            f'seed-feries/?annee=2026')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertGreater(resp.data['nb_crees'], 0)

    def test_action_404_autre_societe(self):
        autre_co = make_company('gp-xprj20-autre', 'Autre')
        autre_user = make_user(autre_co, 'user-autre-x20')
        api = auth(autre_user)
        resp = api.post(
            f'/api/django/gestion-projet/calendriers/{self.calendrier.id}/'
            f'seed-feries/?annee=2026')
        self.assertEqual(resp.status_code, 404)

    def test_action_annee_obligatoire(self):
        api = auth(self.user)
        resp = api.post(
            f'/api/django/gestion-projet/calendriers/{self.calendrier.id}/'
            f'seed-feries/')
        self.assertEqual(resp.status_code, 400)
