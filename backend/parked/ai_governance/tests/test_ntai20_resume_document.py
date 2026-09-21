"""NTAI20 — Tests du résumé de long document (map-reduce + repli aperçu).

Couvre : le résumé avec points clés CITÉS par fragment, le découpage du texte
OCR quand la GED n'a pas encore indexé de fragments, le repli sur l'aperçu
plein-texte sans clé LLM, la borne de fragments (document tronqué SIGNALÉ), le
document sans texte et le scoping société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.ai import AIResult, LLMProvider, register_provider
from core.ai import registry

from ..extraction import (RESUME_FRAGMENTS_MAX, RESUME_TAILLE_FRAGMENT,
                          fragments_du_document, resumer_document)

User = get_user_model()

URL = '/api/django/ai/resumer-document/'


class FakeResumeLLM(LLMProvider):
    key = 'fake_ntai20'
    appels = 0

    def is_configured(self):
        return True

    def complete(self, *, prompt, system=None, max_tokens=512):
        FakeResumeLLM.appels += 1
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'text': f'Résumé {FakeResumeLLM.appels}.'})


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntai20ResumeDocumentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from apps.ged.models import Cabinet, Document, Folder

        cls.company = make_company('ntai20-co', 'NTAI20 Co')
        cls.autre = make_company('ntai20-autre', 'NTAI20 Autre')
        cls.user = User.objects.create_user(
            username='ntai20-user', password='x', company=cls.company,
            role_legacy='normal')

        cabinet = Cabinet.objects.create(company=cls.company, nom='Cabinet')
        dossier = Folder.objects.create(
            company=cls.company, cabinet=cabinet, nom='Dossier')
        cls.document = Document.objects.create(
            company=cls.company, folder=dossier, nom='Contrat long',
            texte_ocr='A' * (RESUME_TAILLE_FRAGMENT * 3))
        cls.vide = Document.objects.create(
            company=cls.company, folder=dossier, nom='Scan sans texte')

        cabinet_autre = Cabinet.objects.create(company=cls.autre, nom='Cab.')
        dossier_autre = Folder.objects.create(
            company=cls.autre, cabinet=cabinet_autre, nom='Dossier')
        cls.document_autre = Document.objects.create(
            company=cls.autre, folder=dossier_autre, nom='Contrat voisin',
            texte_ocr='Texte de l\'autre société.')

    def setUp(self):
        FakeResumeLLM.appels = 0

    def _with_fake_llm(self):
        register_provider(FakeResumeLLM)
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_ntai20', None))

    # --- Découpage ----------------------------------------------------------

    def test_texte_ocr_decoupe_en_fragments(self):
        fragments = fragments_du_document(self.document)
        self.assertEqual(len(fragments), 3)
        self.assertEqual(len(fragments[0]), RESUME_TAILLE_FRAGMENT)

    def test_document_sans_texte_n_a_aucun_fragment(self):
        self.assertEqual(fragments_du_document(self.vide), [])

    # --- Résumé -------------------------------------------------------------

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai20'})
    def test_resume_avec_points_cles_cites(self):
        self._with_fake_llm()
        resultat = resumer_document(
            company=self.company, document_id=self.document.id)
        self.assertEqual(resultat['source'], 'llm')
        self.assertEqual(len(resultat['points_cles']), 3)
        # Chaque point renvoie à un fragment RÉEL, numéroté.
        self.assertEqual(resultat['points_cles'][0]['citation'],
                         '[fragment 1]')
        self.assertEqual(resultat['points_cles'][2]['fragment'], 3)
        self.assertTrue(resultat['resume'])
        self.assertFalse(resultat['tronque'])

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai20'})
    def test_document_trop_long_est_signale_tronque(self):
        from apps.ged.models import Cabinet, Document, Folder

        cabinet = Cabinet.objects.create(company=self.company, nom='Cab. 2')
        dossier = Folder.objects.create(
            company=self.company, cabinet=cabinet, nom='Dossier 2')
        enorme = Document.objects.create(
            company=self.company, folder=dossier, nom='Très long',
            texte_ocr='B' * (RESUME_TAILLE_FRAGMENT * (RESUME_FRAGMENTS_MAX + 2)))

        self._with_fake_llm()
        resultat = resumer_document(
            company=self.company, document_id=enorme.id)
        self.assertTrue(resultat['tronque'])
        self.assertEqual(len(resultat['points_cles']), RESUME_FRAGMENTS_MAX)

    @override_settings(AI_PROVIDERS={})
    def test_sans_llm_repli_sur_l_apercu(self):
        resultat = resumer_document(
            company=self.company, document_id=self.document.id)
        self.assertEqual(resultat['source'], 'apercu')
        self.assertEqual(resultat['resume'], '')
        self.assertEqual(resultat['points_cles'], [])
        self.assertTrue(resultat['apercu'])

    def test_document_sans_texte_refuse_proprement(self):
        from ..services import AiCopiloteUnavailable

        with self.assertRaises(AiCopiloteUnavailable):
            resumer_document(company=self.company, document_id=self.vide.id)

    def test_document_d_une_autre_societe_introuvable(self):
        from ..services import AiCopiloteUnavailable

        with self.assertRaises(AiCopiloteUnavailable):
            resumer_document(company=self.company,
                             document_id=self.document_autre.id)

    # --- Endpoint -----------------------------------------------------------

    @override_settings(AI_PROVIDERS={})
    def test_endpoint_rend_l_apercu_sans_cle(self):
        reponse = auth(self.user).post(
            URL, {'document_id': self.document.id}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(reponse.json()['source'], 'apercu')

    def test_endpoint_exige_un_document(self):
        reponse = auth(self.user).post(URL, {}, format='json')
        self.assertEqual(reponse.status_code, 400)
