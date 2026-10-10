"""ENF1b — causes racines PLATEFORME des « Server error » et du cluster
« Undocumented Content-Type » de l'api-fuzz du 09/10/2026 (run 37897343514).

* Identifiant non numérique fourni par le client (``null,null``, ``{}``,
  ``AAA``) : le ``ValueError`` « Field 'id' expected a number » d'une
  recherche ORM → 404 (paramètre de chemin) / 400 (corps), jamais 500.
  18 des 29 « Server error » (ventes, ged, onboarding, stock, automation,
  installations, facturation).
* ``django.core.exceptions.ValidationError`` (valeur brute passée au modèle)
  → 400, jamais 500 (identity/service-accounts).
* ``OPTIONS`` sur une action de liste PUT/PATCH ou une vue sans
  ``serializer_class`` → 200, jamais 500 (8 opérations).
* URL d'API interne sans route → 404 JSON ``ErreurApi``, jamais la page HTML
  de Django (510 « Undocumented Content-Type »).
* Corps d'erreur LISTE (``raise ValidationError('…')``) → objet.

Domaine atteint par HTTP uniquement : ``core`` n'importe aucune app.
"""
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import SimpleTestCase, TestCase
from rest_framework import exceptions as drf_exceptions
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.exceptions import taqinor_exception_handler

User = get_user_model()

_ID_INVALIDE = "Field 'id' expected a number but got 'null,null'."


def _context(kwargs=None, method='POST'):
    return {'request': SimpleNamespace(method=method, request_id='rid-1b'),
            'view': SimpleNamespace(kwargs=kwargs or {})}


class ExceptionsClientTests(SimpleTestCase):

    def test_id_non_numerique_du_chemin_donne_404(self):
        response = taqinor_exception_handler(
            ValueError(_ID_INVALIDE), _context({'pk': 'null,null'}))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error']['code'], 'not_found')

    def test_id_non_numerique_du_corps_donne_400(self):
        response = taqinor_exception_handler(
            ValueError("Field 'id' expected a number but got '{}'."),
            _context({}))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'validation_error')
        self.assertIn('id', response.data)

    def test_autre_value_error_reste_un_500(self):
        response = taqinor_exception_handler(
            ValueError('bug serveur'), _context({}))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data['error']['code'], 'server_error')

    def test_validation_error_django_par_champ_donne_400(self):
        response = taqinor_exception_handler(
            DjangoValidationError({'expire_le': ['Format invalide.']}),
            _context())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['expire_le'], ['Format invalide.'])
        self.assertEqual(response.data['error']['fields'],
                         {'expire_le': ['Format invalide.']})

    def test_validation_error_django_liste_donne_un_objet(self):
        response = taqinor_exception_handler(
            DjangoValidationError(['Format invalide.']), _context())
        self.assertEqual(response.status_code, 400)
        self.assertIsInstance(response.data, dict)
        self.assertEqual(response.data['detail'], 'Format invalide.')

    def test_corps_liste_drf_replie_en_objet(self):
        response = taqinor_exception_handler(
            drf_exceptions.ValidationError('Existe déjà.'), _context())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'Existe déjà.')
        self.assertEqual(response.data['non_field_errors'], ['Existe déjà.'])
        self.assertEqual(response.data['error']['code'], 'validation_error')


class FuzzPlateformeHttpTests(TestCase):
    """Les requêtes EXACTES du fuzz du 09/10 — corps en JSON depuis D2 (vues sans
    fichier en JSON seul : un multipart y répond 415, par conception)."""

    def setUp(self):
        co = Company.objects.create(nom='ENF1b Co', slug='enf1b-co')
        user = User.objects.create_user(
            username='enf1b_admin', password='x', role_legacy='admin',
            company=co, is_staff=True)
        self.api = APIClient()
        self.api.cookies['access_token'] = str(AccessToken.for_user(user))

    def _json_404(self, response):
        self.assertEqual(response.status_code, 404)
        self.assertTrue(response['Content-Type'].startswith('application/json'),
                        response['Content-Type'])
        self.assertEqual(response.json()['error']['code'], 'not_found')

    def test_id_null_null_du_chemin_404(self):
        for methode, url in (
                ('delete', '/api/django/ventes/presets/null%2Cnull/'),
                ('post', '/api/django/onboarding/items-masques/null%2Cnull/masquer/'),
                ('post', '/api/django/ged/documents/null%2Cnull/purger/')):
            with self.subTest(url=url):
                response = getattr(self.api, methode)(url)
                self.assertEqual(response.status_code, 404, response.content)

    def test_fk_accolades_du_corps_400(self):
        for url, corps in (
                ('/api/django/ged/legal-holds/',
                 {'document': '{}', 'motif': ''}),
                ('/api/django/stock/revalorisations-stock/',
                 {'produit': '{}', 'nouveau_cout': ''})):
            with self.subTest(url=url):
                response = self.api.post(url, corps, format='json')
                self.assertEqual(response.status_code, 400, response.content)

    def test_service_account_date_invalide_400(self):
        response = self.api.post(
            '/api/django/identity/service-accounts/',
            {'nom': '0', 'scopes': 'None', 'actif': 'False', 'expire_le': '{}'},
            format='json')
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()['error']['code'], 'validation_error')

    def test_options_actions_de_liste_200(self):
        for url in ('/api/django/parametres/statuts/bulk/',
                    '/api/django/core/theme/courant/',
                    '/api/django/calepinage/gabarits-dossiers/'):
            with self.subTest(url=url):
                response = self.api.options(url)
                self.assertEqual(response.status_code, 200, response.content)

    def test_url_sans_route_404_json(self):
        self._json_404(self.api.get('/api/django/calepinage/gabarits-dossiers/0.5/'))
        self._json_404(self.api.get('/api/v1/nexiste-pas/'))
        self._json_404(self.api.get('/api/django/nexiste-pas/'))
