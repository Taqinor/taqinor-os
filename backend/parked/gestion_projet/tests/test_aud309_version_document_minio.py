"""AUD309 — le fichier d'une `VersionDocument` va dans MinIO, pas sur le disque.

Défaut : `VersionDocument.fichier` était un `FileField` Django ordinaire qui
contournait `records.storage.store_attachment`. Or le dépôt n'a AUCUNE
plomberie de service de médias — pas de `MEDIA_URL`/`MEDIA_ROOT`/`STORAGES`
dans les settings, pas de route `/media/` dans `erp_agentique/urls.py`, pas de
`location /media/` côté nginx : l'URL sérialisée ne résolvait donc jamais. Le
fichier n'était pas perdu pour autant — le bind-mount `./backend/django_core`
l'écrivait sur le disque HÔTE, où il s'accumulait non tracké et inaccessible à
l'application.

Rouge d'abord (structurel, vérifiable ici) : rien ne sert `/media/…`, et une
version déposée par l'ancien chemin n'expose aucune URL exploitable. Vert :
la version porte une clé MinIO préfixée par sa société et le sérialiseur rend
une URL présignée.

Run :
    docker compose exec django_core python manage.py test \
        apps.gestion_projet.tests.test_aud309_version_document_minio -v 2
"""
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import Resolver404, resolve
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.gestion_projet import services
from apps.gestion_projet.models import DocumentProjet, Projet, VersionDocument
from apps.gestion_projet.serializers import VersionDocumentSerializer
from authentication.models import Company

User = get_user_model()

PDF = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'


def _fichier(nom='plan.pdf'):
    return SimpleUploadedFile(nom, PDF, content_type='application/pdf')


class MediaJamaisServiTests(TestCase):
    """Le ROUGE : rien dans ce dépôt ne peut resservir un `FileField`."""

    def test_aucune_route_media(self):
        with self.assertRaises(Resolver404):
            resolve('/media/gestion_projet/documents/plan.pdf')

    def test_aucun_reglage_de_stockage_de_medias(self):
        # `MEDIA_ROOT` vide + `MEDIA_URL` non routée = un FileField écrit sur le
        # disque du conteneur (bind-mounté sur l'hôte) et jamais resservi.
        self.assertFalse(getattr(settings, 'MEDIA_ROOT', '') or '')


class DepotVersMinioTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='aud309-co', defaults={'nom': 'AUD309 Co'})[0]
        self.user = User.objects.create_user(
            username='aud309', password='x', company=self.co,
            role_legacy='responsable')
        self.projet = Projet.objects.create(
            company=self.co, code='P-AUD309', nom='Projet AUD309')
        self.document = DocumentProjet.objects.create(
            company=self.co, projet=self.projet, nom='Plan toiture')

    def _meta(self):
        return ({
            'file_key': f'attachments/{self.co.id}/abc123.pdf',
            'filename': 'plan.pdf', 'size': len(PDF),
            'mime': 'application/pdf',
        }, None)

    def test_la_version_porte_une_cle_minio_scopee_societe(self):
        with mock.patch('apps.records.storage.store_attachment',
                        return_value=self._meta()) as stocke:
            version = services.deposer_version_document(
                self.document, _fichier(), auteur=self.user)

        # Le fichier est passé par le pipeline MinIO, avec la société.
        self.assertEqual(
            stocke.call_args.kwargs['company'], self.co)
        version.refresh_from_db()
        self.assertEqual(
            version.file_key, f'attachments/{self.co.id}/abc123.pdf')
        self.assertEqual(version.filename, 'plan.pdf')
        self.assertEqual(version.mime, 'application/pdf')
        self.assertEqual(version.size, len(PDF))
        # Plus rien n'est écrit dans le FileField legacy.
        self.assertFalse(version.fichier)

    def test_url_serialisee_est_une_url_presignee(self):
        with mock.patch('apps.records.storage.store_attachment',
                        return_value=self._meta()):
            version = services.deposer_version_document(
                self.document, _fichier(), auteur=self.user)

        with mock.patch('apps.records.storage.presign_attachment',
                        return_value='https://minio/erp-uploads/abc123.pdf?sig=x'
                        ) as presigne:
            data = VersionDocumentSerializer(version).data

        presigne.assert_called_once_with(
            f'attachments/{self.co.id}/abc123.pdf')
        self.assertEqual(
            data['fichier_url'], 'https://minio/erp-uploads/abc123.pdf?sig=x')
        self.assertEqual(
            data['file_key'], f'attachments/{self.co.id}/abc123.pdf')
        # L'ancien champ mort n'est plus exposé du tout.
        self.assertNotIn('fichier', data)

    def test_version_historique_sans_cle_rend_none_jamais_une_url_morte(self):
        legacy = VersionDocument.objects.create(
            company=self.co, document=self.document, version=1,
            fichier='gestion_projet/documents/vieux.pdf')

        data = VersionDocumentSerializer(legacy).data

        self.assertIsNone(data['fichier_url'])
        self.assertEqual(data['file_key'], '')

    def test_format_refuse_ne_cree_aucune_version(self):
        with mock.patch('apps.records.storage.store_attachment',
                        return_value=(None, 'Format non supporté (PDF, PNG, '
                                            'JPEG ou WebP uniquement).')):
            with self.assertRaises(ValidationError):
                services.deposer_version_document(
                    self.document, _fichier('virus.exe'), auteur=self.user)

        self.assertFalse(
            VersionDocument.objects.filter(document=self.document).exists())
        self.document.refresh_from_db()
        self.assertEqual(self.document.derniere_version, 0)

    def test_endpoint_deposer_renvoie_400_sur_format_refuse(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

        with mock.patch('apps.records.storage.store_attachment',
                        return_value=(None, 'Format non supporté.')):
            resp = api.post(
                f'/api/django/gestion-projet/documents/{self.document.id}'
                '/deposer/', {'fichier': _fichier()}, format='multipart')

        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(VersionDocument.objects.exists())
