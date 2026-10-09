"""ACHT43 (C-ACHT-042) — l'arrivée et le départ dépôt passent par les MÊMES
gestes (`field_services.enregistrer_arrivee` / `enregistrer_depart_depot`)
dans la vue et dans la synchro terrain : `arrivee_dans_fenetre` et la
position de départ sont posés par les deux chemins.

Rejoue CINT-17 : vue checkin -> arrivee_dans_fenetre True ; sync checkin ->
applied, arrivee_dans_fenetre None.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht43_parite_checkin"
"""
import datetime
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import Installation, Intervention

User = get_user_model()
BASE = '/api/django/installations/interventions'
SYNC = '/api/django/installations/sync/'


class PariteCheckinTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht43', defaults={'nom': 'Co ACHT43'})
        self.user = User.objects.create_user(
            username='resp-acht43', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT43')
        self.vue = self._iv(inst)
        self.sync = self._iv(inst)

    def _iv(self, inst):
        return Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', created_by=self.user,
            technicien=self.user, fenetre_debut=datetime.time(0, 0),
            fenetre_fin=datetime.time(23, 59, 59))

    def _op(self, op_type, iv, **payload):
        payload['intervention'] = iv.id
        r = self.api.post(SYNC, {'ops': [{
            'client_op_id': str(uuid.uuid4()), 'op_type': op_type,
            'payload': payload}]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        res = r.data['results'][0]
        self.assertEqual(res['status'], 'applied', res)

    def test_sync_checkin_pose_fenetre(self):
        self._op('intervention.checkin', self.sync, lat=33.5, lng=-7.6)
        self.sync.refresh_from_db()
        self.assertIs(self.sync.arrivee_dans_fenetre, True)
        self.assertEqual(self.sync.arrivee_gps_lat, 33.5)

    def test_sync_depart_pose_position(self):
        self._op('intervention.depart_depot', self.sync, lat=33.1, lng=-7.2)
        self.sync.refresh_from_db()
        self.assertEqual(self.sync.depart_gps_lat, 33.1)
        self.assertEqual(self.sync.depart_gps_lng, -7.2)

    def test_parite_vue_sync(self):
        self.api.post(f'{BASE}/{self.vue.id}/checkin/',
                      {'lat': 33.5, 'lng': -7.6}, format='json')
        self.api.post(f'{BASE}/{self.vue.id}/depart-depot/',
                      {'lat': 33.1, 'lng': -7.2}, format='json')
        self._op('intervention.checkin', self.sync, lat=33.5, lng=-7.6)
        self._op('intervention.depart_depot', self.sync, lat=33.1, lng=-7.2)
        self.vue.refresh_from_db()
        self.sync.refresh_from_db()
        for champ in ('arrivee_dans_fenetre', 'arrivee_gps_lat',
                      'arrivee_gps_lng', 'depart_gps_lat', 'depart_gps_lng'):
            self.assertEqual(getattr(self.vue, champ),
                             getattr(self.sync, champ), champ)
        self.assertIsNotNone(self.sync.arrivee_site_le)
        self.assertIsNotNone(self.sync.depart_depot_le)
