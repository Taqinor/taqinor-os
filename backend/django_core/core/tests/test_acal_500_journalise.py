"""ACAL315 — un 500 du gestionnaire d'exceptions unique n'est JAMAIS muet.

Constat live (audit PUB) : « django_core logs gave no Python traceback for
the 500s ; request_id null in the shell » — la base non migrée
(ProgrammingError) est restée invisible. Ici, une VRAIE vue DRF lève une
exception non gérée et passe par le VRAI ``taqinor_exception_handler``
(REST_FRAMEWORK['EXCEPTION_HANDLER']) — aucun mock du handler.
"""
from types import SimpleNamespace

from django.db import ProgrammingError, IntegrityError
from django.test import RequestFactory, SimpleTestCase, TestCase
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework.test import APIClient
from rest_framework import exceptions as drf_exceptions
from django.core.exceptions import (
    ValidationError as DjangoValidationError, PermissionDenied as DjangoPermissionDenied,
)
from django.contrib.auth import get_user_model
from django.http import Http404
from django.apps import apps

from core.middleware import RequestIdMiddleware
from core.exceptions import taqinor_exception_handler
from authentication.models import Company
from core.unicite import ConflitUnicite, contraintes_societe, decrire_contrainte


class _VueQuiCasse(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        raise ProgrammingError('relation "x" does not exist')


class Acal500JournaliseTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.vue = _VueQuiCasse.as_view()

    def test_exception_non_geree_journalise_la_pile(self):
        requete = self.factory.get('/api/django/test/acal315/')
        with self.assertLogs('core.exceptions', level='ERROR') as journal:
            reponse = self.vue(requete)
        self.assertEqual(reponse.status_code, 500)
        self.assertEqual(reponse.data['error']['code'], 'server_error')
        request_id = reponse.data['error']['request_id']
        self.assertEqual(len(journal.records), 1)
        record = journal.records[0]
        # La pile est là (exc_info) et c'est bien l'exception levée.
        self.assertIsNotNone(record.exc_info)
        self.assertIs(record.exc_info[0], ProgrammingError)
        # Le request_id de la réponse est celui du journal.
        self.assertEqual(record.request_id, request_id)
        self.assertIn(request_id, record.getMessage())
        self.assertEqual(record.path, '/api/django/test/acal315/')
        self.assertEqual(record.method, 'GET')
        # Le message générique ne fuite jamais le détail interne au client.
        self.assertNotIn('relation', reponse.data['error']['message'])

    def test_request_id_jamais_null(self):
        # 1) Sans middleware (shell, requête construite à la main).
        requete = self.factory.get('/api/django/test/acal315/')
        with self.assertLogs('core.exceptions', level='ERROR'):
            reponse = self.vue(requete)
        request_id = reponse.data['error']['request_id']
        self.assertIsInstance(request_id, str)
        self.assertTrue(request_id)
        self.assertEqual(reponse['X-Request-ID'], request_id)

        # 2) Avec le middleware de corrélation, sans en-tête entrant.
        pile = RequestIdMiddleware(self.vue)
        requete = self.factory.get('/api/django/test/acal315/')
        with self.assertLogs('core.exceptions', level='ERROR') as journal:
            reponse = pile(requete)
        request_id = reponse.data['error']['request_id']
        self.assertIsInstance(request_id, str)
        self.assertTrue(request_id)
        self.assertEqual(reponse['X-Request-ID'], request_id)
        self.assertEqual(journal.records[0].request_id, request_id)


# ENF1b — causes racines PLATEFORME des « Server error » et du cluster « Undocumented Content-Type »
# de l'api-fuzz du 09/10/2026 (run 37897343514).
# * Identifiant non numérique fourni par le client (``null,null``, ``{}``,
#   ``AAA``) : le ``ValueError`` « Field 'id' expected a number » d'une
#   recherche ORM → 404 (paramètre de chemin) / 400 (corps), jamais 500.
#   18 des 29 « Server error » (ventes, ged, onboarding, stock, automation,
#   installations, facturation).
# * ``django.core.exceptions.ValidationError`` (valeur brute passée au modèle)
#   → 400, jamais 500 (identity/service-accounts).
# * ``OPTIONS`` sur une action de liste PUT/PATCH ou une vue sans
#   ``serializer_class`` → 200, jamais 500 (8 opérations).
# * URL d'API interne sans route → 404 JSON ``ErreurApi``, jamais la page HTML
#   de Django (510 « Undocumented Content-Type »).
# * Corps d'erreur LISTE (``raise ValidationError('…')``) → objet.
# Domaine atteint par HTTP uniquement : ``core`` n'importe aucune app.
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


# ENF2 — plateforme API : enveloppe des exceptions Django (C3) et doublon par société en 409 nommé
# avant l'écriture, puis en filet depuis la contrainte en base (C6).
def _contexte_sans_vue(method='POST'):
    return {'request': SimpleNamespace(method=method, request_id='rid-1'),
            'view': None}


class _FausseCause(Exception):
    """Exception pilote psycopg2 simulée (pgcode + diag)."""

    def __init__(self, pgcode, constraint=None, table=None, detail=None):
        super().__init__('violation')
        self.pgcode = pgcode
        self.diag = SimpleNamespace(
            constraint_name=constraint, table_name=table,
            message_detail=detail)


def _integrity(pgcode, **diag):
    exc = IntegrityError('violation')
    exc.__cause__ = _FausseCause(pgcode, **diag)
    return exc


class EnveloppeDjangoExceptionsTests(SimpleTestCase):
    """C3 — l'exception D'ORIGINE (Django) donne le bon code."""

    def test_http404_django_donne_not_found(self):
        response = taqinor_exception_handler(
            Http404('No Marque matches the given query.'), _contexte_sans_vue('GET'))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error']['code'], 'not_found')
        self.assertEqual(
            response.data['error']['message'], 'Ressource introuvable.')
        self.assertNotIn('inattendue', response.data['error']['message'])

    def test_permission_denied_django_donne_permission_denied(self):
        response = taqinor_exception_handler(
            DjangoPermissionDenied(), _contexte_sans_vue('GET'))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['error']['code'], 'permission_denied')
        self.assertTrue(response.data['error']['message'])

    def test_permission_denied_django_garde_son_message(self):
        response = taqinor_exception_handler(
            DjangoPermissionDenied('Réservé au Directeur.'), _contexte_sans_vue('GET'))
        self.assertEqual(
            response.data['error']['message'], 'Réservé au Directeur.')

    def test_conflit_unicite_porte_ses_champs(self):
        response = taqinor_exception_handler(
            ConflitUnicite('Marque : doublon.', champs=['nom']), _contexte_sans_vue())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'unique_conflict')
        self.assertEqual(
            response.data['error']['fields'], {'nom': ['Cette valeur existe déjà.']})


