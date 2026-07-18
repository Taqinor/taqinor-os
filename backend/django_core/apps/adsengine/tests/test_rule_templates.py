"""ADSENG14 — Tests du catalogue FIXE de règles + CRUD (seed / catalogue).

Prouve : le catalogue porte exactement les 8 templates du PLAN, chaque règle
seedée naît en DÉFAUT SÛR (off + dry-run + propose), les overrides de params
hors whitelist sont ignorés, le seed est idempotent et company-scopé, et les
endpoints ``catalogue`` (lecture) / ``seed`` (écriture) respectent les
permissions fines.
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import rule_templates as rt
from apps.adsengine.models import RulePolicy

User = get_user_model()
CAT = '/api/django/adsengine/regles/catalogue/'
SEED = '/api/django/adsengine/regles/seed/'

# 8 gabarits d'origine + 7 gabarits « vocabulaire v2 » (ADSDEEP38).
EXPECTED_KEYS = {
    'stop_loss_cpl', 'revive', 'frequency_high', 'zero_delivery',
    'budget_pacing_breach', 'cpl_band', 'low_backlog', 'recon_divergence',
    # ADSDEEP38 — vocabulaire de conditions v2.
    'cpa_window_regression', 'cost_per_conversation_high', 'link_ctr_low',
    'hold_rate_low', 'top_spend_low_result', 'frequency_ratio_regression',
    'surf_scale_budget',
}
EXPECTED_COUNT = len(EXPECTED_KEYS)


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


class CatalogueShapeTests(SimpleTestCase):
    def test_catalogue_has_expected_templates(self):
        self.assertEqual(set(rt.RULE_TEMPLATES), EXPECTED_KEYS)
        self.assertEqual(len(rt.RULE_TEMPLATES), EXPECTED_COUNT)

    def test_every_template_has_required_fields(self):
        for key, tpl in rt.RULE_TEMPLATES.items():
            for field in ('label_fr', 'severity', 'cadence', 'scope',
                          'conditions', 'editable_params', 'default_params'):
                self.assertIn(field, tpl, f'{key} manque {field}')
            self.assertIn(tpl['cadence'], rt.CADENCES)
            # Le DSL de conditions est bien AND/OR.
            self.assertIn(tpl['conditions'].get('logic'), ('all', 'any'))

    def test_actionable_vs_alert_only(self):
        # Les templates de pause/rotation sont actionnables ; les templates
        # purement informatifs (revive, cpl_band, low_backlog, recon) non.
        self.assertTrue(rt.is_actionable('zero_delivery'))
        self.assertEqual(rt.action_kind('zero_delivery'), 'pause')
        self.assertTrue(rt.is_actionable('frequency_high'))
        self.assertEqual(rt.action_kind('frequency_high'), 'rotate_creative')
        for alert_only in ('revive', 'cpl_band', 'low_backlog',
                           'recon_divergence'):
            self.assertFalse(rt.is_actionable(alert_only))
            self.assertIsNone(rt.action_kind(alert_only))

    def test_resolve_params_ignores_non_whitelisted(self):
        params = rt.resolve_params(
            'stop_loss_cpl',
            {'threshold_mad': 500, 'evil_field': 999, 'window_days': 3})
        self.assertEqual(params['threshold_mad'], 500)   # whitelisté
        self.assertEqual(params['window_days'], 3)       # whitelisté
        self.assertNotIn('evil_field', params)           # ignoré
        self.assertIn('min_samples', params)             # défaut conservé

    def test_defaults_are_not_mutated(self):
        rt.resolve_params('stop_loss_cpl', {'threshold_mad': 1})
        self.assertEqual(
            rt.RULE_TEMPLATES['stop_loss_cpl']['default_params']
            ['threshold_mad'], 250)

    def test_instantiate_conditions_returns_frozen_dsl_and_params(self):
        conditions, params = rt.instantiate_conditions(
            'frequency_high', {'frequency_max': 2.5})
        self.assertEqual(
            conditions, rt.RULE_TEMPLATES['frequency_high']['conditions'])
        self.assertEqual(params['frequency_max'], 2.5)


class SeedDefaultPoliciesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Seed Co', slug='seed-co')

    def test_seed_creates_safe_off_dry_run(self):
        created = rt.seed_default_policies(self.company)
        self.assertEqual(len(created), EXPECTED_COUNT)
        rows = RulePolicy.objects.filter(company=self.company)
        self.assertEqual(rows.count(), EXPECTED_COUNT)
        # Défaut sûr : aucune règle activée, toutes en simulation, mode propose.
        self.assertFalse(rows.filter(enabled=True).exists())
        self.assertFalse(rows.filter(dry_run=False).exists())
        self.assertFalse(rows.exclude(mode=RulePolicy.Mode.PROPOSE).exists())
        # Une règle en simulation ne peut jamais être auto-effective.
        for r in rows:
            self.assertFalse(r.is_auto_effective)

    def test_seed_is_idempotent(self):
        rt.seed_default_policies(self.company)
        again = rt.seed_default_policies(self.company)
        self.assertEqual(len(again), 0)  # rien de nouveau au 2e passage
        self.assertEqual(
            RulePolicy.objects.filter(company=self.company).count(),
            EXPECTED_COUNT)

    def test_seed_is_company_scoped(self):
        other = Company.objects.create(nom='Other', slug='other-seed')
        rt.seed_default_policies(self.company)
        self.assertEqual(
            RulePolicy.objects.filter(company=other).count(), 0)


class CatalogueApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Cat Co', slug='cat-co')
        self.viewer = make_user(self.company, 'catviewer', ['adsengine_view'])
        self.manager = make_user(
            self.company, 'catmgr', ['adsengine_view', 'adsengine_manage'])

    def test_catalogue_lists_all_templates(self):
        resp = auth(self.viewer).get(CAT)
        self.assertEqual(resp.status_code, 200, resp.data)
        keys = {t['template_key'] for t in resp.data['templates']}
        self.assertEqual(keys, EXPECTED_KEYS)

    def test_catalogue_requires_view_permission(self):
        nobody = make_user(self.company, 'catnobody', [])
        self.assertEqual(auth(nobody).get(CAT).status_code, 403)

    def test_seed_endpoint_creates_and_is_idempotent(self):
        resp = auth(self.manager).post(SEED, {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], EXPECTED_COUNT)
        self.assertEqual(resp.data['total'], EXPECTED_COUNT)
        # 2e appel : rien de créé, total stable.
        resp2 = auth(self.manager).post(SEED, {}, format='json')
        self.assertEqual(resp2.data['created'], 0)
        self.assertEqual(resp2.data['total'], EXPECTED_COUNT)

    def test_seed_requires_manage_permission(self):
        # Un simple viewer (lecture seule) ne peut pas seeder.
        self.assertEqual(
            auth(self.viewer).post(SEED, {}, format='json').status_code, 403)
        self.assertEqual(
            RulePolicy.objects.filter(company=self.company).count(), 0)
