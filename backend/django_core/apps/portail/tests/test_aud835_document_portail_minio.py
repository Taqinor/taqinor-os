"""AUD835 — le document déposé par le client au portail va dans MinIO.

Le ``FileField`` historique écrivait sur le disque du conteneur, sans
``MEDIA_ROOT`` exploitable, sans route ``/media/``, sans ``location /media/``
nginx (ROUGE structurel vérifié ici). Le dépôt GED canonique (WIR94) lisait,
lui, les octets ENCORE EN MÉMOIRE au ``pre_save`` : router l'upload vers MinIO
sans toucher au récepteur aurait fait disparaître ce dépôt EN SILENCE — d'où
le second volet de ce test.

VERT : clé MinIO préfixée par la société, ``fichier_present`` vrai depuis la
clé, et le dépôt GED relit les octets par la clé.

Run :
    docker compose exec django_core python manage.py test \
        apps.portail.tests.test_aud835_document_portail_minio -v 2
"""
from unittest import mock

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import Resolver404, resolve

from apps.compta.serializers import DocumentClientPortailSerializer
from apps.portail.models import DocumentClientPortail
from authentication.models import Company

PDF = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'


class MediaJamaisServiTests(TestCase):
    def test_aucune_route_media(self):
        with self.assertRaises(Resolver404):
            resolve('/media/compta/portail_docs/facture.pdf')

    def test_aucun_reglage_de_stockage_de_medias(self):
        self.assertFalse(getattr(settings, 'MEDIA_ROOT', '') or '')


class DocumentPortailVersMinioTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='aud835-portail-co', defaults={'nom': 'AUD835 Portail'})[0]

    def _meta(self):
        return ({
            'file_key': f'attachments/{self.co.id}/portail835.pdf',
            'filename': 'facture.pdf', 'size': len(PDF),
            'mime': 'application/pdf',
        }, None)

    def _creer(self):
        serializer = DocumentClientPortailSerializer(data={
            'client_id': 0, 'type_document': 'facture_onee',
            'libelle': 'Facture ONEE janvier',
            'fichier': SimpleUploadedFile('facture.pdf', PDF,
                                          'application/pdf'),
        })
        serializer.is_valid(raise_exception=True)
        return serializer.save(company=self.co)

    def test_le_document_porte_une_cle_minio_scopee_societe(self):
        with mock.patch('apps.records.storage.store_attachment',
                        return_value=self._meta()) as stocke:
            # Le dépôt GED (WIR94) est testé séparément ci-dessous : ici on
            # neutralise la relecture MinIO pour ne mesurer que le stockage.
            with mock.patch('apps.records.storage.fetch_attachment',
                            return_value=(None, 'Fichier introuvable.')):
                doc = self._creer()

        self.assertEqual(stocke.call_args.kwargs['company'], self.co)
        doc.refresh_from_db()
        self.assertEqual(doc.fichier_key,
                         f'attachments/{self.co.id}/portail835.pdf')
        self.assertEqual(doc.fichier_filename, 'facture.pdf')
        self.assertEqual(doc.fichier_mime, 'application/pdf')
        self.assertFalse(doc.fichier)

    def test_fichier_present_reste_vrai_depuis_la_cle(self):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(None, 'Fichier introuvable.')):
            doc = DocumentClientPortail.objects.create(
                company=self.co, libelle='Déposé',
                fichier_key=f'attachments/{self.co.id}/portail835.pdf',
                fichier_filename='facture.pdf', fichier_mime='application/pdf',
                fichier_size=len(PDF))
        data = DocumentClientPortailSerializer(doc).data
        self.assertTrue(data['fichier_present'])
        self.assertNotIn('fichier', data)

    def test_le_depot_ged_relit_les_octets_par_la_cle(self):
        """WIR94 conservé : sans ce raccord, le dépôt GED disparaissait."""
        cle = f'attachments/{self.co.id}/portail835.pdf'
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(PDF, None)) as relit:
            with mock.patch('apps.ged.services.deposit_document') as depose:
                depose.return_value = (mock.Mock(pk=4242), True)
                doc = DocumentClientPortail.objects.create(
                    company=self.co, libelle='Facture ONEE',
                    fichier_key=cle, fichier_filename='facture.pdf',
                    fichier_mime='application/pdf', fichier_size=len(PDF))

        relit.assert_called_once_with(cle)
        kwargs = depose.call_args.kwargs
        self.assertEqual(kwargs['company'], self.co)
        self.assertEqual(kwargs['source_type'],
                         'portail.documentclientportail')
        self.assertEqual(kwargs['contenu_bytes'], PDF)
        self.assertEqual(kwargs['mime'], 'application/pdf')
        doc.refresh_from_db()
        self.assertEqual(doc.document_ged_id, 4242)

    def test_sans_cle_ni_fichier_aucun_depot_ged(self):
        with mock.patch('apps.ged.services.deposit_document') as depose:
            DocumentClientPortail.objects.create(
                company=self.co, libelle='Sans fichier')
        self.assertFalse(depose.called)
