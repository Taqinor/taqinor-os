"""ACRM26 (C-ACRM-021) — seul le palier admin écrit les équipes
commerciales.

Sonde V_VA LVIEW2-8 : un Commercial PATCHait ``equipes/<id>/``
{responsable: moi} (200) puis lisait l'équipe d'un collègue dans
``forecast/rollup/`` ([1]). Désormais : 403, ``responsable`` inchangé, le
rollup ne la contient pas ; un admin écrit comme avant.

Rôles réels ; aucun mock.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import EquipeCommerciale
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    COMMERCIAL_PERMISSIONS, DIRECTEUR_PERMISSIONS)

User = get_user_model()
URL = '/api/django/crm/equipes/'


class EquipesAdminTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM26 Solaire', slug='acrm26-equipes')
        commercial = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS), est_systeme=True)
        directeur = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
        self.moi = User.objects.create_user(
            username='acrm26-moi', password='x', company=self.company,
            role=commercial)
        self.collegue = User.objects.create_user(
            username='acrm26-collegue', password='x', company=self.company,
            role=commercial)
        self.admin = User.objects.create_user(
            username='acrm26-admin', password='x', company=self.company,
            role=directeur)
        self.equipe = EquipeCommerciale.objects.create(
            company=self.company, nom='Équipe du collègue',
            responsable=self.collegue)

    def _api(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(user)}'))
        return api

    def test_commercial_refuse(self):
        api = self._api(self.moi)
        resp = api.patch(f'{URL}{self.equipe.pk}/',
                         {'responsable': self.moi.pk}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.equipe.refresh_from_db()
        self.assertEqual(self.equipe.responsable_id, self.collegue.pk)
        self.assertEqual(api.post(URL, {'nom': 'Mienne'},
                                  format='json').status_code, 403)
        self.assertEqual(api.delete(f'{URL}{self.equipe.pk}/').status_code,
                         403)
        rollup = api.get('/api/django/crm/forecast/rollup/')
        self.assertEqual(rollup.status_code, 200)
        self.assertNotIn(self.equipe.pk,
                         [e.get('equipe_id') for e in rollup.data['equipes']])
        # La lecture reste ouverte.
        self.assertEqual(api.get(URL).status_code, 200)

    def test_admin_ok(self):
        resp = self._api(self.admin).patch(
            f'{URL}{self.equipe.pk}/', {'responsable': self.moi.pk},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.equipe.refresh_from_db()
        self.assertEqual(self.equipe.responsable_id, self.moi.pk)
