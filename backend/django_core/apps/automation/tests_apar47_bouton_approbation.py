"""APAR47 — un bouton UI ne contourne ni l'approbation ni sa cible.

Constat C-APAR-005 : ``services.declencher_bouton_ui`` appelait
``engine.run_action`` directement (une règle ``requires_approval=True``
s'exécutait sur le clic d'un Commercial) et la vue ``declencher`` acceptait
n'importe quel ``target_model`` (un bouton « crm.lead » exécutait sa règle sur
un devis).

Test-du-test : rappeler ``engine.run_action`` sans passer par
``_needs_approval`` dans ``declencher_bouton_ui`` ⇒
``test_lead_cree_une_demande`` rouge.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.automation.models import (
    ActionType, AutomationApproval, AutomationRule, AutomationRun,
    TriggerType,
)
from apps.crm.models import Client, Lead, LeadActivity
from apps.crm.stages import NEW
from apps.ventes.models import Devis
from authentication.models import Company
from core.models import UiActionBouton

URL = '/api/django/core/ui-boutons/'


class BoutonApprobationTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='apar47-co', defaults={'nom': 'APAR47'})
        self.commercial = get_user_model().objects.create_user(
            username='apar47-commercial', password='x', company=self.co,
            role_legacy='normal')
        self.regle = AutomationRule.objects.create(
            company=self.co, nom='Relance validée', enabled=True,
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'Relance APAR47'}, requires_approval=True)
        self.bouton = UiActionBouton.objects.create(
            company=self.co, cible='crm.lead', libelle='Relancer',
            type_action=UiActionBouton.TypeAction.AUTOMATION,
            ref=self.regle.pk)
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.commercial)}'))

    def _declencher(self, target_model, target_id):
        return self.api.post(f'{URL}{self.bouton.pk}/declencher/', {
            'target_model': target_model, 'target_id': target_id,
        }, format='json')

    def test_devis_cible_non_autorisee(self):
        client = Client.objects.create(
            company=self.co, nom='C47', email='c47@example.invalid')
        devis = Devis.objects.create(
            company=self.co, client=client, reference='DEV-APAR47',
            statut='envoye')
        res = self._declencher('ventes.devis', devis.pk)
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn('cible non autorisée', res.data['detail'])
        self.assertEqual(AutomationRun.objects.filter(
            rule=self.regle).count(), 0)
        self.assertEqual(AutomationApproval.objects.filter(
            rule=self.regle).count(), 0)

    def test_lead_cree_une_demande(self):
        lead = Lead.objects.create(
            company=self.co, nom='Lead APAR47', stage=NEW)
        res = self._declencher('crm.lead', lead.pk)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data['ok'])
        self.assertIn("Demande d'approbation créée", res.data['message'])
        demande = AutomationApproval.objects.get(rule=self.regle)
        self.assertEqual(demande.status, AutomationApproval.Status.PENDING)
        self.assertEqual(demande.target_id, lead.pk)
        self.assertEqual(demande.requested_by_id, self.commercial.pk)
        runs = AutomationRun.objects.filter(rule=self.regle)
        self.assertEqual(
            list(runs.values_list('status', flat=True)),
            [AutomationRun.Status.PENDING_APPROVAL])
        self.assertFalse(LeadActivity.objects.filter(
            lead=lead, body='Relance APAR47').exists())
