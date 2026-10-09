"""ACHT76 (C-ACHT-072) — unicité PAR SOCIÉTÉ validée dans les sérialiseurs des
six référentiels de chantier : 400 en français sous le champ au lieu d'un 500
(IntegrityError) ; la même clé dans une AUTRE société reste acceptée ; un
PATCH qui garde sa propre clé reste 200.

Rejoue COUT-7 : les 6 doublons répondaient `500 server_error`.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht76_unicite_referentiels"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import (
    ChecklistEtapeModele, ChecklistTemplate, Equipe,
    FicheInterventionTemplate, SafetyChecklistSlot, ShotListSlot,
    StageModele,
)

User = get_user_model()
BASE = '/api/django/installations'


def _api(user):
    api = APIClient()
    api.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class UniciteReferentielsTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='ACHT76', slug='acht76-co')
        self.autre = Company.objects.create(nom='ACHT76 B', slug='acht76-b')
        self.admin = User.objects.create_user(
            username='admin-acht76', password='x', company=self.co,
            role_legacy='admin')
        self.admin_b = User.objects.create_user(
            username='admin-b-acht76', password='x', company=self.autre,
            role_legacy='admin')
        self.api = _api(self.admin)
        StageModele.objects.create(
            company=self.co, cle='etude_site', libelle='Étude', ordre=1)
        ShotListSlot.objects.create(
            company=self.co, cle='toit_avant', libelle='Toit avant',
            phase='avant')
        SafetyChecklistSlot.objects.create(
            company=self.co, cle='epi', libelle='EPI')
        self.tpl = ChecklistTemplate.objects.create(
            company=self.co, nom='Défaut')
        ChecklistEtapeModele.objects.create(
            company=self.co, template=self.tpl, cle='etape1', libelle='E1')
        FicheInterventionTemplate.objects.create(
            company=self.co, nom='Pose', type_intervention='pose')
        Equipe.objects.create(company=self.co, nom='E1')

    def _cas(self, tpl_id):
        return [
            ('etapes-chantier', {'cle': 'etude_site', 'libelle': 'X',
                                 'ordre': 5}, 'cle'),
            ('shotlist-slots', {'cle': 'toit_avant', 'libelle': 'X',
                                'phase': 'avant'}, 'cle'),
            ('consignes-securite', {'cle': 'epi', 'libelle': 'X'}, 'cle'),
            ('checklist-etapes', {'template': tpl_id, 'cle': 'etape1',
                                  'libelle': 'X'}, 'cle'),
            ('fiche-intervention-templates', {
                'nom': 'Autre', 'type_intervention': 'pose'},
             'type_intervention'),
            ('equipes', {'nom': 'E1'}, 'nom'),
        ]

    def test_doublons_400_sous_le_champ(self):
        for route, corps, champ in self._cas(self.tpl.id):
            r = self.api.post(f'{BASE}/{route}/', corps, format='json')
            self.assertEqual(r.status_code, 400, (route, r.data))
            self.assertIn(champ, r.data, route)
        self.assertEqual(StageModele.objects.filter(company=self.co).count(), 1)
        self.assertEqual(Equipe.objects.filter(company=self.co).count(), 1)

    def test_autre_societe_accepte(self):
        api_b = _api(self.admin_b)
        tpl_b = ChecklistTemplate.objects.create(
            company=self.autre, nom='Défaut B')
        for route, corps, _champ in self._cas(tpl_b.id):
            r = api_b.post(f'{BASE}/{route}/', corps, format='json')
            self.assertEqual(r.status_code, 201, (route, r.data))

    def test_patch_garde_sa_cle(self):
        etape = StageModele.objects.get(company=self.co, cle='etude_site')
        r = self.api.patch(f'{BASE}/etapes-chantier/{etape.id}/',
                           {'cle': 'etude_site', 'libelle': 'Renommée'},
                           format='json')
        self.assertEqual(r.status_code, 200, r.data)
        equipe = Equipe.objects.get(company=self.co, nom='E1')
        r = self.api.patch(f'{BASE}/equipes/{equipe.id}/',
                           {'nom': 'E1', 'description': 'ok'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
