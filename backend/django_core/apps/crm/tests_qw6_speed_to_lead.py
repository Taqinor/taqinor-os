"""QW6 — Speed-to-lead assurance: no orphaned, silent lead.

Couvre :
  - ``default_responsable_for`` : round-robin parmi les utilisateurs
    commerciaux actifs (permission ``crm_creer``) quand aucun responsable par
    défaut n'est configuré — jamais un lead sans owner quand des commerciaux
    existent ;
  - ``pick_round_robin_owner`` : le moins chargé (le moins de leads assignés)
    gagne le tour ; company-scopé ; None si aucun commercial ;
  - ``notify_new_lead`` atteint bien le owner assigné (round-robin OU
    responsable par défaut configuré) + son supérieur (QJ27).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Lead
from apps.crm.services import (
    default_responsable_for, notify_new_lead, pick_round_robin_owner,
)
from apps.notifications.models import Notification
from apps.parametres.models import CompanyProfile
from apps.roles.models import Role

User = get_user_model()


class RoundRobinOwnerTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor QW6', slug='taqinor-qw6')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_creer', 'crm_voir'])

    def test_no_commercial_user_returns_none(self):
        self.assertIsNone(pick_round_robin_owner(self.company))

    def test_single_commercial_user_picked(self):
        user = User.objects.create_user(
            username='commercial1', password='x', company=self.company, role=self.role)
        self.assertEqual(pick_round_robin_owner(self.company), user)

    def test_least_loaded_user_picked(self):
        busy = User.objects.create_user(
            username='busy', password='x', company=self.company, role=self.role)
        free = User.objects.create_user(
            username='free', password='x', company=self.company, role=self.role)
        # Charge `busy` avec deux leads déjà assignés.
        Lead.objects.create(company=self.company, nom='L1', owner=busy)
        Lead.objects.create(company=self.company, nom='L2', owner=busy)
        self.assertEqual(pick_round_robin_owner(self.company), free)

    def test_rotates_after_assignment(self):
        u1 = User.objects.create_user(
            username='u1', password='x', company=self.company, role=self.role)
        u2 = User.objects.create_user(
            username='u2', password='x', company=self.company, role=self.role)
        first = pick_round_robin_owner(self.company)
        self.assertIn(first, (u1, u2))
        Lead.objects.create(company=self.company, nom='L1', owner=first)
        second = pick_round_robin_owner(self.company)
        self.assertNotEqual(second, first)

    def test_company_scoped(self):
        other = Company.objects.create(nom='Autre QW6', slug='qw6-autre')
        other_role = Role.objects.create(
            company=other, nom='Commercial', permissions=['crm_creer'])
        User.objects.create_user(
            username='other_user', password='x', company=other, role=other_role)
        # Pas d'utilisateur commercial dans self.company : None malgré un
        # commercial existant dans une AUTRE société.
        self.assertIsNone(pick_round_robin_owner(self.company))


class DefaultResponsableForFallbackTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor QW6 Default', slug='taqinor-qw6-default')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_creer'])

    def test_configured_default_takes_priority(self):
        configured = User.objects.create_user(
            username='configured', password='x', company=self.company, role=self.role)
        User.objects.create_user(
            username='other_commercial', password='x', company=self.company, role=self.role)
        CompanyProfile.objects.create(
            company=self.company, responsable_defaut_leads=configured)
        self.assertEqual(default_responsable_for(self.company), configured)

    def test_unconfigured_falls_back_to_round_robin(self):
        user = User.objects.create_user(
            username='rr_user', password='x', company=self.company, role=self.role)
        CompanyProfile.objects.create(company=self.company)  # pas de défaut
        self.assertEqual(default_responsable_for(self.company), user)

    def test_no_default_no_commercial_returns_none(self):
        CompanyProfile.objects.create(company=self.company)
        self.assertIsNone(default_responsable_for(self.company))


class SpeedToLeadNotificationReachesAssignedOwnerTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor QW6 Notif', slug='taqinor-qw6-notif')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_creer'])

    def test_round_robin_assigned_lead_still_gets_notified(self):
        owner = User.objects.create_user(
            username='rr_owner', password='x', company=self.company, role=self.role)
        CompanyProfile.objects.create(company=self.company)  # pas de défaut
        assigned = default_responsable_for(self.company)
        self.assertEqual(assigned, owner)

        lead = Lead.objects.create(
            company=self.company, nom='Prospect QW6', owner=assigned)
        notify_new_lead(lead)
        # Un lead créé AVEC owner déclenche aussi LEAD_ASSIGNED (signals) : on ne
        # compte que la notification produite par notify_new_lead (event dédié).
        self.assertEqual(Notification.objects.filter(
            recipient=owner, event_type='lead_new').count(), 1)

    def test_no_commercial_no_default_never_crashes(self):
        CompanyProfile.objects.create(company=self.company)
        lead = Lead.objects.create(
            company=self.company, nom='Prospect orphelin',
            owner=default_responsable_for(self.company))
        # owner=None : notify_new_lead ne doit jamais lever, simplement no-op.
        notify_new_lead(lead)
        self.assertEqual(Notification.objects.count(), 0)
