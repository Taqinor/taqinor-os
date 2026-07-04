"""Tests XRH23 — Parsing de CV par OCR (key-gated).

Couvre :
* avec une clé (faux fournisseur OCR câblé) : un CV pré-remplit les champs
  VIDES uniquement (jamais d'écrasement d'un champ déjà saisi) ;
* sans clé : l'action répond 503 douce, message explicite, aucune exception ;
* sans CV attaché : 503 douce également ;
* isolation société (une autre société ne peut pas parser une candidature qui
  n'est pas la sienne — 404).
"""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import services
from apps.rh.models import Candidature, OuverturePoste
from core.ai import AIResult, OCRProvider, register_provider
from core.ai import registry as ai_registry

User = get_user_model()

CANDIDATURES = '/api/django/rh/candidatures/'


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


class FakeCVProvider(OCRProvider):
    key = 'fake_cv_xrh23'

    def is_configured(self):
        return True

    def extract(self, *, content, mime_type, schema, hint=None):
        return AIResult(ok=True, configured=True, provider=self.key, data={
            'nom': 'Fahmi', 'prenom': 'Yassir',
            'email': 'yassir.fahmi@example.com',
            'telephone': '0612345678',
            'diplome': 'Ingénieur électricité',
            'competences': ['electricite', 'solaire', 'senior'],
        })


class ParsingCvOcrTests(TestCase):
    def setUp(self):
        self.co = make_company('cv-a', 'A')
        self.rh = make_user(self.co, 'cv-rh')
        self.ouverture = OuverturePoste.objects.create(
            company=self.co, intitule='Technicien pose')
        self.cv = SimpleUploadedFile(
            'cv.pdf', b'%PDF-1.4 fake cv', content_type='application/pdf')

    def _make_candidature(self, **kwargs):
        return Candidature.objects.create(
            company=self.co, ouverture=self.ouverture,
            cv_fichier=self.cv, **kwargs)

    def test_sans_cle_reponse_503_douce(self):
        cand = self._make_candidature(nom='Vide')
        resp = auth(self.rh).post(
            f'{CANDIDATURES}{cand.id}/parser-cv/')
        self.assertEqual(resp.status_code, 503, resp.data)
        self.assertIn('detail', resp.data)

    def test_sans_cv_attache_503_douce(self):
        cand = Candidature.objects.create(
            company=self.co, ouverture=self.ouverture, nom='Sans CV')
        resp = auth(self.rh).post(
            f'{CANDIDATURES}{cand.id}/parser-cv/')
        self.assertEqual(resp.status_code, 503, resp.data)

    def test_avec_cle_prefill_champs_vides_uniquement(self):
        register_provider(FakeCVProvider)
        self.addCleanup(
            lambda: ai_registry._REGISTRY['ocr'].pop('fake_cv_xrh23', None))
        cand = self._make_candidature(nom='', email='', telephone='')

        with override_settings(AI_PROVIDERS={'ocr': 'fake_cv_xrh23'}):
            resp = auth(self.rh).post(
                f'{CANDIDATURES}{cand.id}/parser-cv/')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            set(resp.data['champs_remplis']),
            {'nom', 'email', 'telephone'})
        self.assertIn('senior', resp.data['tags_suggeres'])
        cand.refresh_from_db()
        self.assertEqual(cand.nom, 'Yassir Fahmi')
        self.assertEqual(cand.email, 'yassir.fahmi@example.com')
        self.assertEqual(cand.telephone, '0612345678')

    def test_avec_cle_ne_jamais_ecraser_champ_deja_saisi(self):
        register_provider(FakeCVProvider)
        self.addCleanup(
            lambda: ai_registry._REGISTRY['ocr'].pop('fake_cv_xrh23', None))
        cand = self._make_candidature(
            nom='Nom Déjà Saisi', email='deja@example.com', telephone='')

        with override_settings(AI_PROVIDERS={'ocr': 'fake_cv_xrh23'}):
            resp = auth(self.rh).post(
                f'{CANDIDATURES}{cand.id}/parser-cv/')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['champs_remplis'], ['telephone'])
        cand.refresh_from_db()
        self.assertEqual(cand.nom, 'Nom Déjà Saisi')
        self.assertEqual(cand.email, 'deja@example.com')
        self.assertEqual(cand.telephone, '0612345678')

    def test_service_directement_leve_indisponible_sans_cv(self):
        cand = Candidature.objects.create(
            company=self.co, ouverture=self.ouverture, nom='X')
        with self.assertRaises(services.CvParsingUnavailable):
            services.parser_cv(cand)

    def test_isolation_societe_404(self):
        co_b = make_company('cv-b', 'B')
        rh_b = make_user(co_b, 'cv-rh-b')
        cand = self._make_candidature(nom='A')
        resp = auth(rh_b).post(f'{CANDIDATURES}{cand.id}/parser-cv/')
        self.assertEqual(resp.status_code, 404)
