"""ENF2 — plateforme API : causes racines C3/C4/C5/C6 du fuzz api du 07/10/2026.

* C3 — ``Http404``/``PermissionDenied`` Django : enveloppe ``not_found`` /
  ``permission_denied`` (et non ``server_error`` + « erreur inattendue »).
* C6 — doublon par société : 409 ``unique_conflict`` nommé AVANT l'écriture
  (``core.unicite`` via ``TenantMixin``) et, en filet, depuis la contrainte en
  base (vue hors ``TenantMixin``) ; une violation d'unicité sur une LECTURE
  reste un 500 (bug serveur jamais masqué en conflit client).
* C4 — cookie ``access_token`` présent mais vide : jamais de repli silencieux
  sur le Bearer de la même requête.
* C5 — routes publiques à jeton : aucun authentificateur JWT, un Bearer
  périmé ne transforme jamais un lien public en 401.

Les modèles domaine sont lus par ``apps.get_model`` / via l'API HTTP : ``core``
n'importe aucune app (contrat import-linter).
"""
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.db import IntegrityError
from django.http import Http404
from django.test import SimpleTestCase, TestCase
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.permissions import AllowAny
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.exceptions import taqinor_exception_handler
from core.unicite import ConflitUnicite, contraintes_societe, decrire_contrainte

User = get_user_model()


def _context(method='POST'):
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
            Http404('No Marque matches the given query.'), _context('GET'))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error']['code'], 'not_found')
        self.assertEqual(
            response.data['error']['message'], 'Ressource introuvable.')
        self.assertNotIn('inattendue', response.data['error']['message'])

    def test_permission_denied_django_donne_permission_denied(self):
        response = taqinor_exception_handler(
            DjangoPermissionDenied(), _context('GET'))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['error']['code'], 'permission_denied')
        self.assertTrue(response.data['error']['message'])

    def test_permission_denied_django_garde_son_message(self):
        response = taqinor_exception_handler(
            DjangoPermissionDenied('Réservé au Directeur.'), _context('GET'))
        self.assertEqual(
            response.data['error']['message'], 'Réservé au Directeur.')

    def test_conflit_unicite_porte_ses_champs(self):
        response = taqinor_exception_handler(
            ConflitUnicite('Marque : doublon.', champs=['nom']), _context())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'unique_conflict')
        self.assertEqual(
            response.data['error']['fields'], {'nom': ['Cette valeur existe déjà.']})


class FiletUniciteTests(SimpleTestCase):
    """C6 — traduction de la violation d'unicité Postgres (SQLSTATE 23505)."""

    def test_violation_unicite_sur_ecriture_donne_409(self):
        response = taqinor_exception_handler(
            _integrity('23505', constraint='inconnue'), _context('POST'))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'unique_conflict')
        self.assertEqual(response.data['error']['request_id'], 'rid-1')

    def test_violation_unicite_sur_lecture_reste_un_500(self):
        response = taqinor_exception_handler(
            _integrity('23505', constraint='inconnue'), _context('GET'))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data['error']['code'], 'server_error')

    def test_autre_integrity_error_reste_un_500(self):
        # NOT NULL (23502) : un défaut de la vue/du serializer, pas un conflit.
        response = taqinor_exception_handler(
            _integrity('23502'), _context('POST'))
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


class CookieVideTests(TestCase):
    """C4 — un cookie `access_token` vide n'est jamais remplacé en silence."""

    def setUp(self):
        co = Company.objects.create(nom='ENF2 Cookie', slug='enf2-cookie')
        self.user = User.objects.create_user(
            username='enf2_cookie', password='x', role_legacy='admin', company=co)
        self.url = '/api/django/auth/me/'

    def test_bearer_seul_accepte(self):
        self.assertEqual(_client(self.user).get(self.url).status_code, 200)

    def test_cookie_vide_plus_bearer_valide_refuse(self):
        api = _client(self.user)
        api.cookies['access_token'] = ''
        response = api.get(self.url)
        self.assertEqual(response.status_code, 401, response.content)
        self.assertEqual(response.json()['error']['code'], 'not_authenticated')

    def test_cookie_vide_seul_equivaut_a_anonyme(self):
        api = APIClient()
        api.cookies['access_token'] = ''
        self.assertEqual(api.get(self.url).status_code, 401)
        # …et une route publique reste joignable (pas de 401 forcé).
        public = api.get('/api/django/statuspage/public/')
        self.assertNotEqual(public.status_code, 401)

    def test_cookie_valide_reste_prioritaire(self):
        api = APIClient()
        api.cookies['access_token'] = str(AccessToken.for_user(self.user))
        self.assertEqual(api.get(self.url).status_code, 200)


def _routes(patterns, prefixe=''):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from _routes(p.url_patterns, prefixe + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefixe + str(p.pattern), p.callback


def _route_publique(route):
    return ('public' in route or '<str:token>' in route
            or '<str:idempotency_key>' in route)


class VuesPubliquesSansJwtTests(TestCase):
    """C5 — une route publique (AllowAny, lien à jeton) n'exécute AUCUN
    authentificateur JWT : un Bearer périmé ne la transforme pas en 401."""

    def test_aucune_route_publique_n_authentifie_par_jwt(self):
        fautives = set()
        for route, callback in _routes(get_resolver().url_patterns):
            cls = getattr(callback, 'cls', None) or getattr(
                callback, 'view_class', None)
            if cls is None or not _route_publique(route):
                continue
            perms = getattr(cls, 'permission_classes', None) or []
            if not perms or not all(p is AllowAny for p in perms):
                continue
            noms = {getattr(a, '__name__', '')
                    for a in getattr(cls, 'authentication_classes', [])}
            if 'CookieJWTAuthentication' in noms:
                fautives.add(f'{route} ({cls.__module__}.{cls.__name__})')
        self.assertEqual(sorted(fautives), [])

    def test_bearer_perime_sur_lien_public_ne_donne_pas_401(self):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION='Bearer jeton.perime.invalide')
        for url in ('/api/django/public/sav/ticket/inconnu/',
                    '/api/django/ged/signature/inconnu/',
                    '/api/django/statuspage/public/incidents/999999/'):
            with self.subTest(url=url):
                self.assertNotEqual(api.get(url).status_code, 401)
