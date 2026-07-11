"""QW4 — Actioned callback obligation (contact_preference=phone_ok), distinct
from a generic WhatsApp reply notice.

Couvre :
  - ``services.callback_sla_hours`` : SLA rappel plus serré que le SLA
    générique (moitié, plancher 2h) ; 0 (générique désactivé) → 0 ;
  - ``services.notify_lead_callback_requested`` : notifie owner+supérieur pour
    un lead phone_ok, idempotent (jamais deux fois), no-op pour whatsapp_only ;
  - ``selectors.leads_callback_sla_depasse`` : liste un rappel demandé non
    actionné au-delà du SLA rappel, jamais un lead whatsapp_only, company-
    scopé, SLA désactivé → vide ;
  - ``escalader_rappels_demandes`` (commande) : escalade chaque rappel SLA-
    dépassé une seule fois (idempotent), jamais un lead sans phone_ok.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm.management.commands.escalader_rappels_demandes import (
    escalader_rappels_demandes,
)
from apps.crm.models import Lead, LeadActivity
from apps.crm.services import (
    callback_sla_hours, notify_lead_callback_requested,
)
from apps.crm import selectors
from apps.notifications.models import Notification
from apps.parametres.models import CompanyProfile

User = get_user_model()


def _phone_ok_lead(company, hours_ago=6, owner=None, contacted=False):
    lead = Lead.objects.create(
        company=company, nom='Prospect rappel', telephone='+212600112233',
        contact_preference=Lead.ContactPreference.PHONE_OK)
    updates = {
        'date_creation': timezone.now() - datetime.timedelta(hours=hours_ago),
        'owner': owner,
    }
    if contacted:
        updates['first_contacted_at'] = timezone.now()
    Lead.objects.filter(pk=lead.pk).update(**updates)
    lead.refresh_from_db()
    return lead


class CallbackSlaHoursTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor QW4', slug='taqinor-qw4')

    def test_half_of_generic_sla_floored_at_two(self):
        CompanyProfile.objects.create(company=self.company, lead_sla_hours=24)
        self.assertEqual(callback_sla_hours(self.company), 12)

    def test_floor_at_two_hours(self):
        CompanyProfile.objects.create(company=self.company, lead_sla_hours=2)
        self.assertEqual(callback_sla_hours(self.company), 2)

    def test_disabled_generic_sla_disables_callback_sla(self):
        CompanyProfile.objects.create(company=self.company, lead_sla_hours=0)
        self.assertEqual(callback_sla_hours(self.company), 0)


class NotifyLeadCallbackRequestedTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor QW4 Notif', slug='taqinor-qw4-notif')
        from apps.roles.models import Role
        role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_voir'])
        self.owner = User.objects.create_user(
            username='owner_qw4', password='x', company=self.company, role=role)

    def test_phone_ok_lead_notifies_owner(self):
        lead = Lead.objects.create(
            company=self.company, nom='Test', telephone='+212611223344',
            owner=self.owner, contact_preference=Lead.ContactPreference.PHONE_OK)
        notify_lead_callback_requested(lead)
        # QW4 — un lead créé AVEC owner déclenche aussi la notification générique
        # LEAD_ASSIGNED (apps.notifications.signals) ; on ne compte donc QUE la
        # notification produite par la fonction testée (son event_type dédié).
        self.assertEqual(Notification.objects.filter(
            recipient=self.owner, event_type='lead_callback_requested').count(), 1)
        notif = Notification.objects.get(
            recipient=self.owner, event_type='lead_callback_requested')
        self.assertIn('Rappeler', notif.title)

    def test_whatsapp_only_lead_never_notified(self):
        lead = Lead.objects.create(
            company=self.company, nom='Test', telephone='+212611223355',
            owner=self.owner, contact_preference=Lead.ContactPreference.WHATSAPP_ONLY)
        notify_lead_callback_requested(lead)
        self.assertEqual(Notification.objects.filter(
            recipient=self.owner, event_type='lead_callback_requested').count(), 0)

    def test_idempotent_never_notifies_twice(self):
        lead = Lead.objects.create(
            company=self.company, nom='Test', telephone='+212611223366',
            owner=self.owner, contact_preference=Lead.ContactPreference.PHONE_OK)
        notify_lead_callback_requested(lead)
        notify_lead_callback_requested(lead)
        self.assertEqual(Notification.objects.filter(
            recipient=self.owner, event_type='lead_callback_requested').count(), 1)

    def test_no_preference_never_notified(self):
        lead = Lead.objects.create(
            company=self.company, nom='Test', telephone='+212611223377',
            owner=self.owner)
        notify_lead_callback_requested(lead)
        self.assertEqual(Notification.objects.filter(
            recipient=self.owner, event_type='lead_callback_requested').count(), 0)


class LeadsCallbackSlaDepasseSelectorTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor QW4 Sel', slug='taqinor-qw4-sel')
        CompanyProfile.objects.create(company=self.company, lead_sla_hours=8)  # callback = 4h

    def test_uncontacted_phone_ok_past_sla_is_listed(self):
        now = timezone.now()
        lead = _phone_ok_lead(self.company, hours_ago=10)
        qs = selectors.leads_callback_sla_depasse(self.company, now=now)
        self.assertIn(lead, list(qs))

    def test_contacted_lead_not_listed(self):
        now = timezone.now()
        lead = _phone_ok_lead(self.company, hours_ago=10, contacted=True)
        qs = selectors.leads_callback_sla_depasse(self.company, now=now)
        self.assertNotIn(lead, list(qs))

    def test_whatsapp_only_lead_never_listed(self):
        now = timezone.now()
        lead = Lead.objects.create(
            company=self.company, nom='WA only', telephone='+212600000001',
            contact_preference=Lead.ContactPreference.WHATSAPP_ONLY)
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=now - datetime.timedelta(hours=48))
        qs = selectors.leads_callback_sla_depasse(self.company, now=now)
        self.assertNotIn(lead, list(qs))

    def test_recent_within_sla_not_listed(self):
        now = timezone.now()
        lead = _phone_ok_lead(self.company, hours_ago=1)
        qs = selectors.leads_callback_sla_depasse(self.company, now=now)
        self.assertNotIn(lead, list(qs))

    def test_sla_disabled_returns_empty(self):
        now = timezone.now()
        _phone_ok_lead(self.company, hours_ago=100)
        qs = selectors.leads_callback_sla_depasse(
            self.company, now=now, seuil_heures=0)
        self.assertEqual(list(qs), [])

    def test_company_scoped(self):
        other = Company.objects.create(nom='Autre QW4', slug='qw4-autre')
        CompanyProfile.objects.create(company=other, lead_sla_hours=8)
        now = timezone.now()
        lead_a = _phone_ok_lead(self.company, hours_ago=10)
        _phone_ok_lead(other, hours_ago=10)
        qs = selectors.leads_callback_sla_depasse(self.company, now=now)
        self.assertEqual(list(qs), [lead_a])


class EscaladerRappelsDemandesCommandTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor QW4 Cmd', slug='taqinor-qw4-cmd')
        CompanyProfile.objects.create(company=self.company, lead_sla_hours=8)
        from apps.roles.models import Role
        role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_voir'])
        self.owner = User.objects.create_user(
            username='owner_qw4_cmd', password='x', company=self.company, role=role)

    def test_escalates_callback_sla_breach_once(self):
        now = timezone.now()
        lead = _phone_ok_lead(self.company, hours_ago=10, owner=self.owner)

        escalated = escalader_rappels_demandes(now=now)
        self.assertEqual(escalated, 1)
        self.assertTrue(LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE,
            body__icontains='rappel').exists())
        self.assertEqual(Notification.objects.filter(recipient=self.owner).count(), 1)

        # Deuxième passage — idempotent.
        escalated_2 = escalader_rappels_demandes(now=now)
        self.assertEqual(escalated_2, 0)
        self.assertEqual(Notification.objects.filter(recipient=self.owner).count(), 1)

    def test_whatsapp_only_lead_never_escalated(self):
        now = timezone.now()
        lead = Lead.objects.create(
            company=self.company, nom='WA only', telephone='+212600000002',
            owner=self.owner, contact_preference=Lead.ContactPreference.WHATSAPP_ONLY)
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=now - datetime.timedelta(hours=48))
        escalated = escalader_rappels_demandes(now=now)
        self.assertEqual(escalated, 0)

    def test_dry_run_never_writes(self):
        now = timezone.now()
        _phone_ok_lead(self.company, hours_ago=10, owner=self.owner)
        escalated = escalader_rappels_demandes(now=now, dry_run=True)
        self.assertEqual(escalated, 1)
        self.assertEqual(LeadActivity.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)


class QX15ContactPreferenceSetAtClockTests(TestCase):
    """QX15 — the SLA clock measures from `contact_preference_set_at`, not
    blindly from `date_creation`. An OLD lead whose callback preference is
    set NOW must not appear instantly SLA-breached (false-urgent noise)."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor QX15', slug='taqinor-qx15')
        CompanyProfile.objects.create(company=self.company, lead_sla_hours=8)  # callback = 4h

    def test_old_lead_fresh_preference_not_escalated(self):
        now = timezone.now()
        lead = Lead.objects.create(
            company=self.company, nom='Vieux lead', telephone='+212600222233',
            contact_preference=Lead.ContactPreference.PHONE_OK)
        # Lead créé il y a 30 jours, mais la préférence vient d'être posée.
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=now - datetime.timedelta(days=30),
            contact_preference_set_at=now)
        qs = selectors.leads_callback_sla_depasse(self.company, now=now)
        self.assertNotIn(lead, list(qs))

    def test_old_preference_set_at_still_escalates(self):
        now = timezone.now()
        lead = Lead.objects.create(
            company=self.company, nom='Rappel ancien', telephone='+212600222244',
            contact_preference=Lead.ContactPreference.PHONE_OK)
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=now - datetime.timedelta(days=30),
            contact_preference_set_at=now - datetime.timedelta(hours=10))
        qs = selectors.leads_callback_sla_depasse(self.company, now=now)
        self.assertIn(lead, list(qs))

    def test_null_set_at_falls_back_to_date_creation(self):
        # Lead créé avant l'ajout du champ (NULL) — comportement historique
        # inchangé : mesure depuis date_creation.
        now = timezone.now()
        lead = _phone_ok_lead(self.company, hours_ago=10)
        self.assertIsNone(lead.contact_preference_set_at)
        qs = selectors.leads_callback_sla_depasse(self.company, now=now)
        self.assertIn(lead, list(qs))

    def test_webhook_stamps_contact_preference_set_at(self):
        from django.test import override_settings
        from django.urls import reverse
        import json as _json

        with override_settings(WEBSITE_LEAD_WEBHOOK_SECRET='qx15-secret'):
            url = reverse('website-lead-webhook')
            res = self.client.post(
                url,
                data=_json.dumps({
                    'fullName': 'Test QX15',
                    'phoneE164': '+212600222255',
                    'contactPreference': 'phone_ok',
                    'consent': True,
                }),
                content_type='application/json',
                HTTP_X_WEBHOOK_SECRET='qx15-secret',
            )
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNotNone(lead.contact_preference_set_at)

    def test_services_stamps_contact_preference_set_at(self):
        from apps.crm.services import notify_client_contact_request

        lead = Lead.objects.create(
            company=self.company, nom='Via proposition',
            telephone='+212600222266')
        self.assertIsNone(lead.contact_preference_set_at)
        notify_client_contact_request('DEV-001', lead, canal='rappel')
        lead.refresh_from_db()
        self.assertEqual(lead.contact_preference, Lead.ContactPreference.PHONE_OK)
        self.assertIsNotNone(lead.contact_preference_set_at)
