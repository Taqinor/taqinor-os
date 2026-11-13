"""ADOC29 — un document détruit emporte son binaire du stockage objet.

Constat #52 de l'audit documents (2026-10-05) : ni la purge définitive ni la
disposition « détruire » n'appelaient records.storage.delete_attachment —
le fichier restait dans MinIO après le certificat de destruction.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.ged import services
from apps.ged.models import (
    Cabinet, CertificatDestruction, Document, DocumentVersion, Folder,
    PolitiqueRetention,
)
from authentication.models import Company

User = get_user_model()


class PurgeMinioTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc29', defaults={'nom': 'ADOC29'})[0]
        self.admin = User.objects.create_user(
            username='adoc29-admin', password='x', company=self.co,
            role_legacy='admin')
        self.admin2 = User.objects.create_user(
            username='adoc29-admin2', password='x', company=self.co,
            role_legacy='admin')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=cab, nom='R')

    def _doc(self, nom, *cles):
        doc = Document.objects.create(company=self.co, folder=self.folder,
                                      nom=nom)
        for i, cle in enumerate(cles, start=1):
            DocumentVersion.objects.create(
                company=self.co, document=doc, version=i, file_key=cle)
        return doc

    def test_purge_supprime_binaire(self):
        doc = self._doc('D', 'attachments/k.pdf')
        services.mettre_en_corbeille(doc, self.admin)
        with mock.patch('apps.records.storage.delete_attachment') as efface:
            services.purger_definitivement(doc)
        efface.assert_called_once_with('attachments/k.pdf', lever=True)
        self.assertFalse(Document.objects.filter(pk=doc.pk).exists())

    def test_cle_partagee_conservee(self):
        doc = self._doc('D', 'attachments/k.pdf', 'attachments/shared.pdf')
        autre = self._doc('Autre', 'attachments/shared.pdf')
        services.mettre_en_corbeille(doc, self.admin)
        with mock.patch('apps.records.storage.delete_attachment') as efface:
            services.purger_definitivement(doc)
        cles = [appel.args[0] for appel in efface.call_args_list]
        self.assertEqual(cles, ['attachments/k.pdf'])
        self.assertTrue(DocumentVersion.objects.filter(
            document=autre, file_key='attachments/shared.pdf').exists())

    def test_echec_stockage_laisse_le_document(self):
        doc = self._doc('D', 'attachments/k.pdf')
        # delete() remet `doc.pk` à None en mémoire même si la transaction
        # est annulée : on garde l'id pour relire la base.
        doc_id = doc.pk
        services.mettre_en_corbeille(doc, self.admin)
        # ADOC189 (sonde C-ADOC-VER-031) — seul le client MinIO est simulé :
        # c'est `delete_attachment` RÉEL qui doit faire remonter l'échec.
        with mock.patch('apps.records.storage.get_minio_client',
                        return_value=self._client_en_panne()):
            with self.assertRaises(RuntimeError):
                services.purger_definitivement(doc)
        self.assertTrue(Document.objects.filter(pk=doc_id).exists())
        self.assertEqual(
            DocumentVersion.objects.filter(document_id=doc_id).count(), 1)

    @staticmethod
    def _client_en_panne():
        client = mock.Mock()
        client.delete_object.side_effect = RuntimeError('minio indisponible')
        return client

    def test_echec_stockage_annule_la_disposition(self):
        """ADOC189 — disposition « détruire », MinIO en panne : document et
        version conservés, aucun certificat, demande non exécutée."""
        PolitiqueRetention.objects.create(
            company=self.co, nom='Globale', duree_conservation_jours=30)
        doc = self._doc('Vieux', 'attachments/vieux.pdf')
        Document.objects.filter(pk=doc.pk).update(
            created_at=timezone.now() - timedelta(days=400))
        demande = services.creer_demande_disposition(
            self.co, libelle='Purge', document_ids=[doc.pk], user=self.admin)
        services.approuver_demande_disposition(demande, user=self.admin2)
        with mock.patch('apps.records.storage.get_minio_client',
                        return_value=self._client_en_panne()):
            with self.assertRaises(RuntimeError):
                services.executer_demande_disposition(demande, user=self.admin2)
        self.assertTrue(Document.objects.filter(pk=doc.pk).exists())
        self.assertEqual(
            DocumentVersion.objects.filter(document_id=doc.pk).count(), 1)
        self.assertEqual(CertificatDestruction.objects.count(), 0)
        demande.refresh_from_db()
        self.assertNotEqual(demande.statut, 'executee')

    def test_disposition_supprime_binaire(self):
        PolitiqueRetention.objects.create(
            company=self.co, nom='Globale', duree_conservation_jours=30)
        doc = self._doc('Vieux', 'attachments/vieux.pdf')
        Document.objects.filter(pk=doc.pk).update(
            created_at=timezone.now() - timedelta(days=400))
        demande = services.creer_demande_disposition(
            self.co, libelle='Purge', document_ids=[doc.pk], user=self.admin)
        services.approuver_demande_disposition(demande, user=self.admin2)
        with mock.patch('apps.records.storage.delete_attachment') as efface:
            certificats = services.executer_demande_disposition(
                demande, user=self.admin2)
        efface.assert_called_once_with('attachments/vieux.pdf', lever=True)
        self.assertEqual(len(certificats), 1)
        self.assertEqual(CertificatDestruction.objects.count(), 1)

    def test_cle_tenue_par_piece_jointe_conservee(self):
        """ADOC192 (C-ADOC-VER4-010) — un document importé d'une pièce jointe
        (clé K partagée) est purgé sans effacer K ; un document natif garde
        son effacement. L'import marque la source partagée."""
        from django.contrib.contenttypes.models import ContentType
        from apps.ged.management.commands.migrate_attachments_to_ged import (
            import_attachments,
        )
        from apps.records.models import Attachment
        att = Attachment.objects.create(
            company=self.co, object_id=self.folder.pk,
            content_type=ContentType.objects.get_for_model(Folder),
            uploaded_by=self.admin, file_key='attachments/K.pdf',
            filename='K.pdf', size=1, mime='application/pdf')
        import_attachments(company=self.co)
        import_attachments(company=self.co)  # ré-import : aucun doublon
        version = DocumentVersion.objects.get(file_key='attachments/K.pdf')
        doc = version.document
        self.assertEqual(doc.custom_data['source_partagee'],
                         f'records.Attachment:{att.pk}')
        natif = self._doc('Natif', 'attachments/natif.pdf')
        self.assertEqual(services._cles_binaires_exclusives(doc), [])
        client = mock.Mock()
        with mock.patch('apps.records.storage.get_minio_client',
                        return_value=client):
            for d in (doc, natif):
                services.mettre_en_corbeille(d, self.admin)
                services.purger_definitivement(d)
        self.assertEqual(
            [c.kwargs['Key'] for c in client.delete_object.call_args_list],
            ['attachments/natif.pdf'])
        self.assertTrue(Attachment.objects.filter(pk=att.pk).exists())

    def test_piece_jointe_purgee_jamais_reimportee(self):
        """ACEL61 (C-ACEL-002) — importée puis purgée ⇒ jamais réimportée ;
        cible autorisée à la corbeille ⇒ sautée ; l'original reste intact."""
        from django.contrib.contenttypes.models import ContentType
        from apps.crm.models import Lead
        from apps.ged.management.commands.migrate_attachments_to_ged import (
            import_attachments,
        )
        from apps.records.models import Attachment
        att = Attachment.objects.create(
            company=self.co, object_id=self.folder.pk,
            content_type=ContentType.objects.get_for_model(Folder),
            uploaded_by=self.admin, file_key='attachments/P.pdf',
            filename='P.pdf', size=1, mime='application/pdf')
        import_attachments(company=self.co)
        doc = DocumentVersion.objects.get(file_key='attachments/P.pdf').document
        with mock.patch('apps.records.storage.get_minio_client'):
            services.mettre_en_corbeille(doc, self.admin)
            services.purger_definitivement(doc)
        lead = Lead.objects.create(company=self.co, nom='Corbeille')
        Attachment.objects.create(
            company=self.co, object_id=lead.pk,
            content_type=ContentType.objects.get_for_model(Lead),
            uploaded_by=self.admin, file_key='attachments/L.pdf',
            filename='L.pdf', size=1, mime='application/pdf')
        lead.soft_delete(self.admin)
        for _ in range(2):  # le marqueur est relu en base au 3e import
            compteurs = import_attachments(company=self.co)
            self.assertEqual(compteurs['skipped'], 2)
            self.assertEqual(compteurs['documents'], 0)
        self.assertFalse(Document.objects.filter(
            versions__file_key__in=['attachments/P.pdf', 'attachments/L.pdf']).exists())
        self.assertFalse(DocumentVersion.objects.filter(
            file_key__in=['attachments/P.pdf', 'attachments/L.pdf']).exists())
        self.assertTrue(Attachment.objects.filter(pk=att.pk, file_key='attachments/P.pdf').exists())