class FiletUniciteTests(SimpleTestCase):
    """C6 — traduction de la violation d'unicité Postgres (SQLSTATE 23505)."""

    def test_violation_unicite_sur_ecriture_donne_409(self):
        response = taqinor_exception_handler(
            _integrity('23505', constraint='inconnue'), _contexte_sans_vue('POST'))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'unique_conflict')
        self.assertEqual(response.data['error']['request_id'], 'rid-1')

    def test_violation_unicite_sur_lecture_reste_un_500(self):
        response = taqinor_exception_handler(
            _integrity('23505', constraint='inconnue'), _contexte_sans_vue('GET'))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data['error']['code'], 'server_error')

    def test_autre_integrity_error_reste_un_500(self):
        # NOT NULL (23502) : un défaut de la vue/du serializer, pas un conflit.
        response = taqinor_exception_handler(
            _integrity('23502'), _contexte_sans_vue('POST'))
        self.assertEqual(response.status_code, 500)

    def test_contrainte_nommee_retrouve_modele_et_champs(self):
        model, champs = decrire_contrainte(
            'stock_plancomptage_company_classe_uniq')
        self.assertEqual(model._meta.label, 'stock.PlanComptageTournant')
        self.assertEqual(champs, ('classe_abc',))

    def test_unique_together_retrouve_les_champs_par_le_detail(self):
        tag = apps.get_model('records', 'Tag')
        model, champs = decrire_contrainte(
            'records_tag_company_id_nom_abc_uniq',
            table=tag._meta.db_table,
            detail='Key (company_id, nom)=(3, x) already exists.')
        self.assertIs(model, tag)
        self.assertEqual(champs, ('nom',))

    def test_contraintes_societe_ignore_les_conditionnelles(self):
        plan = apps.get_model('stock', 'PlanComptageTournant')
        self.assertIn(('company', 'classe_abc'), contraintes_societe(plan))


