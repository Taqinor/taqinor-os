"""XSAL8 — Scan de carte de visite (photo) → pré-remplissage du lead express.

Couvre :
  - avec un fournisseur OCR configuré (faux fournisseur câblé) : la photo
    renvoie les champs reconnus (jamais de création de lead) ;
  - le pré-check de doublons est inclus dans la réponse ;
  - sans clé : 503 douce, message explicite, aucune exception ;
  - fichier non-image (magic bytes) : 400, jamais d'appel OCR ;
  - fichier trop volumineux : 400 (pas d'appel réseau) ;
  - aucun lead n'est jamais créé par cette action ;
  - company-scopée (le pré-check de doublons ne fuit jamais entre sociétés).
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Lead
from core.ai import AIResult, OCRProvider, register_provider

User = get_user_model()

SCAN_URL = '/api/django/crm/leads/scan-carte/'

# JPEG magic bytes minimal (suffisant pour passer la détection).
_FAKE_JPEG = b'\xff\xd8\xff\xe0' + b'\x00' * 20


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class FakeCarteVisiteProvider(OCRProvider):
    key = 'fake_carte_visite_xsal8'

    def is_configured(self):
        return True

    def extract(self, *, content, mime_type, schema, hint=None):
        return AIResult(ok=True, configured=True, provider=self.key, data={
            'nom': 'Benali', 'prenom': 'Amina', 'societe': 'Ferme Al Baraka',
            'telephone': '0612345678', 'email': 'amina@example.com',
        })


class ScanCarteVisiteTests(TestCase):
    def setUp(self):
        self.company = make_company('xsal8-a', 'A')
        self.user = make_user(self.company, 'xsal8-user')

    def _post(self, content=None, filename='carte.jpg'):
        content = content if content is not None else _FAKE_JPEG
        upload = SimpleUploadedFile(filename, content, content_type='image/jpeg')
        return auth(self.user).post(
            SCAN_URL, {'file': upload}, format='multipart')

    def test_sans_cle_reponse_503_douce(self):
        resp = self._post()
        self.assertEqual(resp.status_code, 503, resp.data)
        self.assertIn('detail', resp.data)
        self.assertEqual(Lead.objects.count(), 0)

    def test_avec_cle_prefill_les_champs(self):
        register_provider(FakeCarteVisiteProvider)
        with override_settings(AI_PROVIDERS={'ocr': 'fake_carte_visite_xsal8'}):
            resp = self._post()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nom'], 'Benali')
        self.assertEqual(resp.data['prenom'], 'Amina')
        self.assertEqual(resp.data['societe'], 'Ferme Al Baraka')
        self.assertEqual(resp.data['telephone'], '0612345678')
        self.assertEqual(resp.data['email'], 'amina@example.com')
        # Jamais de création automatique — l'utilisateur valide.
        self.assertEqual(Lead.objects.count(), 0)

    def test_avec_cle_inclut_le_pre_check_doublons(self):
        Lead.objects.create(
            company=self.company, nom='Benali existant',
            telephone='0612345678')
        register_provider(FakeCarteVisiteProvider)
        with override_settings(AI_PROVIDERS={'ocr': 'fake_carte_visite_xsal8'}):
            resp = self._post()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['doublons']), 1)
        self.assertEqual(resp.data['doublons'][0]['nom'], 'Benali existant')

    def test_doublon_ne_fuit_pas_entre_societes(self):
        other = make_company('xsal8-other', 'Other')
        Lead.objects.create(
            company=other, nom='Autre société', telephone='0612345678')
        register_provider(FakeCarteVisiteProvider)
        with override_settings(AI_PROVIDERS={'ocr': 'fake_carte_visite_xsal8'}):
            resp = self._post()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['doublons'], [])

    def test_fichier_non_image_rejete_400(self):
        resp = self._post(content=b'pas-une-image-du-tout', filename='x.txt')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(Lead.objects.count(), 0)

    def test_fichier_trop_volumineux_rejete_400(self):
        big = _FAKE_JPEG + b'\x00' * (9 * 1024 * 1024)
        register_provider(FakeCarteVisiteProvider)
        with override_settings(AI_PROVIDERS={'ocr': 'fake_carte_visite_xsal8'}):
            resp = self._post(content=big)
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_sans_fichier_400(self):
        resp = auth(self.user).post(SCAN_URL, {}, format='multipart')
        self.assertEqual(resp.status_code, 400, resp.data)
