"""APAR9 — le webhook entrant public n'exécute QUE la règle de son jeton.

Constat C-APAR-009 : ``public_views.incoming_webhook`` appelait
``engine.evaluate(WEBHOOK_INBOUND, …)`` qui tirait TOUTES les règles
WEBHOOK_INBOUND de la société — un POST sur le jeton A exécutait aussi la
règle B (déclencheur désactivé + HMAC) et la règle C (sans webhook). La
création d'un déclencheur sur une règle d'un autre type était acceptée (201)
et un ``hmac_secret`` fourni pour un déclencheur existant était ignoré.

Test-du-test : retirer la garde ``rule_id`` de ``engine._trigger_matches``
(WEBHOOK_INBOUND) ⇒ ``test_post_jeton_a_ne_tire_que_a`` rouge.
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, IncomingWebhookTrigger,
    TriggerType,
)
from authentication.models import Company

BASE = '/api/django/automation/incoming-webhooks/'


class WebhookRegleUniqueTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='apar9-co', defaults={'nom': 'APAR9'})
        self.admin = get_user_model().objects.create_user(
            username='apar9-admin', password='x', company=self.co,
            role_legacy='admin')

        def regle(nom, trigger=TriggerType.WEBHOOK_INBOUND):
            return AutomationRule.objects.create(
                company=self.co, nom=nom, trigger_type=trigger,
                trigger_config={}, action_type=ActionType.WAIT,
                action_config={}, enabled=True)

        self.a = regle('A')
        self.b = regle('B')
        self.c = regle('C')
        self.d = regle('D', TriggerType.DATE_ECHEANCE_CHAMP)
        self.trig_a = IncomingWebhookTrigger.objects.create(
            company=self.co, rule=self.a)
        IncomingWebhookTrigger.objects.create(
            company=self.co, rule=self.b, enabled=False, hmac_secret='s3cr3t')

    def _api(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        return api

    def _runs(self, rule):
        return AutomationRun.objects.filter(company=self.co, rule=rule).count()

    def test_post_jeton_a_ne_tire_que_a(self):
        resp = self.client.post(
            f'/api/django/public/hooks/{self.trig_a.token}/',
            data=json.dumps({'x': 1}), content_type='application/json')
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(self._runs(self.a), 1)
        self.assertEqual(self._runs(self.b), 0)
        self.assertEqual(self._runs(self.c), 0)

    def test_creation_sur_regle_non_webhook_refusee(self):
        resp = self._api().post(BASE, {'rule': self.d.pk}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('rule', resp.data)
        self.assertFalse(
            IncomingWebhookTrigger.objects.filter(rule=self.d).exists())

    def test_patch_vers_regle_non_webhook_refuse(self):
        resp = self._api().patch(
            f'{BASE}{self.trig_a.pk}/', {'rule': self.d.pk}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('rule', resp.data)

    def test_secret_pour_declencheur_existant_explicite(self):
        resp = self._api().post(
            BASE, {'rule': self.a.pk, 'hmac_secret': 'nouveau'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('hmac_secret', resp.data)
        self.trig_a.refresh_from_db()
        self.assertEqual(self.trig_a.hmac_secret, '')

    def test_creation_nominale(self):
        resp = self._api().post(
            BASE, {'rule': self.c.pk, 'hmac_secret': 'k'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            IncomingWebhookTrigger.objects.get(rule=self.c).hmac_secret, 'k')
