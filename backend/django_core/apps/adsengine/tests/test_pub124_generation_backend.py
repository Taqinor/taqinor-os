"""PUB124 — Tests du BACKEND LLM RÉEL de ``generation.py``.

``_default_generator`` restait inerte MÊME avec sa clé (« aucun backend LLM
câblé ») : le pipeline PUB16 tournait à vide. Prouve :

  * résolution de clé ``ADSENGINE_GEN_API_KEY`` puis repli ``GROQ_API_KEY`` ;
  * SANS AUCUNE clé → NO-OP byte-identique (golden figé dans ce fichier) :
    aucun appel réseau, aucun asset, aucun lot ;
  * le prompt ne porte QUE le brief + les composants + les FAITS de la table
    PUBLIÉE (aucun autre chiffre, aucune donnée d'une autre société) ;
  * la sortie JSON est parsée en composants, une réponse illisible rend ZÉRO
    variante (jamais une variante fabriquée, jamais un crash) ;
  * le vérificateur AUTORITAIRE ``claim_check`` tranche : un chiffre inventé
    dans la sortie du backend mocké fait REJETER la variante, et son verdict
    est persisté dans l'audit du lot ;
  * la sortie n'est QUE des assets PENDING dans un lot EN ATTENTE — jamais une
    dépense, jamais une publication.
"""
import json
from datetime import date
from unittest import mock

from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import generation, tasks, tier_router
from apps.adsengine.models import (
    CreativeAsset, CreativeGenerationBatch, EngineAction, FactEntry, FactTable,
)

NO_ENV = {'ADSENGINE_GEN_API_KEY': '', 'GROQ_API_KEY': ''}


def publish_table(company):
    table = FactTable.create_draft(company)
    FactEntry.objects.create(
        table=table, company=company, cle='economie_annuelle',
        valeur='12 000', unite='MAD', source='étude interne',
        verifie_le=date(2026, 1, 1))
    FactEntry.objects.create(
        table=table, company=company, cle='autoconsommation', valeur='82',
        unite='%', source='RedaSolar', verifie_le=date(2026, 1, 1))
    table.publish()
    return table


class KeyResolutionTests(SimpleTestCase):
    @mock.patch.dict('os.environ', {'ADSENGINE_GEN_API_KEY': 'dedicated',
                                    'GROQ_API_KEY': 'shared'})
    def test_dedicated_key_wins(self):
        self.assertEqual(generation.resolve_api_key(),
                         ('dedicated', 'ADSENGINE_GEN_API_KEY'))

    @mock.patch.dict('os.environ', {'ADSENGINE_GEN_API_KEY': '',
                                    'GROQ_API_KEY': 'shared'})
    def test_groq_key_is_the_fallback(self):
        self.assertEqual(generation.resolve_api_key(),
                         ('shared', 'GROQ_API_KEY'))

    @mock.patch.dict('os.environ', NO_ENV)
    def test_no_key_at_all(self):
        self.assertEqual(generation.resolve_api_key(), ('', ''))
        self.assertIsNone(generation._default_generator())

    @mock.patch.dict('os.environ', {'ADSENGINE_GEN_MODEL': 'mon-modele',
                                    'ADSENGINE_GEN_BASE_URL': 'https://x/v1/'})
    def test_model_and_base_url_are_env_configurable(self):
        self.assertEqual(generation.gen_model(), 'mon-modele')
        self.assertEqual(generation.gen_base_url(), 'https://x/v1')

    @mock.patch.dict('os.environ', {'ADSENGINE_GEN_MODEL': '',
                                    'ADSENGINE_GEN_BASE_URL': ''})
    def test_defaults_match_the_repo_existing_groq_caller(self):
        # Mêmes valeurs que l'unique autre appelant LLM du dépôt (apps/qhse).
        self.assertEqual(generation.gen_base_url(),
                         'https://api.groq.com/openai/v1')
        self.assertEqual(generation.gen_model(), 'llama-3.1-8b-instant')

    @mock.patch.dict('os.environ', {'ADSENGINE_GEN_API_KEY': 'secret-123',
                                    'GROQ_API_KEY': ''})
    def test_backend_status_never_exposes_the_key(self):
        status = generation.backend_status()
        self.assertTrue(status['enabled'])
        self.assertEqual(status['key_env'], 'ADSENGINE_GEN_API_KEY')
        self.assertNotIn('secret-123', json.dumps(status))


