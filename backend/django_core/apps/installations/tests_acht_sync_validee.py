"""ACHT30 (C-ACHT-028) — la synchro refuse toute écriture sur une
réconciliation validée ou une intervention validée (`consommation_ligne`,
`serial`, `reserve`) par les gardes communes `consommation_modifiable` /
`intervention_modifiable`, aussi lues par les vues.

Rejoue CINT-5 : op `consommation_ligne` (qté 3) appliquée sur une
réconciliation validée (ligne 10 sortie du stock) ; `serial` et `reserve`
appliqués sur une intervention validée ; la vue renvoyait déjà 400.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_sync_validee"
"""
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import (
    ComponentSerial, ConsommationLigne, Installation, Intervention,
    MaterielConsommation, Reserve,
)

User = get_user_model()
SYNC = '/api/django/installations/sync/'


class SyncValideeTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht30', defaults={'nom': 'Co ACHT30'})
        self.user = User.objects.create_user(
            username='resp-acht30', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT30')
        self.iv = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', created_by=self.user,
            technicien=self.user, statut=Intervention.Statut.VALIDEE)
        self.cons = MaterielConsommation.objects.create(
            company=self.company, intervention=self.iv, valide=True)
        self.ligne = ConsommationLigne.objects.create(
            company=self.company, consommation=self.cons,
            designation='Câble', quantite_prevue=Decimal('10'),
            quantite_utilisee=Decimal('10'), stock_applique=True)

    def _sync(self, op_type, **payload):
        payload.setdefault('intervention', self.iv.id)
        r = self.api.post(SYNC, {'ops': [{
            'client_op_id': str(uuid.uuid4()), 'op_type': op_type,
            'payload': payload}]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data['results'][0]

    def test_consommation_validee_refusee(self):
        res = self._sync('intervention.consommation_ligne',
                         ligne=self.ligne.id, quantite_utilisee='3')
        self.assertEqual(res['status'], 'error', res)
        self.assertEqual(res['error'], 'Réconciliation déjà validée.')
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.quantite_utilisee, Decimal('10'))

    def test_serial_intervention_validee_refuse(self):
        res = self._sync('intervention.serial', numero_serie='SN-ACHT30')
        self.assertEqual(res['status'], 'error', res)
        self.assertEqual(res['error'], 'Intervention validée.')
        self.assertFalse(ComponentSerial.objects.filter(
            intervention=self.iv).exists())

    def test_reserve_intervention_validee_refusee(self):
        res = self._sync('intervention.reserve', description='Reprise')
        self.assertEqual(res['status'], 'error', res)
        self.assertEqual(res['error'], 'Intervention validée.')
        self.assertFalse(Reserve.objects.filter(
            intervention=self.iv).exists())

    def test_vue_meme_garde(self):
        r = self.api.post(
            f'/api/django/installations/interventions/{self.iv.id}/'
            'modifier-ligne-consommation/',
            {'ligne': self.ligne.id, 'quantite_utilisee': '3'},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('Réconciliation déjà validée.', str(r.data))
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.quantite_utilisee, Decimal('10'))
