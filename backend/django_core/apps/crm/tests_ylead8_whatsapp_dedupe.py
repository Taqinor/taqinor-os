"""YLEAD8 — Rattacher l'inbound WhatsApp à un lead OUVERT existant.

Couvre :
  - un 2e message WhatsApp du même numéro ne crée PAS de 2e lead, mais
    ajoute une activité au lead OUVERT existant ;
  - un numéro inconnu crée bien un lead (avec le téléphone/whatsapp posé,
    pour que le PROCHAIN message le retrouve) ;
  - un lead existant mais PERDU ou ARCHIVÉ n'est pas réutilisé (nouveau
    lead créé — cohérent avec YLEAD11 qui gère la réactivation séparément) ;
  - company-scopé : deux sociétés ne partagent jamais un lead même avec le
    même numéro ;
  - gated : ``compta.services.capturer_message_whatsapp`` est un NO-OP quand
    WhatsApp est désactivé (comportement inchangé), et route bien vers
    ``resolve_or_create_lead_from_whatsapp`` quand activé — idempotent par
    ``wa_message_id`` (retry Meta ne recrée rien).
"""
from django.test import TestCase, override_settings

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


class CapturerMessageWhatsappGatedTests(TestCase):
    """Vérifie le câblage compta.services.capturer_message_whatsapp → YLEAD8."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor YLEAD8 Gate', slug='taqinor-ylead8-gate')

    @override_settings(WHATSAPP_ENABLED=False)
    def test_noop_when_whatsapp_disabled(self):
        from apps.compta.services import capturer_message_whatsapp
        log = capturer_message_whatsapp(
            self.company, wa_message_id='wamid.1', expediteur='+212661110000')
        self.assertIsNone(log)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 0)

    @override_settings(WHATSAPP_ENABLED=True, WHATSAPP_ACCESS_TOKEN='tok')
    def test_second_inbound_message_reuses_lead_via_ylead8(self):
        from apps.compta.services import capturer_message_whatsapp
        log1 = capturer_message_whatsapp(
            self.company, wa_message_id='wamid.a', expediteur='+212661110001',
            nom_profil='Youssef')
        log2 = capturer_message_whatsapp(
            self.company, wa_message_id='wamid.b', expediteur='+212661110001',
            nom_profil='Youssef')
        self.assertIsNotNone(log1.lead_id)
        self.assertEqual(log1.lead_id, log2.lead_id)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 1)

    @override_settings(WHATSAPP_ENABLED=True, WHATSAPP_ACCESS_TOKEN='tok')
    def test_retry_same_wa_message_id_is_idempotent(self):
        """Un retry Meta (même wa_message_id) ne retraite pas le message."""
        from apps.compta.services import capturer_message_whatsapp
        log1 = capturer_message_whatsapp(
            self.company, wa_message_id='wamid.retry', expediteur='+212661110002')
        log2 = capturer_message_whatsapp(
            self.company, wa_message_id='wamid.retry', expediteur='+212661110002')
        self.assertEqual(log1.pk, log2.pk)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 1)
