"""ACRM32 — ``Lead.whatsapp_normalise`` (calculée par ``Lead.save``) :
``find_duplicates_by_contact`` cherche sur ``phone_normalise`` OU
``whatsapp_normalise`` ; un message WhatsApp d'un numéro connu seulement en
``whatsapp`` retrouve son lead (aucun brouillon) ; la clé est une PII —
rejoue la sonde LSVC2-3.

Test-du-test : retirer la branche ``whatsapp_normalise`` ⇒
test_find_duplicates_trouve_whatsapp échoue.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import services, stages
from apps.crm.models import Lead
from apps.crm.serializers import LEAD_PII_FIELDS
from apps.roles.models import Role
from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS

User = get_user_model()


class DoublonWhatsappTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM32 Solaire', slug='acrm32-wa')
        self.lead = Lead.objects.create(
            company=self.company, nom='WhatsApp seul', telephone='',
            whatsapp='0612345678', stage=stages.CONTACTED)

    def test_cle_persistee(self):
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.whatsapp_normalise, '612345678')

    def test_find_duplicates_trouve_whatsapp(self):
        trouves = services.find_duplicates_by_contact(
            self.company, phone='+212612345678')
        self.assertEqual([le.pk for le in trouves], [self.lead.pk])

    def test_whatsapp_entrant_sans_doublon(self):
        avant = Lead.objects.filter(company=self.company).count()
        lead = services.resolve_or_create_lead_from_whatsapp(
            self.company, '+212612345678', nom='Client')
        self.assertEqual(lead.pk, self.lead.pk)
        self.assertEqual(Lead.objects.filter(company=self.company).count(),
                         avant)

    def test_garde_cadence_voit_le_whatsapp(self):
        autre = Lead.objects.create(
            company=self.company, nom='Même personne',
            telephone='0612345678', stage=stages.NEW)
        doublons = services.find_duplicates_by_contact(
            self.company, phone=autre.telephone, email=autre.email,
            exclude_pk=autre.pk, whatsapp=autre.whatsapp)
        self.assertIn(self.lead.pk, [le.pk for le in doublons])

    def test_pii_masquee(self):
        self.assertIn('whatsapp_normalise', LEAD_PII_FIELDS)
        sans_pii = Role.objects.create(
            company=self.company, nom='Commercial sans PII',
            permissions=[p for p in COMMERCIAL_PERMISSIONS
                         if p != 'client_pii_voir'])
        user = User.objects.create_user(
            username='acrm32-masque', password='x', company=self.company,
            role=sans_pii)
        Lead.objects.filter(pk=self.lead.pk).update(owner=user)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.get(f'/api/django/crm/leads/{self.lead.pk}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['whatsapp_normalise'])
