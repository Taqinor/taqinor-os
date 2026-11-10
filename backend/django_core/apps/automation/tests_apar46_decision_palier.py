"""APAR46 — « qui peut décider » est porté par les SERVICES de décision.

Constat C-APAR-004 : seule la vue ``AutomationApprovalViewSet`` gardait le
palier approbateur ; la boîte unifiée (``reporting/approbations-en-attente/
decider/``), la décision en masse et le jeton push appelaient
``automation.services.decider_approval`` / ``core.workflow.decide_step`` sans
contrôle — un Commercial (palier normal) y approuvait, y compris SA propre
demande.

Test-du-test : retirer ``verifier_decideur_approval`` de
``decider_approval`` ⇒ le cas agrégateur/automation redevient 200.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.automation.models import (
    ActionType, ApprovalRequest, ApprovalRequestType, AutomationApproval,
    AutomationRule, AutomationRun, TriggerType,
)
from apps.notifications.approval_tokens import make_approval_token
from authentication.models import Company
from core import workflow as core_workflow
from core.models import (
    WorkflowDefinition, WorkflowStepDefinition, WorkflowStepInstance,
)

User = get_user_model()
BASE = '/api/django/reporting/approbations-en-attente/'
NOW = timezone.make_aware(datetime.datetime(2026, 1, 1, 8, 0, 0))


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DecisionPalierTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='apar46-co', defaults={'nom': 'APAR46'})
        self.commercial = User.objects.create_user(
            username='apar46-commercial', password='x', company=self.co,
            role_legacy='normal')
        self.resp = User.objects.create_user(
            username='apar46-resp', password='x', company=self.co,
            role_legacy='responsable')
        self.regle = AutomationRule.objects.create(
            company=self.co, nom='Activité différée', enabled=True,
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.WAIT, action_config={},
            requires_approval=True)
        self.n = 0

    def _approval(self):
        return AutomationApproval.objects.create(
            company=self.co, rule=self.regle, requested_by=self.commercial,
            status=AutomationApproval.Status.PENDING, description='x')

    def _step(self):
        self.n += 1
        wf = WorkflowDefinition.objects.create(
            company=self.co, code=f'apar46-{self.n}', nom='APAR46')
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=1, nom='Palier 1')
        cible = Company.objects.get_or_create(
            slug=f'apar46-cible-{self.n}', defaults={'nom': 'Cible'})[0]
        instance = core_workflow.demarrer_workflow(wf, cible, self.co, now=NOW)
        return core_workflow.etape_courante_de(instance)

    def _objet(self, source):
        return self._approval() if source == 'automation' else self._step()

    def _toujours_en_attente(self, source, obj):
        obj.refresh_from_db()
        if source == 'automation':
            self.assertEqual(obj.status, AutomationApproval.Status.PENDING)
            self.assertIsNone(obj.decided_by_id)
            self.assertFalse(AutomationRun.objects.filter(
                rule=self.regle).exists())  # aucun run_approved
        else:
            self.assertEqual(obj.statut, WorkflowStepInstance.STATUT_EN_ATTENTE)
            self.assertIsNone(obj.assignee_id)

    def _decider(self, chemin, user, source, obj):
        if chemin == 'inbox':
            r = _api(user).post(BASE + 'decider/', {
                'source': source, 'id': obj.pk, 'decision': 'approuver',
            }, format='json')
            return r.status_code
        if chemin == 'masse':
            r = _api(user).post(BASE + 'decider-en-masse/', {
                'items': [{'source': source, 'id': obj.pk}],
                'decision': 'approuver',
            }, format='json')
            self.assertEqual(r.status_code, 200, r.data)
            return 200 if r.data['resultats'][0]['ok'] else 403
        token = make_approval_token(user.pk, source, obj.pk, 'approuver')
        r = APIClient().post(BASE + 'decider-push/', {'token': token},
                             format='json')
        return r.status_code

    def test_commercial_refuse_sur_tous_les_chemins(self):
        for source in ('automation', 'workflow'):
            for chemin in ('inbox', 'masse', 'push'):
                with self.subTest(source=source, chemin=chemin):
                    obj = self._objet(source)
                    self.assertEqual(
                        self._decider(chemin, self.commercial, source, obj),
                        403)
                    self._toujours_en_attente(source, obj)

    def test_responsable_decide(self):
        for source in ('automation', 'workflow'):
            for chemin in ('inbox', 'masse', 'push'):
                with self.subTest(source=source, chemin=chemin):
                    obj = self._objet(source)
                    self.assertEqual(
                        self._decider(chemin, self.resp, source, obj), 200)

    def test_demandeur_responsable_ne_decide_pas_sa_demande(self):
        approval = AutomationApproval.objects.create(
            company=self.co, rule=self.regle, requested_by=self.resp,
            status=AutomationApproval.Status.PENDING, description='x')
        self.assertEqual(
            self._decider('inbox', self.resp, 'automation', approval), 403)
        self._toujours_en_attente('automation', approval)

    def test_type_palier_admin_refuse_au_palier_responsable(self):
        """APFS111 — un type « admin » n'est décidé (approuver, rejeter) que
        par le palier administrateur ; un type « responsable » reste ouvert
        au palier responsable. Mutant : retirer le contrôle ⇒ 200."""
        admin = User.objects.create_user(
            username='apfs111-admin', password='x', company=self.co,
            role_legacy='admin')
        base = '/api/django/automation/approval-requests/'

        def demande(palier):
            type_ = ApprovalRequestType.objects.create(
                company=self.co, nom=f'APFS111 {palier}',
                palier_approbateur=palier, min_approbations=1)
            return ApprovalRequest.objects.create(
                company=self.co, request_type=type_,
                demandeur=self.commercial, payload={})

        req = demande('admin')
        for geste in ('approve', 'reject'):
            with self.subTest(geste=geste):
                r = _api(self.resp).post(f'{base}{req.pk}/{geste}/', {},
                                         format='json')
                self.assertEqual(r.status_code, 403, r.data)
                self.assertEqual(
                    r.data['detail'], 'Décision réservée au palier '
                    'administrateur pour ce type de demande.')
                req.refresh_from_db()
                self.assertEqual(req.status, ApprovalRequest.Status.PENDING)
                self.assertFalse(req.decisions.exists())
        r = _api(admin).post(f'{base}{req.pk}/approve/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        req.refresh_from_db()
        self.assertEqual(req.status, ApprovalRequest.Status.APPROVED)

        ouverte = demande('responsable')
        r = _api(self.resp).post(f'{base}{ouverte.pk}/approve/', {},
                                 format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_message_explicite(self):
        r = _api(self.commercial).post(BASE + 'decider/', {
            'source': 'automation', 'id': self._approval().pk,
            'decision': 'approuver'}, format='json')
        self.assertIn('palier approbateur', r.data['detail'])
