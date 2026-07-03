"""YLEAD14 — Recyclage des leads non travaillés (SLA speed-to-lead → escalade).

Couvre :
  - ``selectors.leads_sla_depasse`` : un lead NEW assigné sans contact depuis
    plus que le seuil (``now`` injecté) est listé ; un lead déjà contacté ne
    l'est pas ; company-scopé ; SLA désactivé (0) → liste vide ;
  - la commande escalade (activité + notification) chaque lead SLA-dépassé,
    une seule fois (idempotent — un second passage ne re-notifie pas) ;
  - un lead déjà contacté n'est jamais escaladé ;
  - désassignation optionnelle au 2e seuil (``lead_sla_deassign_hours``),
    désactivée par défaut (0 → jamais désassigné) ;
  - best-effort : company-scopé, aucune fuite entre sociétés.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from django.contrib.auth import get_user_model

from apps.crm import selectors, stages
from apps.crm.management.commands.recycler_leads_non_travailles import (
    recycler_leads_non_travailles,
)
from apps.crm.models import Lead, LeadActivity
from apps.notifications.models import Notification
from apps.parametres.models import CompanyProfile

User = get_user_model()


def _old_new_lead(company, hours_ago=48, owner=None):
    lead = Lead.objects.create(
        company=company, nom='Prospect ancien', stage=stages.NEW, owner=owner)
    Lead.objects.filter(pk=lead.pk).update(
        date_creation=timezone.now() - datetime.timedelta(hours=hours_ago))
    lead.refresh_from_db()
    return lead


class LeadsSlaDepasseSelectorTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor YLEAD14', slug='taqinor-ylead14')
        CompanyProfile.objects.create(company=self.company, lead_sla_hours=24)

    def test_uncontacted_lead_past_sla_is_listed(self):
        now = timezone.now()
        lead = _old_new_lead(self.company, hours_ago=48)
        qs = selectors.leads_sla_depasse(self.company, now=now)
        self.assertIn(lead, list(qs))

    def test_already_contacted_lead_is_not_listed(self):
        now = timezone.now()
        lead = _old_new_lead(self.company, hours_ago=48)
        lead.first_contacted_at = timezone.now()
        lead.stage = stages.CONTACTED
        lead.save(update_fields=['first_contacted_at', 'stage'])
        qs = selectors.leads_sla_depasse(self.company, now=now)
        self.assertNotIn(lead, list(qs))

    def test_recent_lead_within_sla_not_listed(self):
        now = timezone.now()
        lead = _old_new_lead(self.company, hours_ago=1)
        qs = selectors.leads_sla_depasse(self.company, now=now)
        self.assertNotIn(lead, list(qs))

    def test_sla_disabled_returns_empty(self):
        now = timezone.now()
        _old_new_lead(self.company, hours_ago=100)
        qs = selectors.leads_sla_depasse(self.company, now=now, seuil_heures=0)
        self.assertEqual(list(qs), [])

    def test_company_scoped(self):
        other = Company.objects.create(nom='Autre', slug='ylead14-autre')
        CompanyProfile.objects.create(company=other, lead_sla_hours=24)
        now = timezone.now()
        lead_a = _old_new_lead(self.company, hours_ago=48)
        _old_new_lead(other, hours_ago=48)
        qs = selectors.leads_sla_depasse(self.company, now=now)
        self.assertEqual(list(qs), [lead_a])


class RecyclerLeadsCommandTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor YLEAD14 Cmd', slug='taqinor-ylead14-cmd')
        self.profile = CompanyProfile.objects.create(
            company=self.company, lead_sla_hours=24)
        from apps.roles.models import Role
        role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['crm_voir'])
        self.owner = User.objects.create_user(
            username='owner_ylead14', password='x',
            company=self.company, role=role)

    def test_escalates_sla_breached_lead_once(self):
        now = timezone.now()
        lead = _old_new_lead(self.company, hours_ago=48, owner=self.owner)

        escalated, deassigned = recycler_leads_non_travailles(now=now)
        self.assertEqual(escalated, 1)
        self.assertEqual(deassigned, 0)

        notes = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE)
        self.assertTrue(
            any('recyclage SLA' in (n.body or '') for n in notes))
        self.assertEqual(
            Notification.objects.filter(recipient=self.owner).count(), 1)

        # Deuxième passage — idempotent : pas de deuxième escalade/notif.
        escalated_2, _ = recycler_leads_non_travailles(now=now)
        self.assertEqual(escalated_2, 0)
        self.assertEqual(
            Notification.objects.filter(recipient=self.owner).count(), 1)

    def test_contacted_lead_is_never_escalated(self):
        now = timezone.now()
        lead = _old_new_lead(self.company, hours_ago=48, owner=self.owner)
        lead.first_contacted_at = timezone.now()
        lead.stage = stages.CONTACTED
        lead.save(update_fields=['first_contacted_at', 'stage'])

        escalated, _ = recycler_leads_non_travailles(now=now)
        self.assertEqual(escalated, 0)
        self.assertFalse(
            LeadActivity.objects.filter(lead=lead).exists())

    def test_deassign_disabled_by_default(self):
        """lead_sla_deassign_hours=0 (défaut) → jamais désassigné, même très
        ancien — comportement actuel préservé tant que non configuré."""
        now = timezone.now()
        lead = _old_new_lead(self.company, hours_ago=500, owner=self.owner)
        _, deassigned = recycler_leads_non_travailles(now=now)
        self.assertEqual(deassigned, 0)
        lead.refresh_from_db()
        self.assertEqual(lead.owner_id, self.owner.id)

    def test_deassign_after_second_threshold(self):
        self.profile.lead_sla_deassign_hours = 100
        self.profile.save(update_fields=['lead_sla_deassign_hours'])
        now = timezone.now()
        lead = _old_new_lead(self.company, hours_ago=150, owner=self.owner)

        _, deassigned = recycler_leads_non_travailles(now=now)
        self.assertEqual(deassigned, 1)
        lead.refresh_from_db()
        self.assertIsNone(lead.owner_id)

    def test_dry_run_does_not_write(self):
        now = timezone.now()
        lead = _old_new_lead(self.company, hours_ago=48, owner=self.owner)
        escalated, _ = recycler_leads_non_travailles(now=now, dry_run=True)
        self.assertEqual(escalated, 1)
        self.assertFalse(LeadActivity.objects.filter(lead=lead).exists())
        self.assertEqual(Notification.objects.count(), 0)
