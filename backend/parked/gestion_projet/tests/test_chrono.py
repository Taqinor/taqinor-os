"""Tests du chrono start/stop sur tâche (XPRJ5).

Couvre : start/stop crée la timesheet avec la durée arrondie (quart d'heure
supérieur par défaut), un seul chrono actif par utilisateur (démarrer un
nouveau arrête l'ancien), un utilisateur sans ``RessourceProfil`` reçoit un
400 explicite à l'arrêt, l'endpoint global ``chrono-actif``.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import services
from apps.gestion_projet.models import ChronoEnCours, Projet, RessourceProfil, Tache

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


class ChronoServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-chrono-svc', 'S')
        self.user = make_user(self.co, 'chrono-svc')
        self.projet = Projet.objects.create(company=self.co, code='P-C', nom='C')
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T', ordre=1)
        self.ressource = RessourceProfil.objects.create(
            company=self.co, nom='R', user=self.user)

    def test_arrondi_quart_heure_superieur(self):
        # 1 minute -> arrondi à 15 min = 0.25 h.
        self.assertEqual(
            services._arrondir_duree_heures(1, 15), Decimal('0.25'))
        # exactement 15 -> reste 15 min = 0.25 h.
        self.assertEqual(
            services._arrondir_duree_heures(15, 15), Decimal('0.25'))
        # 16 minutes -> arrondi à 30 min = 0.50 h.
        self.assertEqual(
            services._arrondir_duree_heures(16, 15), Decimal('0.50'))
        # 0 minute -> 0 h.
        self.assertEqual(
            services._arrondir_duree_heures(0, 15), Decimal('0'))

    def test_demarrer_puis_arreter_cree_timesheet(self):
        services.demarrer_chrono(self.tache, self.user)
        chrono = ChronoEnCours.objects.get(user=self.user)
        # Recule le départ de 20 min pour simuler une durée écoulée.
        chrono.demarre_a = timezone.now() - timedelta(minutes=20)
        chrono.save(update_fields=['demarre_a'])

        timesheet = services.arreter_chrono(self.user)
        self.assertEqual(timesheet.heures, Decimal('0.50'))  # 20 min -> 30 min
        self.assertEqual(timesheet.ressource_id, self.ressource.id)
        self.assertEqual(timesheet.tache_id, self.tache.id)
        self.assertFalse(
            ChronoEnCours.objects.filter(user=self.user).exists())

    def test_un_seul_chrono_actif_par_user(self):
        tache2 = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T2', ordre=2)
        services.demarrer_chrono(self.tache, self.user)
        services.demarrer_chrono(tache2, self.user)
        self.assertEqual(
            ChronoEnCours.objects.filter(user=self.user).count(), 1)
        chrono = ChronoEnCours.objects.get(user=self.user)
        self.assertEqual(chrono.tache_id, tache2.id)

    def test_arreter_sans_chrono_actif_leve(self):
        with self.assertRaises(services.ChronoError):
            services.arreter_chrono(self.user)

    def test_arreter_sans_ressource_profil_leve(self):
        user_sans_ressource = make_user(self.co, 'chrono-sans-res')
        services.demarrer_chrono(self.tache, user_sans_ressource)
        with self.assertRaises(services.ChronoError):
            services.arreter_chrono(user_sans_ressource)


class ChronoApiTests(TestCase):
    TACHES_BASE = '/api/django/gestion-projet/taches/'
    CHRONO_ACTIF = '/api/django/gestion-projet/chrono-actif/'

    def setUp(self):
        self.co = make_company('gp-chrono-api', 'A')
        self.user = make_user(self.co, 'chrono-api')
        self.projet = Projet.objects.create(company=self.co, code='P-CA', nom='A')
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T', ordre=1)
        RessourceProfil.objects.create(
            company=self.co, nom='R', user=self.user)

    def test_demarrer_puis_arreter_endpoint(self):
        api = auth(self.user)
        resp = api.post(f'{self.TACHES_BASE}{self.tache.id}/demarrer-chrono/')
        self.assertEqual(resp.status_code, 201, resp.data)

        resp = api.post(f'{self.TACHES_BASE}{self.tache.id}/arreter-chrono/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('heures', resp.data)

    def test_arreter_sans_avoir_demarre_400(self):
        api = auth(self.user)
        resp = api.post(f'{self.TACHES_BASE}{self.tache.id}/arreter-chrono/')
        self.assertEqual(resp.status_code, 400)

    def test_chrono_actif_endpoint(self):
        api = auth(self.user)
        resp = api.get(self.CHRONO_ACTIF)
        self.assertEqual(resp.status_code, 204)

        api.post(f'{self.TACHES_BASE}{self.tache.id}/demarrer-chrono/')
        resp = api.get(self.CHRONO_ACTIF)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['tache'], self.tache.id)

    def test_isolation_tenant(self):
        co_b = make_company('gp-chrono-b', 'B')
        user_b = make_user(co_b, 'chrono-b')
        api = auth(user_b)
        resp = api.post(f'{self.TACHES_BASE}{self.tache.id}/demarrer-chrono/')
        self.assertEqual(resp.status_code, 404)
