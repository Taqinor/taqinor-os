"""Tests de la détection des temps manquants + rappels (XPRJ7).

Couvre : ``selectors.temps_manquants`` liste les jours OUVRÉS sans saisie par
ressource active liée à un user (fériés/indispos exclus via
``Indisponibilite``), l'endpoint ``timesheets/manquants/``, et la commande
``rappels_timesheets`` (idempotente — notifie une fois par ressource/jour).
"""
from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors, services
from apps.gestion_projet.models import Indisponibilite, Projet, RessourceProfil, Timesheet
from apps.notifications.models import EventType, Notification

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


class TempsManquantsSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-manq-svc', 'S')
        self.user = make_user(self.co, 'manq-svc')
        self.projet = Projet.objects.create(company=self.co, code='P-M', nom='M')
        self.res = RessourceProfil.objects.create(
            company=self.co, nom='R', user=self.user)
        # Semaine du lundi 2026-07-06 au vendredi 2026-07-10 (jours ouvrés).
        self.debut = date(2026, 7, 6)
        self.fin = date(2026, 7, 10)

    def test_aucune_saisie_tous_jours_manquants(self):
        data = selectors.temps_manquants(self.co, self.debut, self.fin)
        self.assertEqual(len(data['lignes']), 1)
        ligne = data['lignes'][0]
        self.assertEqual(ligne['ressource_id'], self.res.id)
        self.assertEqual(ligne['jours_attendus'], 5)
        self.assertEqual(len(ligne['jours_manquants']), 5)

    def test_jour_sasi_exclu_des_manquants(self):
        Timesheet.objects.create(
            company=self.co, projet=self.projet, ressource=self.res,
            date=date(2026, 7, 6), heures=Decimal('8'))
        data = selectors.temps_manquants(self.co, self.debut, self.fin)
        ligne = data['lignes'][0]
        self.assertEqual(len(ligne['jours_manquants']), 4)
        self.assertNotIn(date(2026, 7, 6), ligne['jours_manquants'])

    def test_weekend_exclu(self):
        # Samedi/dimanche ne sont jamais des jours ouvrés attendus.
        data = selectors.temps_manquants(
            self.co, date(2026, 7, 11), date(2026, 7, 12))
        self.assertEqual(data['lignes'], [])

    def test_indisponibilite_exclut_le_jour(self):
        Indisponibilite.objects.create(
            company=self.co, ressource=self.res,
            date_debut=date(2026, 7, 6), date_fin=date(2026, 7, 7))
        data = selectors.temps_manquants(self.co, self.debut, self.fin)
        ligne = data['lignes'][0]
        self.assertEqual(ligne['jours_attendus'], 3)  # 5 - 2 jours indispo

    def test_ressource_sans_user_ignoree(self):
        RessourceProfil.objects.create(company=self.co, nom='Sans user')
        data = selectors.temps_manquants(self.co, self.debut, self.fin)
        # Toujours une seule ligne (celle avec user).
        self.assertEqual(len(data['lignes']), 1)

    def test_ressource_tout_saisi_absente_des_lignes(self):
        for i in range(6, 11):
            Timesheet.objects.create(
                company=self.co, projet=self.projet, ressource=self.res,
                date=date(2026, 7, i), heures=Decimal('8'))
        data = selectors.temps_manquants(self.co, self.debut, self.fin)
        self.assertEqual(data['lignes'], [])


class TempsManquantsApiTests(TestCase):
    BASE = '/api/django/gestion-projet/timesheets/manquants/'

    def setUp(self):
        self.co = make_company('gp-manq-api', 'A')
        self.user = make_user(self.co, 'manq-api')
        RessourceProfil.objects.create(company=self.co, nom='R', user=self.user)

    def test_endpoint_retourne_lignes(self):
        api = auth(self.user)
        resp = api.get(
            f'{self.BASE}?debut=2026-07-06&fin=2026-07-10')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['lignes']), 1)

    def test_endpoint_sans_dates_400(self):
        api = auth(self.user)
        resp = api.get(self.BASE)
        self.assertEqual(resp.status_code, 400)


class RappelsTimesheetsServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-manq-rappel', 'R')
        self.user = make_user(self.co, 'manq-rappel')
        RessourceProfil.objects.create(company=self.co, nom='R', user=self.user)

    def test_notifie_une_fois_par_ressource(self):
        resultat = services.rappeler_temps_manquants(
            self.co, date(2026, 7, 6), date(2026, 7, 10))
        self.assertEqual(resultat['nb_en_retard'], 1)
        self.assertEqual(resultat['nb_notifies'], 1)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.user, event_type=EventType.DIGEST).count(),
            1)

    def test_rerun_idempotent_meme_jour(self):
        services.rappeler_temps_manquants(
            self.co, date(2026, 7, 6), date(2026, 7, 10))
        resultat2 = services.rappeler_temps_manquants(
            self.co, date(2026, 7, 6), date(2026, 7, 10))
        self.assertEqual(resultat2['nb_notifies'], 0)
        self.assertEqual(resultat2['nb_deja_notifies'], 1)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.user, event_type=EventType.DIGEST).count(),
            1)

    def test_aucune_ressource_en_retard_zero_notif(self):
        co2 = make_company('gp-manq-rappel-vide', 'V')
        resultat = services.rappeler_temps_manquants(
            co2, date(2026, 7, 6), date(2026, 7, 10))
        self.assertEqual(resultat['nb_en_retard'], 0)
        self.assertEqual(resultat['nb_notifies'], 0)


class RappelsTimesheetsCommandTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-manq-cmd', 'C')
        self.user = make_user(self.co, 'manq-cmd')
        RessourceProfil.objects.create(company=self.co, nom='R', user=self.user)

    def test_commande_notifie_et_idempotente(self):
        out = StringIO()
        call_command(
            'rappels_timesheets', company='gp-manq-cmd',
            debut='2026-07-06', fin='2026-07-10', stdout=out)
        self.assertIn('1 notification', out.getvalue())

        out2 = StringIO()
        call_command(
            'rappels_timesheets', company='gp-manq-cmd',
            debut='2026-07-06', fin='2026-07-10', stdout=out2)
        self.assertIn('0 notification', out2.getvalue())
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.user, event_type=EventType.DIGEST).count(),
            1)

    def test_commande_company_inconnue_leve(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command('rappels_timesheets', company='inconnue-xyz')
