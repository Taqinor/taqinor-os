"""ACHT27 (C-ACHT-025) — la synchro hors-ligne terrain est bornée à la portée
du viewset : `field_sync._intervention` / `_chantier` résolvent leur cible
par le même sélecteur que `InterventionViewSet` / `InstallationViewSet`
(`selectors.scoper_interventions` / `scoper_chantiers`). Une op sur une
cible invisible revient « inconnue » sans rien écrire.

Rejoue CINT-1 : le technicien B (portée équipe, sans superviseur) obtient
404 en GET sur l'intervention de A, mais ses ops `terminer` / `signer_client`
étaient `applied` et `cocher_checklist` passait le filtre.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_sync_portee"
"""
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.field_sync import FIELD_OP_HANDLERS
from apps.installations.models import (
    ChantierChecklistItem, Installation, Intervention,
)
from apps.roles.models import Role
from apps.roles.permissions_registre import SCOPE_TEAM

User = get_user_model()
SYNC = '/api/django/installations/sync/'


class SyncPorteeTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht27', defaults={'nom': 'Co ACHT27'})
        role = Role.objects.create(
            company=self.company, nom='technicien-equipe-acht27',
            permissions=['installation_voir', 'intervention_gerer',
                         SCOPE_TEAM])
        self.chef = User.objects.create_user(
            username='acht27-chef', password='x', company=self.company,
            role_legacy='responsable')
        self.a = User.objects.create_user(
            username='acht27-a', password='x', company=self.company,
            role_legacy='normal', role=role)
        self.b = User.objects.create_user(
            username='acht27-b', password='x', company=self.company,
            role_legacy='normal', role=role)
        self.inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT27',
            technicien_responsable=self.a, created_by=self.chef)
        self.iv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', technicien=self.a,
            created_by=self.chef, statut=Intervention.Statut.SUR_SITE)
        self.item = ChantierChecklistItem.objects.create(
            company=self.company, installation=self.inst, cle='acht27',
            libelle='Étape ACHT27')

    def _api(self, user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def _op(self, op_type, **payload):
        return {'client_op_id': str(uuid.uuid4()), 'op_type': op_type,
                'payload': payload}

    def _sync(self, user, ops):
        r = self._api(user).post(SYNC, {'ops': ops}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data['results']

    def _payload_cible(self, op_type):
        _handler, cible, cle = FIELD_OP_HANDLERS[op_type]
        if cible == 'chantier':
            return {cle: self.inst.id, 'cle': 'acht27', 'fait': True}
        return {cle: self.iv.id, 'signature_client': 'data:image/png;base64,AA',
                'signataire_nom': 'Client'}

    def test_chaque_op_type_hors_portee_inconnu(self):
        for op_type in FIELD_OP_HANDLERS:
            with self.subTest(op_type=op_type):
                res = self._sync(
                    self.b, [self._op(op_type, **self._payload_cible(op_type))])
                self.assertEqual(res[0]['status'], 'error', res)
                self.assertRegex(res[0]['error'],
                                 r'(Intervention inconnue|Chantier inconnu)')
        self.iv.refresh_from_db()
        self.assertEqual(self.iv.statut, Intervention.Statut.SUR_SITE)
        self.assertFalse(self.iv.signature_client)
        self.item.refresh_from_db()
        self.assertFalse(self.item.fait)

    def test_le_titulaire_applique(self):
        res = self._sync(self.a, [
            self._op('intervention.signer_client',
                     intervention=self.iv.id,
                     signature_client='data:image/png;base64,AA',
                     signataire_nom='Client'),
            self._op('chantier.cocher_checklist', chantier=self.inst.id,
                     cle='acht27', fait=True),
            self._op('intervention.terminer', intervention=self.iv.id),
        ])
        self.assertEqual([r['status'] for r in res],
                         ['applied', 'applied', 'applied'], res)
        self.iv.refresh_from_db()
        self.assertEqual(self.iv.statut, Intervention.Statut.TERMINEE)


class LectureChantierTechnicienInterventionTests(TestCase):
    """ERR-CHT-TECH-CHANTIER-404 — le technicien d'une intervention LIT son
    chantier (panneau « Infos client ») sans en être le responsable ; rien
    d'autre ne s'élargit (écriture, synchro, autre société)."""

    URL = '/api/django/installations/chantiers/{}/'

    def _user(self, company, role, username):
        return User.objects.create_user(
            username=username, password='x', company=company,
            role_legacy='normal', role=role)

    def _role(self, company, nom):
        return Role.objects.create(
            company=company, nom=nom,
            permissions=['installation_voir', 'intervention_gerer',
                         SCOPE_TEAM])

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-cht404', defaults={'nom': 'Co CHT404'})
        role = self._role(self.company, 'technicien-cht404')
        chef = User.objects.create_user(
            username='cht404-chef', password='x', company=self.company,
            role_legacy='responsable')
        self.a = self._user(self.company, role, 'cht404-a')
        self.b = self._user(self.company, role, 'cht404-b')
        self.c = self._user(self.company, role, 'cht404-c')
        # Chantier de A (responsable) ; l'intervention est assignée à B.
        self.inst = Installation.objects.create(
            company=self.company, reference='CH-CHT404',
            technicien_responsable=self.a, created_by=chef)
        for _ in range(2):  # deux interventions → aucune ligne dupliquée
            Intervention.objects.create(
                company=self.company, installation=self.inst,
                type_intervention='pose', technicien=self.b,
                created_by=chef)
        ChantierChecklistItem.objects.create(
            company=self.company, installation=self.inst, cle='cht404',
            libelle='Étape CHT404')
        autre = Company.objects.create(slug='co-cht404-autre', nom='Autre')
        self.x = self._user(
            autre, self._role(autre, 'technicien-cht404-autre'), 'cht404-x')

    def _api(self, user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_technicien_assigne_lit_le_chantier(self):
        r = self._api(self.b).get(self.URL.format(self.inst.id))
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        self.assertEqual(r.data['id'], self.inst.id)
        data = self._api(self.b).get(
            '/api/django/installations/chantiers/').data
        lignes = data['results'] if isinstance(data, dict) else data
        # La fiche seule s'ouvre : la LISTE reste bornée (ACHT50 / ACHT79).
        self.assertNotIn(self.inst.id, [c['id'] for c in lignes])

    def test_technicien_non_assigne_meme_societe_404(self):
        r = self._api(self.c).get(self.URL.format(self.inst.id))
        self.assertEqual(r.status_code, 404)

    def test_autre_societe_404(self):
        r = self._api(self.x).get(self.URL.format(self.inst.id))
        self.assertEqual(r.status_code, 404)

    def test_aucune_ecriture_elargie(self):
        r = self._api(self.b).patch(
            self.URL.format(self.inst.id), {'notes': 'b'}, format='json')
        self.assertEqual(r.status_code, 404)
        r = self._api(self.b).post(SYNC, {'ops': [{
            'client_op_id': str(uuid.uuid4()),
            'op_type': 'chantier.cocher_checklist',
            'payload': {'chantier': self.inst.id, 'cle': 'cht404',
                        'fait': True}}]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['results'][0]['status'], 'error', r.data)
        self.assertFalse(ChantierChecklistItem.objects.get(
            installation=self.inst).fait)
