"""AACQ20 — un lead effacé (DSR/rétention) ne fournit plus aucun
identifiant publicitaire au CAPI : ``anonymiser_lead`` purge ``fbclid`` et
``gclid`` (``external_id`` gardé pour la dédup), ``lead_capi_identifiers``
renvoie ``is_erased`` et plus aucun identifiant, la couverture de match
l'exclut — rejoue la sonde LMETA-6.

Test-du-test : retirer ``fbclid`` de ``update_fields`` ⇒
test_anonymiser_purge_fbclid_gclid échoue.
"""
from django.test import TestCase

from authentication.models import Company
from apps.crm import selectors
from apps.crm.dsr_provider import anonymiser_lead
from apps.crm.models import Lead


class LeadEffaceCapiTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='AACQ20 Solaire', slug='aacq20-capi')
        self.lead = Lead.objects.create(
            company=self.company, nom='Meta', telephone='0612345678',
            canal=Lead.Canal.META_ADS, external_system='meta_lead_ads',
            external_id='123456789012345', fbclid='abcFBCLID', gclid='g1')
        self.vivant = Lead.objects.create(
            company=self.company, nom='Vivant', telephone='0611111111',
            canal=Lead.Canal.META_ADS, fbclid='vivantFB')

    def test_anonymiser_purge_fbclid_gclid(self):
        anonymiser_lead(self.company, self.lead, motif='test')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.fbclid or '', '')
        self.assertEqual(self.lead.gclid, '')
        self.assertEqual(self.lead.external_id, '123456789012345')

    def test_selecteur_is_erased(self):
        self.assertFalse(selectors.lead_capi_identifiers(
            self.company, self.vivant.pk)['is_erased'])
        anonymiser_lead(self.company, self.lead, motif='test')
        ids = selectors.lead_capi_identifiers(self.company, self.lead.pk)
        self.assertTrue(ids['is_erased'])
        self.assertEqual(ids['leadgen_id'], '')
        self.assertEqual(ids['fbclid'], '')
        self.assertEqual(ids['phone'], '')
        self.assertEqual(ids['email'], '')

    def test_couverture_exclut_efface(self):
        avant = selectors.meta_lead_match_coverage(self.company)
        self.assertEqual(avant['meta_leads'], 2)
        anonymiser_lead(self.company, self.lead, motif='test')
        apres = selectors.meta_lead_match_coverage(self.company)
        self.assertEqual(apres['meta_leads'], 1)
        self.assertEqual(apres['with_leadgen_id'], 0)
