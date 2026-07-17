"""ADSDEEP21 — Tests du parser de noms Odoo : extraction form/campagne/date ;
les deals ESTIMÉS (sans match téléphone) sont SÉPARÉS des attribués exacts et
toujours étiquetés « estimation ».
"""
from django.test import SimpleTestCase

from apps.adsengine.odoo_selectors import (
    estimated_attribution_from_names, parse_odoo_lead_name,
)


class ParseNameTests(SimpleTestCase):
    def test_parses_agency_form_and_date(self):
        parsed = parse_odoo_lead_name('DAZZLEMEDAI-TAQINOR FORM-26/03/2026')
        self.assertEqual(parsed['source'], 'DAZZLEMEDAI')
        self.assertEqual(parsed['form_hint'], 'TAQINOR FORM')
        self.assertEqual(parsed['date'], '26/03/2026')
        self.assertIn('DAZZLEMEDAI', parsed['campaign_hint'])

    def test_empty_or_useless_name_is_none(self):
        self.assertIsNone(parse_odoo_lead_name(''))
        self.assertIsNone(parse_odoo_lead_name(None))

    def test_name_without_form_still_parses_source(self):
        parsed = parse_odoo_lead_name('CAMPAGNE-PRINTEMPS')
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['source'], 'CAMPAGNE')
        self.assertEqual(parsed['form_hint'], '')


class EstimatedAttributionTests(SimpleTestCase):
    def _deals(self):
        return [
            # Exact (phone matché) — NE DOIT PAS être ré-estimé.
            {'phone_norm': 'match1', 'source_name': 'AGENCY-FORM-01/01/2026',
             'lead_id': 1},
            # Sans match → estimé.
            {'phone_norm': 'nomatch', 'source_name':
             'DAZZLEMEDAI-TAQINOR FORM-26/03/2026', 'lead_id': 2},
            {'phone_norm': '', 'source_name':
             'DAZZLEMEDAI-TAQINOR FORM-26/03/2026', 'lead_id': 3},
            # Nom inexploitable.
            {'phone_norm': '', 'source_name': '', 'lead_id': 4},
        ]

    def test_estimated_separated_from_matched(self):
        res = estimated_attribution_from_names(
            self._deals(), matched_phone_keys={'match1'})
        # Le deal exact (match1) n'apparaît jamais dans les estimations.
        all_ids = [i for e in res['estimations'] for i in e['deal_ids']]
        self.assertNotIn(1, all_ids)
        self.assertIn(2, all_ids)
        self.assertIn(3, all_ids)
        self.assertEqual(res['unparseable'], 1)  # le deal 4 (nom vide)

    def test_always_labeled_estimation(self):
        res = estimated_attribution_from_names(self._deals())
        for e in res['estimations']:
            self.assertEqual(e['attribution_type'], 'estimation')

    def test_grouping_by_campaign_hint(self):
        res = estimated_attribution_from_names(
            self._deals(), matched_phone_keys={'match1'})
        # Les deux deals DAZZLEMEDAI (même nom) → un seul groupe, count=2.
        group = next(e for e in res['estimations']
                     if 'DAZZLEMEDAI' in e['campaign_hint'])
        self.assertEqual(group['count'], 2)
        self.assertEqual(group['date'], '26/03/2026')
