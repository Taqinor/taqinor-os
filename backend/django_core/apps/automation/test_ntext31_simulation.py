"""NTEXT31 — simulation (dry-run) d'une règle d'automatisation.

``POST automation/rules/<id>/simuler/`` liste ce que la règle FERAIT (par
action et par étape) sans muter l'enregistrement, sans envoyer d'email et sans
créer le moindre objet — seule une ligne ``AutomationRun`` de statut
``simulation`` est écrite comme trace.
"""
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead
from apps.customfields.models import CustomFieldDef, CustomObjectDef, CustomRecord

from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, AutomationStep, TriggerType,
)
from apps.automation.simulation import simuler_regle

User = get_user_model()

URL = '/api/django/automation/rules/'


class SimulationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='NTEXT31 Co')
        self.autre = Company.objects.create(nom='NTEXT31 Autre')
        self.user = User.objects.create_user(
            username='ntext31_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

        self.lead = Lead.objects.create(
            company=self.company, nom='Client Test', stage='NEW',
            email='client@example.com', priorite='normale')
        self.objet = CustomObjectDef.objects.create(
            company=self.company, code='suivi', libelle='Suivi')
        CustomFieldDef.objects.create(
            company=self.company, module='custom:suivi', code='titre',
            libelle='Titre', type='text')

        self.rule = AutomationRule.objects.create(
            company=self.company, nom='Email + champ',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.SET_FIELD, action_config={})
        AutomationStep.objects.create(
            rule=self.rule, ordre=1, action_type=ActionType.SEND_EMAIL,
            action_config={'body': 'Bonjour {nom}'})
        AutomationStep.objects.create(
            rule=self.rule, ordre=2, action_type=ActionType.SET_FIELD,
            action_config={'field': 'priorite', 'value': 'haute'})

    def _simuler(self, **corps):
        corps.setdefault('target_model', 'crm.lead')
        corps.setdefault('target_id', self.lead.pk)
        return self.api.post(f'{URL}{self.rule.pk}/simuler/', corps,
                             format='json')

    def test_lists_both_effects_without_touching_anything(self):
        res = self._simuler(context={'nom': 'Amine'})
        self.assertEqual(res.status_code, 200, res.data)
        effets = res.data['effets']
        self.assertEqual(len(effets), 2)
        self.assertEqual(effets[0]['action_type'], ActionType.SEND_EMAIL)
        self.assertEqual(effets[0]['destinataire'], 'client@example.com')
        self.assertIn('Amine', effets[0]['corps'])
        self.assertEqual(effets[1]['champ'], 'priorite')
        self.assertEqual(effets[1]['valeur'], 'haute')
        self.assertEqual(effets[1]['etape_ordre'], 2)

        # AUCUN effet : ni mutation, ni email.
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.priorite, 'normale')
        self.assertEqual(len(mail.outbox), 0)

    def test_a_simulation_run_is_logged(self):
        self._simuler()
        run = AutomationRun.objects.get(company=self.company, rule=self.rule)
        self.assertEqual(run.status, AutomationRun.Status.SIMULATION)
        self.assertEqual(run.target_model, 'crm.lead')
        self.assertEqual(run.target_id, self.lead.pk)

    def test_custom_record_action_is_described_not_created(self):
        regle = AutomationRule.objects.create(
            company=self.company, nom='Créer suivi',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.CREATE_CUSTOM_RECORD,
            action_config={'object_code': 'suivi',
                           'data': {'titre': 'Lead {nom}'}})
        effets = simuler_regle(regle, self.lead, self.company,
                               context={'nom': 'Amine'})
        self.assertEqual(len(effets), 1)
        self.assertEqual(effets[0]['object_code'], 'suivi')
        self.assertEqual(effets[0]['donnees']['titre'], 'Lead Amine')
        self.assertEqual(CustomRecord.objects.count(), 0)

    def test_wait_and_loop_are_described_not_executed(self):
        regle = AutomationRule.objects.create(
            company=self.company, nom='Attente + boucle',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.SET_FIELD, action_config={})
        AutomationStep.objects.create(
            rule=regle, ordre=1, action_type=ActionType.WAIT,
            action_config={'delai_minutes': 60})
        AutomationStep.objects.create(
            rule=regle, ordre=2, action_type=ActionType.FOR_EACH,
            action_config={'source': 'contexte:lignes', 'sous_actions': [
                {'action_type': ActionType.SET_FIELD,
                 'action_config': {'field': 'priorite', 'value': 'haute'}}]})
        effets = simuler_regle(
            regle, self.lead, self.company,
            context={'lignes': [{'a': 1}, {'a': 2}, {'a': 3}]})
        self.assertEqual(effets[0]['delai_minutes'], 60)
        self.assertEqual(effets[1]['iterations'], 3)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.priorite, 'normale')
        # Une étape WAIT simulée ne planifie AUCUNE reprise.
        from apps.automation.models import AutomationScheduledStep
        self.assertEqual(AutomationScheduledStep.objects.count(), 0)

    def test_missing_target_is_400(self):
        res = self.api.post(f'{URL}{self.rule.pk}/simuler/', {},
                            format='json')
        self.assertEqual(res.status_code, 400)

    def test_target_of_other_company_is_404(self):
        etranger = Lead.objects.create(
            company=self.autre, nom='X', stage='NEW')
        res = self._simuler(target_id=etranger.pk)
        self.assertEqual(res.status_code, 404)

    def test_limited_role_cannot_simulate(self):
        limite = User.objects.create_user(
            username='ntext31_normal', password='x', role_legacy='normal',
            company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(limite)}')
        res = api.post(f'{URL}{self.rule.pk}/simuler/',
                       {'target_model': 'crm.lead',
                        'target_id': self.lead.pk}, format='json')
        self.assertEqual(res.status_code, 403)
