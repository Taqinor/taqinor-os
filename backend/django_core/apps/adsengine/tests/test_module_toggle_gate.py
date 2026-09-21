"""SOLMVP17 — le ``ModuleToggle`` gate enfin l'API adsengine.

Avant cette lane, ``apps.adsengine`` portait ``installable=False`` dans son
manifeste : ``DisabledModuleMiddleware`` (voir
``core/tests/test_disabled_module_enforcement.py``) ignore tout module hors
de ``_installable()``, donc désactiver « Publicité » côté
``ModuleToggle(actif=False)`` masquait l'écran côté frontend mais NE COUPAIT
PAS son API — trou constaté le 20/09/2026 (décision fondateur 5 : Publicité
est un module VENDU aux clients, il doit se comporter comme les autres).

Prouve, sur un VRAI endpoint (``/api/django/adsengine/connexions/``) :
  * ``ModuleToggle(module='adsengine', actif=False)`` → 404 pour la société ;
  * sans ligne de toggle → l'endpoint répond normalement (pas de 404).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from core.models import ModuleToggle

User = get_user_model()

BASE = '/api/django/adsengine/connexions/'


def make_user(company):
    role = Role.objects.create(
        company=company, nom='ads-role',
        permissions=['adsengine_view', 'adsengine_manage'])
    return User.objects.create_user(
        username='ads_toggle_user', password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ModuleToggleGateTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Ads Toggle Co',
                                              slug='ads-toggle-co')
        self.user = make_user(self.company)

    def test_toggle_off_returns_404(self):
        ModuleToggle.objects.create(
            company=self.company, module='adsengine', actif=False)
        resp = auth(self.user).get(BASE)
        self.assertEqual(resp.status_code, 404, resp.data)

    def test_no_toggle_passes_through(self):
        resp = auth(self.user).get(BASE)
        self.assertNotEqual(resp.status_code, 404, resp.data)
        self.assertEqual(resp.status_code, 200, resp.data)
