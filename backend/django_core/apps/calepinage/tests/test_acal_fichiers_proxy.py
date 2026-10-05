"""ACAL200 — photos, plan importé et aperçu servis par un proxy Django.

Le navigateur ne lit JAMAIS MinIO : ``url`` est un chemin relatif même
origine, les octets sont lus par le serveur dans LE BON bucket (résolu par le
préfixe de la clé de la pièce), et le document as-built incorpore les octets.
Les deux lecteurs de stockage sont remplacés à leur frontière
(``lire_fichier_toiture`` = bucket PDF, ``fetch_attachment`` = bucket des
téléversements) : ce que l'on prouve ici est le ROUTAGE par préfixe et le
périmètre société.

Run ::

    python manage.py test apps.calepinage.tests.test_acal_fichiers_proxy -v 2
"""
from __future__ import annotations

import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage, PhotoSite, ProvenanceTerrain
from apps.calepinage.services.photos import ajouter_photo_site, photo_en_ligne
from apps.crm.models import Lead
from apps.records.models import Attachment
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company

User = get_user_model()

PNG_PDF = (b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR'
           + b'\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00'
           + b'BUCKET-PDF')
PNG_UPLOADS = (b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR'
               + b'\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00'
               + b'BUCKET-UPLOADS')
HIER = datetime.date.today() - datetime.timedelta(days=1)


def _lire_pdf(cle):
    """Le bucket PDF : ne connaît QUE les clés ``roofs/…``."""
    return PNG_PDF if str(cle).startswith('roofs/') else None


def _fetch_uploads(cle):
    """Le bucket des téléversements : ne connaît QUE ``attachments/…``."""
    if str(cle).startswith('attachments/'):
        return PNG_UPLOADS, None
    return None, 'Fichier introuvable.'


class BaseFichiers(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='Fichiers Co',
                                              slug='fichiers-co-200')
        self.autre = Company.objects.create(nom='Voisine Fichiers',
                                            slug='voisine-fichiers-200')
        role = Role.objects.create(company=self.company, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='acal200', password='x', company=self.company,
            role=role)
        lead = Lead.objects.create(company=self.company, nom='Toit Anfa')
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=lead.pk, titre='Toit Anfa')
        self.autre_calepinage = Calepinage.objects.create(
            company=self.company, lead_id=lead.pk, titre='Autre toit')

        mock.patch('apps.ventes.services.stocker_image_toiture').start()
        mock.patch('apps.ventes.services.lire_fichier_toiture',
                   side_effect=_lire_pdf).start()
        mock.patch('apps.records.storage.fetch_attachment',
                   side_effect=_fetch_uploads).start()
        self.addCleanup(mock.patch.stopall)

        # Une photo DÉPOSÉE dans le module (clé roofs/…, bucket PDF).
        self.photo_module = ajouter_photo_site(
            self.calepinage,
            SimpleUploadedFile('vol.png', PNG_PDF, content_type='image/png'),
            prise_le=HIER, user=self.user)
        # Une photo REPRISE d'une visite : l'Attachment de la visite
        # (clé attachments/…, bucket des téléversements).
        piece = Attachment.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=self.calepinage.pk,
            file_key=f'attachments/{self.company.pk}/visite-abc.png',
            filename='visite.png', size=len(PNG_UPLOADS), mime='image/png')
        self.photo_reprise = PhotoSite.objects.create(
            company=self.company, calepinage=self.calepinage,
            attachment=piece, genre=PhotoSite.Genre.SOL, prise_le=HIER,
            provenance=ProvenanceTerrain.VISITE)

    def _api(self, user=None):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(user or self.user)}'))
        return api

    def _url(self, photo, calepinage=None):
        calepinage = calepinage or self.calepinage
        return (f'/api/django/calepinage/calepinages/{calepinage.pk}'
                f'/photos/{photo.pk}/fichier/')


class UrlRelativeTest(BaseFichiers):

    def test_photo_url_est_un_chemin_relatif(self):
        for photo in (self.photo_module, self.photo_reprise):
            url = photo_en_ligne(photo)['url']
            self.assertEqual(url, self._url(photo))
            self.assertNotIn('minio', url)
            self.assertFalse(url.startswith('http'))

    def test_la_liste_sert_le_chemin_relatif(self):
        reponse = self._api().get(
            f'/api/django/calepinage/calepinages/{self.calepinage.pk}'
            '/photos/')
        self.assertEqual(reponse.status_code, 200)
        for ligne in reponse.data['photos']:
            self.assertTrue(ligne['url'].startswith(
                '/api/django/calepinage/calepinages/'), ligne['url'])


class FichierPhotoTest(BaseFichiers):

    def test_fichier_photo_module_et_photo_reprise_rendent_les_octets(self):
        api = self._api()
        module = api.get(self._url(self.photo_module))
        self.assertEqual(module.status_code, 200)
        self.assertEqual(module['Content-Type'], 'image/png')
        self.assertEqual(module.content, PNG_PDF)
        reprise = api.get(self._url(self.photo_reprise))
        self.assertEqual(reprise.status_code, 200)
        self.assertEqual(reprise['Content-Type'], 'image/png')
        self.assertEqual(reprise.content, PNG_UPLOADS)

    def test_photo_autre_societe_404(self):
        role = Role.objects.create(company=self.autre, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        voisin = User.objects.create_user(
            username='acal200_voisin', password='x', company=self.autre,
            role=role)
        reponse = self._api(voisin).get(self._url(self.photo_module))
        self.assertEqual(reponse.status_code, 404)

    def test_photo_d_un_autre_calepinage_404(self):
        reponse = self._api().get(
            self._url(self.photo_module, calepinage=self.autre_calepinage))
        self.assertEqual(reponse.status_code, 404)

    def test_photo_absente_404(self):
        reponse = self._api().get(
            f'/api/django/calepinage/calepinages/{self.calepinage.pk}'
            '/photos/999999/fichier/')
        self.assertEqual(reponse.status_code, 404)


class AsBuiltTest(BaseFichiers):

    def test_asbuilt_incorpore_les_octets_de_la_photo_reprise(self):
        import base64

        from apps.calepinage.services.documents.document_asbuilt import (
            html_du_document_asbuilt,
        )

        html = html_du_document_asbuilt(self.calepinage, svg_planche='')
        attendu = 'data:image/png;base64,%s' % base64.b64encode(
            PNG_UPLOADS).decode('ascii')
        self.assertIn(attendu, html)
        self.assertNotIn('Image indisponible', html)
        self.assertNotIn('/photos/', html)