class PromptTests(SimpleTestCase):
    def test_prompt_carries_only_brief_components_and_published_facts(self):
        messages = generation.build_messages({
            'seed_brief': 'panneaux solaires économies maison sud',
            'region': 'marrakech',
            'components': ['hook facture'],
            'facts': [{'cle': 'autoconsommation', 'valeur': '82',
                       'unite': '%', 'region': ''}],
            'asset_type': 'static',
            'max_variants': 3,
        })
        self.assertEqual(messages[0]['role'], 'system')
        self.assertIn('RÈGLE ABSOLUE', messages[0]['content'])
        self.assertIn('ACCROCHE', messages[0]['content'])
        payload = json.loads(messages[1]['content'])
        self.assertEqual(set(payload), {
            'brief', 'region', 'composants_approuves', 'faits',
            'nombre_de_variantes', 'type_asset'})
        self.assertEqual(payload['faits'], [
            {'cle': 'autoconsommation', 'valeur': '82', 'unite': '%',
             'region': ''}])
        # Le SEUL chiffre du prompt est celui de la table publiée.
        self.assertNotIn('12 000', messages[1]['content'])


class ParseVariantsTests(SimpleTestCase):
    def test_parses_the_documented_shape(self):
        variants = generation.parse_variants(json.dumps({'variants': [{
            'hook_text': 'Jusqu\'à 82 % d\'autoconsommation',
            'primary_text': 'Économisez 12 000 MAD par an.',
            'cta': 'Devis gratuit', 'hook_tag': 'FACTURE',
            'angle_tag': 'ROI',
            'claims': [{'fact_key': 'autoconsommation'},
                       {'fact_key': 'economie_annuelle'}],
        }]}))
        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0]['hook_tag'], 'FACTURE')
        self.assertEqual(variants[0]['claims'],
                         [{'fact_key': 'autoconsommation'},
                          {'fact_key': 'economie_annuelle'}])

    def test_bare_list_is_accepted(self):
        variants = generation.parse_variants(
            json.dumps([{'hook_text': 'A', 'claims': []}]))
        self.assertEqual(len(variants), 1)

    def test_claims_given_as_plain_strings_are_normalised(self):
        variants = generation.parse_variants(json.dumps({'variants': [
            {'hook_text': 'A', 'claims': ['economie_annuelle']}]}))
        self.assertEqual(variants[0]['claims'],
                         [{'fact_key': 'economie_annuelle'}])

    def test_unknown_keys_are_dropped(self):
        variants = generation.parse_variants(json.dumps({'variants': [
            {'hook_text': 'A', 'policy_stamp': {'passed': True},
             'company': 99, 'claims': []}]}))
        self.assertEqual(set(variants[0]), {'hook_text', 'claims'})

    def test_max_variants_is_enforced(self):
        variants = generation.parse_variants(
            json.dumps({'variants': [{'hook_text': f'A{i}', 'claims': []}
                                     for i in range(9)]}),
            max_variants=2)
        self.assertEqual(len(variants), 2)

    def test_unreadable_output_yields_zero_variants(self):
        self.assertEqual(generation.parse_variants('pas du json'), [])
        self.assertEqual(generation.parse_variants('{"autre": 1}'), [])
        self.assertEqual(generation.parse_variants(None), [])

    def test_empty_variant_is_dropped(self):
        self.assertEqual(
            generation.parse_variants(json.dumps({'variants': [
                {'cta': 'Devis', 'claims': []}]})),
            [])


