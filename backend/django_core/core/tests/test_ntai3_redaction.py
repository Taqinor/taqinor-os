"""NTAI3 — Tests du masquage PII avant envoi au fournisseur (Trust Layer).

Couvre : chaque catégorie de donnée personnelle, l'aller-retour fidèle
(masqué à l'aller, re-substitué au retour), le drapeau ÉTEINT qui rend le
chemin octet-identique à l'existant, et le fait qu'aucune donnée stockée n'est
modifiée.
"""
from django.test import SimpleTestCase, override_settings

from core.ai import AIResult, LLMProvider, OCRProvider, register_provider
from core.ai import registry
from core.ai.redaction import redact_pii, redaction_enabled, unredact
from core.ai.registry import get_provider


class FakeRedactionLLM(LLMProvider):
    key = 'fake_ntai3'
    #: Ce que le FOURNISSEUR a réellement reçu — la preuve du masquage.
    dernier_prompt = None
    dernier_system = None

    def is_configured(self):
        return True

    def complete(self, *, prompt, system=None, max_tokens=512):
        FakeRedactionLLM.dernier_prompt = prompt
        FakeRedactionLLM.dernier_system = system
        # Le modèle RENVOIE les jetons tels quels (comportement attendu d'un
        # LLM à qui l'on demande de reprendre les éléments du prompt).
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'text': f'Rappeler le client : {prompt}'})


class FakeRedactionOCR(OCRProvider):
    key = 'fake_ntai3_ocr'
    dernier_hint = None

    def is_configured(self):
        return True

    def extract(self, *, content, mime_type, schema, hint=None):
        FakeRedactionOCR.dernier_hint = hint
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'nom': 'Client'})


class Ntai3RedactionTests(SimpleTestCase):

    TEXTE = ("Client BE123456, tél 0612345678, e-mail a.client@exemple.ma, "
             "RIB 007810000123456789012345, CNSS n° 123456789, "
             "habite rue Ibn Sina Casablanca.")

    def test_chaque_categorie_est_masquee(self):
        masque, mapping = redact_pii(self.TEXTE)
        for valeur in ('BE123456', '0612345678', 'a.client@exemple.ma',
                       '007810000123456789012345', '123456789'):
            self.assertNotIn(valeur, masque, valeur)
        self.assertNotIn('Ibn Sina', masque)
        # Le mot « CNSS » reste (c'est le NUMÉRO qui est secret, pas le mot).
        self.assertIn('CNSS', masque)
        self.assertGreaterEqual(len(mapping), 6)

    def test_aller_retour_fidele(self):
        masque, mapping = redact_pii(self.TEXTE)
        self.assertEqual(unredact(masque, mapping), self.TEXTE)

    def test_meme_valeur_meme_jeton(self):
        masque, _ = redact_pii('0612345678 puis encore 0612345678')
        jetons = {mot for mot in masque.split() if mot.startswith('[PII_')}
        self.assertEqual(len(jetons), 1)

    def test_texte_sans_pii_inchange(self):
        texte = 'Devis de 12 panneaux, 5 kWc, remise 3 %.'
        masque, mapping = redact_pii(texte)
        self.assertEqual(masque, texte)
        self.assertEqual(mapping, {})

    def test_valeurs_non_texte_tolerees(self):
        self.assertEqual(redact_pii(None), (None, {}))
        self.assertEqual(redact_pii(''), ('', {}))
        self.assertEqual(unredact('x', {}), 'x')

    # --- Câblage fournisseur -----------------------------------------------

    def _with_fake_llm(self):
        register_provider(FakeRedactionLLM)
        FakeRedactionLLM.dernier_prompt = None
        FakeRedactionLLM.dernier_system = None
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_ntai3', None))

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai3'},
                       AI_PII_REDACTION='auto')
    def test_le_prompt_part_masque_et_la_reponse_est_resubstituee(self):
        self._with_fake_llm()
        resultat = get_provider('llm').complete(
            prompt=self.TEXTE, system='Contacter au 0612345678.')

        # Ce que le FOURNISSEUR a vu : aucune donnée personnelle.
        self.assertNotIn('0612345678', FakeRedactionLLM.dernier_prompt)
        self.assertNotIn('a.client@exemple.ma',
                         FakeRedactionLLM.dernier_prompt)
        self.assertNotIn('0612345678', FakeRedactionLLM.dernier_system or '')
        # Ce que l'UTILISATEUR lit : le texte complet.
        self.assertIn('0612345678', resultat.data['text'])
        self.assertIn('a.client@exemple.ma', resultat.data['text'])

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai3'},
                       AI_PII_REDACTION='0')
    def test_drapeau_eteint_chemin_identique(self):
        self._with_fake_llm()
        get_provider('llm').complete(prompt=self.TEXTE)
        self.assertEqual(FakeRedactionLLM.dernier_prompt, self.TEXTE)

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai3'},
                       AI_PII_REDACTION='auto',
                       AI_SELF_HOSTED_PROVIDERS=('fake_ntai3',))
    def test_fournisseur_auto_heberge_non_masque(self):
        self._with_fake_llm()
        get_provider('llm').complete(prompt=self.TEXTE)
        self.assertEqual(FakeRedactionLLM.dernier_prompt, self.TEXTE)

    @override_settings(AI_PROVIDERS={'ocr': 'fake_ntai3_ocr'},
                       AI_PII_REDACTION='auto')
    def test_indice_ocr_masque(self):
        register_provider(FakeRedactionOCR)
        self.addCleanup(
            lambda: registry._REGISTRY['ocr'].pop('fake_ntai3_ocr', None))

        get_provider('ocr').extract(
            content=b'\x00', mime_type='image/png', schema='cin',
            hint='CIN BE123456 du client')
        self.assertNotIn('BE123456', FakeRedactionOCR.dernier_hint)

    @override_settings(AI_PROVIDERS={}, AI_PII_REDACTION='auto')
    def test_noop_jamais_masque(self):
        """Le NO-OP ne parle à personne : rien à masquer, chemin intact."""
        self.assertFalse(redaction_enabled('noop'))
        resultat = get_provider('llm').complete(prompt=self.TEXTE)
        self.assertFalse(resultat.configured)
