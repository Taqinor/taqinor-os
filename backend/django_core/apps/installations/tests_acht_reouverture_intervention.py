"""ACHT36 (C-ACHT-032) — la réouverture d'une intervention terminée/validée
est un geste borné : `date_realisee` remise à vide et tracée au recul,
`intervention_completed` émis seulement à la première clôture
(`cloturee_notifiee_le`), op de synchro `terminer` limitée à
terminee/validee, compte-rendu public servi seulement en terminee/validee.

Rejoue CINT-9 (date 01/10 après re-clôture, 1 événement, applied a_preparer,
public 200).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_reouverture_intervention"
"""
import datetime
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import (
    Installation, Intervention, InterventionActivity,
)
from core.events import intervention_completed

User = get_user_model()
SYNC = '/api/django/installations/sync/'
BASE = '/api/django/installations/interventions'
PUBLIC = '/api/django/public/installations/intervention-rapport'


class ReouvertureInterventionTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht36', defaults={'nom': 'Co ACHT36'})
        self.user = User.objects.create_user(
            username='resp-acht36', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT36')
        self.iv = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', created_by=self.user,
            technicien=self.user, statut=Intervention.Statut.SUR_SITE)
        self.evenements = []

        def _abonne(sender, **kwargs):
            self.evenements.append(kwargs)

        intervention_completed.connect(_abonne, dispatch_uid='acht36-temoin')
        self.addCleanup(intervention_completed.disconnect,
                        dispatch_uid='acht36-temoin')

    def _patch(self, statut):
        r = self.api.patch(f'{BASE}/{self.iv.id}/', {'statut': statut},
                           format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_date_realisee_remise_a_vide(self):
        self._patch('terminee')
        Intervention.objects.filter(pk=self.iv.pk).update(
            date_realisee=datetime.date(2026, 10, 1))
        self._patch('sur_site')
        self.iv.refresh_from_db()
        self.assertIsNone(self.iv.date_realisee)
        ligne = InterventionActivity.objects.filter(
            intervention=self.iv, field='date_realisee').order_by('-id')[0]
        self.assertEqual((ligne.old_value, ligne.new_value),
                         ('2026-10-01', '—'))
        self._patch('terminee')
        self.iv.refresh_from_db()
        self.assertIsNotNone(self.iv.date_realisee)
        self.assertNotEqual(self.iv.date_realisee, datetime.date(2026, 10, 1))

    def test_completed_une_fois(self):
        self._patch('terminee')
        self.assertEqual(len(self.evenements), 1)
        self.iv.refresh_from_db()
        notifie = self.iv.cloturee_notifiee_le
        self.assertIsNotNone(notifie)
        self._patch('sur_site')
        self._patch('terminee')
        self.assertEqual(len(self.evenements), 1)
        self.iv.refresh_from_db()
        self.assertEqual(self.iv.cloturee_notifiee_le, notifie)

    def test_sync_recul_refuse(self):
        self._patch('terminee')
        r = self.api.post(SYNC, {'ops': [{
            'client_op_id': str(uuid.uuid4()),
            'op_type': 'intervention.terminer',
            'payload': {'intervention': self.iv.id,
                        'statut': 'a_preparer'}}]}, format='json')
        res = r.data['results'][0]
        self.assertEqual(res['status'], 'error', res)
        self.assertIn('Statut non admis par la synchro', res['error'])
        self.iv.refresh_from_db()
        self.assertEqual(self.iv.statut, Intervention.Statut.TERMINEE)

    def test_lien_public_suspendu(self):
        self._patch('terminee')
        self.iv.refresh_from_db()
        self.iv.ensure_lien_rapport_token()
        token = self.iv.lien_rapport_token
        self.assertEqual(self.client.get(f'{PUBLIC}/{token}/').status_code,
                         200)
        self._patch('sur_site')
        self.assertEqual(self.client.get(f'{PUBLIC}/{token}/').status_code,
                         404)
        self._patch('terminee')
        self.assertEqual(self.client.get(f'{PUBLIC}/{token}/').status_code,
                         200)
