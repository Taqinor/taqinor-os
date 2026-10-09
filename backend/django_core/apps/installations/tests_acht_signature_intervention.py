"""ACHT28 (C-ACHT-026) — un service unique `enregistrer_signature_intervention`
(validation ADOC78, refus 409 d'une re-signature sans motif, motif et ancien
signataire tracés, champs suivis au chatter) appelé par l'action
`signer-client` ET l'op de synchro `intervention.signer_client`.

Rejoue CINT-2 (op de synchro portant une URL `http://169.254.169.254/…`
appliquée, URL stockée puis injectée dans la fiche SAV) et CINT-4
(re-signature 200, `signe_le` écrasé, chatter sans ancienne valeur).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_signature_intervention"
"""
import uuid
from datetime import datetime, timezone as dt_tz

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import (
    Installation, Intervention, InterventionActivity,
)

User = get_user_model()
SIG_A = 'data:image/png;base64,QUFB'
SIG_B = 'data:image/png;base64,QkJC'
URL_SSRF = 'http://169.254.169.254/latest/meta-data/x.png'


class SignatureInterventionTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht28', defaults={'nom': 'Co ACHT28'})
        self.user = User.objects.create_user(
            username='resp-acht28', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT28')
        self.non_signee = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', created_by=self.user,
            technicien=self.user, statut=Intervention.Statut.SUR_SITE)
        self.signee_le = datetime(2026, 10, 1, 9, 0, tzinfo=dt_tz.utc)
        self.signee = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', created_by=self.user,
            technicien=self.user, statut=Intervention.Statut.VALIDEE,
            signature_client=SIG_A, signataire_nom='Client A',
            signe_le=self.signee_le)

    def _sync(self, interv, signature, nom='Client B'):
        r = self.api.post('/api/django/installations/sync/', {'ops': [{
            'client_op_id': str(uuid.uuid4()),
            'op_type': 'intervention.signer_client',
            'payload': {'intervention': interv.id,
                        'signature_client': signature,
                        'signataire_nom': nom}}]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data['results'][0]

    def _signer(self, interv, **extra):
        corps = {'signature_client': SIG_B, 'signataire_nom': 'Client B'}
        corps.update(extra)
        return self.api.post(
            f'/api/django/installations/interventions/{interv.id}/'
            'signer-client/', corps, format='json')

    def _assert_signature_a(self):
        self.signee.refresh_from_db()
        self.assertEqual(self.signee.signature_client, SIG_A)
        self.assertEqual(self.signee.signataire_nom, 'Client A')
        self.assertEqual(self.signee.signe_le, self.signee_le)

    def test_sync_url_refusee(self):
        res = self._sync(self.non_signee, URL_SSRF)
        self.assertEqual(res['status'], 'error', res)
        self.assertIn('Signature invalide', res['error'])
        self.non_signee.refresh_from_db()
        self.assertFalse(self.non_signee.signature_client)
        self.assertIsNone(self.non_signee.signe_le)

    def test_resignature_sans_motif_409(self):
        r = self._signer(self.signee)
        self.assertEqual(r.status_code, 409, r.data)
        self._assert_signature_a()

    def test_resignature_motif_tracee(self):
        r = self._signer(self.signee,
                         motif_override_signature='Erreur de signataire')
        self.assertEqual(r.status_code, 200, r.data)
        self.signee.refresh_from_db()
        self.assertEqual(self.signee.signature_client, SIG_B)
        note = InterventionActivity.objects.filter(
            intervention=self.signee,
            body__contains='Signature remplacée (motif : Erreur de '
                           'signataire)').first()
        self.assertIsNotNone(note)
        self.assertIn('Client A', note.body)
        self.assertIn('Client B', note.body)
        self.assertTrue(InterventionActivity.objects.filter(
            intervention=self.signee, field='signataire_nom',
            old_value='Client A', new_value='Client B').exists())

    def test_sync_ne_reecrit_pas(self):
        res = self._sync(self.signee, SIG_B)
        self.assertEqual(res['status'], 'error', res)
        self._assert_signature_a()
