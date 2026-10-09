"""ACRM20 — un lead portant un rappel MANUEL à venir (``relance_date`` ≥
aujourd'hui, posée par le vrai PATCH) reste hors dormance au placement des
anciens leads : pas de Froid, pas d'étiquette, pas de Réveil, ``relance_date``
inchangée, compté dans ``ignores['rappel_manuel_a_venir']`` — rejoue la
sonde LSVC4-11.

Test-du-test : retirer le test ``relance_date >= aujourd'hui`` ⇒
test_rappel_manuel_tient_hors_dormance échoue (lead au Froid).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import stages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.services import placer_anciens_leads

User = get_user_model()


class PlacementRappelManuelTests(TestCase):

    def setUp(self):
        from apps.roles.models import Role
        from apps.roles.permissions_registre import ADMIN_PERMISSIONS
        self.company = Company.objects.create(
            nom='ACRM20 Solaire', slug='acrm20-rappel')
        role, _ = Role.objects.get_or_create(
            company=self.company, nom='Administrateur',
            defaults={'permissions': ADMIN_PERMISSIONS, 'est_systeme': True})
        self.user = User.objects.create_user(
            username='acrm20-admin', password='x', company=self.company,
            role=role, role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.dans_20 = timezone.localdate() + datetime.timedelta(days=20)

    def _vieux_lead(self, nom):
        lead = Lead.objects.create(
            company=self.company, nom=nom, stage=stages.CONTACTED,
            owner=self.user)
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=timezone.now() - datetime.timedelta(days=60))
        return lead

    def test_rappel_manuel_tient_hors_dormance(self):
        lead = self._vieux_lead('Rappel')
        resp = self.api.patch(f'/api/django/crm/leads/{lead.pk}/',
                              {'relance_date': self.dans_20.isoformat()},
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        lead.refresh_from_db()
        tags_avant = lead.tags
        rapport = placer_anciens_leads(self.company, self.user, apply=True)
        self.assertEqual(rapport['ignores']['rappel_manuel_a_venir'], 1)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)
        self.assertEqual(lead.tags, tags_avant)
        self.assertEqual(lead.relance_date, self.dans_20)
        self.assertFalse(RelanceEtape.objects.filter(
            lead=lead, cadence='reveil').exists())

    def test_sans_rappel_dormant(self):
        lead = self._vieux_lead('Sans rappel')
        rapport = placer_anciens_leads(self.company, self.user, apply=True)
        self.assertEqual(rapport['ignores']['rappel_manuel_a_venir'], 0)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.COLD)
