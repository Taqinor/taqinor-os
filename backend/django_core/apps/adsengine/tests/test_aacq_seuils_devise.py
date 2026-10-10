"""AACQ3 — D-AACQ-1 tranchée (a) : seuils et plafonds dans la devise du compte.

Chaque seuil ``*_mad`` d'une ``RulePolicy`` et chaque plafond de
``GuardrailConfig`` porte la devise POSÉE PAR LE SERVEUR à la saisie (devise du
compte Meta), jamais lue du corps. L'évaluation ne compare que si cette devise
égale celle du compte : une règle saisie en USD sur un compte USD se déclenche
à son seuil ; une règle antérieure (sans devise) reste « non applicable » hors
MAD, avec l'invite de ressaisie ; un changement de devise du compte rebascule
la règle en « non applicable ». Aucun taux de change, aucun appel Meta.
"""
import datetime

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import budget_applier, guardrails, rule_templates, rules_engine
from apps.adsengine.models import (
    AdCampaignMirror, AdSetMirror, EngineAction, GuardrailConfig,
    InsightSnapshot, MetaConnection, RulePolicy,
)

User = get_user_model()
TODAY = datetime.date(2026, 7, 16)
INVITE = 'ressaisir le seuil dans la devise du compte'


def _snap(company, obj, *, day, spend, results):
    ct = ContentType.objects.get_for_model(type(obj))
    InsightSnapshot.objects.create(
        company=company, content_type=ct, object_id=obj.pk,
        date=TODAY - datetime.timedelta(days=day),
        spend=str(spend), results=results)


