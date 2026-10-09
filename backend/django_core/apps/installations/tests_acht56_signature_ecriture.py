"""ACHT56 (C-ACHT-055) — `signer_client` et le POST de `tool-return` sont des
ÉCRITURES (IsResponsableOrAdmin que le Technicien franchit par
`intervention_gerer`) : un Viewer ne pose plus de signature client.

Rejoue CTEN-7/7b : Viewer SIGNER-CLIENT 200 (la sienne et celle du pair).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht56_signature_ecriture"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import Installation, Intervention
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    TECHNICIEN_PERMISSIONS, VIEWER_PERMISSIONS,
)

User = get_user_model()
BASE = '/api/django/installations/interventions'
SIG = 'data:image/png;base64,QUFB'


class SignatureEcritureTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACHT56', slug='acht56-co')
        role_viewer = Role.objects.create(
            company=self.company, nom='Viewer',
            permissions=list(VIEWER_PERMISSIONS))
        role_tech = Role.objects.create(
            company=self.company, nom='Technicien',
            permissions=list(TECHNICIEN_PERMISSIONS))
        self.viewer = User.objects.create_user(
            username='viewer-acht56', password='x', company=self.company,
            role=role_viewer)
        self.tech = User.objects.create_user(
            username='tech-acht56', password='x', company=self.company,
            role=role_tech)
        inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT56')
        self.iv_viewer = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', technicien=self.viewer)
        self.iv_tech = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', technicien=self.tech)

    def _api(self, user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_viewer_ne_signe_pas(self):
        api = self._api(self.viewer)
        for iv in (self.iv_viewer, self.iv_tech):
            r = api.post(f'{BASE}/{iv.id}/signer-client/', {
                'signature_client': SIG, 'signataire_nom': 'Faux client'},
                format='json')
            self.assertIn(r.status_code, (403, 404), (iv.id, r.data))
            iv.refresh_from_db()
            self.assertFalse(iv.signature_client)
            self.assertFalse(iv.signataire_nom)
            self.assertIsNone(iv.signe_le)
        r = api.post(f'{BASE}/{self.iv_viewer.id}/tool-return/', {},
                     format='json')
        self.assertEqual(r.status_code, 403, r.data)

    def test_lecture_tool_return_viewer_ok(self):
        r = self._api(self.viewer).get(
            f'{BASE}/{self.iv_viewer.id}/tool-return/')
        self.assertEqual(r.status_code, 200, r.data)

    def test_technicien_signe(self):
        r = self._api(self.tech).post(
            f'{BASE}/{self.iv_tech.id}/signer-client/', {
                'signature_client': SIG, 'signataire_nom': 'M. Alaoui'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.iv_tech.refresh_from_db()
        self.assertEqual(self.iv_tech.signature_client, SIG)
