"""QJR584 — corriger le téléphone d'un lead fait suivre son WhatsApp quand il
n'en était qu'une copie ; un WhatsApp distinct n'est jamais touché."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead

User = get_user_model()


class WhatsappSuitTelephoneTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='wa-suit', defaults={'nom': 'wa-suit'})
        self.user = User.objects.create_user(
            username='wa-suit-u', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _patch(self, lead, body):
        resp = self.api.patch(
            f'/api/django/crm/leads/{lead.pk}/', body, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        lead.refresh_from_db()

    def test_whatsapp_copie_suit_le_nouveau_telephone(self):
        lead = Lead.objects.create(
            company=self.company, nom='WA1', owner=self.user,
            telephone='0612345678', whatsapp='+212612345678')
        self._patch(lead, {'telephone': '0698765432'})
        # Le serializer stocke le téléphone au format canonique « 212… »
        # (LeadSerializer._canonical_phone) ; le WhatsApp copie suit ce numéro.
        self.assertEqual(lead.telephone, '212698765432')
        self.assertEqual(lead.whatsapp, '212698765432')

    def test_whatsapp_distinct_reste_intact(self):
        lead = Lead.objects.create(
            company=self.company, nom='WA2', owner=self.user,
            telephone='0612345678', whatsapp='0655555555')
        self._patch(lead, {'telephone': '0698765432'})
        self.assertEqual(lead.whatsapp, '0655555555')
