"""ADOC129 — les jalons portail sont LA timeline synchronisée (D-ADOC-3).

Constat (C-ADOC-059/060, sondes #102/#107) : l'administration portail
créait des jalons à la main (POST 201) à côté des jalons synchronisés du
chantier (CHT11, ``upsert_jalon_chantier``) — une saisie « Installation » puis
la synchro de la même phase donnaient DEUX lignes au client ; PATCH/DELETE
passaient sans aucune trace au Journal.

Correctif : POST → 405 ; PATCH libellé/date/atteint et ``marquer_non_atteint``
tracés ancien→nouveau (``apps.audit``) ; DELETE d'un jalon synchronisé → 409,
d'un jalon hérité (sans clé de phase) → 204 ; ``cle_phase`` exposé en lecture.

Run :
    python manage.py test apps.portail.tests.test_adoc_jalons_correction -v2
"""
import itertools

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.audit.models import AuditLog
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.portail.models import JalonChantierPortail
from apps.portail.services import upsert_jalon_chantier
from authentication.models import Company, CustomUser

_seq = itertools.count(1)

RACINE = '/api/django/portail/jalons-chantier-portail/'


class JalonsCorrectionTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.co, _ = Company.objects.get_or_create(
            slug=f'adoc129-{n}', defaults={'nom': f'ADOC129 {n}'})
        self.resp = CustomUser.objects.create_user(
            username=f'adoc129-resp-{n}', password='motdepasse-test-1234',
            company=self.co, role_legacy='responsable')
        client = Client.objects.create(
            company=self.co, nom='Client', prenom='ADOC129',
            email=f'adoc129-{n}@example.invalid')
        self.chantier = Installation.objects.create(
            company=self.co, reference=f'CHT-ADOC129-{n}', client=client)
        # Jalon synchronisé par CHT11 (clé de phase « pose »).
        self.pose = upsert_jalon_chantier(
            self.co, self.chantier.id, 'pose', 'Pose', atteint=True)
        # Jalon hérité saisi à la main avant ADOC129 (aucune clé de phase).
        self.herite = JalonChantierPortail.objects.create(
            company=self.co, chantier_id=self.chantier.id,
            libelle='Installation', ordre=4)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.resp)}')

    def _journal(self, jalon, action):
        return AuditLog.objects.filter(
            content_type=ContentType.objects.get_for_model(
                JalonChantierPortail),
            object_id=str(jalon.id), action=action)

    def test_creation_manuelle_refusee(self):
        res = self.api.post(RACINE, {
            'chantier_id': self.chantier.id, 'libelle': 'Installation',
        }, format='json')
        self.assertEqual(res.status_code, 405, res.content)
        self.assertEqual(JalonChantierPortail.objects.filter(
            chantier_id=self.chantier.id, libelle='Installation').count(), 1)

    def test_correction_tracee(self):
        res = self.api.patch(f'{RACINE}{self.pose.id}/', {
            'libelle': 'Pose des panneaux', 'date_jalon': '2026-10-02',
        }, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()['cle_phase'], 'pose')
        self.pose.refresh_from_db()
        self.assertEqual(self.pose.libelle, 'Pose des panneaux')
        self.assertEqual(str(self.pose.date_jalon), '2026-10-02')
        ligne = self._journal(self.pose, AuditLog.Action.UPDATE).last()
        self.assertIsNotNone(ligne, 'aucune trace AuditLog de la correction')
        diff = {c['field']: (c['old'], c['new']) for c in ligne.changes}
        self.assertEqual(diff['libelle'], ('Pose', 'Pose des panneaux'))
        self.assertEqual(diff['date_jalon'][1], '2026-10-02')

        # « Marquer non atteint » : correction tracée elle aussi.
        res = self.api.post(f'{RACINE}{self.pose.id}/marquer_non_atteint/')
        self.assertEqual(res.status_code, 200, res.content)
        self.pose.refresh_from_db()
        self.assertFalse(self.pose.atteint)
        ligne = self._journal(self.pose, AuditLog.Action.UPDATE).last()
        diff = {c['field']: (c['old'], c['new']) for c in ligne.changes}
        self.assertEqual(diff['atteint'], ('True', 'False'))

    def test_cle_phase_et_chantier_non_modifiables(self):
        res = self.api.patch(f'{RACINE}{self.pose.id}/', {
            'cle_phase': 'autre', 'chantier_id': 999999,
        }, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        self.pose.refresh_from_db()
        self.assertEqual(self.pose.cle_phase, 'pose')
        self.assertEqual(self.pose.chantier_id, self.chantier.id)

    def test_synchro_apres_correction_une_seule_ligne(self):
        self.api.patch(f'{RACINE}{self.pose.id}/', {
            'libelle': 'Pose des panneaux'}, format='json')
        upsert_jalon_chantier(
            self.co, self.chantier.id, 'pose', 'Pose', atteint=True)
        self.assertEqual(JalonChantierPortail.objects.filter(
            chantier_id=self.chantier.id, cle_phase='pose').count(), 1)
        # Aucune création manuelle possible ⇒ pas de doublon « Installation ».
        self.api.post(RACINE, {
            'chantier_id': self.chantier.id, 'libelle': 'Pose'},
            format='json')
        self.assertEqual(JalonChantierPortail.objects.filter(
            chantier_id=self.chantier.id).count(), 2)

    def test_suppression_jalon_synchronise_refusee(self):
        res = self.api.delete(f'{RACINE}{self.pose.id}/')
        self.assertEqual(res.status_code, 409, res.content)
        self.assertEqual(res.json()['detail'],
                         'jalon issu du chantier : corrigez-le')
        self.assertTrue(JalonChantierPortail.objects.filter(
            pk=self.pose.id).exists())
        res = self.api.delete(f'{RACINE}{self.herite.id}/')
        self.assertEqual(res.status_code, 204, res.content)
        self.assertFalse(JalonChantierPortail.objects.filter(
            pk=self.herite.id).exists())
