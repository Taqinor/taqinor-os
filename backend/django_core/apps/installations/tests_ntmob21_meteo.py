"""NTMOB21 — météo terrain (Open-Meteo) pour « Ma journée ».

Aucun appel réseau réel : ``weather.fetch_forecast`` est mocké (l'API externe
n'est jamais jointe en test). On vérifie le message, le cache serveur d'une
heure (un seul appel externe pour deux requêtes au même point) et le repli
gracieux quand la source est indisponible.
"""
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company, CustomUser

URL = '/api/django/installations/meteo/'


class Ntmob21MeteoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='Taqinor NTMOB21',
                                              slug='taqinor-ntmob21')
        self.user = CustomUser.objects.create_user(
            username='tech-ntmob21', password='x', company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def test_message_de_pluie_quand_le_seuil_est_franchi(self):
        with patch('apps.installations.weather.fetch_forecast',
                   return_value={'precipitation_mm': 12.0,
                                 'windgusts_kmh': 10.0}):
            resp = self.api.get(URL, {'lat': 33.57, 'lon': -7.59})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['disponible'])
        self.assertIn('Pluie', resp.data['message'])

    def test_pas_de_message_quand_la_journee_est_calme(self):
        with patch('apps.installations.weather.fetch_forecast',
                   return_value={'precipitation_mm': 0.0,
                                 'windgusts_kmh': 5.0}):
            resp = self.api.get(URL, {'lat': 33.57, 'lon': -7.59})
        self.assertTrue(resp.data['disponible'])
        self.assertIsNone(resp.data['message'])

    def test_cache_serveur_une_heure_par_coordonnee(self):
        with patch('apps.installations.weather.fetch_forecast',
                   return_value={'precipitation_mm': 12.0,
                                 'windgusts_kmh': 10.0}) as mock_fetch:
            self.api.get(URL, {'lat': 33.57, 'lon': -7.59})
            self.api.get(URL, {'lat': 33.57, 'lon': -7.59})
            self.assertEqual(mock_fetch.call_count, 1)
            # Un autre point n'est pas servi par la même entrée de cache.
            self.api.get(URL, {'lat': 31.63, 'lon': -8.01})
            self.assertEqual(mock_fetch.call_count, 2)

    def test_repli_gracieux_si_la_source_est_indisponible(self):
        with patch('apps.installations.weather.fetch_forecast',
                   return_value=None):
            resp = self.api.get(URL, {'lat': 33.57, 'lon': -7.59})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['disponible'])
        self.assertIn('indisponible', resp.data['message'])

    def test_coordonnees_absentes_ne_font_jamais_planter(self):
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['disponible'])

    def test_anonyme_refuse(self):
        anon = APIClient()
        self.assertIn(anon.get(URL).status_code, (401, 403))
