"""ACRM6 (C-ACRM-003) — « placement-cadences » (aperçu ET application)
n'opère que sur les leads de la PORTÉE de l'appelant.

D-ACRM-2 (recommandation appliquée par défaut) : borner à la portée plutôt
que réserver l'action au palier admin. Sonde V_VA LVIEW1-3 : un Commercial
voyait dans l'aperçu, puis plaçait, le lead L1 d'un collègue hors équipe
(GET L1 → 404). La commande système garde toute la société (``None``).

Rôles réels ; aucun mock.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import stages
from apps.crm.models import Lead, RelanceEtape
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    COMMERCIAL_PERMISSIONS, DIRECTEUR_PERMISSIONS)

User = get_user_model()
URL = '/api/django/crm/leads/placement-cadences/'


class PlacementPorteeTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM6 Solaire', slug='acrm6-placement')
        commercial = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS), est_systeme=True)
        directeur = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
        self.moi = User.objects.create_user(
            username='acrm6-moi', password='x', company=self.company,
            role=commercial)
        self.collegue = User.objects.create_user(
            username='acrm6-collegue', password='x', company=self.company,
            role=commercial)
        self.admin = User.objects.create_user(
            username='acrm6-admin', password='x', company=self.company,
            role=directeur)
        self.mien = Lead.objects.create(
            company=self.company, nom='Mien', owner=self.moi,
            stage=stages.CONTACTED)
        self.l1 = Lead.objects.create(
            company=self.company, nom='L1Collegue', owner=self.collegue,
            stage=stages.CONTACTED, tags='')
        # Aucune cadence d'avance : les deux leads sont candidats.
        RelanceEtape.objects.filter(company=self.company).delete()

    def _api(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(user)}'))
        return api

    def test_apercu_sans_hors_portee(self):
        api = self._api(self.moi)
        self.assertEqual(
            api.get(f'/api/django/crm/leads/{self.l1.pk}/').status_code, 404)
        resp = api.post(URL, {'apply': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertNotIn(self.l1.pk, [e['lead'] for e in resp.data['apercu']])
        self.assertIn(self.mien.pk, [e['lead'] for e in resp.data['apercu']])
        self.assertEqual(resp.data['total_candidats'], 1)

    def test_application_sans_hors_portee(self):
        avant = (self.l1.stage, self.l1.tags)
        api = self._api(self.moi)
        for _ in range(10):
            resp = api.post(URL, {'apply': True, 'limite': 200},
                            format='json')
            self.assertEqual(resp.status_code, 200, resp.content)
            if resp.data['restants'] == 0:
                break
        self.assertEqual(
            RelanceEtape.objects.filter(lead=self.l1).count(), 0)
        self.l1.refresh_from_db()
        self.assertEqual((self.l1.stage, self.l1.tags), avant)
        self.assertTrue(RelanceEtape.objects.filter(lead=self.mien).exists())

    def test_admin_toute_la_societe(self):
        resp = self._api(self.admin).post(URL, {'apply': False},
                                          format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        leads = {e['lead'] for e in resp.data['apercu']}
        self.assertEqual(leads, {self.mien.pk, self.l1.pk})
