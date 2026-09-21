"""NTAI15/NTAI16 — Tests de l'extraction documentaire à la demande.

Couvre : les deux nouveaux gabarits (bulletin de paie, facture fournisseur)
listés par ``available_schemas()``, l'extraction d'un PDF qui rend les champs
structurés, la dégradation propre sans clé OCR, les garde-fous de fichier, la
NON-ÉCRITURE, et le rapprochement de facture (totaux + écart signalé, jamais
corrigé).
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.ai import AIResult, OCRProvider, register_provider
from core.ai import registry
from core.ai.schemas import (BULLETIN_PAIE_SCHEMA, FACTURE_FOURNISSEUR_SCHEMA,
                             available_schemas, get_schema)

from ..extraction import rapprocher_facture

User = get_user_model()

URL = '/api/django/ai/extraire/'

#: PDF minimal (les octets magiques suffisent : le faux fournisseur ne lit
#: jamais le contenu).
PDF = b'%PDF-1.4\n%fake pour test\n'

BULLETIN = {
    'matricule': 'M-042', 'nom': 'Salarié Test', 'periode': '2026-08',
    'salaire_brut': '9 500,00', 'salaire_net': '7 480,00',
    'cnss': '418,00', 'amo': '204,25', 'ir': '1 397,75',
    'conges': '1,5', 'jours_travailles': '26',
}

FACTURE = {
    'fournisseur': 'SunRak', 'ice': '001234567000012',
    'numero_facture': 'FA-2026-118', 'date_facture': '2026-08-31',
    'lignes': [
        {'designation': 'Panneau 550 Wc', 'reference': 'PV550',
         'quantite': 10, 'prix_unitaire_ht': '900', 'total_ht': '9000'},
        {'designation': 'Câble solaire 6 mm²', 'quantite': 2,
         'total_ht': '600'},
    ],
    'total_ht': '9600', 'total_tva': '1920', 'total_ttc': '11520',
}


class FakeOCR(OCRProvider):
    key = 'fake_ntai15'
    #: Charge renvoyée (pilotée par chaque test).
    charge = dict(BULLETIN)
    dernier_schema = None

    def is_configured(self):
        return True

    def extract(self, *, content, mime_type, schema, hint=None):
        FakeOCR.dernier_schema = schema
        return AIResult(ok=True, configured=True, provider=self.key,
                        data=dict(FakeOCR.charge))


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntai15ExtractionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntai15-co', 'NTAI15 Co')
        cls.autre = make_company('ntai15-autre', 'NTAI15 Autre')
        cls.user = User.objects.create_user(
            username='ntai15-user', password='x', company=cls.company,
            role_legacy='normal')

    def _with_fake_ocr(self, charge):
        FakeOCR.charge = dict(charge)
        FakeOCR.dernier_schema = None
        register_provider(FakeOCR)
        self.addCleanup(
            lambda: registry._REGISTRY['ocr'].pop('fake_ntai15', None))

    def _poster(self, schema, contenu=PDF):
        fichier = SimpleUploadedFile('piece.pdf', contenu,
                                     content_type='application/pdf')
        return auth(self.user).post(
            f'{URL}?schema={schema}', {'file': fichier}, format='multipart')

    # --- Gabarits -----------------------------------------------------------

    def test_gabarits_declares(self):
        self.assertIn('bulletin_paie', available_schemas())
        self.assertIn('facture_fournisseur', available_schemas())
        self.assertIs(get_schema('bulletin_paie'), BULLETIN_PAIE_SCHEMA)
        self.assertIs(get_schema('facture_fournisseur'),
                      FACTURE_FOURNISSEUR_SCHEMA)

    def test_champs_obligatoires_du_bulletin(self):
        self.assertEqual(
            set(BULLETIN_PAIE_SCHEMA.required_keys()),
            {'periode', 'salaire_brut', 'salaire_net'})

    # --- NTAI15 : bulletin de paie -----------------------------------------

    @override_settings(AI_PROVIDERS={'ocr': 'fake_ntai15'})
    def test_bulletin_rend_les_champs_structures(self):
        self._with_fake_ocr(BULLETIN)
        reponse = self._poster('bulletin_paie')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        corps = reponse.json()
        self.assertEqual(FakeOCR.dernier_schema, 'bulletin_paie')
        self.assertEqual(corps['champs']['salaire_net'], '7 480,00')
        self.assertEqual(corps['champs_manquants'], [])
        # Contrat explicite : rien n'est écrit, le fichier n'est pas conservé.
        self.assertFalse(corps['applique'])
        self.assertFalse(corps['fichier_conserve'])

    @override_settings(AI_PROVIDERS={'ocr': 'fake_ntai15'})
    def test_champ_obligatoire_absent_est_signale(self):
        charge = dict(BULLETIN)
        charge['salaire_net'] = ''
        self._with_fake_ocr(charge)
        corps = self._poster('bulletin_paie').json()
        self.assertIn('salaire_net', corps['champs_manquants'])

    @override_settings(AI_PROVIDERS={'ocr': 'fake_ntai15'})
    def test_clefs_hors_gabarit_ecartees(self):
        charge = dict(BULLETIN)
        charge['champ_invente'] = 'valeur bavarde'
        self._with_fake_ocr(charge)
        corps = self._poster('bulletin_paie').json()
        self.assertNotIn('champ_invente', corps['champs'])

    @override_settings(AI_PROVIDERS={})
    def test_sans_cle_ocr_degradation_douce(self):
        reponse = self._poster('bulletin_paie')
        self.assertEqual(reponse.status_code, 503)
        self.assertIn('saisie manuelle', reponse.json()['detail'])

    @override_settings(AI_PROVIDERS={'ocr': 'fake_ntai15'})
    def test_gabarit_inconnu_refuse(self):
        self._with_fake_ocr(BULLETIN)
        reponse = self._poster('gabarit_fantome')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('Gabarit inconnu', reponse.json()['detail'])

    @override_settings(AI_PROVIDERS={'ocr': 'fake_ntai15'})
    def test_format_non_reconnu_refuse(self):
        self._with_fake_ocr(BULLETIN)
        reponse = self._poster('bulletin_paie', contenu=b'texte brut')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('Format non reconnu', reponse.json()['detail'])

    def test_fichier_absent_refuse(self):
        reponse = auth(self.user).post(
            f'{URL}?schema=bulletin_paie', {}, format='multipart')
        self.assertEqual(reponse.status_code, 400)

    # --- NTAI16 : facture fournisseur + rapprochement ----------------------

    @override_settings(AI_PROVIDERS={'ocr': 'fake_ntai15'})
    def test_facture_rend_entete_lignes_et_rapprochement(self):
        self._with_fake_ocr(FACTURE)
        corps = self._poster('facture_fournisseur').json()
        self.assertEqual(corps['champs']['numero_facture'], 'FA-2026-118')
        self.assertEqual(len(corps['champs']['lignes']), 2)

        rapprochement = corps['rapprochement']
        self.assertEqual(len(rapprochement['lignes']), 2)
        self.assertEqual(rapprochement['total_ht_calcule'], '9600')
        self.assertEqual(rapprochement['total_ht_imprime'], '9600')
        self.assertEqual(rapprochement['ecart_total_ht'], '0')
        self.assertFalse(rapprochement['applique'])

    def test_ecart_de_total_signale_jamais_corrige(self):
        """Une facture qui ne s'additionne pas est SIGNALÉE, pas « réparée »."""
        champs = dict(FACTURE)
        champs['total_ht'] = '9700'  # 100 de plus que la somme des lignes
        rapprochement = rapprocher_facture(self.company, champs)
        self.assertEqual(rapprochement['total_ht_calcule'], '9600')
        self.assertEqual(rapprochement['ecart_total_ht'], '100')
        # Le total imprimé n'est PAS remplacé par le total calculé.
        self.assertEqual(rapprochement['total_ht_imprime'], '9700')

    def test_rapprochement_sans_lignes_ne_plante_pas(self):
        rapprochement = rapprocher_facture(self.company, {'total_ht': '100'})
        self.assertEqual(rapprochement['lignes'], [])
        self.assertIsNone(rapprochement['total_ht_calcule'])