def _client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class UniciteParSocieteApiTests(TestCase):
    """C6 — bout en bout : doublon → 409 nommé, jamais un 500."""

    def setUp(self):
        self.co = Company.objects.create(nom='ENF2 Co', slug='enf2-co')
        self.autre = Company.objects.create(nom='ENF2 Autre', slug='enf2-autre')
        self.admin = User.objects.create_user(
            username='enf2_admin', password='x', role_legacy='admin',
            company=self.co)
        self.admin_autre = User.objects.create_user(
            username='enf2_admin_autre', password='x', role_legacy='admin',
            company=self.autre)
        self.api = _client(self.admin)

    def test_doublon_prevalide_409_avant_ecriture(self):
        url = '/api/django/stock/marques/'
        premier = self.api.post(url, {'nom': 'ENF2-Marque'}, format='json')
        self.assertEqual(premier.status_code, 201, premier.content)
        second = self.api.post(url, {'nom': 'ENF2-Marque'}, format='json')
        self.assertEqual(second.status_code, 409, second.content)
        corps = second.json()
        self.assertEqual(corps['error']['code'], 'unique_conflict')
        self.assertEqual(corps['error']['fields'], {'nom': ['Cette valeur existe déjà.']})
        marque = apps.get_model('stock', 'Marque')
        self.assertEqual(
            marque.objects.filter(company=self.co, nom='ENF2-Marque').count(), 1)

    def test_meme_valeur_dans_une_autre_societe_acceptee(self):
        url = '/api/django/stock/marques/'
        self.api.post(url, {'nom': 'ENF2-Partage'}, format='json')
        autre = _client(self.admin_autre).post(
            url, {'nom': 'ENF2-Partage'}, format='json')
        self.assertEqual(autre.status_code, 201, autre.content)

    def test_modification_vers_un_doublon_409_et_sur_soi_200(self):
        url = '/api/django/stock/marques/'
        a = self.api.post(url, {'nom': 'ENF2-A'}, format='json').json()
        self.api.post(url, {'nom': 'ENF2-B'}, format='json')
        conflit = self.api.patch(f"{url}{a['id']}/", {'nom': 'ENF2-B'}, format='json')
        self.assertEqual(conflit.status_code, 409, conflit.content)
        soi = self.api.patch(f"{url}{a['id']}/", {'nom': 'ENF2-A'}, format='json')
        self.assertEqual(soi.status_code, 200, soi.content)

    def test_vue_hors_tenantmixin_filet_en_base_409(self):
        """records/tags n'hérite pas de TenantMixin : la contrainte
        ``unique_together`` en base refuse, le gestionnaire répond 409 en
        nommant le champ (lu dans le DETAIL Postgres)."""
        url = '/api/django/records/tags/'
        self.assertEqual(
            self.api.post(url, {'nom': 'enf2'}, format='json').status_code, 201)
        second = self.api.post(url, {'nom': 'enf2'}, format='json')
        self.assertEqual(second.status_code, 409, second.content)
        self.assertEqual(second.json()['error']['code'], 'unique_conflict')
        self.assertEqual(second.json()['error']['fields'],
                         {'nom': ['Cette valeur existe déjà.']})

    def test_get_object_or_404_envelope_not_found(self):
        response = self.api.get('/api/django/stock/marques/999999/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error']['code'], 'not_found')
