"""ADSENG23 — Tests de l'identité de lancement (nommage + UTM, dd-treasury §c).

Prouve : ``generate_launch_identity`` produit un nommage PARSABLE (aller-retour
encode→parse exact au niveau campagne/adset/ad) ; la convention
``utm_content = 'ad-<ad_id>'`` (ADSENG1) fait l'aller-retour ; le vocabulaire
marché/objectif est fermé (valeur inconnue → refus) ; les UTM suivent le casing
Règle 0 ; et l'indice d'ad set est plus-haut-utilisé + 1 (jamais count()+1)."""
import datetime

from django.test import TestCase

from authentication.models import Company
from apps.adsengine import identity
from apps.adsengine.models import AdCampaignMirror, AdSetMirror


class GenerateIdentityTests(TestCase):
    def test_campaign_name_and_utm_shape(self):
        ident = identity.generate_launch_identity(
            market='resid', objective='ctwa', city='Casablanca',
            launch_date=datetime.date(2026, 7, 16), variant='A')
        self.assertEqual(
            ident['campaign_name'], 'TQ-20260716-resid-ctwa-casablanca-a')
        self.assertEqual(ident['utm_source'], 'meta')
        self.assertEqual(ident['utm_medium'], 'cpc')
        self.assertEqual(ident['utm_campaign'], 'resid_ctwa_casablanca_a')
        # utm_content vide tant qu'aucune ad n'est nommée.
        self.assertIsNone(ident['utm_content'])

    def test_accents_and_spaces_are_slugged(self):
        ident = identity.generate_launch_identity(
            market='agri', objective='ctwa', city='El Jadida',
            launch_date=datetime.date(2026, 1, 5), variant='b2')
        self.assertEqual(ident['city'], 'eljadida')
        self.assertEqual(
            ident['campaign_name'], 'TQ-20260105-agri-ctwa-eljadida-b2')

    def test_unknown_market_or_objective_refused(self):
        with self.assertRaises(ValueError):
            identity.generate_launch_identity(
                market='spatial', objective='ctwa', city='x',
                launch_date=datetime.date(2026, 7, 1), variant='a')
        with self.assertRaises(ValueError):
            identity.generate_launch_identity(
                market='resid', objective='teleport', city='x',
                launch_date=datetime.date(2026, 7, 1), variant='a')

    def test_market_for_type_installation(self):
        self.assertEqual(
            identity.market_for_type_installation('residentiel'), 'resid')
        self.assertEqual(
            identity.market_for_type_installation('industriel'), 'indcom')
        self.assertEqual(
            identity.market_for_type_installation('commercial'), 'indcom')
        self.assertEqual(
            identity.market_for_type_installation('agricole'), 'agri')
        with self.assertRaises(ValueError):
            identity.market_for_type_installation('nucleaire')


class RoundTripTests(TestCase):
    def test_campaign_name_round_trip(self):
        ident = identity.generate_launch_identity(
            market='indcom', objective='leadform', city='Tanger',
            launch_date=datetime.date(2026, 3, 12), variant='c')
        parsed = identity.parse_campaign_name(ident['campaign_name'])
        self.assertEqual(parsed['market'], 'indcom')
        self.assertEqual(parsed['objective'], 'leadform')
        self.assertEqual(parsed['city'], 'tanger')
        self.assertEqual(parsed['variant'], 'c')
        self.assertEqual(parsed['launch_date'], datetime.date(2026, 3, 12))

    def test_adset_and_ad_name_round_trip(self):
        ident = identity.generate_launch_identity(
            market='resid', objective='ctwa', city='Rabat',
            launch_date=datetime.date(2026, 7, 16), variant='a')
        camp = ident['campaign_name']
        adset_name = ident['adset_name_tmpl'].format(
            campaign_name=camp, n=3)
        self.assertEqual(adset_name, f'{camp}-AS-03')
        parsed_as = identity.parse_adset_name(adset_name)
        self.assertEqual(parsed_as['campaign_name'], camp)
        self.assertEqual(parsed_as['n'], 3)
        ad_name = ident['ad_name_tmpl'].format(
            campaign_name=camp, n=3, creative_asset_id='789')
        parsed_ad = identity.parse_ad_name(ad_name)
        self.assertEqual(parsed_ad['campaign_name'], camp)
        self.assertEqual(parsed_ad['n'], 3)
        self.assertEqual(parsed_ad['creative_asset_id'], '789')

    def test_malformed_names_raise(self):
        with self.assertRaises(ValueError):
            identity.parse_campaign_name('TQ-bad')
        with self.assertRaises(ValueError):
            identity.parse_campaign_name('XX-20260716-r-o-c-v')
        with self.assertRaises(ValueError):
            identity.parse_adset_name('no-suffix')
        with self.assertRaises(ValueError):
            identity.parse_ad_name('no-ad-marker')


class UtmContentConventionTests(TestCase):
    def test_build_and_parse_ad_content(self):
        self.assertEqual(identity.build_utm_content('123'), 'ad-123')
        self.assertEqual(identity.parse_utm_content('ad-123'), '123')

    def test_empty_and_non_ad_content(self):
        self.assertIsNone(identity.build_utm_content(''))
        self.assertIsNone(identity.parse_utm_content('carousel_b'))
        self.assertIsNone(identity.parse_utm_content(''))


class NextAdsetIndexTests(TestCase):
    def test_highest_used_plus_one_not_count_plus_one(self):
        company = Company.objects.create(nom='Ni', slug='ni')
        camp = 'TQ-20260716-resid-ctwa-casablanca-a'
        AdCampaignMirror.objects.create(company=company, meta_id='c1', name=camp)
        # Deux ad sets : indices 01 et 03 (le 02 « supprimé »).
        AdSetMirror.objects.create(
            company=company, meta_id='as1', name=f'{camp}-AS-01')
        AdSetMirror.objects.create(
            company=company, meta_id='as3', name=f'{camp}-AS-03')
        # count()+1 donnerait 3 (collision avec 03) ; plus-haut+1 donne 4.
        self.assertEqual(identity.next_adset_index(company, camp), 4)

    def test_first_index_is_one(self):
        company = Company.objects.create(nom='Ni2', slug='ni2')
        self.assertEqual(
            identity.next_adset_index(company, 'TQ-20260716-resid-ctwa-x-a'), 1)
