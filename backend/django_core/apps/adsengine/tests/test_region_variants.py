"""PUB85 — Variantes localisées par ville (dimension région sur FactEntry).

Prouve : une variante générée pour une ville cite le fait RÉGIONAL publié quand
il existe ; une ville sans fait régional retombe sur le fait NATIONAL (jamais un
chiffre local inventé — règle checked-facts-only).
"""
import datetime

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import generation
from apps.adsengine.models import FactEntry, FactTable


def _generator(variants):
    """Générateur injecté (déterministe) qui renvoie ``variants`` tels quels."""
    def _gen(_context):
        return variants
    return _gen


class RegionVariantTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Region Co', slug='region-co')
        self.table = FactTable.create_draft(self.company)
        self.table.publish()
        # Fait NATIONAL + surcharge RÉGIONALE (Marrakech) pour la même clé.
        FactEntry.objects.create(
            table=self.table, cle='production_kwh_kwc_an', valeur='1500',
            unite='kWh/kWc/an', source='national', verifie_le=datetime.date(2026, 1, 1))
        FactEntry.objects.create(
            table=self.table, cle='production_kwh_kwc_an', valeur='1750',
            unite='kWh/kWc/an', source='mesure locale', region='marrakech',
            verifie_le=datetime.date(2026, 1, 1))

    def test_resolve_facts_prefers_regional(self):
        facts = generation.resolve_facts_for_region(self.company, 'marrakech')
        self.assertEqual(facts['production_kwh_kwc_an'].valeur, '1750')
        self.assertEqual(facts['production_kwh_kwc_an'].region, 'marrakech')

    def test_resolve_facts_falls_back_to_national(self):
        facts = generation.resolve_facts_for_region(self.company, 'agadir')
        self.assertEqual(facts['production_kwh_kwc_an'].valeur, '1500')
        self.assertEqual(facts['production_kwh_kwc_an'].region, '')

    def test_city_variant_cites_regional_fact(self):
        variant = {
            'hook_text': 'À Marrakech, 1750 kWh/kWc/an',
            'claims': [{'fact_key': 'production_kwh_kwc_an'}],
        }
        res = generation.generate_grounded_variants(
            self.company, 'production locale', generator=_generator([variant]),
            region='marrakech', create_assets=False)
        self.assertEqual(res['region'], 'marrakech')
        report = res['variants'][0]
        self.assertTrue(report['grounded'])
        claim = report['claims'][0]
        self.assertEqual(claim['valeur'], '1750')  # valeur régionale citée
        self.assertEqual(claim['region'], 'marrakech')

    def test_city_without_fact_uses_national_variant(self):
        variant = {
            'hook_text': 'À Agadir, 1500 kWh/kWc/an',
            'claims': [{'fact_key': 'production_kwh_kwc_an'}],
        }
        res = generation.generate_grounded_variants(
            self.company, 'production locale', generator=_generator([variant]),
            region='agadir', create_assets=False)
        report = res['variants'][0]
        self.assertTrue(report['grounded'])
        claim = report['claims'][0]
        self.assertEqual(claim['valeur'], '1500')  # valeur nationale
        self.assertEqual(claim['region'], '')

    def test_regional_number_not_grounded_nationally(self):
        # Une variante citant le chiffre RÉGIONAL sans demander la région
        # (national) n'est PAS ancrée (le nombre local n'existe pas au national).
        variant = {
            'hook_text': '1750 kWh/kWc/an partout',
            'claims': [{'fact_key': 'production_kwh_kwc_an'}],
        }
        res = generation.generate_grounded_variants(
            self.company, 'x', generator=_generator([variant]),
            region=None, create_assets=False)
        report = res['variants'][0]
        self.assertFalse(report['grounded'])
        self.assertIn('1750', report['uncited_numbers'])
