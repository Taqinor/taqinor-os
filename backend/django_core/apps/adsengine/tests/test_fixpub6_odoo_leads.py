"""FIXPUB6 — Leads Odoo attribués PAR ANNONCE (coût-par-lead).

``odoo_selectors.all_leads`` normalise TOUS les leads Odoo (no-op sans config) ;
``odoo_leads.odoo_leads_by_ad`` les attribue à une annonce en 3 paliers (exact
téléphone → estimation nom → estimation fenêtre date) et calcule ``cpl_odoo`` ;
``metrics.ads_cockpit_rows`` porte ``leads_odoo`` + ``cpl_odoo`` par ligne.
"""
import datetime
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import sync
from apps.adsengine.metrics import ads_cockpit_rows
from apps.adsengine.models import MetaLeadMirror
from apps.adsengine.odoo_leads import odoo_leads_by_ad
from apps.adsengine.odoo_selectors import all_leads


def _phone_key(telephone):
    from apps.crm.selectors import normalize_phone_key
    return normalize_phone_key(telephone)


class FakeOdooClient:
    """Client Odoo mocké : ``read_leads`` renvoie des dicts bruts crm.lead."""

    def __init__(self, rows):
        self._rows = rows

    def read_leads(self, since=None):
        return list(self._rows)


class AllLeadsSelectorTests(TestCase):
    def test_normalizes_and_flags_won(self):
        client = FakeOdooClient([
            {'id': 1, 'name': 'Sara', 'phone': '+212612345678',
             'probability': 100, 'create_date': '2026-07-16 09:00:00'},
            {'id': 2, 'name': 'Karim', 'mobile': '+212698765432',
             'probability': 20, 'create_date': '2026-07-17 09:00:00'},
        ])
        rows = all_leads(client=client)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['phone_norm'], _phone_key('+212612345678'))
        self.assertTrue(rows[0]['won'])
        self.assertEqual(rows[1]['phone_norm'], _phone_key('+212698765432'))
        self.assertFalse(rows[1]['won'])

    def test_noop_without_config(self):
        # Aucune variable ODOO_* → OdooClient.from_env() None → [].
        self.assertEqual(all_leads(), [])


class OdooLeadsByAdTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='OL Co', slug='ol')

    def _seed_ad(self, meta_id, name, spend, day, adset_id=None):
        payload = {'id': meta_id, 'name': name}
        if adset_id is not None:
            payload['adset_id'] = adset_id
        ad = sync.sync_ads(self.company, [payload])[0]
        sync.upsert_insight(self.company, ad, date=day, spend=spend)
        return ad

    def _seed_campaign(self, camp_id, camp_name, adset_id):
        sync.sync_campaigns(
            self.company, [{'id': camp_id, 'name': camp_name}])
        sync.sync_adsets(
            self.company,
            [{'id': adset_id, 'name': adset_id, 'campaign_id': camp_id}])

    def test_exact_phone_attribution_and_cpl(self):
        self._seed_ad('ad1', 'AD1', '300.00', datetime.date(2026, 7, 16))
        key = _phone_key('+212612345678')
        MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='lg1', ad_id='ad1',
            phone_key=key, crm_lead_id=1)
        leads = [
            {'phone_norm': key, 'date': None, 'source_name': 'x',
             'lead_id': 10, 'won': True},
            {'phone_norm': key, 'date': None, 'source_name': 'y',
             'lead_id': 11, 'won': False},
            {'phone_norm': 'unknownkey', 'date': None, 'source_name': '',
             'lead_id': 12, 'won': False},
        ]
        with patch('apps.adsengine.odoo_leads.odoo_all_leads',
                   return_value=leads):
            res = odoo_leads_by_ad(self.company)
        self.assertEqual(res['attributed'], 2)
        self.assertEqual(res['unattributed'], 1)
        row = next(a for a in res['ads'] if a['ad_id'] == 'ad1')
        self.assertEqual(row['leads_odoo'], 2)
        self.assertEqual(row['leads_exact'], 2)
        self.assertEqual(row['leads_estimes'], 0)
        self.assertEqual(row['attribution_type'], 'exact')
        # coût-par-lead = dépense ad (300) / 2 = 150.
        self.assertEqual(row['cpl_odoo'], '150.00')
        self.assertEqual(sorted(row['lead_ids']), [10, 11])

    def test_formulaire_single_ad_from_sibling(self):
        # DATAPUB1 — un formulaire servi par UNE annonce : un lead placé par
        # téléphone apprend l'empreinte, un SECOND lead du même formulaire (sans
        # téléphone) en hérite au palier « formulaire ».
        self._seed_ad('ad2', 'TAQINOR FORM', '400.00',
                      datetime.date(2026, 7, 16))
        key = _phone_key('+212612345678')
        MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='lg2', ad_id='ad2',
            phone_key=key, crm_lead_id=1)
        leads = [
            {'phone_norm': key, 'date': None,
             'source_name': 'TAQINOR FORM-4.0', 'lead_id': 20, 'won': False},
            {'phone_norm': '', 'date': None,
             'source_name': 'TAQINOR FORM-4.0', 'lead_id': 21, 'won': False},
        ]
        with patch('apps.adsengine.odoo_leads.odoo_all_leads',
                   return_value=leads):
            res = odoo_leads_by_ad(self.company)
        self.assertEqual(res['attributed'], 2)
        self.assertEqual(res['tiers']['telephone'], 1)
        self.assertEqual(res['tiers']['formulaire'], 1)
        row = next(a for a in res['ads'] if a['ad_id'] == 'ad2')
        self.assertEqual(row['leads_odoo'], 2)
        self.assertEqual(row['leads_exact'], 1)
        self.assertEqual(row['leads_formulaire'], 1)
        self.assertEqual(row['attribution_type'], 'mixte')
        # coût-par-lead = dépense ad (400) / 2 = 200.
        self.assertEqual(row['cpl_odoo'], '200.00')

    def test_formulaire_campagne_tier_spend_weighted(self):
        # DATAPUB1 — un formulaire servi par DEUX annonces d'une MÊME campagne :
        # les leads non plaçables héritent au niveau CAMPAGNE (formulaire_campagne)
        # et le CPL est réparti pondéré par la dépense (CPL par annonce = CPL
        # campagne).
        self._seed_campaign('camp1', 'Campagne Solaire', 'as1')
        self._seed_ad('adA', 'AD A', '300.00',
                      datetime.date(2026, 7, 16), adset_id='as1')
        self._seed_ad('adB', 'AD B', '100.00',
                      datetime.date(2026, 7, 16), adset_id='as1')
        keyA = _phone_key('+212611111111')
        keyB = _phone_key('+212622222222')
        MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='lgA', ad_id='adA',
            campaign_id='camp1', phone_key=keyA)
        MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='lgB', ad_id='adB',
            campaign_id='camp1', phone_key=keyB)
        leads = [
            # deux leads placés par téléphone (empreinte : {adA, adB}).
            {'phone_norm': keyA, 'date': None,
             'source_name': 'TAQINOR FORM-4.0', 'lead_id': 1, 'won': False},
            {'phone_norm': keyB, 'date': None,
             'source_name': 'TAQINOR FORM-4.0', 'lead_id': 2, 'won': False},
            # deux leads du même formulaire, sans téléphone → campagne.
            {'phone_norm': '', 'date': None,
             'source_name': 'TAQINOR FORM-4.0', 'lead_id': 3, 'won': False},
            {'phone_norm': '', 'date': None,
             'source_name': 'TAQINOR FORM-4.0', 'lead_id': 4, 'won': False},
        ]
        with patch('apps.adsengine.odoo_leads.odoo_all_leads',
                   return_value=leads):
            res = odoo_leads_by_ad(self.company)
        self.assertEqual(res['attributed'], 4)
        self.assertEqual(res['tiers']['telephone'], 2)
        self.assertEqual(res['tiers']['formulaire_campagne'], 2)
        self.assertEqual(len(res['campaigns']), 1)
        camp = res['campaigns'][0]
        self.assertEqual(camp['campaign_id'], 'camp1')
        self.assertEqual(camp['campaign_name'], 'Campagne Solaire')
        self.assertEqual(camp['leads_odoo'], 2)
        self.assertEqual(sorted(camp['ad_ids']), ['adA', 'adB'])
        self.assertEqual(camp['attribution_type'], 'formulaire_campagne')
        # dépense campagne = 300 + 100 = 400 ; CPL = 400 / 2 = 200.
        self.assertEqual(camp['spend'], '400.00')
        self.assertEqual(camp['cpl_odoo'], '200.00')
        # répartition pondérée : chaque annonce a le même CPL (= CPL campagne).
        cpls = {p['ad_id']: p['cpl_odoo'] for p in camp['per_ad']}
        self.assertEqual(cpls['adA'], '200.00')
        self.assertEqual(cpls['adB'], '200.00')

    def test_pure_name_estimation_tier(self):
        # Un nom encodé NON-formulaire (sans jeton « form ») reste au palier NOM.
        self._seed_ad('ad2', 'DAZZLEMEDAI CAMPAGNE', '200.00',
                      datetime.date(2026, 7, 16))
        leads = [
            {'phone_norm': '', 'date': '2026-03-26 09:00:00',
             'source_name': 'DAZZLEMEDAI-26/03/2026',
             'lead_id': 20, 'won': False},
        ]
        with patch('apps.adsengine.odoo_leads.odoo_all_leads',
                   return_value=leads):
            res = odoo_leads_by_ad(self.company)
        self.assertEqual(res['attributed'], 1)
        self.assertEqual(res['tiers']['nom'], 1)
        row = next(a for a in res['ads'] if a['ad_id'] == 'ad2')
        self.assertEqual(row['leads_estimes'], 1)
        self.assertEqual(row['attribution_type'], 'estimation')
        self.assertEqual(row['cpl_odoo'], '200.00')

    def test_date_window_estimation_tier(self):
        # Nom non exploitable + une SEULE annonce active le jour du lead.
        self._seed_ad('ad3', 'Pompage', '100.00', datetime.date(2026, 7, 20))
        leads = [
            {'phone_norm': '', 'date': '2026-07-20 11:00:00',
             'source_name': '', 'lead_id': 30, 'won': False},
        ]
        with patch('apps.adsengine.odoo_leads.odoo_all_leads',
                   return_value=leads):
            res = odoo_leads_by_ad(self.company)
        self.assertEqual(res['attributed'], 1)
        row = next(a for a in res['ads'] if a['ad_id'] == 'ad3')
        self.assertEqual(row['leads_odoo'], 1)
        self.assertEqual(row['attribution_type'], 'estimation')

    def test_unattributed_when_ambiguous_date(self):
        # Deux annonces actives le même jour → fenêtre date ambiguë → non attribué.
        self._seed_ad('ad4', 'A4', '100.00', datetime.date(2026, 7, 21))
        self._seed_ad('ad5', 'A5', '100.00', datetime.date(2026, 7, 21))
        leads = [
            {'phone_norm': '', 'date': '2026-07-21 08:00:00',
             'source_name': '', 'lead_id': 40, 'won': False},
        ]
        with patch('apps.adsengine.odoo_leads.odoo_all_leads',
                   return_value=leads):
            res = odoo_leads_by_ad(self.company)
        self.assertEqual(res['attributed'], 0)
        self.assertEqual(res['unattributed'], 1)

    def test_unattributed_by_source_and_total(self):
        # DATAPUB2 — aucun lead ignoré en silence : les non-attribués sont
        # comptés PAR nom de source, et le total réconcilie attribués +
        # non-attribués.
        self._seed_ad('ad1', 'AD1', '100.00', datetime.date(2026, 7, 16))
        key = _phone_key('+212612345678')
        MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='lg1', ad_id='ad1',
            phone_key=key, crm_lead_id=1)
        leads = [
            {'phone_norm': key, 'date': None, 'source_name': 'x',
             'lead_id': 1, 'won': False},
            {'phone_norm': 'nope', 'date': None,
             'source_name': 'INCONNU FORM-9', 'lead_id': 2, 'won': False},
            {'phone_norm': 'nope2', 'date': None,
             'source_name': 'INCONNU FORM-9', 'lead_id': 3, 'won': False},
            {'phone_norm': 'nope3', 'date': None,
             'source_name': 'AUTRE', 'lead_id': 4, 'won': False},
        ]
        with patch('apps.adsengine.odoo_leads.odoo_all_leads',
                   return_value=leads):
            res = odoo_leads_by_ad(self.company)
        self.assertEqual(res['attributed'], 1)
        self.assertEqual(res['unattributed'], 3)
        self.assertEqual(res['total'], 4)
        by_source = {r['source_name']: r['count']
                     for r in res['unattributed_by_source']}
        self.assertEqual(by_source['INCONNU FORM-9'], 2)
        self.assertEqual(by_source['AUTRE'], 1)
        # trié décroissant : le plus gros bucket en tête.
        self.assertEqual(res['unattributed_by_source'][0]['count'], 2)

    def test_noop_without_odoo_config(self):
        self._seed_ad('ad1', 'AD1', '300.00', datetime.date(2026, 7, 16))
        res = odoo_leads_by_ad(self.company)
        self.assertFalse(res['configured'])
        self.assertEqual(res['ads'], [])
        self.assertEqual(res['campaigns'], [])


