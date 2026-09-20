"""YLEAD8 — Rattacher l'inbound WhatsApp à un lead OUVERT existant.

Couvre :
  - un 2e message WhatsApp du même numéro ne crée PAS de 2e lead, mais
    ajoute une activité au lead OUVERT existant ;
  - un numéro inconnu crée bien un lead (avec le téléphone/whatsapp posé,
    pour que le PROCHAIN message le retrouve) ;
  - un lead existant mais PERDU ou ARCHIVÉ n'est pas réutilisé (nouveau
    lead créé — cohérent avec YLEAD11 qui gère la réactivation séparément) ;
  - company-scopé : deux sociétés ne partagent jamais un lead même avec le
    même numéro.
"""
from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Lead, LeadActivity
from apps.crm.services import resolve_or_create_lead_from_whatsapp


class ResolveOrCreateFromWhatsappTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor YLEAD8', slug='taqinor-ylead8')

    def test_unknown_number_creates_lead_with_phone_set(self):
        lead = resolve_or_create_lead_from_whatsapp(
            self.company, '+212661112233', nom='Nadia')
        self.assertIsNotNone(lead.pk)
        self.assertEqual(lead.telephone, '+212661112233')
        self.assertEqual(lead.whatsapp, '+212661112233')
        self.assertEqual(lead.company_id, self.company.id)

    def test_second_message_same_number_reuses_open_lead(self):
        first = resolve_or_create_lead_from_whatsapp(
            self.company, '+212661112233', nom='Nadia')
        second = resolve_or_create_lead_from_whatsapp(
            self.company, '+212661112233', nom='Nadia')
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            Lead.objects.filter(company=self.company).count(), 1)
        notes = LeadActivity.objects.filter(
            lead=second, kind=LeadActivity.Kind.NOTE)
        self.assertTrue(
            any('WhatsApp' in (n.body or '') for n in notes))

    def test_lost_lead_is_reactivated_not_duplicated(self):
        """Un lead PERDU n'est pas 'ouvert', mais une nouvelle touche
        WhatsApp le RÉACTIVE (YLEAD11) au lieu de créer un doublon."""
        lost = resolve_or_create_lead_from_whatsapp(
            self.company, '+212661112244', nom='Karim')
        lost.perdu = True
        lost.save(update_fields=['perdu'])

        second = resolve_or_create_lead_from_whatsapp(
            self.company, '+212661112244', nom='Karim')
        self.assertEqual(lost.pk, second.pk)
        self.assertEqual(
            Lead.objects.filter(company=self.company).count(), 1)
        second.refresh_from_db()
        self.assertFalse(second.perdu)

    def test_archived_lead_is_not_reused(self):
        archived = resolve_or_create_lead_from_whatsapp(
            self.company, '+212661112255', nom='Sara')
        from django.utils import timezone
        archived.archived_at = timezone.now()
        archived.save(update_fields=['archived_at'])

        second = resolve_or_create_lead_from_whatsapp(
            self.company, '+212661112255', nom='Sara')
        self.assertNotEqual(archived.pk, second.pk)

    def test_company_scoped_same_number_two_companies(self):
        other_company = Company.objects.create(
            nom='Taqinor YLEAD8 B', slug='taqinor-ylead8-b')
        lead_a = resolve_or_create_lead_from_whatsapp(
            self.company, '+212661119999', nom='Ali')
        lead_b = resolve_or_create_lead_from_whatsapp(
            other_company, '+212661119999', nom='Ali')
        self.assertNotEqual(lead_a.pk, lead_b.pk)
        self.assertEqual(lead_a.company_id, self.company.id)
        self.assertEqual(lead_b.company_id, other_company.id)
