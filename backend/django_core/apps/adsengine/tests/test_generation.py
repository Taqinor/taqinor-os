"""AGEN2 — Tests de la génération ANCRÉE (``generation.py``).

Prouve (dd-assumption-engine §10.2 point 1) :
  * NO-OP propre sans clé et sans générateur injecté (aucun asset).
  * un *seed-brief* de 5 mots → des variantes conformes (chaque chiffre cité)
    deviennent des ``CreativeAsset`` PENDING (``policy_stamp={}``).
  * TOUT chiffre sans citation → la variante ÉCHOUE (aucun asset créé).
  * une citation vers une clé inexistante → échec.
"""
from datetime import date

from django.test import TestCase

from authentication.models import Company
from apps.adsengine.models import CreativeAsset, FactEntry, FactTable
from apps.adsengine import generation


def _publish_table(company):
    table = FactTable.create_draft(company)
    FactEntry.objects.create(
        table=table, cle='economie_annuelle', valeur='12 000',
        unite='MAD', source='étude interne', verifie_le=date(2026, 1, 1))
    FactEntry.objects.create(
        table=table, cle='autoconsommation', valeur='82',
        unite='%', source='RedaSolar', verifie_le=date(2026, 1, 1))
    table.publish()
    return table


class GenerationNoKeyTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Gen Co', slug='gen-co')

    def test_no_key_no_generator_is_noop(self):
        _publish_table(self.company)
        result = generation.generate_grounded_variants(
            self.company, 'panneaux solaires économies maison sud')
        self.assertFalse(result['enabled'])
        self.assertEqual(result['assets'], [])
        self.assertEqual(result['variants'], [])
        self.assertEqual(CreativeAsset.objects.count(), 0)


class GenerationGroundingTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Gen Co', slug='gen-co')
        self.table = _publish_table(self.company)

    def test_five_word_brief_yields_conformant_variants(self):
        # « quelques mots » = 5 mots ; le générateur mock rend une variante
        # dont chaque chiffre cite une FactEntry publiée.
        def mock_gen(context):
            self.assertEqual(len(context['seed_brief'].split()), 5)
            return [{
                'asset_type': 'static',
                'hook_text': 'Jusqu\'à 82 % d\'autoconsommation',
                'primary_text': 'Économisez 12 000 MAD par an.',
                'cta': 'Devis gratuit',
                'claims': [
                    {'fact_key': 'autoconsommation'},
                    {'fact_key': 'economie_annuelle'},
                ],
            }]

        result = generation.generate_grounded_variants(
            self.company, 'panneaux solaires économies maison sud',
            generator=mock_gen)
        self.assertTrue(result['enabled'])
        self.assertEqual(len(result['assets']), 1)
        self.assertEqual(result['rejected'], [])
        asset = result['assets'][0]
        self.assertEqual(asset.policy_stamp, {})  # PENDING
        self.assertFalse(asset.is_policy_passed)
        self.assertTrue(result['variants'][0]['grounded'])

    def test_number_without_citation_fails(self):
        def mock_gen(context):
            return [{
                'asset_type': 'static',
                'hook_text': 'Économisez 99 999 MAD',  # chiffre non cité
                'primary_text': '',
                'cta': 'Devis',
                'claims': [],
            }]

        result = generation.generate_grounded_variants(
            self.company, 'un deux trois quatre cinq', generator=mock_gen)
        self.assertEqual(result['assets'], [])
        self.assertEqual(len(result['rejected']), 1)
        self.assertIn('99 999', result['rejected'][0]['uncited_numbers'])
        self.assertEqual(CreativeAsset.objects.count(), 0)

    def test_citation_to_unknown_key_fails(self):
        def mock_gen(context):
            return [{
                'hook_text': 'Autoconsommation 82 %',
                'primary_text': '',
                'cta': '',
                'claims': [{'fact_key': 'cle_inexistante'}],
            }]

        result = generation.generate_grounded_variants(
            self.company, 'un deux trois quatre cinq', generator=mock_gen)
        self.assertEqual(result['assets'], [])
        self.assertIn('cle_inexistante',
                      result['rejected'][0]['unknown_keys'])

    def test_text_without_numbers_is_grounded(self):
        def mock_gen(context):
            return [{
                'hook_text': 'Passez au solaire',
                'primary_text': 'Confort et sérénité.',
                'cta': 'Contactez-nous',
                'claims': [],
            }]

        result = generation.generate_grounded_variants(
            self.company, 'un deux trois quatre cinq', generator=mock_gen)
        self.assertEqual(len(result['assets']), 1)
        self.assertTrue(result['variants'][0]['grounded'])
