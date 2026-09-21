"""NTSCM34 — Activation par module SCM via `core.ModuleToggle`.

Le module `scm` déclare déjà son `module_manifest` (clé `scm`, IDENTIQUE au
2ᵉ segment d'URL `api/django/scm/`) depuis sa création — `core.permissions.
DisabledModuleMiddleware` le couvre donc GÉNÉRIQUEMENT, sans code
supplémentaire dans `apps/scm/views.py` (même patron que
`apps/veille_ao/tests/test_smoke.py::ModuleDesactiveTests`, réutilisé ici).
Cette lane n'ajoute que : (a) la preuve que le gating fonctionne réellement
pour `scm`, et (b) la migration de données 0011 qui désactive le module par
défaut pour les sociétés déjà en base (voir sa docstring).

Critère d'acceptation : une société sans le module SCM actif reçoit 404 sur
`scm/tableau-bord/`, une société avec le module actif y accède normalement."""
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from authentication.models import Company
from core import permissions
from core.models import ModuleToggle
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()


class ScmModuleToggleMiddlewareTests(TestCase):
    """Vérification directe du middleware (même patron que veille_ao) —
    rapide, sans dépendre de l'authentification JWT complète."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME SCM toggle')
        cls.autre = Company.objects.create(nom='Autre société SCM')
        cls.user = User.objects.create_user(
            username='scm_toggle', password='x', role_legacy='normal',
            company=cls.company)
        cls.autre_user = User.objects.create_user(
            username='scm_toggle_autre', password='x', role_legacy='normal',
            company=cls.autre)

    def _middleware(self):
        from django.http import HttpResponse
        sentinelle = HttpResponse('ok')
        middleware = permissions.DisabledModuleMiddleware(lambda requete: sentinelle)
        return middleware, sentinelle

    def _requete(self, user, path='/api/django/scm/tableau-bord/'):
        requete = RequestFactory().get(path)
        requete.user = user
        return requete

    def test_module_desactive_rend_404(self):
        ModuleToggle.objects.create(company=self.company, module='scm', actif=False)
        middleware, sentinelle = self._middleware()
        reponse = middleware(self._requete(self.user))
        self.assertEqual(reponse.status_code, 404)
        self.assertIsNot(reponse, sentinelle)

    def test_module_actif_par_defaut_passe(self):
        middleware, sentinelle = self._middleware()
        reponse = middleware(self._requete(self.user))
        self.assertIs(reponse, sentinelle)

    def test_desactivation_isolee_par_societe(self):
        ModuleToggle.objects.create(company=self.company, module='scm', actif=False)
        middleware, sentinelle = self._middleware()
        reponse = middleware(self._requete(self.autre_user))
        self.assertIs(reponse, sentinelle)


class ScmModuleToggleEndToEndTests(TestCase):
    """Vérification bout-en-bout via un vrai appel API (JWT), sur l'endpoint
    cité par le critère d'acceptation."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME SCM e2e')
        cls.user = User.objects.create_user(
            username='scm_toggle_e2e', password='x', role_legacy='admin',
            company=cls.company)

    def _client(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_endpoint_404_module_desactive_puis_200_une_fois_reactive(self):
        toggle = ModuleToggle.objects.create(
            company=self.company, module='scm', actif=False)
        resp = self._client(self.user).get('/api/django/scm/tableau-bord/')
        self.assertEqual(resp.status_code, 404)

        toggle.actif = True
        toggle.save(update_fields=['actif'])
        resp = self._client(self.user).get('/api/django/scm/tableau-bord/')
        self.assertEqual(resp.status_code, 200, resp.data)
