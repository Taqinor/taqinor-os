"""QJR647 — le troisième stockage de géométrie de toit ``ventes.RoofLayout``
(FG245, ``/api/django/ventes/calepinages/``, sans appelant) est retiré.

Survivants : ``apps.calepinage`` (``/api/django/calepinage/calepinages/``) et
le cache ``Devis.roof_layout``. Le nom d'URL ``calepinage-list`` n'est plus
défini deux fois.

Run :
    python manage.py test apps.ventes.tests.test_fg245_retrait_roof_layout -v2
"""
from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()


class RetraitRoofLayoutTest(TestCase):
    def test_l_endpoint_ventes_calepinages_n_existe_plus(self):
        company = Company.objects.create(nom='QJR647', slug='qjr647')
        user = User.objects.create_user(
            username='qjr647', password='x', role_legacy='admin',
            company=company)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        self.assertEqual(
            api.get('/api/django/ventes/calepinages/').status_code, 404)

    def test_calepinage_list_resout_vers_l_app_calepinage(self):
        self.assertEqual(reverse('calepinage-list'),
                         '/api/django/calepinage/calepinages/')

    def test_le_modele_n_existe_plus(self):
        with self.assertRaises(LookupError):
            apps.get_model('ventes', 'RoofLayout')
