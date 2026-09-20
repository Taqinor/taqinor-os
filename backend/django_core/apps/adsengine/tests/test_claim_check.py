"""AGEN3 — Corpus rouge/vert du vérificateur whitelist numérique.

Prouve (dd-assumption-engine §10.2 point 2) : un FAUX chiffre est TOUJOURS
bloqué, un chiffre vérifié aux formats FR (``1 234,56``, ``82 %``,
``12 000 MAD``, ``6,4 kWc``) passe, et sans table publiée tout chiffre est
bloqué (zéro passage mou).
"""
from datetime import date

from django.test import TestCase

from authentication.models import Company
from apps.adsengine.models import CreativeAsset, FactEntry, FactTable
from apps.adsengine import claim_check


class ParseFrNumberTests(TestCase):
    def test_fr_formats(self):
        self.assertEqual(claim_check.parse_fr_number('12 000'), 12000.0)
        self.assertEqual(claim_check.parse_fr_number('1 234,56'), 1234.56)
        self.assertEqual(claim_check.parse_fr_number('82'), 82.0)
        self.assertEqual(claim_check.parse_fr_number('6,4'), 6.4)
        self.assertIsNone(claim_check.parse_fr_number('abc'))


class ExtractTests(TestCase):
    def test_extracts_number_and_unit(self):
        claims = claim_check.extract_number_units(
            'Économisez 12 000 MAD et 82 % d\'autoconsommation, 6,4 kWc.')
        by_frag = {c['fragment']: c for c in claims}
        self.assertEqual(by_frag['12 000']['unit'], 'MAD')
        self.assertEqual(by_frag['82']['unit'], '%')
        self.assertEqual(by_frag['6,4']['unit'], 'kWc')

    def test_extracts_compound_units_whole(self):
        # PUB-P8/C1 — l'unité COMPOSÉE est lue EN ENTIER (elle ne l'était qu'à
        # moitié : « kWh » pour « kWh/kWc/an »), sinon « 1750 kW » se comparait
        # par préfixe au fait « 1750 kWh/kWc/an ».
        claims = claim_check.extract_number_units(
            'Production 1750 kWh/kWc/an, mensualité 500 MAD/mois, '
            '4,5 kWh/kWc/jour.')
        by_frag = {c['fragment']: c['unit'] for c in claims}
        self.assertEqual(by_frag['1750'], 'kWh/kWc/an')
        self.assertEqual(by_frag['500'], 'MAD/mois')
        self.assertEqual(by_frag['4,5'], 'kWh/kWc/jour')

    def test_bare_unit_stays_bare(self):
        # « kW » reste « kW » (pas de composante inventée) et un mot ordinaire
        # de la phrase n'est jamais avalé comme composante d'unité.
        claims = claim_check.extract_number_units(
            '1750 kW, 500 MAD par mois, 3 ans.')
        by_frag = {c['fragment']: c['unit'] for c in claims}
        self.assertEqual(by_frag['1750'], 'kW')
        self.assertEqual(by_frag['500'], 'MAD')
        self.assertEqual(by_frag['3'], 'an')

    def test_unit_components_compare_at_the_boundary(self):
        self.assertEqual(claim_check.unit_components('kWh/kWc/an'),
                         ['kWh', 'kWc', 'an'])
        self.assertEqual(claim_check.unit_components('kwh/kwp/année'),
                         ['kWh', 'kWc', 'an'])
        self.assertEqual(claim_check.unit_components('m3/h'), ['m³', 'h'])
        self.assertEqual(claim_check.unit_components(''), [])
        # kW ≠ kWh (ni sa composée) ; MAD ≠ MAD/mois.
        self.assertNotEqual(claim_check.unit_components('kW'),
                            claim_check.unit_components('kWh'))
        self.assertNotEqual(claim_check.unit_components('kW'),
                            claim_check.unit_components('kWh/kWc/an'))
        self.assertNotEqual(claim_check.unit_components('MAD'),
                            claim_check.unit_components('MAD/mois'))


class VerifyTextTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Claim Co', slug='claim-co')
        table = FactTable.create_draft(self.company)
        FactEntry.objects.create(
            table=table, cle='economie', valeur='12 000', unite='MAD',
            source='étude', verifie_le=date(2026, 1, 1))
        FactEntry.objects.create(
            table=table, cle='autoconso', valeur='82', unite='%',
            source='étude', verifie_le=date(2026, 1, 1))
        FactEntry.objects.create(
            table=table, cle='puissance', valeur='6,4', unite='kWc',
            source='étude', verifie_le=date(2026, 1, 1))
        table.publish()
        self.table = table

    # ── VERT : chiffres présents dans la table ──
    def test_green_all_numbers_cited(self):
        result = claim_check.verify_text(
            self.company,
            'Économisez 12 000 MAD, 82 % d\'autoconsommation, 6,4 kWc.')
        self.assertTrue(result['ok'])
        self.assertEqual(result['violations'], [])
        self.assertEqual(len(result['matched']), 3)

    def test_green_text_without_numbers(self):
        result = claim_check.verify_text(
            self.company, 'Passez au solaire en toute sérénité.')
        self.assertTrue(result['ok'])

    # ── ROUGE : un faux chiffre est TOUJOURS bloqué ──
    def test_red_false_number_blocked(self):
        result = claim_check.verify_text(
            self.company, 'Économisez 99 999 MAD par an.')
        self.assertFalse(result['ok'])
        self.assertEqual(len(result['violations']), 1)
        self.assertIn('99 999', result['violations'][0]['reason'])

    def test_red_right_number_wrong_unit_blocked(self):
        # 82 existe mais en %, pas en MAD → l'unité doit coïncider.
        result = claim_check.verify_text(
            self.company, 'Payez seulement 82 MAD.')
        self.assertFalse(result['ok'])

    def test_red_no_published_table_blocks_all_numbers(self):
        other = Company.objects.create(nom='Vide', slug='vide')
        result = claim_check.verify_text(other, 'Économisez 12 000 MAD.')
        self.assertFalse(result['ok'])
        self.assertIn('aucune table', result['violations'][0]['reason'].lower())

    def test_verify_asset_uses_all_text_fields(self):
        asset = CreativeAsset.objects.create(
            company=self.company, asset_type='static',
            hook_text='82 %', primary_text='Économie 12 000 MAD',
            cta='6,4 kWc', policy_stamp={})
        self.assertTrue(claim_check.verify_asset(asset)['ok'])
