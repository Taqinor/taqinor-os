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


class CleLibereeParLaLigneTests(TestCase):
    """ADOC200 (C-ADOC-VER4-010) — la photo supprimée libère sa clé
    (``liberee_par``) : son binaire part ; une photo importée en créatif
    garde le sien. Seul le client MinIO est simulé (frontière externe) :
    ``delete_attachment`` est RÉEL ici."""

    _iv = SuppressionPreuvesTests._iv
    _photo = SuppressionPreuvesTests._photo

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-adoc200', defaults={'nom': 'Co ADOC200'})
        self.user = User.objects.create_user(
            username='resp-adoc200', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        inst = Installation.objects.create(
            company=self.company, reference='CH-ADOC200')
        self.validee = self._iv(inst, Intervention.Statut.VALIDEE)
        self.en_cours = self._iv(inst, Intervention.Statut.SUR_SITE)

    def test_photo_importee_en_creatif_conservee(self):
        from apps.adsengine.models import CreativeAsset
        p, q = self._photo(self.en_cours), self._photo(self.validee)
        Attachment.objects.filter(pk=q.pk).update(file_key='k/creatif')
        CreativeAsset.objects.create(
            company=self.company, asset_type='static', file_key='k/creatif')
        client = mock.MagicMock()
        with mock.patch('apps.records.storage.get_minio_client',
                        return_value=client):
            for iv, photo in ((self.en_cours, p), (self.validee, q)):
                r = self.api.post(
                    f'{BASE}/{iv.id}/supprimer-photo/',
                    {'photo': photo.id, 'motif': 'doublon'}, format='json')
                self.assertEqual(r.status_code, 204, r.data)
        self.assertFalse(Attachment.objects.filter(
            pk__in=(p.pk, q.pk)).exists())
        self.assertEqual(
            [c.kwargs['Key'] for c in client.delete_object.call_args_list],
            [p.file_key])
        self.assertTrue(CreativeAsset.objects.filter(
            file_key='k/creatif').exists())

    def test_photo_checklist_supprimee_decoche_et_trace(self):
        """ACSV18 (C-ACSV-023) — supprimer l'unique photo d'une étape à photo
        obligatoire cochée la décoche (gate photos la redemande) et le note au
        chatter ; avec une seconde photo restante : cochée, note seule.
        ROUGE AVANT : `fait` vrai, 0 note."""
        from django.utils import timezone

        from apps.installations.models import (
            ChantierChecklistItem, InstallationActivity, PhotoChecklistMeta,
        )
        from apps.installations.services import raison_refus_cocher_etape
        admin = User.objects.create_user(
            username='admin-acsv18', password='x', company=self.company,
            role_legacy='admin')
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(admin)}')
        inst = Installation.objects.create(company=self.company, reference='CH-ACSV18')
        item = ChantierChecklistItem.objects.create(
            company=self.company, installation=inst, cle='tableau',
            libelle='Photo du tableau', photo_obligatoire=True, fait=True,
            fait_par=self.user, fait_le=timezone.now())
        ct = ContentType.objects.get_for_model(Installation)

        def photo(n):
            att = Attachment.objects.create(
                company=self.company, content_type=ct, object_id=inst.id,
                file_key=f'k/acsv18-{n}', filename=f'tableau-{n}.png',
                uploaded_by=self.user)
            PhotoChecklistMeta.objects.create(
                company=self.company, attachment=att, checklist_item=item)
            return att

        def notes():
            return list(InstallationActivity.objects.filter(
                installation=inst, body__startswith="Photo de l'étape").values_list('body', flat=True))

        p1, p2 = photo(1), photo(2)
        with mock.patch('apps.records.views.delete_attachment'):
            r = api.delete(f'/api/django/records/attachments/{p1.id}/')
            self.assertEqual(r.status_code, 204, getattr(r, 'data', r))
            item.refresh_from_db()
            self.assertTrue(item.fait)
            self.assertEqual(notes(), ["Photo de l'étape « Photo du tableau » supprimée."])
            r = api.delete(f'/api/django/records/attachments/{p2.id}/')
            self.assertEqual(r.status_code, 204, getattr(r, 'data', r))
        item.refresh_from_db()
        self.assertFalse(item.fait)
        self.assertIsNone(item.fait_par)
        self.assertIsNone(item.fait_le)
        self.assertIn("Photo de l'étape « Photo du tableau » supprimée — étape décochée "
                      '(aucune photo restante).', notes())
        self.assertIsNotNone(raison_refus_cocher_etape(item, True))
