"""ASEC13 / D-ASEC-2 — l'inscription libre ``/auth/register-company/`` est
parquée par défaut.

Éteinte (``TENANT_SIGNUP_ENABLED`` faux, défaut) : 404, aucune société ni
utilisateur créés. Allumée : e-mail obligatoire ; une erreur survenue après la
création de la société ne laisse rien derrière (création atomique).
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from authentication.models import Company

User = get_user_model()

_URL = '/api/django/auth/register-company/'
_LOCMEM_CACHE = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
}


def _corps(**extra):
    corps = {
        'company_nom': 'ASEC13 SARL', 'username': 'asec13_boss',
        'password': 'Mot-de-passe-solide-13', 'email': 'boss@asec13.ma',
    }
    corps.update(extra)
    return corps


@override_settings(CACHES=_LOCMEM_CACHE)
class InscriptionParqueeTests(TestCase):
    def setUp(self):
        cache.clear()  # throttle d'inscription (3/h par IP)
        self.api = APIClient(raise_request_exception=False)

    def _compter(self):
        return Company.objects.count(), User.objects.count()

    @override_settings(TENANT_SIGNUP_ENABLED=False)
    def test_eteint_404_rien_cree(self):
        avant = self._compter()
        resp = self.api.post(_URL, _corps(), format='json')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self._compter(), avant)

    @override_settings(TENANT_SIGNUP_ENABLED=True)
    def test_allume_email_obligatoire(self):
        avant = self._compter()
        resp = self.api.post(_URL, _corps(email=''), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('email', resp.data)
        self.assertEqual(self._compter(), avant)
        resp = self.api.post(_URL, _corps(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    @override_settings(TENANT_SIGNUP_ENABLED=True)
    def test_allume_atomique(self):
        avant = self._compter()
        with mock.patch('authentication.views._create_system_roles',
                        side_effect=RuntimeError('panne simulée')):
            resp = self.api.post(_URL, _corps(), format='json')
        self.assertGreaterEqual(resp.status_code, 500)
        self.assertEqual(self._compter(), avant)
        self.assertFalse(Company.objects.filter(nom='ASEC13 SARL').exists())
