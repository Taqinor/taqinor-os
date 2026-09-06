"""GED33 — OCR de pièces (CIN/facture/BL) → métadonnées.

Couvre la couche DÉTERMINISTE (parsing local, sans clé, sans MinIO) :
  * détection du type de pièce (cin/facture/bl/inconnu) ;
  * extraction des champs typés (numero_cin, numero_facture, montant_ttc,
    numero_bl, date) sans jamais rien inventer ;
  * fusion ADDITIVE dans custom_data (jamais d'écrasement d'une valeur posée) ;
  * OCR text désactivé sans clé (no-op) mais parsing du texte déjà indexé OK ;
  * isolation société (custom_data posé côté serveur).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import Cabinet, Document, Folder, ValidationOcrDocument

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DetectionTests(TestCase):
    def test_detecte_cin(self):
        self.assertEqual(
            services.detecter_type_piece('CARTE NATIONALE D\'IDENTITE'),
            services.PIECE_CIN)

    def test_detecte_facture(self):
        self.assertEqual(
            services.detecter_type_piece('FACTURE N° 42 — Total TTC 1200'),
            services.PIECE_FACTURE)

    def test_detecte_bl(self):
        self.assertEqual(
            services.detecter_type_piece('BON DE LIVRAISON n° BL-7'),
            services.PIECE_BL)

    def test_inconnu(self):
        self.assertEqual(services.detecter_type_piece('texte quelconque'), '')
        self.assertEqual(services.detecter_type_piece(''), '')


class ExtractionTests(TestCase):
    def test_extrait_cin(self):
        meta = services.extraire_metadonnees_piece(
            'CARTE NATIONALE\nNom: X\nCIN AB123456')
        self.assertEqual(meta['type_piece'], services.PIECE_CIN)
        self.assertEqual(meta['numero_cin'], 'AB123456')

    def test_extrait_facture(self):
        meta = services.extraire_metadonnees_piece(
            'FACTURE N°: F-2026-001\nDate 15/06/2026\nTotal TTC: 1 234,50')
        self.assertEqual(meta['type_piece'], services.PIECE_FACTURE)
        self.assertEqual(meta['numero_facture'], 'F-2026-001')
        self.assertEqual(meta['date'], '15/06/2026')
        self.assertIn('1', meta['montant_ttc'])

    def test_extrait_bl(self):
        meta = services.extraire_metadonnees_piece(
            'BON DE LIVRAISON N° BL-77\nDate 01/01/2026')
        self.assertEqual(meta['type_piece'], services.PIECE_BL)
        self.assertEqual(meta['numero_bl'], 'BL-77')

    def test_aucune_invention_si_champ_absent(self):
        meta = services.extraire_metadonnees_piece(
            'FACTURE sans numéro ni montant')
        self.assertEqual(meta.get('type_piece'), services.PIECE_FACTURE)
        self.assertNotIn('montant_ttc', meta)
        self.assertNotIn('numero_facture', meta)

    def test_type_force(self):
        meta = services.extraire_metadonnees_piece(
            'CIN AB123456', type_piece=services.PIECE_CIN)
        self.assertEqual(meta['numero_cin'], 'AB123456')


class OcrPieceFusionTests(TestCase):
    def setUp(self):
        self.co = make_company('ged33', 'Ged33')
        self.cab = Cabinet.objects.create(company=self.co, nom='Pièces')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='CIN')
        self.doc = Document.objects.create(
            company=self.co, folder=self.folder, nom='Pièce')

    @override_settings(GED_OCR_ENABLED=False)
    def test_parsing_du_texte_ocr_existant_sans_cle(self):
        # OCR désactivé : aucun texte fabriqué depuis un binaire, MAIS un
        # texte_ocr déjà indexé est parsé (parsing local gratuit).
        services.set_ocr_text(self.doc, 'CARTE NATIONALE\nCIN AB654321')
        meta = services.ocr_piece_vers_metadonnees(self.doc, file_bytes=None)
        self.assertEqual(meta.get('numero_cin'), 'AB654321')
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.custom_data.get('numero_cin'), 'AB654321')

    @override_settings(GED_OCR_ENABLED=False)
    def test_fusion_additive_sans_ecrasement(self):
        self.doc.custom_data = {'numero_cin': 'EXISTANT'}
        self.doc.save(update_fields=['custom_data'])
        services.set_ocr_text(self.doc, 'CIN AB111111')
        services.ocr_piece_vers_metadonnees(self.doc, file_bytes=None)
        self.doc.refresh_from_db()
        # La valeur préexistante n'est jamais écrasée.
        self.assertEqual(self.doc.custom_data.get('numero_cin'), 'EXISTANT')

    @override_settings(GED_OCR_ENABLED=False)
    def test_aucun_texte_aucune_meta(self):
        meta = services.ocr_piece_vers_metadonnees(self.doc, file_bytes=None)
        self.assertEqual(meta, {})


class OcrPieceEndpointRouteParValidationTests(TestCase):
    """DRAFT165-64 (AUDV12) — l'action REST ``ocr-piece/`` appelait TOUJOURS
    l'ancienne ``ocr_piece_vers_metadonnees`` : un document à faible confiance
    n'atterrissait jamais dans la file ``ValidationOcrDocument`` malgré
    ``ValidationOcrDocumentViewSet`` déjà exposé sur ``/validations-ocr/``."""

    def setUp(self):
        self.co = make_company('ged33-route', 'Ged33Route')
        self.user = make_user(self.co, 'ged33-route-user')
        self.cab = Cabinet.objects.create(company=self.co, nom='Pièces')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='Factures')
        self.doc = Document.objects.create(
            company=self.co, folder=self.folder, nom='Facture scannée')

    @override_settings(GED_OCR_ENABLED=False)
    def test_faible_confiance_met_en_file_de_validation(self):
        services.set_ocr_text(self.doc, 'facture')
        resp = auth(self.user).post(
            f'/api/django/ged/documents/{self.doc.pk}/ocr-piece/',
            {'type_piece': 'facture'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['en_validation'])
        self.assertTrue(
            ValidationOcrDocument.objects.filter(document=self.doc).exists())
        # Les métadonnées ne sont PAS fusionnées tant que non validées.
        self.doc.refresh_from_db()
        self.assertNotIn('numero_facture', self.doc.custom_data or {})

    @override_settings(GED_OCR_ENABLED=False)
    def test_haute_confiance_fusionne_directement_sans_file(self):
        services.set_ocr_text(
            self.doc,
            'FACTURE N: 2026-042\nTotal TTC: 1500,00\nDate: 01/07/2026\n'
            'Merci pour votre confiance, ceci est un texte suffisamment long.')
        resp = auth(self.user).post(
            f'/api/django/ged/documents/{self.doc.pk}/ocr-piece/',
            {'type_piece': 'facture'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['en_validation'])
        self.assertFalse(
            ValidationOcrDocument.objects.filter(document=self.doc).exists())
        self.doc.refresh_from_db()
        self.assertIn('numero_facture', self.doc.custom_data)
