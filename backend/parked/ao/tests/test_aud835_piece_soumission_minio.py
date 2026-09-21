"""AUD835 — la pièce d'un dossier de soumission va dans MinIO, pas sur le disque.

ROUGE D'ABORD (structurel, vérifié ici) : ce dépôt ne peut PAS resservir un
``FileField``. Aucun ``MEDIA_ROOT``/``MEDIA_URL`` exploitable dans les settings,
aucune route ``/media/`` dans ``erp_agentique/urls.py``, aucune ``location
/media/`` côté nginx — l'URL d'un ``FileField`` ne résolvait donc jamais : le
document déposé n'était récupérable par PERSONNE en production.

VERT : la pièce porte une clé MinIO préfixée par sa société (SCA42) et le
sérialiseur rend une URL présignée ; une ligne historique sans clé rend
``None``, jamais une URL morte.

Run :
    docker compose exec django_core python manage.py test \
        apps.ao.tests.test_aud835_piece_soumission_minio -v 2
"""
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import Resolver404, resolve

from apps.ao.models import AppelOffre, DossierSoumission, PieceSoumission
from apps.ao.serializers import PieceSoumissionSerializer
from authentication.models import Company

User = get_user_model()

PDF = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'


def fichier(nom='attestation.pdf'):
    return SimpleUploadedFile(nom, PDF, content_type='application/pdf')


class MediaJamaisServiTests(TestCase):
    """Le ROUGE : rien dans ce dépôt ne peut resservir un ``FileField``."""

    def test_aucune_route_media(self):
        with self.assertRaises(Resolver404):
            resolve('/media/compta/soumissions/attestation.pdf')

    def test_aucun_reglage_de_stockage_de_medias(self):
        self.assertFalse(getattr(settings, 'MEDIA_ROOT', '') or '')


class PieceSoumissionVersMinioTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='aud835-ao-co', defaults={'nom': 'AUD835 AO'})[0]
        self.user = User.objects.create_user(
            username='aud835-ao', password='x', company=self.co,
            role_legacy='responsable')
        self.appel = AppelOffre.objects.create(
            company=self.co, reference='AO-AUD835', objet='Centrale PV')
        self.dossier = DossierSoumission.objects.create(
            company=self.co, appel_offre=self.appel)

    def _meta(self):
        return ({
            'file_key': f'attachments/{self.co.id}/ao835.pdf',
            'filename': 'attestation.pdf', 'size': len(PDF),
            'mime': 'application/pdf',
        }, None)

    def _creer(self):
        serializer = PieceSoumissionSerializer(data={
            'dossier': self.dossier.pk, 'libelle': 'Attestation fiscale',
            'fichier': fichier(),
        })
        serializer.is_valid(raise_exception=True)
        return serializer.save(company=self.co)

    def test_la_piece_porte_une_cle_minio_scopee_societe(self):
        with mock.patch('apps.records.storage.store_attachment',
                        return_value=self._meta()) as stocke:
            piece = self._creer()

        self.assertEqual(stocke.call_args.kwargs['company'], self.co)
        piece.refresh_from_db()
        self.assertEqual(piece.fichier_key,
                         f'attachments/{self.co.id}/ao835.pdf')
        self.assertEqual(piece.fichier_filename, 'attestation.pdf')
        self.assertEqual(piece.fichier_mime, 'application/pdf')
        self.assertEqual(piece.fichier_size, len(PDF))
        # Plus rien n'est écrit dans le FileField legacy.
        self.assertFalse(piece.fichier)

    def test_url_serialisee_est_une_url_presignee(self):
        with mock.patch('apps.records.storage.store_attachment',
                        return_value=self._meta()):
            piece = self._creer()

        with mock.patch('apps.records.storage.presign_attachment',
                        return_value='https://minio/x?sig=1') as presigne:
            data = PieceSoumissionSerializer(piece).data

        presigne.assert_called_once_with(f'attachments/{self.co.id}/ao835.pdf')
        self.assertEqual(data['fichier_url'], 'https://minio/x?sig=1')
        # L'entrée d'upload n'est jamais rendue (aucune URL morte publiée).
        self.assertNotIn('fichier', data)

    def test_ligne_historique_sans_cle_rend_none(self):
        legacy = PieceSoumission.objects.create(
            company=self.co, dossier=self.dossier, libelle='Vieille pièce',
            fichier='compta/soumissions/vieux.pdf')
        self.assertIsNone(PieceSoumissionSerializer(legacy).data['fichier_url'])

    def test_format_refuse_ne_cree_aucune_piece(self):
        from rest_framework.exceptions import ValidationError

        with mock.patch('apps.records.storage.store_attachment',
                        return_value=(None, 'Format non supporté.')):
            with self.assertRaises(ValidationError):
                self._creer()
        self.assertEqual(PieceSoumission.objects.count(), 0)