class LlmCallTests(SimpleTestCase):
    def _response(self, content, *, status_ok=True):
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            'choices': [{'message': {'content': content}}]}
        return resp

    @mock.patch.dict('os.environ', {'ADSENGINE_GEN_API_KEY': 'k',
                                    'ADSENGINE_GEN_MODEL': '',
                                    'ADSENGINE_GEN_BASE_URL': ''})
    def test_request_shape_matches_the_openai_compatible_contract(self):
        content = json.dumps({'variants': [{'hook_text': 'A', 'claims': []}]})
        with mock.patch('requests.post',
                        return_value=self._response(content)) as post:
            variants = generation.call_llm_variants(
                {'seed_brief': 'un deux trois', 'facts': [],
                 'max_variants': 3})
        self.assertEqual(len(variants), 1)
        self.assertEqual(post.call_count, 1)
        url = post.call_args.args[0]
        self.assertIn('/chat/completions', url)
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'],
                         'Bearer k')
        body = post.call_args.kwargs['json']
        self.assertEqual(body['model'], 'llama-3.1-8b-instant')
        self.assertEqual(body['temperature'], 0)
        self.assertEqual(body['response_format'], {'type': 'json_object'})
        self.assertEqual(body['messages'][0]['role'], 'system')

    @mock.patch.dict('os.environ', {'ADSENGINE_GEN_API_KEY': 'k'})
    def test_network_failure_becomes_a_backend_error(self):
        with mock.patch('requests.post', side_effect=OSError('boom')):
            with self.assertRaises(generation.GenerationBackendError):
                generation.call_llm_variants({'seed_brief': 'x', 'facts': []})

    @mock.patch.dict('os.environ', {'ADSENGINE_GEN_API_KEY': 'k'})
    def test_response_without_content_becomes_a_backend_error(self):
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {'choices': []}
        with mock.patch('requests.post', return_value=resp):
            with self.assertRaises(generation.GenerationBackendError):
                generation.call_llm_variants({'seed_brief': 'x', 'facts': []})

    @mock.patch.dict('os.environ', {'ADSENGINE_GEN_API_KEY': 'k'})
    def test_default_generator_never_raises_and_yields_zero_variants(self):
        gen = generation._default_generator()
        self.assertIsNotNone(gen)
        with mock.patch('requests.post', side_effect=OSError('boom')):
            self.assertEqual(gen({'seed_brief': 'x', 'facts': []}), [])

    @mock.patch.dict('os.environ', NO_ENV)
    def test_no_key_never_calls_the_network(self):
        with mock.patch('requests.post') as post:
            with self.assertRaises(generation.GenerationBackendError):
                generation.call_llm_variants({'seed_brief': 'x', 'facts': []})
        post.assert_not_called()


class NoKeyGoldenTests(TestCase):
    """Sans AUCUNE clé, le NO-OP est byte-identique (golden figé)."""

    def setUp(self):
        self.company = Company.objects.create(nom='Gen Co', slug='gen-pub124')
        publish_table(self.company)

    @mock.patch.dict('os.environ', NO_ENV)
    def test_golden_noop_result_is_unchanged(self):
        with mock.patch('requests.post') as post:
            result = generation.generate_grounded_variants(
                self.company, 'panneaux solaires économies maison sud')
        post.assert_not_called()
        self.assertEqual(result, {
            'enabled': False, 'table_version': None,
            'variants': [], 'assets': [], 'rejected': [],
            'reason': 'ADSENGINE_GEN_API_KEY absent — génération désactivée',
        })
        self.assertEqual(CreativeAsset.objects.count(), 0)

    @mock.patch.dict('os.environ', NO_ENV)
    def test_task_noop_creates_no_batch(self):
        result = tasks._run_grounded_generation(
            self.company, 'panneaux solaires économies maison sud')
        self.assertFalse(result['enabled'])
        self.assertIsNone(result['batch_id'])
        self.assertEqual(CreativeGenerationBatch.objects.count(), 0)


