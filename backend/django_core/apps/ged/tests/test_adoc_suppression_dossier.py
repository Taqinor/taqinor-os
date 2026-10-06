"""ADOC2 — plus aucune cascade ne détruit un document archivé ou sous hold.

Rejoue la sonde #3 de l'audit documents (2026-10-05) : DELETE d'un dossier
contenant un document archivé légalement répondait 204 et emportait le
document ET sa preuve d'archivage ; idem pour une armoire et un legal hold.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import (
    ArchivageLegal, ArchivageLegalError, Cabinet, Document, DocumentVersion,
    Folder, LegalHold, LegalHoldError,
)

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class SuppressionDossierTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc2', defaults={'nom': 'ADOC2'})[0]
        self.admin = User.objects.create_user(
            username='adoc2-admin', password='x', company=self.co,
            role_legacy='admin')
        self.cab = Cabinet.objects.create(company=self.co, nom='Armoire')
        self.dossier = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='Dossier')
        self.sous = Folder.objects.create(
            company=self.co, cabinet=self.cab, parent=self.dossier,
            nom='Sous-dossier')
        self.doc1 = Document.objects.create(
            company=self.co, folder=self.sous, nom='archive.pdf')
        DocumentVersion.objects.create(
            company=self.co, document=self.doc1, version=1,
            file_key='attachments/a.pdf', filename='a.pdf', size=3)
        self.doc2 = Document.objects.create(
            company=self.co, folder=self.sous, nom='hold.pdf')
        self.doc3 = Document.objects.create(
            company=self.co, folder=self.sous, nom='ordinaire.pdf')
        self.doc4 = Document.objects.create(
            company=self.co, folder=self.sous, nom='corbeille.pdf')
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'abc', None)):
            services.archiver_legalement(self.doc1, user=self.admin)
        services.placer_legal_hold(self.doc2, user=self.admin)
        services.mettre_en_corbeille(self.doc4, self.admin)
        self.api = auth(self.admin)

    def _comptes(self):
        return (Document.objects.count(), DocumentVersion.objects.count(),
                ArchivageLegal.objects.count(), LegalHold.objects.count(),
                Folder.objects.count(), Cabinet.objects.count())

    def test_dossier_avec_archive_409(self):
        avant = self._comptes()
        for dossier in (self.sous, self.dossier):
            resp = self.api.delete(f'/api/django/ged/dossiers/{dossier.pk}/')
            self.assertEqual(resp.status_code, 409, resp.content)
            self.assertIn('4 document(s)', resp.data['detail'])
            self.assertIn('dont 1 en corbeille', resp.data['detail'])
        self.assertEqual(self._comptes(), avant)
        liste = self.api.get(f'/api/django/ged/dossiers/?cabinet={self.cab.pk}')
        self.assertEqual(liste.status_code, 200)

    def test_cabinet_avec_hold_409(self):
        avant = self._comptes()
        resp = self.api.delete(f'/api/django/ged/cabinets/{self.cab.pk}/')
        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertEqual(self._comptes(), avant)
        self.assertTrue(Document.objects.filter(pk=self.doc2.pk).exists())

    def test_dossier_vide_204(self):
        vide = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='Vide')
        resp = self.api.delete(f'/api/django/ged/dossiers/{vide.pk}/')
        self.assertEqual(resp.status_code, 204, resp.content)
        self.assertFalse(Folder.objects.filter(pk=vide.pk).exists())
        cab_vide = Cabinet.objects.create(company=self.co, nom='Vide')
        resp = self.api.delete(f'/api/django/ged/cabinets/{cab_vide.pk}/')
        self.assertEqual(resp.status_code, 204, resp.content)

    def test_cascade_orm_leve(self):
        avant = self._comptes()
        with self.assertRaises(ArchivageLegalError), transaction.atomic():
            Folder.objects.filter(pk=self.sous.pk).delete()
        self.assertEqual(self._comptes(), avant)
        # Sans l'archive, le hold de doc2 bloque encore la cascade.
        autre = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='Hold seul')
        Document.objects.filter(pk=self.doc2.pk).update(folder=autre)
        with self.assertRaises(LegalHoldError), transaction.atomic():
            Folder.objects.filter(pk=autre.pk).delete()
        self.assertTrue(Document.objects.filter(pk=self.doc2.pk).exists())
        with self.assertRaises(ArchivageLegalError), transaction.atomic():
            DocumentVersion.objects.filter(document=self.doc1).delete()
