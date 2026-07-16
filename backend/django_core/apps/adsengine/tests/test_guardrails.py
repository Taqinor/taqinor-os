"""ENG3 — Tests des garde-fous (``guardrails.enforce`` + endpoint config).

Invariant central : ``enforce()`` lève TOUJOURS sur une transition ACTIVE, quelle
que soit la config — il n'existe aucun réglage qui puisse autoriser une
activation par le moteur (extension permanente de la règle #3).
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import guardrails
from apps.adsengine.models import GuardrailConfig

User = get_user_model()

BASE = '/api/django/adsengine/garde-fous/'


class EnforceNeverActivatesTests(SimpleTestCase):
    """``enforce`` — pas de base de données requise (logique pure)."""

    def test_paused_transition_is_allowed(self):
        self.assertTrue(guardrails.enforce(target_status='PAUSED'))

    def test_active_transition_always_raises(self):
        with self.assertRaises(guardrails.GuardrailViolation):
            guardrails.enforce(target_status='ACTIVE')

    def test_active_is_case_insensitive(self):
        for value in ('active', 'Active', ' ACTIVE ', 'ACTIF', 'actif'):
            with self.assertRaises(guardrails.GuardrailViolation):
                guardrails.enforce(target_status=value)

    def test_active_raises_regardless_of_permissive_config(self):
        # Une config volontairement « permissive » (plafonds énormes) ne peut
        # RIEN autoriser : l'activation reste interdite en dur. Instance non
        # sauvegardée → pas de DB (SimpleTestCase).
        permissive = GuardrailConfig(
            daily_budget_ceiling_mad=10_000_000,
            weekly_change_pct_max=100,
            anomaly_window_hours=1,
        )
        with self.assertRaises(guardrails.GuardrailViolation):
            guardrails.enforce(target_status='ACTIVE', config=permissive)

    def test_paused_allowed_with_config(self):
        cfg = GuardrailConfig(daily_budget_ceiling_mad=50)
        self.assertTrue(guardrails.enforce(target_status='PAUSED', config=cfg))


class GuardrailConfigEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='GC Co', slug='gc-co')
        role = Role.objects.create(
            company=self.company, nom='gc-role',
            permissions=['adsengine_view', 'adsengine_manage'])
        self.user = User.objects.create_user(
            username='gc_user', password='x', company=self.company,
            role_legacy='normal', role=role)

    def _auth(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        return api

    def test_create_uses_defaults_and_forces_company(self):
        other = Company.objects.create(nom='GC B', slug='gc-b')
        resp = self._auth().post(
            BASE, {'company': other.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        cfg = GuardrailConfig.objects.get(id=resp.data['id'])
        self.assertEqual(cfg.company_id, self.company.id)
        self.assertEqual(cfg.daily_budget_ceiling_mad, 100)
        self.assertEqual(cfg.weekly_change_pct_max, 20)
        self.assertEqual(cfg.anomaly_window_hours, 48)

    def test_no_activation_field_exposed(self):
        # L'activation n'est AUCUN champ : ni le modèle ni l'API ne l'exposent.
        model_fields = {f.name for f in GuardrailConfig._meta.get_fields()}
        for forbidden in ('active', 'activation', 'enabled', 'is_active'):
            self.assertNotIn(forbidden, model_fields)
