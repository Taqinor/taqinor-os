"""ACRM33 — ``signed_lead_phone_keys`` rend les clés du ``telephone`` ET du
``whatsapp`` des leads signés (helper unique ``cles_numeros_lead`` partagé
avec ``find_lead_id_by_phone``) — rejoue la sonde LSEL-7.

Test-du-test : revenir à ``values_list('telephone')`` ⇒
test_whatsapp_seul_compte échoue.
"""
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm import selectors, stages, leads_doublons
from apps.crm.models import Lead


class ClesSigneesWhatsappTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM33 Solaire', slug='acrm33-wa')
        self.lead = Lead.objects.create(
            company=self.company, nom='WhatsApp seul', telephone='',
            whatsapp='+212 6 12 34 56 78', stage=stages.SIGNED)
        self.cle = leads_doublons.normalize_phone('+212 6 12 34 56 78')

    def test_whatsapp_seul_compte(self):
        self.assertTrue(self.cle)
        self.assertEqual(
            selectors.find_lead_id_by_phone(self.company, '0612345678'),
            self.lead.pk)
        self.assertIn(self.cle, selectors.signed_lead_phone_keys(self.company))

    def test_conversation_de_la_pub_comptee_signee(self):
        from apps.adsengine.metrics import conversations_per_ad
        from apps.adsengine.models import CtwaReferral
        CtwaReferral.objects.create(
            company=self.company, wa_message_id='wa-acrm33', ad_id='ad-33',
            phone_key=self.cle, ts=timezone.now())
        res = conversations_per_ad(self.company)
        self.assertEqual(res['total_signed'], 1)

    def test_helper_unique_telephone_et_whatsapp(self):
        lead = Lead(telephone='0611111111', whatsapp='0622222222')
        self.assertEqual(
            selectors.cles_numeros_lead(lead),
            {leads_doublons.normalize_phone('0611111111'),
             leads_doublons.normalize_phone('0622222222')})
