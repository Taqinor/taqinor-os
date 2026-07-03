"""Tests XRH12 — Géofence de pointage chantier (optionnelle).

Couvre :
* pointage à ~2 km d'un chantier avec géofence 500 m → ``hors_zone=True`` +
  un ``IncidentPresence`` créé ;
* géofence désactivée (``geofence_metres=None``, défaut) → aucun flag ;
* tests de la formule haversine (F6) ;
* réglage RH posé côté serveur (singleton par société, get_or_create).
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.rh import services
from apps.rh.models import (
    DossierEmploye,
    IncidentPresence,
    PresenceChantier,
    ReglageRH,
)
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()

REGLAGES = '/api/django/rh/reglages/mon-reglage/'


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


# Chantier de référence : Casablanca centre.
CHANTIER_LAT, CHANTIER_LNG = 33.5731, -7.5898
# ~2 km au nord.
LOIN_LAT, LOIN_LNG = 33.5911, -7.5898
# Même point (0 m).
PRES_LAT, PRES_LNG = 33.5731, -7.5898


class GeofenceServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('geo-a', 'A')
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='G1', nom='Fassi', prenom='Amine')
        self.presence = PresenceChantier.objects.create(
            company=self.co, employe=self.emp, installation_id=42,
            date='2026-07-01')

    def test_haversine_distance_zero_pour_meme_point(self):
        d = services._haversine_metres(
            CHANTIER_LAT, CHANTIER_LNG, CHANTIER_LAT, CHANTIER_LNG)
        self.assertAlmostEqual(d, 0, delta=1)

    def test_haversine_distance_approx_2km(self):
        d = services._haversine_metres(
            CHANTIER_LAT, CHANTIER_LNG, LOIN_LAT, LOIN_LNG)
        self.assertGreater(d, 1800)
        self.assertLess(d, 2200)

    def test_hors_zone_flag_et_incident(self):
        ReglageRH.objects.create(company=self.co, geofence_metres=500)
        with mock.patch(
                'apps.installations.selectors.installation_gps_map',
                return_value={42: (CHANTIER_LAT, CHANTIER_LNG)}):
            services.controler_geofence_presence(
                self.presence, LOIN_LAT, LOIN_LNG)
        self.assertTrue(self.presence.hors_zone)
        self.assertEqual(
            IncidentPresence.objects.filter(employe=self.emp).count(), 1)

    def test_dans_le_rayon_aucun_flag(self):
        ReglageRH.objects.create(company=self.co, geofence_metres=500)
        with mock.patch(
                'apps.installations.selectors.installation_gps_map',
                return_value={42: (CHANTIER_LAT, CHANTIER_LNG)}):
            services.controler_geofence_presence(
                self.presence, PRES_LAT, PRES_LNG)
        self.assertFalse(self.presence.hors_zone)
        self.assertEqual(
            IncidentPresence.objects.filter(employe=self.emp).count(), 0)

    def test_geofence_desactivee_aucun_controle(self):
        # Pas de ReglageRH créé → geofence_metres=None → comportement désactivé.
        with mock.patch(
                'apps.installations.selectors.installation_gps_map',
                return_value={42: (CHANTIER_LAT, CHANTIER_LNG)}) as mocked:
            services.controler_geofence_presence(
                self.presence, LOIN_LAT, LOIN_LNG)
        self.assertFalse(self.presence.hors_zone)
        mocked.assert_not_called()

    def test_sans_gps_reference_chantier_aucun_flag(self):
        ReglageRH.objects.create(company=self.co, geofence_metres=500)
        with mock.patch(
                'apps.installations.selectors.installation_gps_map',
                return_value={42: (None, None)}):
            services.controler_geofence_presence(
                self.presence, LOIN_LAT, LOIN_LNG)
        self.assertFalse(self.presence.hors_zone)


class EmargerGeofenceApiTests(TestCase):
    def setUp(self):
        self.co = make_company('geo-b', 'B')
        self.rh = make_user(self.co, 'geo-rh')
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='G2', nom='Ziani', prenom='Nabil')
        self.presence = PresenceChantier.objects.create(
            company=self.co, employe=self.emp, installation_id=7,
            date='2026-07-01')

    def test_emarger_avec_gps_hors_zone(self):
        ReglageRH.objects.create(company=self.co, geofence_metres=500)
        with mock.patch(
                'apps.installations.selectors.installation_gps_map',
                return_value={7: (CHANTIER_LAT, CHANTIER_LNG)}):
            resp = auth(self.rh).post(
                f'/api/django/rh/presences-chantier/{self.presence.id}/'
                f'emarger/',
                {'gps_lat': str(LOIN_LAT), 'gps_lng': str(LOIN_LNG)})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['hors_zone'])

    def test_reglage_get_or_create_singleton(self):
        resp = auth(self.rh).get(REGLAGES)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['geofence_metres'])
        resp = auth(self.rh).patch(REGLAGES, {'geofence_metres': 300})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['geofence_metres'], 300)
        self.assertEqual(ReglageRH.objects.filter(company=self.co).count(), 1)
