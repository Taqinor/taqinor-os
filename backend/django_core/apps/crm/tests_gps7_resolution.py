"""GPS7 — GPS d'un lead depuis un lien Google Maps ou l'adresse.

Verrouille : l'extraction des coordonnées des différentes formes d'URL
Google Maps (repère !3d/!4d, ?q=, @, « lat, lng » nu), la résolution des
liens COURTS par redirection (réseau mocké), le géocodage d'adresse avec
repli VILLE du gazetier (précision annoncée, jamais maquillée), et le
résolveur HTTP pur (aucune écriture).
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.geolocalisation import (
    coords_depuis_adresse, coords_depuis_lien_maps)

User = get_user_model()


class LienMapsTests(TestCase):
    def test_url_avec_repere_3d4d(self):
        lien = ('https://www.google.com/maps/place/Taqinor/'
                '@33.58,-7.61,17z/data=!3m1!4b1!4m6!3m5!'
                '!3d33.573110!4d-7.589843')
        self.assertEqual(
            coords_depuis_lien_maps(lien),
            (Decimal('33.573110'), Decimal('-7.589843')))

    def test_url_avec_q(self):
        self.assertEqual(
            coords_depuis_lien_maps('https://maps.google.com/?q=31.62,-7.99'),
            (Decimal('31.62'), Decimal('-7.99')))

    def test_url_avec_arobase(self):
        self.assertEqual(
            coords_depuis_lien_maps(
                'https://www.google.com/maps/@34.0209,-6.8417,15z'),
            (Decimal('34.0209'), Decimal('-6.8417')))

    def test_coordonnees_nues(self):
        self.assertEqual(
            coords_depuis_lien_maps('33.5731, -7.5898'),
            (Decimal('33.5731'), Decimal('-7.5898')))

    def test_lien_sans_coordonnees_rend_None(self):
        self.assertIsNone(coords_depuis_lien_maps(
            'https://www.google.com/maps/place/Casablanca'))
        self.assertIsNone(coords_depuis_lien_maps(''))

    def test_lien_court_resolu_par_redirection(self):
        class _Reponse:
            url = 'https://www.google.com/maps/@33.9716,-6.8498,17z'
            text = ''
        with patch('requests.get', return_value=_Reponse()) as m_get:
            coords = coords_depuis_lien_maps('https://maps.app.goo.gl/AbC123')
        self.assertEqual(coords, (Decimal('33.9716'), Decimal('-6.8498')))
        self.assertTrue(m_get.called)

    def test_lien_court_en_panne_rend_None(self):
        with patch('requests.get', side_effect=OSError('down')):
            self.assertIsNone(
                coords_depuis_lien_maps('https://maps.app.goo.gl/AbC123'))


class AdresseTests(TestCase):
    def test_geocodage_nominatim(self):
        class _Reponse:
            ok = True

            @staticmethod
            def json():
                return [{'lat': '33.589886', 'lon': '-7.603869'}]
        with patch('requests.get', return_value=_Reponse()):
            resultat = coords_depuis_adresse(
                '12 rue des Fleurs', 'Casablanca')
        self.assertEqual(
            resultat,
            (Decimal('33.589886'), Decimal('-7.603869'), 'adresse'))

    def test_repli_ville_du_gazetier_quand_le_geocodeur_tombe(self):
        with patch('requests.get', side_effect=OSError('down')):
            resultat = coords_depuis_adresse('adresse illisible', 'Rabat')
        self.assertIsNotNone(resultat)
        lat, lng, precision = resultat
        self.assertEqual(precision, 'ville')
        # L'ancre GeoNames de Rabat, jamais un point inventé.
        self.assertAlmostEqual(float(lat), 34.02, places=1)

    def test_rien_de_resoluble_rend_None(self):
        with patch('requests.get', side_effect=OSError('down')):
            self.assertIsNone(coords_depuis_adresse('', ''))
            self.assertIsNone(coords_depuis_adresse('xyz', 'Atlantis'))


class ResolveurHttpTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='gps7', defaults={'nom': 'gps7'})
        self.user = User.objects.create_user(
            username='gps7-u', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_lien_resolu(self):
        resp = self.api.post(
            '/api/django/crm/leads/resoudre-gps/',
            {'lien': 'https://maps.google.com/?q=33.5731,-7.5898'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['gps_lat'], '33.5731')
        self.assertEqual(resp.data['gps_lng'], '-7.5898')
        self.assertEqual(resp.data['precision'], 'lien')

    def test_lien_illisible_400(self):
        resp = self.api.post(
            '/api/django/crm/leads/resoudre-gps/',
            {'lien': 'https://exemple.com/pas-une-carte'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_adresse_repli_ville(self):
        with patch('requests.get', side_effect=OSError('down')):
            resp = self.api.post(
                '/api/django/crm/leads/resoudre-gps/',
                {'adresse': '', 'ville': 'Marrakech'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['precision'], 'ville')
