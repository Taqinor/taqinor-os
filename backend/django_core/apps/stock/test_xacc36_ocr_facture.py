"""XACC36 — OCR facture fournisseur → brouillon de facture d'achat.

Couvre :
  * un document OCR (fournisseur + ICE + montants) crée un brouillon
    FactureFournisseur aux bons fournisseur/montants ;
  * le matching se fait par ICE puis par nom (jamais par une clé inattendue) ;
  * aucun montant n'est inventé (un champ absent reste vide/0) ;
  * un doublon potentiel (XPUR11) est signalé en warning, jamais bloquant ;
  * sans fournisseur trouvable, l'appel est refusé proprement (dégradation —
    la saisie manuelle reste intacte) ;
  * un scan joint est rattaché comme pièce jointe (records/MinIO, mocké).

Run:
    python manage.py test apps.stock.test_xacc36_ocr_facture -v 2
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import FactureFournisseur, Fournisseur
from apps.stock.services import (
    creer_facture_fournisseur_depuis_ocr, match_fournisseur_from_ocr,
)

User = get_user_model()

_PNG_1x1 = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08'
    b'\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00'
    b'\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')


def _png_file(name='scan.png'):
    from django.core.files.uploadedfile import SimpleUploadedFile
    return SimpleUploadedFile(name, _PNG_1x1, content_type='image/png')


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Xacc36Base(TestCase):
    def setUp(self):
        self.company = _company('xacc36-co')
        self.user = _user(
            self.company, 'xacc36-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Solar Import SARL',
            ice='001234567000089')


class TestMatchFournisseurFromOcr(Xacc36Base):
    def test_match_par_ice_priorite(self):
        Fournisseur.objects.create(
            company=self.company, nom='Autre nom', ice='999999999000099')
        found = match_fournisseur_from_ocr(
            self.company,
            {'fournisseur': 'Nom qui ne matche pas',
             'ice': '001234567000089'})
        self.assertEqual(found.id, self.fournisseur.id)

    def test_match_par_nom_si_pas_ice(self):
        found = match_fournisseur_from_ocr(
            self.company, {'fournisseur': 'solar import sarl'})
        self.assertEqual(found.id, self.fournisseur.id)

    def test_aucun_match_renvoie_none(self):
        found = match_fournisseur_from_ocr(
            self.company, {'fournisseur': 'Fournisseur Inconnu XYZ'})
        self.assertIsNone(found)


class TestCreerFactureDepuisOcr(Xacc36Base):
    def test_cree_brouillon_aux_bons_montants(self):
        fields = {
            'fournisseur': 'Solar Import SARL',
            'ice': '001234567000089',
            'numero': 'INV-2026-042',
            'date': '2026-06-01',
            'date_echeance': '2026-07-01',
            'montant_ht': 10000,
            'montant_tva': 2000,
            'montant_ttc': 12000,
        }
        facture, doublons = creer_facture_fournisseur_depuis_ocr(
            company=self.company, user=self.user, fields=fields)
        self.assertEqual(doublons, [])
        self.assertEqual(facture.fournisseur_id, self.fournisseur.id)
        self.assertEqual(facture.montant_ht, Decimal('10000'))
        self.assertEqual(facture.montant_tva, Decimal('2000'))
        self.assertEqual(facture.montant_ttc, Decimal('12000'))
        self.assertEqual(facture.ref_fournisseur, 'INV-2026-042')
        self.assertEqual(facture.statut, FactureFournisseur.Statut.A_PAYER)
        self.assertIn('OCR', facture.note)

    def test_champ_absent_reste_vide_jamais_invente(self):
        fields = {
            'fournisseur': 'Solar Import SARL',
            'montant_ht': 5000,
            # montant_tva et montant_ttc absents : ne doivent jamais être
            # inventés (0, pas une valeur dérivée arbitraire).
        }
        facture, _ = creer_facture_fournisseur_depuis_ocr(
            company=self.company, user=self.user, fields=fields)
        self.assertEqual(facture.montant_ht, Decimal('5000'))
        self.assertEqual(facture.montant_tva, Decimal('0'))
        self.assertEqual(facture.montant_ttc, Decimal('0'))
        self.assertIsNone(facture.date_facture)

    def test_sans_fournisseur_matche_leve_valueerror(self):
        fields = {'fournisseur': 'Introuvable Corp', 'montant_ht': 100}
        with self.assertRaises(ValueError):
            creer_facture_fournisseur_depuis_ocr(
                company=self.company, user=self.user, fields=fields)
        # Aucune facture n'a été créée (dégradation propre).
        self.assertEqual(FactureFournisseur.objects.count(), 0)

    def test_doublon_detecte_mais_non_bloquant(self):
        FactureFournisseur.objects.create(
            company=self.company, reference='FF-EXIST',
            fournisseur=self.fournisseur, ref_fournisseur='INV-DUP',
            montant_ttc=Decimal('3000'))
        fields = {
            'fournisseur': 'Solar Import SARL',
            'numero': 'INV-DUP',
            'montant_ht': 2500, 'montant_ttc': 2750,
        }
        facture, doublons = creer_facture_fournisseur_depuis_ocr(
            company=self.company, user=self.user, fields=fields)
        self.assertIsNotNone(facture.id)
        self.assertEqual(len(doublons), 1)


class TestDepuisOcrEndpoint(Xacc36Base):
    def test_endpoint_cree_brouillon(self):
        resp = self.api.post(
            '/api/django/stock/factures-fournisseur/depuis-ocr/',
            {'fields': {
                'fournisseur': 'Solar Import SARL',
                'ice': '001234567000089',
                'montant_ht': 8000, 'montant_tva': 1600,
                'montant_ttc': 9600,
            }}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data['montant_ttc']), Decimal('9600'))

    def test_endpoint_sans_fournisseur_refuse_400(self):
        resp = self.api.post(
            '/api/django/stock/factures-fournisseur/depuis-ocr/',
            {'fields': {'fournisseur': 'Zzz Introuvable'}}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_champ_fields_invalide(self):
        resp = self.api.post(
            '/api/django/stock/factures-fournisseur/depuis-ocr/',
            {'fields': 'not-a-dict'}, format='json')
        self.assertEqual(resp.status_code, 400)

    @mock.patch('apps.records.storage.get_minio_client')
    @mock.patch('apps.records.storage.ensure_uploads_bucket')
    def test_endpoint_rattache_scan_en_piece_jointe(
            self, mock_ensure, mock_minio):
        mock_client = mock.MagicMock()
        mock_minio.return_value = mock_client
        resp = self.api.post(
            '/api/django/stock/factures-fournisseur/depuis-ocr/',
            {
                'fields': '{"fournisseur": "Solar Import SARL", '
                          '"montant_ht": 1000, "montant_ttc": 1000}',
                'file': _png_file(),
            }, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)

        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Attachment
        ct = ContentType.objects.get_for_model(FactureFournisseur)
        att = Attachment.objects.filter(
            content_type=ct, object_id=resp.data['id']).first()
        self.assertIsNotNone(att)
