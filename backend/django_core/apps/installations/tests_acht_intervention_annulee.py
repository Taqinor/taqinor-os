"""ACHT34 (C-ACHT-030) — une intervention annulée (drapeau YSERV6) refuse tout
changement de statut (`changer_statut_intervention` : PATCH, actions,
synchro) et toute op de synchro de saisie tant que le chantier n'est pas
réactivé : elle n'émet jamais `intervention_completed`.

Rejoue CINT-7 : sync `terminer` appliqué (terminée, 1 événement) ; PATCH
`statut=terminee` 200.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_intervention_annulee"
"""
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import (
    ComponentSerial, Installation, Intervention, Reserve,
)
from core.events import intervention_completed

User = get_user_model()
SYNC = '/api/django/installations/sync/'
MSG = 'Intervention annulée — réactivez le chantier'


class InterventionAnnuleeTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht34', defaults={'nom': 'Co ACHT34'})
        self.user = User.objects.create_user(
            username='resp-acht34', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT34', annule=True)
        self.iv = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', created_by=self.user,
            technicien=self.user, statut=Intervention.Statut.SUR_SITE,
            annulee=True)
        self.evenements = []

        def _abonne(sender, **kwargs):
            self.evenements.append(kwargs)

        self._abonne = _abonne
        intervention_completed.connect(
            _abonne, dispatch_uid='acht34-temoin')
        self.addCleanup(intervention_completed.disconnect,
                        dispatch_uid='acht34-temoin')

    def _sync(self, op_type, **payload):
        payload.setdefault('intervention', self.iv.id)
        r = self.api.post(SYNC, {'ops': [{
            'client_op_id': str(uuid.uuid4()), 'op_type': op_type,
            'payload': payload}]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data['results'][0]

    def _assert_inchangee(self):
        self.iv.refresh_from_db()
        self.assertEqual(self.iv.statut, Intervention.Statut.SUR_SITE)

    def test_sync_terminer_refuse(self):
        res = self._sync('intervention.terminer')
        self.assertEqual(res['status'], 'error', res)
        self.assertIn(MSG, res['error'])
        self._assert_inchangee()

    def test_patch_terminee_refuse(self):
        r = self.api.patch(
            f'/api/django/installations/interventions/{self.iv.id}/',
            {'statut': Intervention.Statut.TERMINEE}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn(MSG, str(r.data))
        self._assert_inchangee()

    def test_ops_saisie_refusees(self):
        for op_type, extra in (
                ('intervention.serial', {'numero_serie': 'SN-1'}),
                ('intervention.reserve', {'description': 'Reprise'}),
                ('intervention.consommation_ligne',
                 {'ligne': 1, 'quantite_utilisee': '3'}),
                ('intervention.signer_client',
                 {'signature_client': 'data:image/png;base64,AA=='})):
            with self.subTest(op_type=op_type):
                res = self._sync(op_type, **extra)
                self.assertEqual(res['status'], 'error', res)
                self.assertIn(MSG, res['error'])
        self.assertFalse(ComponentSerial.objects.filter(
            intervention=self.iv).exists())
        self.assertFalse(Reserve.objects.filter(
            intervention=self.iv).exists())
        self.iv.refresh_from_db()
        self.assertIsNone(self.iv.signe_le)

    def test_aucun_evenement(self):
        self._sync('intervention.terminer')
        self.api.patch(
            f'/api/django/installations/interventions/{self.iv.id}/',
            {'statut': Intervention.Statut.TERMINEE}, format='json')
        self.assertEqual(self.evenements, [])
