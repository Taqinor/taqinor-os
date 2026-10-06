"""ADOC80 — garde de CLASSE sur toutes les routes de ``apps/documents/urls.py``.

Constats C-ADOC-037 (portée de rôle) et C-ADOC-039 (garde d'état) : un
nouveau document de chantier ne peut plus naître sans la portée de la fiche
chantier ni la garde d'état. Le résolveur Django est parcouru (aucune liste de
routes en dur) et CHAQUE route doit répondre :

* 404 à un rôle restreint hors portée (ni technicien ni créateur) ;
* 404 à un utilisateur d'une autre société ;
* 403 (ou 404) à un compte portail ;
* 409 sur un chantier annulé (pour un responsable qui le voit).

Une route ajoutée sans ces gardes fait échouer le test EN LA NOMMANT — prouvé
par ``test_la_garde_nomme_une_route_sans_garde`` (route factice montée par
``override_settings(ROOT_URLCONF=...)``).

Run :
    python manage.py test apps.documents.tests.test_adoc_garde_classe_endpoints -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import include, path
from rest_framework.test import APIClient
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.documents import urls as documents_urls
from apps.installations.models import Installation
from apps.roles.models import Role
from apps.roles.permissions_registre import SCOPE_TEAM
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
PREFIXE = '/api/django/documents/'


# ── Route factice SANS garde (preuve que la garde nomme la fautive) ─────────
class _VueSansGarde(APIView):
    permission_classes = []

    def get(self, request, pk):
        return HttpResponse(b'%PDF-fuite', content_type='application/pdf')


_routes_factices = [
    path('chantiers/<int:pk>/fiche-fuite/', _VueSansGarde.as_view(),
         name='adoc80-fiche-fuite'),
]
urlpatterns = [
    path('api/django/documents/', include(_routes_factices)),
]


def _routes(patterns):
    """(nom, gabarit de chemin) de chaque route d'un module d'URL documents."""
    return [(p.name or str(p.pattern), str(p.pattern)) for p in patterns]


class GardeClasseEndpointsDocumentsTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'adoc80-co-{n}', nom=f'ADOC80 Co {n}')
        self.autre = Company.objects.create(
            slug=f'adoc80-autre-{n}', nom=f'ADOC80 Autre {n}')
        self.resp = User.objects.create_user(
            username=f'adoc80-resp-{n}', password='x',
            company=self.company, role_legacy='responsable')
        role = Role.objects.create(
            company=self.company, nom='Restreint écriture',
            permissions=[SCOPE_TEAM, 'installations_modifier'])
        self.restreint = User.objects.create_user(
            username=f'adoc80-r-{n}', password='x', company=self.company,
            role=role)
        self.etranger = User.objects.create_user(
            username=f'adoc80-ext-{n}', password='x', company=self.autre,
            role_legacy='responsable')
        client = Client.objects.create(
            company=self.company, nom='Kettani', prenom='Hind',
            telephone='+212600000080')
        self.portail = User.objects.create_user(
            username=f'adoc80-portail-{n}', password='x',
            company=self.company, portee='portail_client',
            portail_client_id=client.pk)
        self.chantier = Installation.objects.create(
            company=self.company, reference=f'CH-ADOC80-{n}', client=client,
            created_by=self.resp, technicien_responsable=self.resp,
            statut=Installation.Statut.INSTALLE)
        self.chantier_annule = Installation.objects.create(
            company=self.company, reference=f'CH-ADOC80-ANN-{n}',
            client=client, created_by=self.resp,
            technicien_responsable=self.resp,
            statut=Installation.Statut.INSTALLE, annule=True)

    def _api(self, user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def _violations(self, routes):
        violations = []
        for nom, gabarit in routes:
            if '<int:pk>' not in gabarit:
                violations.append(f'{nom} : route sans <int:pk> de chantier')
                continue

            def url(pk, gabarit=gabarit):
                return PREFIXE + gabarit.replace('<int:pk>', str(pk))

            cas = (
                ('rôle hors portée', self.restreint, self.chantier, (404,)),
                ('autre société', self.etranger, self.chantier, (404,)),
                ('compte portail', self.portail, self.chantier, (401, 403, 404)),
                ('chantier annulé', self.resp, self.chantier_annule, (409,)),
            )
            for libelle, user, chantier, attendus in cas:
                code = self._api(user).get(url(chantier.pk)).status_code
                if code not in attendus:
                    violations.append(
                        f'{nom} ({gabarit}) — {libelle} : {code}, '
                        f'attendu {attendus}')
        return violations

    def test_toutes_les_routes_documents_portee_et_etat(self):
        routes = _routes(documents_urls.urlpatterns)
        self.assertTrue(routes, 'aucune route lue dans apps/documents/urls.py')
        violations = self._violations(routes)
        self.assertEqual(violations, [], '\n'.join(violations))

    @override_settings(
        ROOT_URLCONF='apps.documents.tests.test_adoc_garde_classe_endpoints')
    def test_la_garde_nomme_une_route_sans_garde(self):
        violations = self._violations(_routes(_routes_factices))
        self.assertTrue(violations)
        self.assertTrue(all('adoc80-fiche-fuite' in v for v in violations))
        self.assertTrue(any('chantier annulé' in v for v in violations))
