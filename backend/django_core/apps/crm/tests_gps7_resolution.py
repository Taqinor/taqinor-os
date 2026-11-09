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
    coords_depuis_adresse, coords_depuis_lien_maps, est_lien_court,
    olc_decoder, olc_encoder,
    olc_retrouver, resoudre_lien_maps)

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


class _NominatimVide:
    """Nominatim joignable mais qui ne connaît pas le lieu (réponse ``[]``)."""
    ok = True

    @staticmethod
    def json():
        return []


class LieuDitTests(TestCase):
    """VREF-LIEUX (08/09/2026) — le douar « sidi hashass » : Nominatim rend
    ``[]``, le lieu-dit GeoNames (Douar Sidi Hashas, près de Madagh) place le
    lead avec la précision ``'lieu-dit'`` ANNONCÉE — jamais maquillée en
    adresse ; un homonyme (« Oulad Ali ») ne place jamais en silence."""

    def test_lieu_dit_geonames_quand_nominatim_ignore_le_douar(self):
        with patch('requests.get', return_value=_NominatimVide()):
            resultat = coords_depuis_adresse('sidi hashass', '')
        self.assertIsNotNone(resultat)
        lat, lng, precision = resultat
        self.assertEqual(precision, 'lieu-dit')
        self.assertEqual((lat, lng), (Decimal('35.00611'), Decimal('-2.37346')))

    def test_adresse_douar_corroboree_par_la_ville_du_lead(self):
        with patch('requests.get', return_value=_NominatimVide()):
            resultat = coords_depuis_adresse('Douar Sidi Hashass', 'Berkane')
        self.assertEqual(resultat[2], 'lieu-dit')

    def test_homonyme_ne_place_jamais_en_silence(self):
        with patch('requests.get', return_value=_NominatimVide()):
            self.assertIsNone(coords_depuis_adresse('oulad ali', ''))


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

    def test_lien_illisible_404(self):
        # ERR-ENF11-FUZZ-CRM : requête conforme, aucune coordonnée à trouver.
        resp = self.api.post(
            '/api/django/crm/leads/resoudre-gps/',
            {'lien': 'https://exemple.com/pas-une-carte'}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_adresse_repli_ville(self):
        with patch('requests.get', side_effect=OSError('down')):
            resp = self.api.post(
                '/api/django/crm/leads/resoudre-gps/',
                {'adresse': '', 'ville': 'Marrakech'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['precision'], 'ville')


_CONSENT = ('https://consent.google.com/ml?continue=https://www.google.com/'
            'maps/search/33.381037,%2B-7.545323?entry%3Dtts&gl=NL')
_GEO_ADRESSE = 'apps.crm.geolocalisation.coords_depuis_adresse'
_CASA = (Decimal('33.5731'), Decimal('-7.5898'), 'ville')


class FormesGoogleTests(TestCase):
    """Formats réels d'un lien / texte client : coordonnées entières, repère
    déposé (``/search/lat,lng``, consentement), DMS (même encodé deux fois),
    plus codes, noms de lieu. Réseau et géocodeur mockés."""

    def _exact(self, texte, attendu):
        with patch(_GEO_ADRESSE, side_effect=AssertionError('géocodé')):
            self.assertEqual(
                resoudre_lien_maps(texte),
                (Decimal(attendu[0]), Decimal(attendu[1]), 'lien'), texte)

    def test_repere_depose_search_et_consentement(self):
        attendu = ('33.381037', '-7.545323')
        self._exact(_CONSENT, attendu)
        self._exact('https://www.google.com/maps/search/33.381037,+-7.545323'
                    '?entry=tts', attendu)

    def test_entiers_search_place_et_nu(self):
        self._exact('https://maps.google.com/?q=33,-7', ('33', '-7'))
        self._exact('https://www.google.com/maps/place/33.5731,-7.5898',
                    ('33.5731', '-7.5898'))
        self._exact('https://www.google.com/maps/search/33.5731,-7.5898/',
                    ('33.5731', '-7.5898'))
        self._exact('33.57; -7.58', ('33.57', '-7.58'))
        self._exact('33.57 -7.58', ('33.57', '-7.58'))
        self._exact('https://www.google.com/maps?ll=33.5,-7.5&z=15',
                    ('33.5', '-7.5'))

    def test_repere_exact_prime_sur_le_centre_de_la_carte(self):
        self._exact(
            'https://www.google.com/maps/place/Taqinor/@33.58,-7.61,17z/'
            'data=!3m1!4b1!4m6!3m5!3d33.573110!4d-7.589843',
            ('33.573110', '-7.589843'))

    def test_degres_minutes_secondes(self):
        attendu = ('33.509472', '-7.688361')
        for texte in (
                '33°30\'34.1"N 7°41\'18.1"W',
                '33° 30′ 34.1″ N, 7° 41′ 18.1″ W',
                "https://www.google.com/maps/place/33%C2%B030'34.1%22N+7%C2%B0"
                "41'18.1%22W",
                'https://consent.google.com/ml?continue=https%3A%2F%2Fwww.'
                'google.com%2Fmaps%2Fplace%2F33%25C2%25B030%2734.1%2522N%2B7'
                '%25C2%25B041%2718.1%2522W'):
            self._exact(texte, attendu)
        self._exact('33.5731 N, 7.5898 W', ('33.5731', '-7.5898'))
        with patch(_GEO_ADRESSE, return_value=None):
            self.assertIsNone(resoudre_lien_maps('33°75\'10"N 7°41\'18"W'))

    def test_plus_code_complet(self):
        lat, lng = olc_decoder('8FVC9G8F+6X')
        self.assertAlmostEqual(float(lat), 47.3655625, places=6)
        self.assertAlmostEqual(float(lng), 8.5249375, places=6)
        # vecteur du jeu de référence OLC : ce point tombe dans la cellule « 6W »
        self.assertEqual(olc_encoder('47.365562', '8.524813'), '8FVC9G8F+6W')
        resultat = resoudre_lien_maps('8FVC9G8F+6X')
        self.assertEqual(resultat[2], 'lien')
        self.assertAlmostEqual(float(resultat[0]), 47.365562, places=5)

    def test_plus_code_court_retrouve_pres_de_la_reference(self):
        self.assertEqual(olc_encoder(47.4, 8.6)[:4], '8FVC')
        lat, lng = olc_retrouver('9G8F+6X', 47.4, 8.6)
        self.assertEqual((float(lat), float(lng)), (47.3655625, 8.5249375))
        plein = olc_encoder('33.5731', '-7.5898')
        court = plein[4:]
        attendu = olc_decoder(plein)
        self.assertEqual(olc_retrouver(court, 33.6, -7.6), attendu)
        with patch(_GEO_ADRESSE, return_value=_CASA) as geo:
            resultat = resoudre_lien_maps(court + ' Casablanca')
        geo.assert_called_once_with('Casablanca', '')
        self.assertEqual(resultat[2], 'lien')
        self.assertAlmostEqual(float(resultat[0]), float(attendu[0]), places=5)
        self.assertAlmostEqual(float(resultat[1]), float(attendu[1]), places=5)
        # même code dans une URL Google (« + » encodé)
        url = ('https://www.google.com/maps/place/' + court.replace('+', '%2B')
               + '+Casablanca')
        with patch(_GEO_ADRESSE, return_value=_CASA):
            self.assertEqual(resoudre_lien_maps(url)[:2], resultat[:2])

    def test_plus_code_court_sans_reference_rend_None(self):
        with patch(_GEO_ADRESSE, return_value=None) as geo:
            self.assertIsNone(resoudre_lien_maps('8CQ9+X2 Casablanca'))
        geo.assert_called_once()
        with patch(_GEO_ADRESSE, side_effect=AssertionError('géocodé')):
            # ni localité ni ville : rien à géocoder, jamais d'invention
            self.assertIsNone(resoudre_lien_maps('8CQ9+X2'))

    def test_plus_code_court_utilise_la_ville_du_lead(self):
        with patch(_GEO_ADRESSE, return_value=_CASA) as geo:
            resultat = resoudre_lien_maps('8CQ9+X2', 'Casablanca')
        geo.assert_called_once_with('', 'Casablanca')
        self.assertEqual(resultat[2], 'lien')

    def test_sans_coordonnee_le_nom_du_lieu_est_geocode(self):
        cas = (
            ('https://www.google.com/maps/place/Hay+Mohammadi,+Casablanca/',
             'Hay Mohammadi, Casablanca'),
            ('https://www.google.com/maps?q=Rue+Allal+Ben+Abdellah+Rabat',
             'Rue Allal Ben Abdellah Rabat'),
            ('https://www.google.com/maps/search/?api=1&query=Ain+Sebaa',
             'Ain Sebaa'),
            ('Hay Hassani, Casablanca', 'Hay Hassani, Casablanca'),
        )
        for texte, nom in cas:
            with patch(_GEO_ADRESSE, return_value=_CASA) as geo:
                resultat = resoudre_lien_maps(texte, 'Casablanca')
            geo.assert_called_once_with(nom, 'Casablanca')
            # la précision du géocodeur est rendue telle quelle (approximatif)
            self.assertEqual(resultat, _CASA, texte)

    def test_url_etrangere_a_google_n_est_pas_geocodee(self):
        with patch(_GEO_ADRESSE, side_effect=AssertionError('géocodé')):
            self.assertIsNone(
                resoudre_lien_maps('https://exemple.com/pas-une-carte'))

    def test_lien_court_vers_le_consentement(self):
        class _Reponse:
            url = _CONSENT
            text = ''
        with patch('requests.get', return_value=_Reponse()):
            self.assertEqual(
                resoudre_lien_maps('https://maps.app.goo.gl/AbC123'),
                (Decimal('33.381037'), Decimal('-7.545323'), 'lien'))
            self.assertEqual(
                coords_depuis_lien_maps('https://maps.app.goo.gl/AbC123'),
                (Decimal('33.381037'), Decimal('-7.545323')))

    def test_seul_un_HOTE_google_court_est_suivi(self):
        with patch('requests.get', side_effect=AssertionError('requête')):
            self.assertIsNone(coords_depuis_lien_maps(
                'http://169.254.169.254/latest/?x=maps.app.goo.gl/'))
            self.assertIsNone(coords_depuis_lien_maps('goo.gl/AbC123'))
        self.assertTrue(est_lien_court('https://maps.app.goo.gl/AbC?g_st=iw'))
        self.assertTrue(est_lien_court('https://goo.gl/maps/AbC'))

    def test_lien_court_ferme_rend_None_sans_geocoder(self):
        with patch('requests.get', side_effect=OSError('down')), patch(
                _GEO_ADRESSE, side_effect=AssertionError('géocodé')):
            self.assertIsNone(
                resoudre_lien_maps('https://maps.app.goo.gl/AbC123'))


class ResolveurHttpFormesTests(TestCase):
    """Le résolveur HTTP annonce la précision et dit quoi faire en échec."""

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='gps7', defaults={'nom': 'gps7'})
        self.user = User.objects.create_user(
            username='gps7-f', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _post(self, corps):
        return self.api.post('/api/django/crm/leads/resoudre-gps/', corps,
                             format='json')

    def test_coordonnees_collees(self):
        resp = self._post({'lien': '33.57, -7.58'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['precision'], 'lien')

    def test_nom_de_lieu_annonce_une_precision_approximative(self):
        with patch(_GEO_ADRESSE, return_value=_CASA):
            resp = self._post({'lien': 'Hay Hassani', 'ville': 'Casablanca'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['precision'], 'ville')

    def test_lien_court_ferme_404_propose_les_coordonnees(self):
        with patch('requests.get', side_effect=OSError('down')):
            resp = self._post({'lien': 'https://maps.app.goo.gl/AbC123'})
        self.assertEqual(resp.status_code, 404)
        self.assertIn('lien court', resp.data['detail'])
        self.assertIn('coordonnées', resp.data['detail'])