class ClaimCheckArbitratesTests(TestCase):
    """Le claim_check EXISTANT tranche la sortie du backend."""

    def setUp(self):
        self.company = Company.objects.create(nom='Gen Co', slug='gen-pub124b')
        publish_table(self.company)

    def _run(self, content, **kw):
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            'choices': [{'message': {'content': content}}]}
        env = {'ADSENGINE_GEN_API_KEY': 'k', 'GROQ_API_KEY': ''}
        with mock.patch.dict('os.environ', env):
            with mock.patch('requests.post', return_value=resp):
                return tasks._run_grounded_generation(
                    self.company, 'panneaux solaires économies maison sud',
                    **kw)

    def test_grounded_variant_becomes_a_pending_asset_in_a_pending_batch(self):
        content = json.dumps({'variants': [{
            'hook_text': "Jusqu'à 82 % d'autoconsommation",
            'primary_text': 'Économisez 12 000 MAD par an.',
            'cta': 'Devis gratuit', 'hook_tag': 'FACTURE',
            'claims': [{'fact_key': 'autoconsommation'},
                       {'fact_key': 'economie_annuelle'}],
        }]})
        result = self._run(content)
        self.assertTrue(result['enabled'])
        self.assertEqual(result['assets'], 1)
        self.assertEqual(result['rejected'], 0)

        asset = CreativeAsset.objects.get(company=self.company)
        # PENDING. PUB125 — le tampon porte désormais le verdict de ROUTAGE
        # (pré-linter policy + palier), écrit sur le chemin réel ; la FRONTIÈRE
        # tient : ce routage ne pose JAMAIS ``passed`` (la check-list policy reste
        # un jugement HUMAIN), donc l'asset n'est toujours pas validé.
        self.assertNotIn('passed', asset.policy_stamp)
        self.assertEqual(asset.policy_stamp['tier'], tier_router.TIER_B)
        self.assertTrue(asset.policy_stamp['revue_humaine'])
        self.assertTrue(asset.policy_stamp['policy_lint']['ok'])
        self.assertFalse(asset.is_policy_passed)
        self.assertTrue(asset.ai_generated)        # PUB126 — lane « gen »
        self.assertEqual(asset.facts_version, 1)

        batch = CreativeGenerationBatch.objects.get(company=self.company)
        self.assertEqual(batch.status,
                         CreativeGenerationBatch.Statut.EN_ATTENTE)
        self.assertEqual(batch.fact_table_version, 1)
        verdicts = batch.claim_verdicts['variants'][0]['claim_verdicts']
        self.assertTrue(verdicts['ok'])
        self.assertEqual(
            {m['fact_key'] for m in verdicts['matched']},
            {'autoconsommation', 'economie_annuelle'})
        # Le backend est imputable, sans jamais la clé.
        self.assertEqual(batch.claim_verdicts['backend']['key_env'],
                         'ADSENGINE_GEN_API_KEY')
        # Aucune dépense, aucune publication : zéro EngineAction.
        self.assertEqual(EngineAction.objects.count(), 0)

    def test_invented_number_is_rejected_and_audited(self):
        content = json.dumps({'variants': [{
            'hook_text': 'Économisez 99 999 MAD par an',
            'primary_text': 'Offre exceptionnelle.',
            'cta': 'Devis',
            # Le modèle CITE une clé réelle mais écrit un chiffre absent : la
            # whitelist dure le voit, la variante tombe.
            'claims': [{'fact_key': 'economie_annuelle'}],
        }]})
        result = self._run(content)
        self.assertEqual(result['assets'], 0)
        self.assertEqual(result['rejected'], 1)
        self.assertEqual(CreativeAsset.objects.count(), 0)

        batch = CreativeGenerationBatch.objects.get(company=self.company)
        rejected = batch.claim_verdicts['rejected'][0]
        self.assertFalse(rejected['claim_verdicts']['ok'])
        self.assertIn(
            '99 999',
            rejected['claim_verdicts']['violations'][0]['fragment'])

    def test_right_number_wrong_unit_is_rejected(self):
        # Le chiffre 82 EXISTE (autoconsommation, en %), mais l'écrire « 82 MAD »
        # est un mensonge d'unité : la garde d'ancrage interne (qui ne compare
        # que les chiffres) le laissait passer — claim_check le barre.
        content = json.dumps({'variants': [{
            'hook_text': 'Seulement 82 MAD par mois',
            'primary_text': 'Offre solaire.', 'cta': 'Devis',
            'claims': [{'fact_key': 'autoconsommation'}],
        }]})
        result = self._run(content)
        self.assertEqual(result['assets'], 0)
        self.assertEqual(result['rejected'], 1)
        batch = CreativeGenerationBatch.objects.get(company=self.company)
        rejected = batch.claim_verdicts['rejected'][0]
        self.assertTrue(rejected['claim_violations_dures'])
        self.assertEqual(
            rejected['claim_violations_dures'][0]['unit'], 'MAD')

    def test_compound_unit_notation_is_not_a_hallucination(self):
        # « 12 000 MAD » cité par son fait : aucune violation dure.
        content = json.dumps({'variants': [{
            'hook_text': 'Économisez 12 000 MAD par an',
            'primary_text': '', 'cta': 'Devis',
            'claims': [{'fact_key': 'economie_annuelle'}],
        }]})
        result = self._run(content)
        self.assertEqual(result['assets'], 1)
        batch = CreativeGenerationBatch.objects.get(company=self.company)
        self.assertEqual(
            batch.claim_verdicts['variants'][0]['claim_violations_dures'], [])

    def test_unreadable_backend_output_creates_an_empty_batch_not_a_crash(self):
        result = self._run('je ne sais pas répondre en JSON')
        self.assertTrue(result['enabled'])
        self.assertEqual(result['assets'], 0)
        self.assertEqual(CreativeAsset.objects.count(), 0)

    def test_text_without_numbers_passes_both_guards(self):
        content = json.dumps({'variants': [{
            'hook_text': 'Passez au solaire', 'primary_text': 'Sérénité.',
            'cta': 'Contactez-nous', 'claims': [],
        }]})
        result = self._run(content)
        self.assertEqual(result['assets'], 1)
