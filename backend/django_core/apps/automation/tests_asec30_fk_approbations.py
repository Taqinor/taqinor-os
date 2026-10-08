"""ASEC30 — automatisations : FK inscriptibles bornées à la société, champs
posés par le serveur figés.

Constat C-ASEC-005 site (e) + C-ASEC-009 volet approbations : déclencheur
webhook, demande d'approbation et délégation acceptaient l'id d'une ligne
d'une AUTRE société ; une demande DÉCIDÉE restait modifiable ; le délégant
d'une délégation changeait au PATCH ; ``active_delegation_for`` ne filtrait
pas par société.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.automation import services
from apps.automation.models import (
    ActionType, ApprovalDelegation, ApprovalRequest, ApprovalRequestType,
    AutomationRule, IncomingWebhookTrigger, TriggerType,
)
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/automation'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _regle(company, nom):
    return AutomationRule.objects.create(
        company=company, nom=nom,
        trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
        action_type=ActionType.CREATE_ACTIVITY, action_config={'body': 'x'})


class AutomationFkTests(TestCase):
    def setUp(self):
        self.a = Company.objects.create(nom='ASEC30 A', slug='asec30-a')
        self.b = Company.objects.create(nom='ASEC30 B', slug='asec30-b')
        self.admin_a = User.objects.create_user(
            username='asec30_admin_a', password='x', role_legacy='admin',
            company=self.a)
        self.collegue_a = User.objects.create_user(
            username='asec30_collegue_a', password='x',
            role_legacy='normal', company=self.a)
        self.user_b = User.objects.create_user(
            username='asec30_user_b', password='x', role_legacy='admin',
            company=self.b)
        self.regle_a = _regle(self.a, 'Règle A')
        self.regle_a2 = _regle(self.a, 'Règle A2')
        self.regle_b = _regle(self.b, 'Règle B')
        self.trigger = IncomingWebhookTrigger.objects.create(
            company=self.a, rule=self.regle_a)
        self.type_a = ApprovalRequestType.objects.create(
            company=self.a, nom='Achat A')
        self.type_b = ApprovalRequestType.objects.create(
            company=self.b, nom='Achat B')
        self.demande = ApprovalRequest.objects.create(
            company=self.a, request_type=self.type_a,
            demandeur=self.collegue_a, payload={'montant': 100},
            status=ApprovalRequest.Status.APPROVED)
        maintenant = timezone.now()
        self.debut = maintenant - timedelta(days=1)
        self.fin = maintenant + timedelta(days=1)
        self.delegation = ApprovalDelegation.objects.create(
            company=self.a, delegant=self.admin_a, suppleant=self.collegue_a,
            date_debut=self.debut, date_fin=self.fin)
        self.api = _api(self.admin_a)

    def test_webhook_rule_etrangere_400(self):
        r = self.api.patch(f'{BASE}/incoming-webhooks/{self.trigger.pk}/',
                           {'rule': self.regle_b.pk}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('rule', r.data)
        r2 = self.api.patch(f'{BASE}/incoming-webhooks/{self.trigger.pk}/',
                            {'rule': 999999}, format='json')
        self.assertEqual(r2.status_code, 400, r2.data)
        self.trigger.refresh_from_db()
        self.assertEqual(self.trigger.rule_id, self.regle_a.pk)

    def test_request_type_etranger_400(self):
        self.demande.status = ApprovalRequest.Status.PENDING
        self.demande.save(update_fields=['status'])
        r = self.api.patch(f'{BASE}/approval-requests/{self.demande.pk}/',
                           {'request_type': self.type_b.pk}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('request_type', r.data)
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.request_type_id, self.type_a.pk)

    def test_demande_decidee_figee(self):
        type_a2 = ApprovalRequestType.objects.create(
            company=self.a, nom='Autre A')
        r = self.api.patch(f'{BASE}/approval-requests/{self.demande.pk}/',
                           {'payload': {'montant': 999999},
                            'request_type': type_a2.pk}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.payload, {'montant': 100})
        self.assertEqual(self.demande.request_type_id, self.type_a.pk)
        self.assertEqual(self.demande.status,
                         ApprovalRequest.Status.APPROVED)

    def test_delegation_suppleant_etranger_400(self):
        avant = ApprovalDelegation.objects.count()
        for champ in ('suppleant', 'delegant'):
            corps = {'delegant': self.admin_a.pk,
                     'suppleant': self.collegue_a.pk,
                     'date_debut': self.debut.isoformat(),
                     'date_fin': self.fin.isoformat()}
            corps[champ] = self.user_b.pk
            r = self.api.post(f'{BASE}/approval-delegations/', corps,
                              format='json')
            self.assertEqual(r.status_code, 400, r.data)
            self.assertIn(champ, r.data)
        self.assertEqual(ApprovalDelegation.objects.count(), avant)
        r_ok = self.api.post(f'{BASE}/approval-delegations/', {
            'delegant': self.admin_a.pk, 'suppleant': self.collegue_a.pk,
            'date_debut': self.debut.isoformat(),
            'date_fin': self.fin.isoformat()}, format='json')
        self.assertEqual(r_ok.status_code, 201, r_ok.data)

    def test_delegant_fige_au_patch(self):
        r = self.api.patch(
            f'{BASE}/approval-delegations/{self.delegation.pk}/',
            {'delegant': self.collegue_a.pk}, format='json')
        self.assertIn(r.status_code, (200, 400), r.data)
        self.delegation.refresh_from_db()
        self.assertEqual(self.delegation.delegant_id, self.admin_a.pk)

    def test_active_delegation_filtre_societe(self):
        # Ligne incohérente d'une autre société portant le délégant de A.
        self.delegation.delete()
        ApprovalDelegation.objects.create(
            company=self.b, delegant=self.admin_a, suppleant=self.user_b,
            date_debut=self.debut, date_fin=self.fin)
        self.assertIsNone(services.active_delegation_for(self.admin_a))
        self.assertNotIn(
            self.admin_a.pk,
            services.visible_demandeur_ids_for(self.user_b) - {self.user_b.pk})
        propre = ApprovalDelegation.objects.create(
            company=self.a, delegant=self.admin_a, suppleant=self.collegue_a,
            date_debut=self.debut, date_fin=self.fin)
        self.assertEqual(services.active_delegation_for(self.admin_a), propre)
