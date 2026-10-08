"""ASEC51 (C-ASEC-017) — permission DRF par défaut : compte INTERNE seulement.

Avant, ``DEFAULT_PERMISSION_CLASSES`` valait ``IsAuthenticated`` : toute vue
sans ``permission_classes`` explicite s'ouvrait à un compte PORTAIL externe
(client / fournisseur / partenaire). Exemple réel : ``CustomRecordViewSet``
(objets personnalisés) — un compte portail sans rôle fin passait la
compat « compte sans rôle » et lisait/écrivait les enregistrements internes.

Désormais le défaut est ``authentication.permissions.IsAuthenticatedInterne`` :
  * compte portail → 403 sur toute vue interne sans garde explicite ;
  * compte interne → comportement inchangé ;
  * vues du portail (gardes ``IsPortal*`` explicites) → inchangées ;
  * anonyme → 401 comme avant.

Test-du-test : remettre ``rest_framework.permissions.IsAuthenticated`` par
défaut ⇒ ``test_portail_refuse_vues_internes_sans_garde`` échoue (200 au lieu
de 403 sur les enregistrements d'objet personnalisé, et la garde de classe
accepte le compte portail).

Run :
    python manage.py test tests.test_asec51_portail_defaut -v2
"""
from django.conf import settings
from django.test import TestCase
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.views import APIView

from apps.customfields.models import CustomObjectDef
from authentication.models import Company, CustomUser
from authentication.permissions import IsAuthenticatedInterne

RECORDS_URL = '/api/django/custom-fields/custom-objects/asec51-obj/records/'
PORTAIL_URL = '/api/django/portail/mes-devis/'


def _vues_drf_sur_le_defaut():
    """Inventaire (routeur + ``@api_view`` + APIView) des vues DRF montées
    dont la classe ne déclare PAS ses ``permission_classes`` (donc sur le
    défaut global). Le contenu de la liste varie avec le code ; la garde ne
    dépend que de la classe par défaut appliquée à chacune."""
    defaut = APIView.permission_classes
    vues = {}

    def walk(patterns, prefix=''):
        for p in patterns:
            if isinstance(p, URLResolver):
                walk(p.url_patterns, prefix + str(p.pattern))
            elif isinstance(p, URLPattern):
                cls = (getattr(p.callback, 'cls', None)
                       or getattr(p.callback, 'view_class', None))
                if cls is None or not issubclass(cls, APIView):
                    continue
                initkwargs = getattr(p.callback, 'initkwargs', None) or {}
                classes = initkwargs.get('permission_classes',
                                         cls.permission_classes)
                if list(classes) == list(defaut):
                    vues[prefix + str(p.pattern)] = cls

    walk(get_resolver().url_patterns)
    return vues


class PortailDefautTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asec51-co', defaults={'nom': 'ASEC51 Société'})
        # Compte interne hérité (sans rôle fin) : la compat ``role`` NULL de
        # ``CustomRecordViewSet`` l'accepte — comportement actuel.
        self.interne = CustomUser.objects.create_user(
            username='asec51-interne', password='motdepasse-test-1234',
            company=self.company)
        # Compte portail client rattaché, mot de passe déjà changé.
        self.portail = CustomUser.objects.create_user(
            username='asec51-portail', password='motdepasse-test-1234',
            company=self.company,
            portee=CustomUser.PORTEE_PORTAIL_CLIENT,
            portail_client_id=424242)
        CustomObjectDef.objects.create(
            company=self.company, code='asec51-obj', libelle='Objet ASEC51')

    def _api(self, user=None):
        api = APIClient()
        if user is not None:
            api.force_authenticate(user=user)
        return api

    def test_defaut_est_interne(self):
        self.assertEqual(
            list(settings.REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES']),
            ['authentication.permissions.IsAuthenticatedInterne'])
        self.assertEqual(list(APIView.permission_classes),
                         [IsAuthenticatedInterne])

    def test_portail_refuse_vues_internes_sans_garde(self):
        # 1) Vue réelle sans garde explicite : lecture ET écriture refusées.
        api = self._api(self.portail)
        self.assertEqual(api.get(RECORDS_URL).status_code, 403)
        self.assertEqual(
            api.post(RECORDS_URL, {'data': {}}, format='json').status_code,
            403)

        # 2) Inventaire : chaque vue montée sur le défaut refuse le compte
        #    portail au niveau de la garde de classe (403), quel que soit son
        #    code métier.
        vues = _vues_drf_sur_le_defaut()
        factory = APIRequestFactory()
        for route, cls in sorted(vues.items()):
            request = factory.get('/')
            drf_request = APIView().initialize_request(request)
            drf_request.user = self.portail
            perms = [perm() for perm in cls.permission_classes]
            with self.subTest(route=route, vue=cls.__name__):
                self.assertFalse(
                    all(p.has_permission(drf_request, None) for p in perms),
                    f'{route} ({cls.__module__}.{cls.__name__}) laisse '
                    'passer un compte portail sur le défaut global')

    def test_portail_vues_portail_ok(self):
        res = self._api(self.portail).get(PORTAIL_URL)
        self.assertEqual(res.status_code, 200, getattr(res, 'data', res))
        # /auth/me/ reste joignable (IsAuthenticated EXPLICITE) : sans lui le
        # shell ne saurait pas router le compte vers /portail.
        me = self._api(self.portail).get('/api/django/auth/me/')
        self.assertEqual(me.status_code, 200)

    def test_interne_inchange(self):
        api = self._api(self.interne)
        self.assertEqual(api.get(RECORDS_URL).status_code, 200)
        self.assertEqual(api.get('/api/django/auth/me/').status_code, 200)
        # Un interne n'entre toujours pas dans le portail.
        self.assertEqual(api.get(PORTAIL_URL).status_code, 403)
        # Anonyme : refusé comme avec ``IsAuthenticated`` (401 avec le
        # cookie-JWT qui expose ``authenticate_header``).
        self.assertIn(self._api().get(RECORDS_URL).status_code, (401, 403))

    def test_garde_unitaire(self):
        factory = APIRequestFactory()
        garde = IsAuthenticatedInterne()
        for user, attendu in ((self.interne, True), (self.portail, False)):
            request = APIView().initialize_request(factory.get('/'))
            request.user = user
            self.assertIs(garde.has_permission(request, None), attendu)
