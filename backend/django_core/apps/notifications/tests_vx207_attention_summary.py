"""VX207 — test de contrat : une seule vérité de comptage.

`GET /notifications/attention-summary/` doit renvoyer le MÊME décompte que
les autres surfaces (badge sidebar via `useApprobationsCount`, en-tête « Ma
file »), en réutilisant les MÊMES fonctions/sélecteurs — jamais une
dérivation client parallèle. Ce test force 5 approbations en attente et
vérifie que le champ `approbations` (et `actions_dues`, qui les inclut)
valent bien 5 — la même donnée que consomme `reporting.approbations_en_
attente` et `records.views.ActivityViewSet.ma_file`.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()


def _make_company(name='VX207 Co'):
    return Company.objects.create(nom=name)


def _make_user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy=role_legacy)


class Vx207AttentionSummaryTests(TestCase):

    def setUp(self):
        self.company = _make_company()
        self.approver = _make_user(self.company, 'vx207_approver', role_legacy='admin')
        self.requester = _make_user(self.company, 'vx207_requester')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.approver)}')

    def _make_rule(self):
        from apps.automation.models import ActionType, AutomationRule, TriggerType
        return AutomationRule.objects.create(
            company=self.company, nom='Règle VX207',
            trigger_type=TriggerType.DEVIS_ACCEPTED,
            action_type=ActionType.SEND_EMAIL,
            requires_approval=True)

    def test_five_pending_approvals_show_five_everywhere(self):
        from apps.automation.models import AutomationApproval
        rule = self._make_rule()
        for i in range(5):
            AutomationApproval.objects.create(
                company=self.company, rule=rule,
                description=f'Action {i}', requested_by=self.requester)

        # 1) L'endpoint canonique VX207.
        resp = self.api.get('/api/django/notifications/attention-summary/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['approbations'], 5)
        self.assertEqual(resp.data['actions_dues'], 5)

        # 2) La même donnée que l'agrégateur `reporting.approbations_en_
        #    attente` (badge sidebar / carte Dashboard / rangée cloche VX86).
        resp2 = self.api.get('/api/django/reporting/approbations-en-attente/')
        self.assertEqual(resp2.status_code, 200, resp2.content)
        self.assertEqual(resp2.data['total'], 5)

        # 3) La même donnée que « Ma file » (VX83) — resume.approbations.
        resp3 = self.api.get('/api/django/records/activities/ma-file/')
        self.assertEqual(resp3.status_code, 200, resp3.content)
        self.assertEqual(resp3.data['resume']['approbations'], 5)

    def test_zero_when_nothing_pending(self):
        resp = self.api.get('/api/django/notifications/attention-summary/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['approbations'], 0)
        self.assertEqual(resp.data['actions_dues'], 0)
        self.assertEqual(resp.data['en_retard'], 0)
        self.assertEqual(resp.data['aujourdhui'], 0)
        self.assertEqual(resp.data['mentions_non_lues'], 0)
