"""ADEP44 (C-ADEP-019) — `ajouter-serial` et `ajouter-reserve` EN LIGNE sont
idempotentes par `client_op_id` (inscrit dans `FieldOp` dans la même
transaction que l'effet) : appel en ligne + rejeu de la même clé par la
synchro (ou second appel en ligne) laissent UN seul objet.

Affirme aussi le contrat `contract_samples/op_terrain_en_ligne.json` (ADEP43).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_adep_op_terrain_idempotente"
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import (
    ComponentSerial, Installation, Intervention, Reserve,
)

User = get_user_model()
BASE = '/api/django/installations'
SYNC = f'{BASE}/sync/'
CONTRAT = (Path(__file__).parent / 'contract_samples'
           / 'op_terrain_en_ligne.json')
OP_SERIAL = 'c0ffee00-0000-4000-8000-000000000301'
OP_RESERVE = 'c0ffee00-0000-4000-8000-000000000302'


class OpTerrainIdempotenteTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-adep44', defaults={'nom': 'Co ADEP44'})
        self.user = User.objects.create_user(
            username='resp-adep44', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        inst = Installation.objects.create(
            company=self.company, reference='CH-ADEP44')
        self.iv = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', created_by=self.user,
            technicien=self.user)
        self.url = f'{BASE}/interventions/{self.iv.id}'

    def _sync(self, op_type, op_id, **payload):
        payload['intervention'] = self.iv.id
        r = self.api.post(SYNC, {'ops': [{
            'client_op_id': op_id, 'op_type': op_type,
            'payload': payload}]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data['results'][0]

    def test_serial_en_ligne_puis_sync_un_objet(self):
        r = self.api.post(f'{self.url}/ajouter-serial/', {
            'client_op_id': OP_SERIAL, 'numero_serie': 'SN-ADEP44'},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIs(r.data['replayed'], False)
        res = self._sync('intervention.serial', OP_SERIAL,
                         numero_serie='SN-ADEP44')
        self.assertEqual(res['status'], 'replayed', res)
        self.assertEqual(self.iv.serials.count(), 1)

    def test_reserve_en_ligne_puis_sync_un_objet(self):
        r = self.api.post(f'{self.url}/ajouter-reserve/', {
            'client_op_id': OP_RESERVE, 'description': 'Reprise coffret'},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        res = self._sync('intervention.reserve', OP_RESERVE,
                         description='Reprise coffret')
        self.assertEqual(res['status'], 'replayed', res)
        self.assertEqual(self.iv.reserves.count(), 1)

    def test_double_appel_en_ligne_meme_cle(self):
        corps = {'client_op_id': OP_SERIAL, 'numero_serie': 'SN-ADEP44-2'}
        r1 = self.api.post(f'{self.url}/ajouter-serial/', corps, format='json')
        r2 = self.api.post(f'{self.url}/ajouter-serial/', corps, format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertIs(r2.data['replayed'], True)
        self.assertEqual(r1.data['id'], r2.data['id'])
        self.assertEqual(ComponentSerial.objects.filter(
            intervention=self.iv).count(), 1)
        corps_r = {'client_op_id': OP_RESERVE, 'description': 'Reprise'}
        a = self.api.post(f'{self.url}/ajouter-reserve/', corps_r,
                          format='json')
        b = self.api.post(f'{self.url}/ajouter-reserve/', corps_r,
                          format='json')
        self.assertEqual(a.data['id'], b.data['id'])
        self.assertEqual(Reserve.objects.filter(
            intervention=self.iv).count(), 1)

    def test_sync_puis_en_ligne_renvoie_l_objet_existant(self):
        res = self._sync('intervention.serial', OP_SERIAL,
                         numero_serie='SN-ADEP44-3')
        self.assertEqual(res['status'], 'applied', res)
        r = self.api.post(f'{self.url}/ajouter-serial/', {
            'client_op_id': OP_SERIAL, 'numero_serie': 'SN-ADEP44-3'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self.iv.serials.count(), 1)

    def test_sans_cle_comportement_inchange(self):
        for n in range(2):
            r = self.api.post(f'{self.url}/ajouter-reserve/', {
                'description': f'R{n}'}, format='json')
            self.assertEqual(r.status_code, 201, r.data)
            self.assertNotIn('replayed', r.data)
        self.assertEqual(self.iv.reserves.count(), 2)

    def test_contrat_op_terrain_en_ligne(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        r = self.api.post(f'{self.url}/ajouter-serial/', {
            'client_op_id': OP_SERIAL, 'numero_serie': 'SN-CONTRAT'},
            format='json')
        self.assertEqual(set(r.data), set(contrat['exemple']))
        rejeu = self.api.post(f'{self.url}/ajouter-serial/', {
            'client_op_id': OP_SERIAL, 'numero_serie': 'SN-CONTRAT'},
            format='json')
        self.assertEqual(set(rejeu.data), set(contrat['exemple_rejeu']))
        self.assertIs(rejeu.data['replayed'], True)
        res = self.api.post(f'{self.url}/ajouter-reserve/', {
            'client_op_id': OP_RESERVE, 'description': 'x'}, format='json')
        self.assertEqual(
            set(res.data), set(contrat['ajouter_reserve']['exemple']))
