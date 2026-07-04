"""XGED11 — Séparation automatique des lots scannés + code-barres/QR.

Couvre :
  * un lot avec 2 pages blanches séparatrices donne 3 sous-lots ;
  * un code-barres décodé se retrouve dans les métadonnées du document créé ;
  * sans lib `pyzbar`, le lot s'importe entier comme aujourd'hui (dégradation
    propre, pas d'erreur).
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from PIL import Image

from authentication.models import Company
from apps.ged import services
from apps.ged.models import Cabinet, Folder

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def _blank_page(size=(200, 200)):
    return Image.new('RGB', size, color=(255, 255, 255))


def _content_page(size=(200, 200)):
    img = Image.new('RGB', size, color=(255, 255, 255))
    for x in range(0, size[0], 4):
        img.putpixel((x, size[1] // 2), (0, 0, 0))
    return img


class XGed11Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged11-a', 'Xged11 A')
        self.admin_a = make_user(self.co_a, 'xged11-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Scan')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Lots scannés')


class SeparationTests(XGed11Base):
    def test_page_blanche_detectee(self):
        self.assertTrue(services._page_est_blanche(_blank_page()))
        self.assertFalse(services._page_est_blanche(_content_page()))

    def test_lot_avec_2_pages_blanches_donne_3_sous_lots(self):
        images = [
            _content_page(), _content_page(),
            _blank_page(),
            _content_page(),
            _blank_page(),
            _content_page(), _content_page(), _content_page(),
        ]
        sous_lots = services.separer_lot_scans_images(images)
        self.assertEqual(len(sous_lots), 3)
        self.assertEqual(len(sous_lots[0]['pages']), 2)
        self.assertEqual(len(sous_lots[1]['pages']), 1)
        self.assertEqual(len(sous_lots[2]['pages']), 3)

    def test_lot_sans_separateur_reste_un_seul_sous_lot(self):
        images = [_content_page(), _content_page(), _content_page()]
        sous_lots = services.separer_lot_scans_images(images)
        self.assertEqual(len(sous_lots), 1)
        self.assertEqual(len(sous_lots[0]['pages']), 3)

    def test_barcode_absent_degrade_proprement(self):
        # Sans pyzbar installé, decoder renvoie '' — jamais d'exception.
        self.assertEqual(services._decoder_barcode(_content_page()), '')
        self.assertFalse(services.barcode_lib_disponible())

    def test_barcode_decode_route_vers_metadonnees(self):
        # Seule la 1ère page (index 0) porte un code-barres simulé : elle
        # ouvre un nouveau sous-lot ('barcode' posé) et n'est PAS une page de
        # contenu ; les pages suivantes forment le contenu de ce sous-lot.
        pages = [_content_page(), _content_page(), _content_page()]
        call_count = {'n': 0}

        def _fake_decode(image):
            call_count['n'] += 1
            return 'DEV-2026-0042' if call_count['n'] == 1 else ''

        with mock.patch.object(services, '_decoder_barcode', side_effect=_fake_decode):
            sous_lots = services.separer_lot_scans_images(pages)
            self.assertEqual(len(sous_lots), 1)
            self.assertEqual(sous_lots[0]['barcode'], 'DEV-2026-0042')
            self.assertEqual(len(sous_lots[0]['pages']), 2)


_FAKE_STORE_RESULT = (
    'attachments/x.pdf',
    {'filename': 'x.pdf', 'size': 10, 'mime': 'application/pdf'},
)


class DeposerLotSepareTests(XGed11Base):
    def test_deposits_one_document_per_sous_lot(self):
        with mock.patch.object(
                services, '_store_bytes', return_value=_FAKE_STORE_RESULT):
            images = [
                _content_page(), _blank_page(), _content_page(),
                _content_page(),
            ]
            created = services.deposer_lot_scans_separe(
                company=self.co_a, folder=self.folder_a, images=images,
                created_by=self.admin_a)
            self.assertEqual(len(created), 2)
            for doc in created:
                self.assertEqual(doc.folder_id, self.folder_a.pk)

    def test_barcode_stored_in_custom_data(self):
        call_count = {'n': 0}

        def _fake_decode(image):
            call_count['n'] += 1
            return 'REF-123' if call_count['n'] == 1 else ''

        with mock.patch.object(
                services, '_store_bytes', return_value=_FAKE_STORE_RESULT), \
             mock.patch.object(
                services, '_decoder_barcode', side_effect=_fake_decode):
            images = [_content_page(), _content_page(), _content_page()]
            created = services.deposer_lot_scans_separe(
                company=self.co_a, folder=self.folder_a, images=images,
                created_by=self.admin_a)
            self.assertTrue(created)
            self.assertEqual(
                created[0].custom_data.get('barcode'), 'REF-123')
