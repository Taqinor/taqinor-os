"""ACHT41 (C-ACHT-040) — chaque suppression de pièce de preuve d'une
intervention (photo, série, mémo, ligne de consommation) est tracée au
chatter et refusée (409) sans `motif` sur une intervention terminée/validée.

Rejoue CINT-15 : `supprimer-photo` sur une validée -> 204, objet stocké
supprimé, 0 ligne d'historique.

Seule la suppression de l'objet stocké (MinIO) est remplacée par un faux :
frontière externe.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht41_suppression_preuves"
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import (
    ComponentSerial, ConsommationLigne, Installation, Intervention,
    InterventionActivity, MaterielConsommation, VoiceMemo,
)
from apps.records.models import Attachment

User = get_user_model()
BASE = '/api/django/installations/interventions'
MSG = 'Intervention terminée : indiquez le motif de la suppression'


class SuppressionPreuvesTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht41', defaults={'nom': 'Co ACHT41'})
        self.user = User.objects.create_user(
            username='resp-acht41', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT41')
        self.validee = self._iv(inst, Intervention.Statut.VALIDEE)
        self.en_cours = self._iv(inst, Intervention.Statut.SUR_SITE)
        patch = mock.patch('apps.records.storage.delete_attachment')
        self.delete_mock = patch.start()
        self.addCleanup(patch.stop)

    def _iv(self, inst, statut):
        return Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', created_by=self.user,
            technicien=self.user, statut=statut)

    def _photo(self, iv):
        ct = ContentType.objects.get_for_model(Intervention)
        return Attachment.objects.create(
            company=self.company, content_type=ct, object_id=iv.id,
            file_key=f'k/{iv.id}', filename='slot:facade|p.png',
            uploaded_by=self.user)

    def _historique(self, iv):
        return list(InterventionActivity.objects.filter(
            intervention=iv, kind='note').values_list('body', flat=True))

    def test_photo_validee_sans_motif_refusee(self):
        photo = self._photo(self.validee)
        r = self.api.post(f'{BASE}/{self.validee.id}/supprimer-photo/',
                          {'photo': photo.id}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn(MSG, str(r.data))
        self.assertTrue(Attachment.objects.filter(pk=photo.pk).exists())
        self.assertFalse(self.delete_mock.called)

    def test_photo_supprimee_tracee(self):
        photo = self._photo(self.validee)
        r = self.api.post(f'{BASE}/{self.validee.id}/supprimer-photo/',
                          {'photo': photo.id, 'motif': 'photo floue'},
                          format='json')
        self.assertEqual(r.status_code, 204)
        self.assertFalse(Attachment.objects.filter(pk=photo.pk).exists())
        lignes = self._historique(self.validee)
        self.assertTrue(any(
            'Photo supprimée — facade' in b
            and 'motif : photo floue' in b and 'resp-acht41' in b
            for b in lignes), lignes)
        # En cours : pas de motif exigé, mais tracé.
        photo2 = self._photo(self.en_cours)
        r = self.api.post(f'{BASE}/{self.en_cours.id}/supprimer-photo/',
                          {'photo': photo2.id}, format='json')
        self.assertEqual(r.status_code, 204)
        self.assertTrue(any('Photo supprimée' in b
                            for b in self._historique(self.en_cours)))

    def test_serial_memo_ligne_tracees(self):
        serial = ComponentSerial.objects.create(
            company=self.company, intervention=self.validee,
            numero_serie='SN-41', created_by=self.user)
        memo = VoiceMemo.objects.create(
            company=self.company, intervention=self.validee,
            created_by=self.user)
        cons = MaterielConsommation.objects.create(
            company=self.company, intervention=self.validee)
        ligne = ConsommationLigne.objects.create(
            company=self.company, consommation=cons, designation='Vis',
            quantite_utilisee=Decimal('3'), hors_nomenclature=True)
        # Sans motif : 409 (série et mémo ; la ligne est d'abord refusée en 400
        # par la garde de réconciliation si elle est validée).
        r = self.api.post(f'{BASE}/{self.validee.id}/supprimer-serial/',
                          {'serial': serial.id}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        r = self.api.post(f'{BASE}/{self.validee.id}/supprimer-memo/',
                          {'memo': memo.id}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        r = self.api.post(
            f'{BASE}/{self.validee.id}/supprimer-ligne-consommation/',
            {'ligne': ligne.id}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        # Avec motif : 204 + trace.
        for url, corps in (
                ('supprimer-serial', {'serial': serial.id}),
                ('supprimer-memo', {'memo': memo.id}),
                ('supprimer-ligne-consommation', {'ligne': ligne.id})):
            corps['motif'] = 'erreur de saisie'
            r = self.api.post(f'{BASE}/{self.validee.id}/{url}/', corps,
                              format='json')
            self.assertEqual(r.status_code, 204, (url, r.data))
        lignes = ' | '.join(self._historique(self.validee))
        for attendu in ('N° de série SN-41 supprimé', 'Mémo vocal supprimé',
                        'Ligne de consommation Vis supprimée'):
            self.assertIn(attendu, lignes)
