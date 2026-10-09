"""ACRM24 (C-ACRM-017) — « Ce navigateur » n'inscrit jamais l'appareil
d'un PROSPECT au registre d'équipe.

Sonde V_VA LVIEW2-4 : un Viewer (création au registre → 403) lisait
l'``appareil_id`` d'un prospect dans « Visiteurs », puis l'inscrivait par
``ce-navigateur`` — les ouvertures de devis de ce prospect ne notifiaient
plus personne. Désormais l'identifiant du corps n'est retenu que s'il est
celui du cookie ``tq_appareil`` de la requête, ou n'a jamais servi à une
visite rattachée à un lead ; sinon un identifiant neuf est inscrit et rendu.

Vue et service réels ; aucun mock.
"""
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import AppareilEquipe, Lead, VisiteExterne
from apps.roles.models import Role
from apps.roles.permissions_registre import VIEWER_PERMISSIONS

User = get_user_model()
URL = '/api/django/crm/appareils-equipe/ce-navigateur/'


class AppareilEquipeTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM24 Solaire', slug='acrm24-appareil')
        role = Role.objects.create(
            company=self.company, nom='Viewer',
            permissions=list(VIEWER_PERMISSIONS), est_systeme=True)
        self.viewer = User.objects.create_user(
            username='acrm24-viewer', password='x', company=self.company,
            role=role)
        self.prospect = Lead.objects.create(
            company=self.company, nom='Prospect')
        self.id_prospect = str(uuid.uuid4())
        VisiteExterne.objects.create(
            company=self.company, lead=self.prospect,
            appareil_id=self.id_prospect)
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.viewer)}'))

    def test_id_prospect_refuse(self):
        resp = self.api.post(URL, {'appareil_id': self.id_prospect},
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertNotEqual(resp.data['appareil_id'], self.id_prospect)
        self.assertFalse(AppareilEquipe.objects.filter(
            company=self.company, appareil_id=self.id_prospect).exists())
        self.assertTrue(AppareilEquipe.objects.filter(
            company=self.company, appareil_id=resp.data['appareil_id']
        ).exists())

    def test_cookie_propre_accepte(self):
        propre = str(uuid.uuid4())
        self.api.cookies['tq_appareil'] = propre
        resp = self.api.post(URL, {'appareil_id': propre}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['appareil_id'], propre)
        self.assertTrue(AppareilEquipe.objects.filter(
            company=self.company, appareil_id=propre).exists())
