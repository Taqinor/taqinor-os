"""Tests WIR94 — dépôt GED canonique de l'upload portail.

Couvre : un fichier téléversé sur ``DocumentClientPortail`` déclenche un dépôt
GED (``ged.services.deposit_document``, mocké ici pour isoler le test de
MinIO — voir ``apps.contrats.tests.test_ged_depot`` pour le même patron) et
lie ``document_ged`` ; sans fichier, aucun dépôt ; un échec GED reste
BEST-EFFORT (le document portail est quand même enregistré) ; un second
``save()`` sans nouveau fichier ne redépose rien (idempotence).

Run :
    python manage.py test apps.portail.tests.test_wir94_ged_routing -v2
"""
import itertools
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.ged.models import Cabinet, Document, Folder
from apps.portail.models import DocumentClientPortail

_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'wir94-co-{n}', defaults={'nom': nom or f'WIR94 Co {n}'})
    return company


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='WIR94',
        email=f'wir94-{company.id}-{n}@example.invalid')


def make_ged_document(company):
    cabinet = Cabinet.objects.create(company=company, nom='Portail client')
    folder = Folder.objects.create(
        company=company, cabinet=cabinet, nom='Documents clients')
    return Document.objects.create(company=company, folder=folder, nom='Doc')


class DocumentClientPortailGedRoutingTests(TestCase):
    def setUp(self):
        self.co = make_company()

    def test_upload_avec_fichier_depose_et_referme_un_document_ged(self):
        ged_doc = make_ged_document(self.co)
        fichier = SimpleUploadedFile(
            'facture.pdf', b'%PDF-1.4 contenu factice',
            content_type='application/pdf')
        with mock.patch(
                'apps.ged.services.deposit_document',
                return_value=(ged_doc, True)) as depose:
            doc = DocumentClientPortail.objects.create(
                company=self.co, client_id=make_client(self.co).id,
                libelle='Facture ONEE janvier', fichier=fichier)
        self.assertTrue(depose.called)
        kwargs = depose.call_args.kwargs
        self.assertEqual(kwargs['company'], self.co)
        self.assertEqual(kwargs['source_type'], 'portail.documentclientportail')
        self.assertEqual(kwargs['source_id'], doc.pk)
        self.assertTrue(kwargs['contenu_bytes'])
        doc.refresh_from_db()
        self.assertEqual(doc.document_ged_id, ged_doc.id)

    def test_sans_fichier_aucun_depot_ged(self):
        with mock.patch('apps.ged.services.deposit_document') as depose:
            doc = DocumentClientPortail.objects.create(
                company=self.co, client_id=make_client(self.co).id,
                libelle='Sans fichier')
        depose.assert_not_called()
        self.assertIsNone(doc.document_ged_id)

    def test_echec_depot_ged_reste_best_effort(self):
        fichier = SimpleUploadedFile(
            'facture.pdf', b'contenu', content_type='application/pdf')
        with mock.patch(
                'apps.ged.services.deposit_document',
                side_effect=RuntimeError('minio down')):
            doc = DocumentClientPortail.objects.create(
                company=self.co, client_id=make_client(self.co).id,
                libelle='Panne GED', fichier=fichier)
        # Le document portail est quand même créé, sans document GED lié.
        self.assertIsNotNone(doc.pk)
        self.assertIsNone(doc.document_ged_id)

    def test_second_save_sans_nouveau_fichier_ne_redepose_pas(self):
        ged_doc = make_ged_document(self.co)
        fichier = SimpleUploadedFile(
            'facture.pdf', b'contenu', content_type='application/pdf')
        with mock.patch(
                'apps.ged.services.deposit_document',
                return_value=(ged_doc, True)) as depose:
            doc = DocumentClientPortail.objects.create(
                company=self.co, client_id=make_client(self.co).id,
                fichier=fichier)
        self.assertEqual(depose.call_count, 1)
        doc.traite = True
        doc.save(update_fields=['traite'])
        self.assertEqual(depose.call_count, 1)
