"""ASEC15 — LA primitive d'adresse IP rend le saut de CONFIANCE.

Avec ``NUM_PROXIES=N`` (prod : 1), ``core.throttling.ip_de_requete`` rend le
N-ième saut de ``X-Forwarded-For`` en partant de la droite — le visiteur que
nginx a ajouté après realip —, exactement comme ``get_ident`` de DRF. Avant
ASEC15 elle rendait l'avant-dernier saut (``len - 1 - N``), donc une valeur
choisie par l'appelant ; et les lecteurs « sécurité » (allowlist NTSEC11,
``UserSession.ip``, ``/metrics``) lisaient même le PREMIER saut.

Vit dans ``apps.identity`` (et non ``core.tests``) : il exerce le middleware
et les modèles d'``identity`` — ``core`` ne doit importer aucune app
(contrat import-linter « core foundation app imports downward only »).

Run :
    python manage.py test apps.identity.tests.test_asec15_ip_primitive -v2
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework.throttling import SimpleRateThrottle

from apps.identity.middleware import NetworkPolicyMiddleware
from apps.identity.models import IpAllowRule, NetworkPolicy
from authentication.models import Company, UserSession
from authentication.throttles import LoginRateThrottle
from core.throttling import ip_de_requete

User = get_user_model()

FORGEE = '10.9.9.9'          # dans l'allowlist : l'attaquant la choisit
VISITEUR = '203.0.113.50'    # adresse réelle, ajoutée par nginx
NGINX = '172.18.0.5'
_LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


def _requete(xff, remote=NGINX):
    return RequestFactory().get(
        '/api/django/crm/leads/', REMOTE_ADDR=remote,
        HTTP_X_FORWARDED_FOR=xff)


@override_settings(NUM_PROXIES=1)
class IpPrimitiveTests(SimpleTestCase):
    def test_num_proxies_1_rend_dernier_saut(self):
        self.assertEqual(
            ip_de_requete(_requete(f'{FORGEE}, {VISITEUR}')), VISITEUR)

    def test_prefixe_forge_long_ne_masque_pas_le_dernier_saut(self):
        forge = ', '.join(['10.0.0.%d' % i for i in range(30)])
        self.assertEqual(
            ip_de_requete(_requete(f'{forge}, {VISITEUR}')), VISITEUR)

    def test_egal_get_ident_drf(self):
        throttle = SimpleRateThrottle.__new__(SimpleRateThrottle)
        for xff in (f'{FORGEE}, {VISITEUR}', VISITEUR,
                    f'1.1.1.1, {FORGEE}, {VISITEUR}'):
            requete = _requete(xff)
            with self.subTest(xff=xff):
                with mock.patch(
                        'rest_framework.throttling.api_settings') as api:
                    api.NUM_PROXIES = 1
                    attendu = throttle.get_ident(requete)
                self.assertEqual(ip_de_requete(requete), attendu)

    def test_num_proxies_absent_inchange(self):
        with override_settings(NUM_PROXIES=None,
                               REST_FRAMEWORK={'NUM_PROXIES': None}):
            self.assertEqual(
                ip_de_requete(_requete(f'{FORGEE}, {VISITEUR}')), VISITEUR)


def _ok(_request):
    return HttpResponse('ok', status=200)


@override_settings(NUM_PROXIES=1)
class AllowlistEtSessionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASEC15', slug='asec15')
        self.user = User.objects.create_user(
            username='asec15_u', password='Bon-mdp-123!', company=self.company)

    def test_allowlist_enforce_non_contournee(self):
        pol = NetworkPolicy.objects.create(
            company=self.company, mode=NetworkPolicy.Mode.ENFORCE,
            applies_to='all')
        IpAllowRule.objects.create(
            company=self.company, policy=pol, cidr='10.0.0.0/8')
        mw = NetworkPolicyMiddleware(_ok)
        # Rouge avant ASEC15 : le premier saut forgé (dans la plage) passait.
        req = _requete(f'{FORGEE}, {VISITEUR}')
        req.user = self.user
        self.assertEqual(mw(req).status_code, 403)
        # Le visiteur réellement dans la plage passe toujours.
        req_ok = _requete(f'{VISITEUR}, 10.1.2.3')
        req_ok.user = self.user
        self.assertEqual(mw(req_ok).status_code, 200)

    @override_settings(CACHES=_LOCMEM)
    def test_user_session_ip_visiteur(self):
        cache.clear()
        with mock.patch.object(
                LoginRateThrottle, 'allow_request', return_value=True):
            resp = APIClient().post(
                '/api/django/token/',
                {'username': 'asec15_u', 'password': 'Bon-mdp-123!'},
                format='json', REMOTE_ADDR=NGINX,
                HTTP_X_FORWARDED_FOR=f'{FORGEE}, {VISITEUR}')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', None))
        session = UserSession.objects.filter(user=self.user).latest('pk')
        session.refresh_from_db()
        self.assertEqual(session.ip_address, VISITEUR)
