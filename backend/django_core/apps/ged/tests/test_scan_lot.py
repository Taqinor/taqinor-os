"""GED31 — Numérisation par lot (scan-to-DMS) + hook OCR.

Couvre (au niveau SERVICE, sans MinIO — on passe des `file_key` déjà connus) :
  * un lot de N fichiers crée N documents + leur version 1, dans le bon dossier ;
  * société + créateur posés côté serveur pour tout le lot ;
  * un lot vide ne crée rien (jamais d'erreur) ;
  * le dossier doit appartenir à la société (garde cross-société) ;
  * le hook OCR (GED33) est un NO-OP sans clé (aucun texte fabriqué).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from authentication.models import Company
from apps.ged import services
from apps.ged.models import Cabinet, Document, DocumentVersion, Folder

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class ScanLotServiceTests(TestCase):
    def setUp(self):
        self.co_a = make_company('ged31-a', 'Ged31 A')
        self.co_b = make_company('ged31-b', 'Ged31 B')
        self.admin_a = make_user(self.co_a, 'ged31-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Scans')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Lot')
        self.cab_b = Cabinet.objects.create(company=self.co_b, nom='Scans')
        self.folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Lot B')

    def test_lot_cree_n_documents_avec_version(self):
        fichiers = [
            {'file_key': 'attachments/a.pdf', 'filename': 'a.pdf',
             'size': 10, 'mime': 'application/pdf'},
            {'file_key': 'attachments/b.pdf', 'filename': 'b.pdf',
             'size': 20, 'mime': 'application/pdf'},
        ]
        docs = services.deposer_lot_scans(
            company=self.co_a, folder=self.folder_a, fichiers=fichiers,
            created_by=self.admin_a)
        self.assertEqual(len(docs), 2)
        for doc in docs:
            self.assertEqual(doc.company_id, self.co_a.id)
            self.assertEqual(doc.created_by_id, self.admin_a.id)
            self.assertEqual(doc.folder_id, self.folder_a.id)
            self.assertEqual(
                DocumentVersion.objects.filter(document=doc).count(), 1)

    def test_lot_vide_ne_cree_rien(self):
        docs = services.deposer_lot_scans(
            company=self.co_a, folder=self.folder_a, fichiers=[],
            created_by=self.admin_a)
        self.assertEqual(docs, [])
        self.assertEqual(Document.objects.filter(company=self.co_a).count(), 0)

    def test_dossier_autre_societe_refuse(self):
        # Déposer dans le dossier de B avec la société A doit échouer (garde).
        with self.assertRaises(ValueError):
            services.deposer_un_scan(
                company=self.co_a, folder=self.folder_b,
                file_key='attachments/x.pdf', filename='x.pdf',
                mime='application/pdf', created_by=self.admin_a)

    @override_settings(GED_OCR_ENABLED=False)
    def test_ocr_noop_sans_cle(self):
        self.assertFalse(services.ocr_enabled())
        # Aucun texte fabriqué : ocr_extract_text renvoie '' même avec des octets.
        self.assertEqual(
            services.ocr_extract_text(b'%PDF-1.4 fake', mime='application/pdf'),
            '')
        docs = services.deposer_lot_scans(
            company=self.co_a, folder=self.folder_a,
            fichiers=[{'file_key': 'attachments/c.pdf', 'filename': 'c.pdf',
                       'mime': 'application/pdf', 'contenu_bytes': b'%PDF fake'}],
            created_by=self.admin_a)
        docs[0].refresh_from_db()
        self.assertEqual(docs[0].texte_ocr, '')

    @override_settings(GED_OCR_ENABLED=True)
    def test_ocr_active_sans_provider_reste_noop(self):
        # Flag activé mais aucun provider concret câblé → toujours no-op (jamais
        # d'appel fantôme, jamais de texte inventé).
        self.assertTrue(services.ocr_enabled())
        self.assertEqual(
            services.ocr_extract_text(b'data', mime='image/png'), '')
