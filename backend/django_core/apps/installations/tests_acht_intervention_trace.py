"""ACHT35 (C-ACHT-031) — un PATCH d'intervention qui change aussi le statut
journalise TOUS les champs suivis modifiés (état « avant » capturé avant la
sauvegarde), et `compte_rendu` est désormais suivi.

Rejoue CINT-8 : seuls statut et date_realisee étaient tracés.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_intervention_trace"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import (
    Installation, Intervention, InterventionActivity,
)

User = get_user_model()
BASE = '/api/django/installations/interventions'


class InterventionTraceTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht35', defaults={'nom': 'Co ACHT35'})
        self.user = User.objects.create_user(
            username='resp-acht35', password='x', company=self.company,
            role_legacy='responsable')
        self.autre = User.objects.create_user(
            username='tech-acht35', password='x', company=self.company,
            role_legacy='technicien')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT35')
        self.iv = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', created_by=self.user,
            technicien=self.user, statut=Intervention.Statut.SUR_SITE)

    def _champs(self):
        return {a.field: (a.old_value, a.new_value)
                for a in InterventionActivity.objects.filter(
                    intervention=self.iv, field__isnull=False)}

    def test_patch_multi_champs_avec_statut(self):
        r = self.api.patch(f'{BASE}/{self.iv.id}/', {
            'statut': 'terminee', 'technicien': self.autre.id,
            'date_prevue': '2026-11-01', 'compte_rendu': 'ok'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        champs = self._champs()
        for cle in ('statut', 'date_realisee', 'technicien', 'date_prevue',
                    'compte_rendu'):
            self.assertIn(cle, champs, champs)
        self.assertEqual(champs['technicien'][1], self.autre.username)
        self.assertEqual(champs['compte_rendu'], ('—', 'ok'))

    def test_compte_rendu_trace(self):
        self.api.patch(f'{BASE}/{self.iv.id}/', {'compte_rendu': 'ok'},
                       format='json')
        r = self.api.patch(f'{BASE}/{self.iv.id}/',
                           {'compte_rendu': 'corrigé'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        derniere = InterventionActivity.objects.filter(
            intervention=self.iv, field='compte_rendu').order_by('-id')[0]
        self.assertEqual((derniere.old_value, derniere.new_value),
                         ('ok', 'corrigé'))
