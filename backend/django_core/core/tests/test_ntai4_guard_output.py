"""NTAI4 — Tests du garde des sorties génératives.

Couvre : une citation de table hors allowlist BLOQUE la sortie, un contenu
inapproprié est filtré, une sortie trop longue est bornée, le happy-path
ressort inchangé, et le garde est inerte sans LLM (chemin NO-OP).
"""
from django.test import SimpleTestCase, override_settings

from core.ai import AIResult, LLMProvider, register_provider
from core.ai import registry
from core.ai.services import (GUARD_TRONCATURE, draft_reply, guard_output,
                              summarize_thread, tables_citees)

FIL = [{'auteur': 'Client', 'texte': 'Bonjour, où en est mon devis ?'}]


class FakeGardeLLM(LLMProvider):
    key = 'fake_ntai4'
    #: Texte que le faux fournisseur renvoie (piloté par chaque test).
    sortie = 'Bonjour, votre devis est en préparation.'

    def is_configured(self):
        return True

    def complete(self, *, prompt, system=None, max_tokens=512):
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'text': FakeGardeLLM.sortie})


class Ntai4GuardOutputTests(SimpleTestCase):

    def _with_fake_llm(self, sortie):
        FakeGardeLLM.sortie = sortie
        register_provider(FakeGardeLLM)
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_ntai4', None))

    # --- Règle (a) : références hors périmètre ------------------------------

    def test_table_hors_allowlist_bloque(self):
        garde = guard_output('La donnée vient de crm.lead et de secret.table.',
                             allowlist_tables={'crm.lead'})
        self.assertTrue(garde.bloque)
        self.assertFalse(garde.utilisable)
        self.assertIn('secret.table', ' '.join(garde.motifs))

    def test_table_dans_l_allowlist_passe(self):
        garde = guard_output('Voir crm.lead pour le détail.',
                             allowlist_tables={'crm.lead'})
        self.assertFalse(garde.bloque)

    def test_sans_allowlist_la_regle_est_desactivee(self):
        """Un brouillon client n'a pas d'allowlist : rien n'est bloqué."""
        garde = guard_output('Voir table.inconnue pour le détail.')
        self.assertFalse(garde.bloque)

    def test_tables_citees_repere_sql_et_pointe(self):
        trouvees = tables_citees('SELECT * FROM devis JOIN crm.lead')
        self.assertIn('devis', trouvees)
        self.assertIn('crm.lead', trouvees)

    # --- Règle (b) : lexique ------------------------------------------------

    @override_settings(AI_TOXIC_TERMS=['abruti'])
    def test_contenu_inapproprie_filtre(self):
        garde = guard_output('Ce client est un abruti fini.')
        self.assertNotIn('abruti', garde.texte)
        self.assertIn('***', garde.texte)
        self.assertTrue(garde.modifie)
        self.assertFalse(garde.bloque)

    @override_settings(AI_TOXIC_TERMS=['abruti'])
    def test_filtrage_insensible_a_la_casse(self):
        self.assertNotIn('Abruti', guard_output('Quel Abruti.').texte)

    # --- Règle (c) : longueur -----------------------------------------------

    def test_sortie_trop_longue_bornee(self):
        garde = guard_output('A' * 50, max_chars=20)
        self.assertTrue(garde.texte.endswith(GUARD_TRONCATURE))
        self.assertLessEqual(len(garde.texte),
                             20 + len(GUARD_TRONCATURE))
        self.assertTrue(garde.modifie)

    # --- Happy path & inertie ----------------------------------------------

    def test_happy_path_inchange(self):
        texte = 'Bonjour, votre devis est prêt. Bien cordialement.'
        garde = guard_output(texte)
        self.assertEqual(garde.texte, texte)
        self.assertFalse(garde.modifie)
        self.assertFalse(garde.bloque)
        self.assertEqual(garde.motifs, [])

    def test_texte_vide_inerte(self):
        garde = guard_output('')
        self.assertEqual(garde.texte, '')
        self.assertFalse(garde.bloque)
        self.assertEqual(garde.motifs, [])

    # --- Application aux services génératifs --------------------------------

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai4'},
                       AI_TOXIC_TERMS=['abruti'])
    def test_draft_reply_filtre_la_sortie(self):
        self._with_fake_llm('Bonjour abruti, votre devis arrive.')
        draft = draft_reply(FIL, channel='email')
        self.assertTrue(draft.available)
        self.assertNotIn('abruti', draft.draft)

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai4'})
    def test_draft_reply_bloque_une_reference_hors_perimetre(self):
        self._with_fake_llm('Données tirées de secret.table.')
        draft = draft_reply(FIL, channel='email',
                            allowlist_tables={'crm.lead'})
        self.assertFalse(draft.available)
        self.assertTrue(draft.configured)
        self.assertEqual(draft.draft, '')

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai4'},
                       AI_TOXIC_TERMS=['abruti'])
    def test_summarize_thread_filtre_la_sortie(self):
        self._with_fake_llm('Le client abruti attend son devis.')
        synthese = summarize_thread(FIL)
        self.assertTrue(synthese.available)
        self.assertNotIn('abruti', synthese.summary)

    @override_settings(AI_PROVIDERS={})
    def test_sans_llm_le_garde_est_inerte(self):
        draft = draft_reply(FIL, channel='email')
        self.assertFalse(draft.configured)
        self.assertEqual(draft.draft, '')