class SeuilsDeviseTests(TestCase):
    def _societe(self, slug, currency='USD'):
        company = Company.objects.create(nom=slug, slug=slug)
        conn = MetaConnection.objects.create(
            company=company, ad_account_id='act_' + slug, currency=currency,
            enabled=True, credentials={'access_token': 'tok'})
        role = Role.objects.create(
            company=company, nom=slug + '-role',
            permissions=['adsengine_view', 'adsengine_manage',
                         'adsengine_approve'])
        user = User.objects.create_user(
            username=slug + '-u', password='x', company=company,
            role_legacy='normal', role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return company, conn, api

    def _campagne_cpl(self, company, cpl, meta_id):
        camp = AdCampaignMirror.objects.create(
            company=company, meta_id=meta_id, name='CAMP', status='ACTIVE')
        for d in range(5):
            _snap(company, camp, day=d, spend=cpl, results=1)
        return camp

    def _regle_api(self, api, body):
        resp = api.post('/api/django/adsengine/regles/', {
            'template_key': 'stop_loss_cpl', 'enabled': True,
            'dry_run': False, 'mode': 'propose', **body,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return RulePolicy.objects.get(pk=resp.data['id'])

    def _eval(self, company, policy):
        template = rule_templates.get_template('stop_loss_cpl')
        return rules_engine._eval_stop_loss(
            company, policy, template, now=TODAY, config=None)

    def test_seuil_usd_declenche_a_31(self):
        company, _conn, api = self._societe('aacq3-usd')
        policy = self._regle_api(api, {'params': {'threshold_mad': 30}})
        policy.refresh_from_db()
        self.assertEqual(policy.threshold_currency, 'USD')
        self.assertEqual(policy.params.get('threshold_mad'), 30)
        camp31 = self._campagne_cpl(company, 31, 'c31')
        findings = {f['target_meta_id']: f for f in self._eval(company, policy)}
        self.assertTrue(findings['c31']['fired'])
        self.assertNotIn('blocked_fr', findings['c31'])
        camp31.delete()
        self._campagne_cpl(company, 29, 'c29')
        findings = {f['target_meta_id']: f for f in self._eval(company, policy)}
        self.assertFalse(findings['c29']['fired'])
        self.assertNotIn('blocked_fr', findings['c29'])

    def test_regle_sans_devise_non_applicable(self):
        company, conn, api = self._societe('aacq3-legacy')
        self._campagne_cpl(company, 31, 'cl')
        ancienne = RulePolicy.objects.create(
            company=company, template_key='stop_loss_cpl', enabled=True,
            dry_run=False, mode=RulePolicy.Mode.PROPOSE,
            params={'threshold_mad': 30})
        self.assertEqual(ancienne.threshold_currency, '')
        f = self._eval(company, ancienne)[0]
        self.assertFalse(f['fired'])
        self.assertTrue(f['insufficient_data'])
        self.assertIn(INVITE, f['blocked_fr'])
        # Règle saisie en USD : un changement de devise du compte la rebascule
        # en « non applicable » (aucun taux appliqué).
        # Une seule règle par (société, template) : l'ancienne est remplacée.
        ancienne.delete()
        nouvelle = self._regle_api(api, {'params': {'threshold_mad': 30}})
        self.assertTrue(self._eval(company, nouvelle)[0]['fired'])
        conn.currency = 'EUR'
        conn.save(update_fields=['currency'])
        f = self._eval(company, nouvelle)[0]
        self.assertFalse(f['fired'])
        self.assertIn('Seuil saisi en USD, compte facturé en EUR', f['blocked_fr'])
        self.assertIn(INVITE, f['blocked_fr'])
        self.assertFalse(EngineAction.objects.filter(company=company).exists())

    def test_devise_du_corps_ignoree(self):
        company, _conn, api = self._societe('aacq3-corps')
        policy = self._regle_api(api, {
            'params': {'threshold_mad': 30}, 'threshold_currency': 'MAD'})
        policy.refresh_from_db()
        self.assertEqual(policy.threshold_currency, 'USD')
        # PATCH sans changer un seuil : la devise n'est pas re-posée.
        RulePolicy.objects.filter(pk=policy.pk).update(threshold_currency='')
        resp = api.patch(f'/api/django/adsengine/regles/{policy.pk}/', {
            'cooldown_hours': 4, 'threshold_currency': 'USD'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        policy.refresh_from_db()
        self.assertEqual(policy.threshold_currency, '')
        # Seuil ressaisi : devise du compte posée par le serveur.
        resp = api.patch(f'/api/django/adsengine/regles/{policy.pk}/', {
            'params': {'threshold_mad': 35}}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        policy.refresh_from_db()
        self.assertEqual(policy.threshold_currency, 'USD')
        # Garde-fous : devise du corps ignorée.
        resp = api.patch('/api/django/adsengine/guardrail/', {
            'max_daily_budget_mad': 120, 'ceiling_currency': 'MAD'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        cfg = GuardrailConfig.objects.get(company=company)
        self.assertEqual(cfg.daily_budget_ceiling_mad, 120)
        self.assertEqual(cfg.ceiling_currency, 'USD')

    def test_armer_sans_seuil_reste_non_applicable(self):
        """AACQ98 — sonde VER-001 : « Armer » (corps exact de ``doArm``) sans
        seuil saisi ne pose pas la devise du compte ; le défaut du gabarit
        (250, calibré en MAD) reste non applicable sur un compte USD. Seuil
        saisi (30 → 'USD', 31/29) : ``test_seuil_usd_declenche_a_31``."""
        company, _conn, api = self._societe('aacq98-usd')
        self._campagne_cpl(company, 300, 'c300')
        resp = api.post('/api/django/adsengine/regles/', {
            'template_key': 'stop_loss_cpl', 'enabled': True,
            'dry_run': False}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['threshold_currency'], '')
        policy = RulePolicy.objects.get(pk=resp.data['id'])
        f = self._eval(company, policy)[0]
        self.assertFalse(f['fired'])
        self.assertIn(INVITE, f['blocked_fr'])
        # Persistance : relue par GET ; désarmer seul ne pose aucune devise.
        url = f'/api/django/adsengine/regles/{policy.pk}/'
        self.assertEqual(api.get(url).data['threshold_currency'], '')
        resp = api.patch(url, {'enabled': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(api.get(url).data['threshold_currency'], '')
        # Garde-fous créés sans plafond : '' ; plafond saisi : devise du compte.
        resp = api.post('/api/django/adsengine/garde-fous/', {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['ceiling_currency'], '')
        resp = api.patch('/api/django/adsengine/guardrail/', {
            'max_daily_budget_mad': 120}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        cfg = GuardrailConfig.objects.get(company=company)
        resp = api.get(f'/api/django/adsengine/garde-fous/{cfg.pk}/')
        self.assertEqual(resp.data['ceiling_currency'], 'USD')
        # Compte MAD : vide = sémantique MAD, la règle reste applicable.
        company_b, _c, api_b = self._societe('aacq98-mad', currency='MAD')
        self._campagne_cpl(company_b, 300, 'b300')
        resp = api_b.post('/api/django/adsengine/regles/', {
            'template_key': 'stop_loss_cpl', 'enabled': True,
            'dry_run': False}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        f = self._eval(company_b, RulePolicy.objects.get(pk=resp.data['id']))[0]
        self.assertTrue(f['fired'])
        self.assertNotIn('blocked_fr', f)

    def test_plafond_usd_borne_budget_usd(self):
        company, _conn, api = self._societe('aacq3-plafond')
        resp = api.patch('/api/django/adsengine/guardrail/', {
            'max_daily_budget_mad': 110}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        cfg = GuardrailConfig.objects.get(company=company)
        self.assertEqual(cfg.ceiling_currency, 'USD')
        # Plafond comparable : violation (et non « inopérant ») au-dessus.
        with self.assertRaises(guardrails.GuardrailViolation) as ctx:
            guardrails.check_daily_ceiling(cfg, 150, company=company)
        self.assertNotIsInstance(ctx.exception, guardrails.GuardrailInoperative)
        self.assertIn('USD', str(ctx.exception))
        self.assertTrue(guardrails.check_daily_ceiling(cfg, 100, company=company))
        # Une action budget en USD est bornée au plafond USD.
        AdSetMirror.objects.create(
            company=company, meta_id='as-usd', name='AS', status='ACTIVE',
            budget='10000')
        action = budget_applier.propose_rebalance_adset_budget(
            company, adset_meta_id='as-usd', current_daily_budget_mad=100,
            target_daily_budget_mad=150, reason_fr='Rééquilibrer.')
        self.assertIsNotNone(action)
        self.assertEqual(action.payload['new_daily_budget_mad'], 110.0)
        # Persistance : rouvrir → plafond et devise identiques.
        cfg.refresh_from_db()
        self.assertEqual((cfg.daily_budget_ceiling_mad, cfg.ceiling_currency),
                         (110, 'USD'))