class SearchReadPaginationTests(SimpleTestCase):
    """DATAPUB1 — ``search_read_all`` pagine jusqu'à une page incomplète : aucune
    limite serveur implicite ne peut tronquer la base de leads."""

    class _PagingFake:
        READ_PAGE_SIZE = 2

        def __init__(self, total):
            self.rows = [{'id': i} for i in range(total)]
            self.offsets = []

        def search_read(self, model, domain=None, *, fields=None, order=None,
                        limit=None, offset=None):
            self.offsets.append(offset)
            return self.rows[offset:offset + limit]

    def test_pages_through_all_records(self):
        from apps.adsengine.odoo_client import OdooClient
        fake = self._PagingFake(5)
        rows = OdooClient.search_read_all(
            fake, 'crm.lead', order='id', page_size=2)
        self.assertEqual([r['id'] for r in rows], [0, 1, 2, 3, 4])
        # 3 pages : la dernière (1 ligne) est incomplète → arrêt.
        self.assertEqual(fake.offsets, [0, 2, 4])

    def test_exact_multiple_stops_on_empty_page(self):
        from apps.adsengine.odoo_client import OdooClient
        fake = self._PagingFake(4)
        rows = OdooClient.search_read_all(
            fake, 'crm.lead', order='id', page_size=2)
        self.assertEqual(len(rows), 4)
        # 4 = 2×2 pleines, puis une page vide qui arrête la boucle.
        self.assertEqual(fake.offsets, [0, 2, 4])


class CockpitLeadsOdooTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CK Co', slug='ck')
        self.ad = sync.sync_ads(
            self.company, [{'id': 'ad1', 'name': 'AD1'}])[0]
        sync.upsert_insight(
            self.company, self.ad, date=datetime.date(2026, 7, 16),
            spend='300.00')
        self.key = _phone_key('+212612345678')
        MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='lg1', ad_id='ad1',
            phone_key=self.key, crm_lead_id=1)

    def test_cockpit_row_carries_leads_odoo_and_cpl(self):
        leads = [
            {'phone_norm': self.key, 'date': None, 'source_name': 'x',
             'lead_id': 10, 'won': True},
            {'phone_norm': self.key, 'date': None, 'source_name': 'y',
             'lead_id': 11, 'won': False},
        ]
        with patch('apps.adsengine.odoo_leads.odoo_all_leads',
                   return_value=leads):
            rows = ads_cockpit_rows(self.company)
        row = next(r for r in rows if r['meta_id'] == 'ad1')
        self.assertEqual(row['leads_odoo'], 2)
        self.assertEqual(row['cpl_odoo'], '150.00')

    def test_cockpit_row_zero_without_odoo(self):
        rows = ads_cockpit_rows(self.company)
        row = next(r for r in rows if r['meta_id'] == 'ad1')
        self.assertEqual(row['leads_odoo'], 0)
        self.assertIsNone(row['cpl_odoo'])
