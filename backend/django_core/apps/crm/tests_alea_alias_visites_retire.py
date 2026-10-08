"""ALEA15 — l'alias déprécié ``/api/django/crm/visites/`` est retiré.

Rejoue la sonde V4 LVIS-11 : avec le module ``visites`` DÉSACTIVÉ, l'alias
sous le préfixe ``crm`` répondait encore 200 (le middleware ne coupait que
``/api/django/visites/``). Authentification par VRAI jeton Bearer : sans lui
le middleware ne voit pas la société (cf. V4).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
from apps.visites.models import VisiteTerrain
from authentication.models import Company
from core.models import ModuleToggle

User = get_user_model()

URL_VISITES = '/api/django/visites/visites/'
URL_ALIAS = '/api/django/crm/visites/'


class AliasVisitesRetireTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ALEA15', slug='alea15')
        role = Role.objects.create(
            company=self.company, nom='Commercial terrain ALEA15',
            permissions=list(dict(CANONICAL_SYSTEM_ROLES)['Commercial terrain']))
        self.terrain = User.objects.create_user(
            username='alea15-terrain', password='x', company=self.company,
            role_legacy='normal', role=role)
        lead = Lead.objects.create(company=self.company, nom='Alaoui')
        self.visite = VisiteTerrain.objects.create(
            company=self.company, lead=lead, commercial=self.terrain)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.terrain)}')

    def test_alias_crm_visites_404(self):
        self.assertEqual(self.api.get(URL_VISITES).status_code, 200)
        self.assertEqual(self.api.get(URL_ALIAS).status_code, 404)
        self.assertEqual(
            self.api.get(f'{URL_ALIAS}{self.visite.id}/').status_code, 404)

    def test_module_off_coupe_tout(self):
        ModuleToggle.objects.create(company=self.company, module='visites',
                                    actif=False)
        self.assertEqual(self.api.get(URL_VISITES).status_code, 404)
        self.assertEqual(self.api.get(URL_ALIAS).status_code, 404)
        self.assertEqual(
            self.api.get(f'{URL_ALIAS}{self.visite.id}/').status_code, 404)
