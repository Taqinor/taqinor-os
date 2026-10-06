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
        efface.assert_called_once_with('attachments/k.pdf')
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
        with mock.patch('apps.records.storage.delete_attachment',
                        side_effect=RuntimeError('minio indisponible')):
            with self.assertRaises(RuntimeError):
                services.purger_definitivement(doc)
        self.assertTrue(Document.objects.filter(pk=doc_id).exists())
        self.assertEqual(
            DocumentVersion.objects.filter(document_id=doc_id).count(), 1)

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
        efface.assert_called_once_with('attachments/vieux.pdf')
        self.assertEqual(len(certificats), 1)
        self.assertEqual(CertificatDestruction.objects.count(), 1)
