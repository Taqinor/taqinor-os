"""NTEXT30 — versionnement d'une règle d'automatisation.

Chaque sauvegarde MODIFIÉE (``PATCH``/``PUT``) d'une règle existante snapshot
son état COURANT (avant modif) sous le prochain rang de version. Restaurer
une version antérieure recrée EXACTEMENT sa config : modifier une règle 3
fois puis restaurer v1 rétablit la config initiale.
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.automation.models import (
    ActionType, AutomationRule, AutomationRuleVersion, AutomationStep,
    TriggerType,
)

User = get_user_model()

RULES = '/api/django/automation/rules/'
VERSIONS = '/api/django/automation/rule-versions/'

_seq = itertools.count(1)


def make_company():
    n = next(_seq)
    return Company.objects.create(
        slug=f'ntext30-co-{n}', nom=f'NTEXT30 Co {n}')


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class VersionnementTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.admin = User.objects.create_user(
            username='ntext30_admin', password='x', role_legacy='admin',
            company=self.co)
        self.api = _auth(self.admin)
        self.rule = AutomationRule.objects.create(
            company=self.co, nom='Règle initiale',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE,
            trigger_config={'stage': 'NEW'},
            action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'v0'})

    def test_creation_ne_cree_aucune_version(self):
        self.assertEqual(
            AutomationRuleVersion.objects.filter(rule=self.rule).count(), 0)

    def test_modification_cree_une_version_numerotee_1(self):
        self.api.patch(f'{RULES}{self.rule.pk}/', {'nom': 'Règle v2'},
                       format='json')
        versions = AutomationRuleVersion.objects.filter(rule=self.rule)
        self.assertEqual(versions.count(), 1)
        v1 = versions.get(version=1)
        # v1 fige l'état AVANT la modif (le nom INITIAL, pas le nouveau).
        self.assertEqual(v1.snapshot['nom'], 'Règle initiale')

    def test_trois_modifications_puis_restaurer_v1_retablit_la_config_initiale(self):
        # État initial : nom='Règle initiale', body='v0'.
        self.api.patch(f'{RULES}{self.rule.pk}/', {
            'nom': 'Règle v2',
            'action_config': {'body': 'v2'},
        }, format='json')
        self.api.patch(f'{RULES}{self.rule.pk}/', {
            'nom': 'Règle v3',
            'action_config': {'body': 'v3'},
        }, format='json')
        self.api.patch(f'{RULES}{self.rule.pk}/', {
            'nom': 'Règle v4',
            'action_config': {'body': 'v4'},
        }, format='json')

        self.rule.refresh_from_db()
        self.assertEqual(self.rule.nom, 'Règle v4')
        self.assertEqual(
            AutomationRuleVersion.objects.filter(rule=self.rule).count(), 3)

        v1 = AutomationRuleVersion.objects.get(rule=self.rule, version=1)
        res = self.api.post(f'{VERSIONS}{v1.pk}/restaurer/')
        self.assertEqual(res.status_code, 200, res.data)

        self.rule.refresh_from_db()
        self.assertEqual(self.rule.nom, 'Règle initiale')
        self.assertEqual(self.rule.action_config, {'body': 'v0'})
        self.assertEqual(
            self.rule.trigger_config, {'stage': 'NEW'})

    def test_restaurer_recree_les_steps_de_la_version(self):
        AutomationStep.objects.create(
            rule=self.rule, ordre=1, action_type=ActionType.SEND_EMAIL,
            action_config={'subject': 'x'})
        self.api.patch(f'{RULES}{self.rule.pk}/', {'nom': 'Règle v2'},
                       format='json')
        # Après le snapshot v1 (qui a gelé l'étape ci-dessus), on retire
        # l'étape courante pour prouver que la restauration la RECRÉE.
        self.rule.steps.all().delete()
        self.assertEqual(self.rule.steps.count(), 0)

        v1 = AutomationRuleVersion.objects.get(rule=self.rule, version=1)
        self.api.post(f'{VERSIONS}{v1.pk}/restaurer/')

        self.rule.refresh_from_db()
        steps = list(self.rule.steps.all())
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].action_type, ActionType.SEND_EMAIL)
        self.assertEqual(steps[0].action_config, {'subject': 'x'})

    def test_versions_scopees_par_regle_et_visibles_via_le_filtre(self):
        autre_rule = AutomationRule.objects.create(
            company=self.co, nom='Autre règle',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.CREATE_ACTIVITY, action_config={})
        self.api.patch(f'{RULES}{self.rule.pk}/', {'nom': 'X'}, format='json')
        self.api.patch(f'{RULES}{autre_rule.pk}/', {'nom': 'Y'},
                       format='json')
        res = self.api.get(f'{VERSIONS}?rule={self.rule.pk}')
        self.assertEqual(res.status_code, 200, res.data)
        ids = [v['rule'] for v in res.data]
        self.assertTrue(all(r == self.rule.pk for r in ids))

    def test_isolation_societe_sur_les_versions(self):
        autre_co = make_company()
        autre_admin = User.objects.create_user(
            username='ntext30_autre', password='x', role_legacy='admin',
            company=autre_co)
        self.api.patch(f'{RULES}{self.rule.pk}/', {'nom': 'X'}, format='json')
        v1 = AutomationRuleVersion.objects.get(rule=self.rule, version=1)
        res = _auth(autre_admin).get(f'{VERSIONS}{v1.pk}/')
        self.assertEqual(res.status_code, 404)
