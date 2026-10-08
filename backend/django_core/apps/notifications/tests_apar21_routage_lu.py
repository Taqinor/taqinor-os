"""APAR21 — les règles de routage (Paramètres › Notifications) sont LUES par
tous les émetteurs de l'app notifications (C-APAR-026) : une règle
``approval_requested → Commercial n`` fait notifier n à la création d'une
approbation d'automatisation ; une règle sur un événement non routable est
refusée (400).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from . import digests, sweeps
from .models import Notification, NotificationRoutingRule
from .services import EVENEMENTS_ROUTABLES, merged_preferences
from .types_evenements import EventType

User = get_user_model()


class RoutageLuTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR21')
        self.admin = User.objects.create_user(
            username='apar21_admin', password='pw', company=self.company,
            role_legacy='admin')
        self.commercial = User.objects.create_user(
            username='apar21_commercial', password='pw',
            company=self.company, role_legacy='normal')

    def _approbation(self):
        from apps.automation.models import (
            ActionType, AutomationApproval, AutomationRule, TriggerType,
        )
        regle = AutomationRule.objects.create(
            company=self.company, nom='APAR21',
            trigger_type=TriggerType.DEVIS_ACCEPTED,
            action_type=ActionType.SEND_EMAIL, requires_approval=True)
        with self.captureOnCommitCallbacks(execute=True):
            AutomationApproval.objects.create(
                company=self.company, rule=regle, description='À valider',
                requested_by=self.admin)

    def test_regle_utilisateur_notifie_la_cible(self):
        NotificationRoutingRule.objects.create(
            company=self.company, event_type=EventType.APPROVAL_REQUESTED,
            target_user=self.commercial, enabled=True)
        self._approbation()
        self.assertEqual(Notification.objects.filter(
            recipient=self.commercial,
            event_type=EventType.APPROVAL_REQUESTED).count(), 1)

    def test_sans_regle_managers_par_defaut(self):
        self._approbation()
        self.assertEqual(Notification.objects.filter(
            recipient=self.admin,
            event_type=EventType.APPROVAL_REQUESTED).count(), 1)
        self.assertFalse(Notification.objects.filter(
            recipient=self.commercial).exists())

    def test_managers_et_digest_lisent_la_regle(self):
        NotificationRoutingRule.objects.create(
            company=self.company, event_type=EventType.CHANTIER_DUE,
            target_user=self.commercial, enabled=True)
        self.assertEqual(
            sweeps._managers(self.company, EventType.CHANTIER_DUE),
            [self.commercial])
        NotificationRoutingRule.objects.create(
            company=self.company, event_type=EventType.DIGEST,
            target_user=self.commercial, enabled=True)
        self.assertEqual(digests._recipients(self.company), [self.commercial])

    def test_palier_du_role_fait_autorite(self):
        from apps.roles.models import Role
        from apps.roles.permissions_registre import ADMIN_PERMISSIONS
        role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=list(ADMIN_PERMISSIONS), est_systeme=True)
        # role_legacy dérivé 'normal' mais Role administrateur.
        self.commercial.role = role
        self.commercial.save()
        self.assertIn(self.commercial, sweeps._managers(self.company))

    def test_evenement_non_routable_refuse(self):
        api = APIClient()
        api.force_authenticate(self.admin)
        r = api.post('/api/django/notifications/routing-rules/', {
            'event_type': EventType.LEAD_ASSIGNED, 'target_role': 'admin'},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('non routable', str(r.data))
        r = api.post('/api/django/notifications/routing-rules/', {
            'event_type': EventType.APPROVAL_REQUESTED,
            'target_user': self.commercial.pk}, format='json')
        self.assertEqual(r.status_code, 201, r.data)

    def test_liste_servie_a_l_ecran(self):
        lignes = {p['event_type']: p['routable']
                  for p in merged_preferences(self.admin)}
        self.assertFalse(lignes[EventType.LEAD_ASSIGNED])
        self.assertTrue(lignes[EventType.APPROVAL_REQUESTED])
        self.assertTrue(EVENEMENTS_ROUTABLES <= set(EventType.values))
