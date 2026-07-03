"""XGED13 — File de validation d'extraction OCR (confiance + tableaux).

Couvre :
  * un document à extraction faible atterrit dans la file (a_valider) ;
  * l'écran de validation permet corriger/valider ;
  * les lignes de tableau extraites sont stockées structurées ;
  * confiance suffisante → fusion directe (comportement GED33 inchangé),
    aucune entrée de validation créée.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
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


class XGed13Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged13-a', 'Xged13 A')
        self.admin_a = make_user(self.co_a, 'xged13-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Factures')
        self.doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Facture scannée')


class ScoreConfianceTests(XGed13Base):
    def test_score_zero_sans_texte(self):
        self.assertEqual(services.score_confiance_extraction('', {}), 0.0)

    def test_score_haut_avec_champs_complets(self):
        texte = (
            'FACTURE N: 2026-042\nTotal TTC: 1500,00\nDate: 01/07/2026\n'
            'Merci pour votre confiance, ceci est un texte suffisamment long.')
        meta = services.extraire_metadonnees_piece(texte, type_piece='facture')
        score = services.score_confiance_extraction(texte, meta)
        self.assertGreater(score, 0.6)

    def test_score_bas_avec_champs_incomplets(self):
        texte = 'facture'
        meta = {'type_piece': 'facture'}
        score = services.score_confiance_extraction(texte, meta)
        self.assertLess(score, 0.6)


class LignesTableauTests(XGed13Base):
    def test_extrait_lignes_tableau(self):
        texte = (
            'Facture N: 001\n'
            'Panneau solaire 450W          4       1200,00\n'
            'Onduleur hybride 5kW          1       8500,00\n'
        )
        lignes = services.extraire_lignes_tableau(texte)
        self.assertEqual(len(lignes), 2)
        self.assertEqual(lignes[0]['designation'], 'Panneau solaire 450W')
        self.assertEqual(lignes[0]['qte'], '4')

    def test_aucune_ligne_sans_motif(self):
        self.assertEqual(services.extraire_lignes_tableau('texte libre sans tableau'), [])


class ExtractionAvecValidationTests(XGed13Base):
    def test_faible_confiance_va_en_file_de_validation(self):
        self.doc.texte_ocr = 'facture'
        self.doc.save(update_fields=['texte_ocr'])
        meta, en_validation = services.ocr_extraction_avec_validation(
            self.doc, type_piece='facture', seuil=0.9)
        self.assertTrue(en_validation)
        self.assertTrue(
            ValidationOcrDocument.objects.filter(document=self.doc).exists())

    def test_haute_confiance_fusionne_directement(self):
        self.doc.texte_ocr = (
            'FACTURE N: 2026-042\nTotal TTC: 1500,00\nDate: 01/07/2026')
        self.doc.save(update_fields=['texte_ocr'])
        meta, en_validation = services.ocr_extraction_avec_validation(
            self.doc, type_piece='facture', seuil=0.1)
        self.assertFalse(en_validation)
        self.assertFalse(
            ValidationOcrDocument.objects.filter(document=self.doc).exists())
        self.doc.refresh_from_db()
        self.assertIn('numero_facture', self.doc.custom_data)


class ValiderExtractionTests(XGed13Base):
    def test_valider_applique_corrections(self):
        validation = ValidationOcrDocument.objects.create(
            company=self.co_a, document=self.doc, score_confiance=0.3,
            champs_extraits={'numero_facture': 'ABC'})
        services.valider_extraction_ocr(
            validation, champs_corriges={'numero_facture': 'CORRIGE-1'},
            user=self.admin_a)
        validation.refresh_from_db()
        self.doc.refresh_from_db()
        self.assertTrue(validation.valide)
        self.assertEqual(validation.valide_par_id, self.admin_a.pk)
        self.assertEqual(self.doc.custom_data['numero_facture'], 'CORRIGE-1')

    def test_valider_endpoint(self):
        validation = ValidationOcrDocument.objects.create(
            company=self.co_a, document=self.doc, score_confiance=0.3,
            champs_extraits={'numero_facture': 'ABC'})
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/validations-ocr/{validation.pk}/valider/',
            {'champs_corriges': {'numero_facture': 'XYZ'}}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['valide'])
