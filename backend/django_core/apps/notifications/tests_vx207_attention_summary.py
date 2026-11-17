"""VX207 — test de contrat : une seule vérité de comptage.

`GET /notifications/attention-summary/` doit renvoyer le MÊME décompte que
les autres surfaces (badge sidebar via `useApprobationsCount`, en-tête « Ma
file »), en réutilisant les MÊMES fonctions/sélecteurs — jamais une
dérivation client parallèle. Ce test force 5 approbations en attente et
vérifie que le champ `approbations` vaut bien 5 — la même donnée que consomme
`reporting.approbations_en_attente` et `records.views.ActivityViewSet.ma_file`.
ASUP64 (D-ASUP-7 = retirer) : la route ne sert plus QUE `approbations`.
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
        self.assertEqual(resp.data, {'approbations': 0})

    def test_seules_les_cles_lues_sont_servies(self):
        """ASUP64 — un Commercial avec un à-faire en retard, un du jour et une
        approbation en attente : la réponse ne porte plus que `approbations`
        (= 1, le chiffre du badge et de la cloche) ; « Ma file » garde ses
        paniers d'à-faire (le survivant)."""
        import datetime

        from django.contrib.contenttypes.models import ContentType

        from apps.automation.models import AutomationApproval
        from apps.crm.models import Lead
        from apps.records.models import Activity

        commercial = _make_user(self.company, 'asup64_commercial')
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(commercial)}')
        lead = Lead.objects.create(company=self.company, nom='ASUP64')
        today = datetime.date.today()
        for due in (today - datetime.timedelta(days=1), today):
            Activity.objects.create(
                company=self.company, content_type=ContentType.objects.get_for_model(Lead),
                object_id=lead.pk, summary='Rappeler', assigned_to=commercial, due_date=due)
        AutomationApproval.objects.create(
            company=self.company, rule=self._make_rule(), description='Action', requested_by=self.requester)

        resp = api.get('/api/django/notifications/attention-summary/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data, {'approbations': 1})
        file = api.get('/api/django/records/activities/ma-file/').data['resume']
        self.assertEqual((file['en_retard'], file['aujourdhui']), (1, 1))
