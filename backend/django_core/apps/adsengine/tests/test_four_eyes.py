"""PUB103 — Tests du garde-fou « quatre yeux » optionnel sur l'approbation.

Prouve : flag OFF (défaut) → le proposeur peut approuver (mode solo intact) ;
flag ON → l'auto-approbation est refusée 403 (service ``FourEyesViolation`` +
API), un SECOND utilisateur approuve normalement ; une proposition machine
(proposed_by None) n'est jamais bloquée.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import services
from apps.adsengine.models import EngineAction, GuardrailConfig

User = get_user_model()


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class FourEyesServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='4E Co', slug='four-eyes')
        self.user_a = make_user(self.company, 'alice', ['adsengine_approve'])
        self.user_b = make_user(self.company, 'bob', ['adsengine_approve'])

    def _action(self, proposed_by):
        return EngineAction.objects.create(
            company=self.company, kind=EngineAction.Kind.PAUSE,
            reason_fr='Pause de sécurité.',
            status=EngineAction.Statut.PROPOSEE, proposed_by=proposed_by)

    def _cfg(self, four_eyes):
        cfg, _ = GuardrailConfig.objects.get_or_create(company=self.company)
        cfg.require_four_eyes = four_eyes
        cfg.save()

    def test_off_allows_self_approval(self):
        self._cfg(False)
        action = self._action(self.user_a)
        services.approve_action(action, user=self.user_a)
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPROUVEE)

    def test_on_blocks_self_approval(self):
        self._cfg(True)
        action = self._action(self.user_a)
        with self.assertRaises(services.FourEyesViolation):
            services.approve_action(action, user=self.user_a)
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)

    def test_on_allows_second_user(self):
        self._cfg(True)
        action = self._action(self.user_a)
        services.approve_action(action, user=self.user_b)
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPROUVEE)
        self.assertEqual(action.approved_by_id, self.user_b.id)

    def test_machine_proposal_never_blocked(self):
        self._cfg(True)
        action = self._action(None)  # proposée par le moteur
        services.approve_action(action, user=self.user_a)
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPROUVEE)


class FourEyesApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='4E API', slug='four-eyes-api')
        self.user_a = make_user(
            self.company, 'alice', ['adsengine_view', 'adsengine_approve'])

    def _action(self):
        return EngineAction.objects.create(
            company=self.company, kind=EngineAction.Kind.PAUSE,
            reason_fr='Pause de sécurité.',
            status=EngineAction.Statut.PROPOSEE, proposed_by=self.user_a)

    def test_self_approval_returns_403_when_flag_on(self):
        cfg, _ = GuardrailConfig.objects.get_or_create(company=self.company)
        cfg.require_four_eyes = True
        cfg.save()
        action = self._action()
        resp = auth(self.user_a).post(
            f'/api/django/adsengine/actions/{action.id}/approve/')
        self.assertEqual(resp.status_code, 403)
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)

    def test_self_approval_ok_when_flag_off(self):
        action = self._action()
        resp = auth(self.user_a).post(
            f'/api/django/adsengine/actions/{action.id}/approve/')
        self.assertEqual(resp.status_code, 200)
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPROUVEE)
