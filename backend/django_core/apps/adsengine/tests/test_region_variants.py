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


class UnitBoundaryTests(TestCase):
    """PUB-P8/C1 — l'unité se compare à la FRONTIÈRE, jamais par préfixe.

    La tolérance ``_hard_claim_violations`` acceptait ``fact_unit.startswith
    (unit)`` : un fait « 1750 kWh/kWc/an » cité « 1750 kW » (une PUISSANCE
    vendue pour une PRODUCTION annuelle) et un fait « 500 MAD/mois » cité
    « 500 MAD » (une mensualité vendue en prix flat) passaient tous deux. Les
    deux sont désormais REJETÉS, et le cas PUB85 légitime — le texte porte
    l'unité composée ENTIÈRE — reste accepté.
    """

    def setUp(self):
        self.company = Company.objects.create(nom='Unit Co', slug='unit-co')
        self.table = FactTable.create_draft(self.company)
        self.table.publish()
        FactEntry.objects.create(
            table=self.table, cle='production_kwh_kwc_an', valeur='1750',
            unite='kWh/kWc/an', source='mesure',
            verifie_le=datetime.date(2026, 1, 1))
        FactEntry.objects.create(
            table=self.table, cle='mensualite', valeur='500',
            unite='MAD/mois', source='offre financement',
            verifie_le=datetime.date(2026, 1, 1))

    def _report(self, hook_text, fact_key):
        res = generation.generate_grounded_variants(
            self.company, 'x', create_assets=False,
            generator=_generator([{
                'hook_text': hook_text,
                'claims': [{'fact_key': fact_key}]}]))
        return res['variants'][0]

    def test_full_compound_unit_is_accepted(self):
        # PUB85 — le texte porte « kWh/kWc/an » EN ENTIER : aucune violation.
        report = self._report('1750 kWh/kWc/an chez vous',
                              'production_kwh_kwc_an')
        self.assertTrue(report['grounded'])
        self.assertEqual(report['claim_violations_dures'], [])
        self.assertTrue(report['claim_verdicts']['ok'])

    def test_kw_cited_against_kwh_per_kwc_per_year_is_rejected(self):
        # « kW » (puissance) n'est PAS la tête tolérable de « kWh/kWc/an ».
        report = self._report('1750 kW garantis', 'production_kwh_kwc_an')
        self.assertFalse(report['grounded'])
        self.assertEqual(
            [v['unit'] for v in report['claim_violations_dures']], ['kW'])

    def test_bare_kwh_cited_against_compound_fact_is_rejected(self):
        # Le fait porte une unité COMPOSÉE : le texte doit la porter ENTIÈRE.
        # « 1750 kWh » (une énergie) n'est pas « 1750 kWh/kWc/an » (un
        # rendement) — choix documenté : PUB85 écrit l'unité complète, la
        # tolérance n'a donc plus à couvrir la tête nue.
        report = self._report('1750 kWh par an', 'production_kwh_kwc_an')
        self.assertFalse(report['grounded'])
        self.assertEqual(
            [v['unit'] for v in report['claim_violations_dures']], ['kWh'])

    def test_bare_mad_cited_against_mad_per_month_is_rejected(self):
        # Mensualité vendue en prix flat : mensonge de prix, jamais une notation.
        report = self._report('Seulement 500 MAD', 'mensualite')
        self.assertFalse(report['grounded'])
        self.assertEqual(
            [v['unit'] for v in report['claim_violations_dures']], ['MAD'])

    def test_full_mad_per_month_is_accepted(self):
        report = self._report('Seulement 500 MAD/mois', 'mensualite')
        self.assertTrue(report['grounded'])
        self.assertEqual(report['claim_violations_dures'], [])
