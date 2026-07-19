"""ADSENGINT1/ADSENGINT2 — Tests de câblage de la CONSOLE adsengine.

Un test par endpoint que ``adsengineApi.js`` appelle : un utilisateur authentifié
de la société obtient 200 et la forme JSON attendue par l'écran, tout est
company-scopé, les secrets ne fuient jamais, et la permission fine est exigée.

Ces tests tournent en CI (l'hôte est en Django 6.x, incompatible manage.py) — ils
sont la SPÉCIFICATION exécutable du contrat front↔back.
"""
import datetime
import json

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine.models import (
    AdCampaignMirror, AdMirror, AdSetMirror, CreativeAsset,
    CreativeGenerationBatch, DecisionLog, EngineAlert, Experiment,
    GuardrailConfig, InsightSnapshot, MetaConnection,
    ReconciliationSnapshot, WeeklyBrief,
)

User = get_user_model()
BASE = '/api/django/adsengine'
SECRET = 'tok-88213-distinctive-secret'


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


class ConsoleWiringTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='Cw Co', slug='cw-co')
        cls.viewer = make_user(cls.company, 'cw-viewer', ['adsengine_view'])
        cls.manager = make_user(
            cls.company, 'cw-manager',
            ['adsengine_view', 'adsengine_manage'])
        cls.nobody = make_user(cls.company, 'cw-nobody', [])

        # Autre société (isolation).
        cls.other = Company.objects.create(nom='Other Co', slug='other-co')
        cls.other_viewer = make_user(
            cls.other, 'other-viewer', ['adsengine_view'])

        # Fixtures société principale.
        cls.campaign = AdCampaignMirror.objects.create(
            company=cls.company, meta_id='cmp-1', name='Campagne A',
            status='PAUSED', objective='ctwa', budget=10000)
        AdCampaignMirror.objects.create(
            company=cls.other, meta_id='other-cmp', name='Autre société',
            status='PAUSED')
        ct = ContentType.objects.get_for_model(AdCampaignMirror)
        InsightSnapshot.objects.create(
            company=cls.company, content_type=ct, object_id=cls.campaign.pk,
            date=datetime.date.today(), spend='120.00', results=6,
            frequency='1.80', cpl='20.00')

        # ADSDEEP60 — hiérarchie Campagne → Ad set → Ad (badge apprentissage).
        cls.adset = AdSetMirror.objects.create(
            company=cls.company, meta_id='as-1', name='Ad set A',
            status='ACTIVE', budget=4000, campaign=cls.campaign,
            learning_status=AdSetMirror.LearningStatus.LEARNING)
        cls.ad = AdMirror.objects.create(
            company=cls.company, meta_id='ad-1', name='Ad A',
            status='ACTIVE', adset=cls.adset)
        ad_ct = ContentType.objects.get_for_model(AdMirror)
        InsightSnapshot.objects.create(
            company=cls.company, content_type=ad_ct, object_id=cls.ad.pk,
            date=datetime.date.today(), spend='30.00', results=2)

        cls.brief = WeeklyBrief.objects.create(
            company=cls.company,
            period_start=datetime.date(2026, 7, 6),
            period_end=datetime.date(2026, 7, 12),
            data={
                'periode': {'debut': '2026-07-06', 'fin': '2026-07-12'},
                'cout_par_signature_cumule': '90.00',
                'signatures_cumulees': 2,
                'propositions': [
                    {'id': 11, 'kind': 'pause', 'reason_fr': 'Mettre en pause'},
                ],
            },
            markdown='# Brief')

        ReconciliationSnapshot.objects.create(
            company=cls.company, date=datetime.date.today(),
            campaign=cls.campaign, meta_leads=8, erp_leads=6, meta_spend='120',
            delta_leads=2, status=ReconciliationSnapshot.Statut.ECART,
            detail={'ratio': 0.25})

        cls.experiment = Experiment.objects.create(
            company=cls.company, name='Exp Hook')
        DecisionLog.objects.create(
            company=cls.company, experiment=cls.experiment,
            summary_fr='Le bras B mène.')

        EngineAlert.objects.create(
            company=cls.company, alert_type=EngineAlert.Type.ANOMALIE,
            message='Anomalie détectée', resolved=True)

        cls.asset = CreativeAsset.objects.create(
            company=cls.company, asset_type=CreativeAsset.AssetType.STATIC,
            file_key='adsengine/1/x.png', source_lane='upload')
        cls.batch = CreativeGenerationBatch.objects.create(
            company=cls.company, visual_ids=[])

    # ── ENG22 — Connexion (statut / save write-only / santé) ──────────────────
    def test_connection_get_status_no_secret(self):
        MetaConnection.objects.create(
            company=self.company, credentials={'access_token': SECRET},
            ad_account_id='act_123456')
        resp = auth(self.viewer).get(f'{BASE}/connection/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['connected'])
        self.assertNotIn(SECRET, json.dumps(resp.data))
        self.assertIn('3456', resp.data['ad_account_id_masque'])
        self.assertNotIn('act_123456', resp.data['ad_account_id_masque'])

    def test_connection_save_write_only_activates_read(self):
        api = auth(self.manager)
        resp = api.post(f'{BASE}/connection/', {
            'access_token': SECRET, 'ad_account_id': 'act_999',
            'app_id': '42'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertNotIn(SECRET, json.dumps(resp.data))
        conn = MetaConnection.objects.get(company=self.company)
        self.assertEqual(conn.credentials['access_token'], SECRET)
        # Un jeton valide active la connexion en LECTURE (la synchro devient
        # possible) ; les campagnes restent PAUSED-only côté meta_client.
        self.assertTrue(conn.enabled)
        self.assertEqual(conn.credentials['app_id'], '42')
        self.assertEqual(conn.ad_account_id, 'act_999')

    def test_connection_save_requires_manage(self):
        resp = auth(self.viewer).post(
            f'{BASE}/connection/', {'access_token': 'x'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_connection_health_statuses_no_secret(self):
        MetaConnection.objects.create(
            company=self.company, credentials={'access_token': SECRET},
            ad_account_id='act_1', pixel_id='px_1')
        resp = auth(self.viewer).get(f'{BASE}/connection/health/')
        self.assertEqual(resp.status_code, 200, resp.data)
        keys = {s['key'] for s in resp.data['statuses']}
        self.assertEqual(
            keys, {'token', 'ad_account', 'page', 'pixel', 'capi', 'paused'})
        self.assertNotIn(SECRET, json.dumps(resp.data))
        token_row = next(
            s for s in resp.data['statuses'] if s['key'] == 'token')
        self.assertTrue(token_row['ok'])

    # ── ENG22 — Garde-fous singleton ─────────────────────────────────────────
    def test_guardrail_get_and_patch_mapping(self):
        api = auth(self.manager)
        get1 = api.get(f'{BASE}/guardrail/')
        self.assertEqual(get1.status_code, 200, get1.data)
        self.assertIn('max_daily_budget_mad', get1.data)
        self.assertIn('require_approval_above_mad', get1.data)
        patch = api.patch(
            f'{BASE}/guardrail/', {'max_daily_budget_mad': 250,
                                   'max_monthly_budget_mad': 5000},
            format='json')
        self.assertEqual(patch.status_code, 200, patch.data)
        self.assertEqual(patch.data['max_daily_budget_mad'], 250)
        cfg = GuardrailConfig.objects.get(company=self.company)
        self.assertEqual(cfg.daily_budget_ceiling_mad, 250)
        self.assertEqual(cfg.monthly_budget_ceiling_mad, 5000)

    def test_guardrail_patch_requires_manage(self):
        resp = auth(self.viewer).patch(
            f'{BASE}/guardrail/', {'max_daily_budget_mad': 9}, format='json')
        self.assertEqual(resp.status_code, 403)

    # ── ENG23 — Dashboard / leads / pacing ───────────────────────────────────
    def test_metrics_dashboard_shape(self):
        resp = auth(self.viewer).get(f'{BASE}/metrics/dashboard/')
        self.assertEqual(resp.status_code, 200, resp.data)
        for k in ('cost_per_signature', 'spend', 'cpl', 'frequency'):
            self.assertIn(k, resp.data)
        self.assertEqual(resp.data['spend'], '120.00')

    def test_metrics_dashboard_prefers_odoo_signatures_when_configured(self):
        """ADSENG-ODOO : connecteur Odoo configuré + signatures RÉELLES -> le
        héro-chiffre du dashboard reflète le coût-par-signature Odoo (le CRM ERP
        peut être vide), avec ``signatures_source`` = 'odoo'. Sans Odoo (défaut
        des tests), le comportement CRM historique est inchangé."""
        from unittest import mock
        odoo_result = {'configured': True, 'signatures': 9,
                       'cost_per_signature': '10.03', 'total_spend': '90.31'}
        with mock.patch(
                'apps.adsengine.odoo_client.is_configured',
                return_value=True), \
                mock.patch(
                    'apps.adsengine.odoo_metrics.odoo_cost_per_signature',
                    return_value=odoo_result):
            resp = auth(self.viewer).get(f'{BASE}/metrics/dashboard/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['cost_per_signature'], '10.03')
        self.assertEqual(resp.data['signatures'], 9)
        self.assertEqual(resp.data['signatures_source'], 'odoo')

    def test_metrics_dashboard_reports_account_currency(self):
        """Régression : Meta rapporte dans la devise du COMPTE (souvent USD) —
        le dashboard l'expose pour que le front n'étiquette plus « MAD » en dur.
        Sans connexion (ou devise inconnue) : repli 'MAD' inchangé."""
        resp = auth(self.viewer).get(f'{BASE}/metrics/dashboard/')
        self.assertEqual(resp.data['currency'], 'MAD')  # repli sans connexion
        MetaConnection.objects.update_or_create(
            company=self.company, defaults={'currency': 'USD'})
        resp = auth(self.viewer).get(f'{BASE}/metrics/dashboard/')
        self.assertEqual(resp.data['currency'], 'USD')

    # ── ADSDEEP61 — Dashboard v2 (conversations réelles + MER mixte) ──────────
    def test_dashboard_v2_shape_and_window(self):
        from apps.adsengine.models import CtwaReferral
        from django.utils import timezone

        CtwaReferral.objects.create(
            company=self.company, wa_message_id='wa-1', ad_id='ad-1',
            ts=timezone.now())
        CtwaReferral.objects.create(
            company=self.company, wa_message_id='wa-2', ad_id='ad-1',
            ts=timezone.now())
        resp = auth(self.viewer).get(f'{BASE}/metrics/dashboard-v2/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['window_days'], 14)
        self.assertEqual(resp.data['conversations']['total'], 2)
        self.assertEqual(len(resp.data['conversations']['sparkline']), 14)
        self.assertEqual(resp.data['mer']['spend'], '120.00')
        self.assertFalse(resp.data['mer']['odoo_configured'])
        self.assertEqual(resp.data['mer']['signed_ca_mad'], '0')
        self.assertEqual(len(resp.data['mer']['spend_sparkline']), 14)
        self.assertEqual(len(resp.data['mer']['signed_ca_sparkline']), 14)

    def test_dashboard_v2_never_blends_cross_currency_mer(self):
        """Doctrine devise-compte : dépense Meta en USD + CA signé Odoo en MAD
        -> AUCUN ratio calculé (jamais une conversion implicite)."""
        MetaConnection.objects.update_or_create(
            company=self.company, defaults={'currency': 'USD'})
        from unittest import mock
        with mock.patch(
                'apps.adsengine.odoo_client.is_configured',
                return_value=True), \
                mock.patch(
                    'apps.adsengine.odoo_selectors.signed_deals',
                    return_value=[{
                        'phone_norm': '212600000000', 'amount_mad': '5000',
                        'date': datetime.date.today().isoformat(),
                        'source_name': 'Client X', 'origin': 'sale_order',
                        'lead_id': None}]):
            resp = auth(self.viewer).get(f'{BASE}/metrics/dashboard-v2/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['mer']['spend_currency'], 'USD')
        self.assertEqual(resp.data['mer']['signed_ca_currency'], 'MAD')
        self.assertEqual(resp.data['mer']['signed_ca_mad'], '5000')
        self.assertIsNone(resp.data['mer']['mer_ratio'])  # jamais fabriqué
        self.assertTrue(resp.data['mer']['odoo_configured'])

    def test_dashboard_v2_requires_view_permission(self):
        resp = auth(self.nobody).get(f'{BASE}/metrics/dashboard-v2/')
        self.assertEqual(resp.status_code, 403)

    def test_connection_status_includes_currency(self):
        MetaConnection.objects.update_or_create(
            company=self.company,
            defaults={'currency': 'USD', 'ad_account_id': 'act_99'})
        resp = auth(self.viewer).get(f'{BASE}/connection/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['currency'], 'USD')

    def test_metrics_leads_includes_odoo_deals_when_configured(self):
        """ADSENG-ODOO : le drill « signature » liste AUSSI les deals signés
        Odoo (sinon le héro affiche un chiffre Odoo mais la liste reste vide).
        ``id`` None (pas de fiche CRM ERP), montant en MAD."""
        from decimal import Decimal
        from unittest import mock
        deals = [{'source_name': 'S00160', 'phone_norm': '661223344',
                  'origin': 'sale_order',
                  'amount_mad': Decimal('24051.36'), 'date': '2026-02-13',
                  'lead_id': None}]
        with mock.patch(
                'apps.adsengine.odoo_client.is_configured',
                return_value=True), \
                mock.patch(
                    'apps.adsengine.odoo_selectors.signed_deals',
                    return_value=deals):
            resp = auth(self.viewer).get(
                f'{BASE}/metrics/leads/', {'metric': 'signature'})
        self.assertEqual(resp.status_code, 200, resp.data)
        odoo_rows = [r for r in resp.data if r.get('source') == 'odoo']
        self.assertEqual(len(odoo_rows), 1)
        self.assertEqual(odoo_rows[0]['nom'], 'S00160')
        self.assertEqual(odoo_rows[0]['etape'], 'Commande confirmée (Odoo)')
        self.assertAlmostEqual(odoo_rows[0]['montant'], 24051.36)
        self.assertIsNone(odoo_rows[0]['id'])

    def test_metrics_leads_is_list(self):
        resp = auth(self.viewer).get(
            f'{BASE}/metrics/leads/', {'metric': 'cost_per_signature'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsInstance(resp.data, list)

    def test_metrics_pacing_shape(self):
        resp = auth(self.viewer).get(f'{BASE}/metrics/pacing/')
        self.assertEqual(resp.status_code, 200, resp.data)
        for k in ('enveloppe_mad', 'depense_mad', 'projection_mad',
                  'jours_restants', 'etat', 'etat_display', 'lignes'):
            self.assertIn(k, resp.data)

    def test_metrics_requires_view_permission(self):
        self.assertEqual(
            auth(self.nobody).get(f'{BASE}/metrics/dashboard/').status_code,
            403)

    # ── ENG42 — Réconciliation ───────────────────────────────────────────────
    def test_reconciliation_list_shape(self):
        resp = auth(self.viewer).get(f'{BASE}/reconciliation/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        row = resp.data[0]
        self.assertEqual(row['campagne'], 'Campagne A')
        self.assertEqual(row['meta_mad'], 8)
        self.assertEqual(row['erp_mad'], 6)
        self.assertEqual(row['ecart_mad'], 2)
        self.assertEqual(row['statut'], 'ecart')

    # ── ENG26 — Brief ────────────────────────────────────────────────────────
    def test_brief_latest_shape(self):
        resp = auth(self.viewer).get(f'{BASE}/brief/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('2026-07-06', resp.data['periode'])
        self.assertTrue(any(
            it.get('action_id') == 11 for it in resp.data['items']))

    # ── ENG24 — Campagnes (liste + sync-now + creative-ranking) ──────────────
    def test_campaigns_list_shape_and_scoping(self):
        resp = auth(self.viewer).get(f'{BASE}/campaigns/')
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data.get('results', resp.data)
        names = {r['name'] for r in rows}
        self.assertIn('Campagne A', names)
        self.assertNotIn('Autre société', names)  # isolation
        row = next(r for r in rows if r['name'] == 'Campagne A')
        self.assertEqual(row['depense_mad'], '120.00')
        self.assertEqual(row['nb_leads'], 6)
        self.assertEqual(row['budget_quotidien_mad'], '100.00')

    def test_campaigns_sync_now_noop_without_live_connection(self):
        resp = auth(self.manager).post(f'{BASE}/campaigns/sync-now/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['synced'])

    def test_campaigns_creative_ranking_is_list(self):
        resp = auth(self.viewer).get(f'{BASE}/campaigns/creative-ranking/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsInstance(resp.data, list)

    def test_campaigns_create_forbidden(self):
        resp = auth(self.manager).post(
            f'{BASE}/campaigns/', {'meta_id': 'x'}, format='json')
        self.assertEqual(resp.status_code, 405)

    # ── ADSDEEP60 — Hiérarchie Campagne → Ad sets → Ads ───────────────────────
    def test_campaign_hierarchy_shape_and_scoping(self):
        resp = auth(self.viewer).get(
            f'{BASE}/campaigns/{self.campaign.pk}/hierarchie/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['name'], 'Campagne A')
        adsets = resp.data['adsets']
        self.assertEqual(len(adsets), 1)
        adset = adsets[0]
        self.assertEqual(adset['name'], 'Ad set A')
        self.assertEqual(adset['statut_display'], 'Active')
        self.assertEqual(adset['budget_quotidien_mad'], '40.00')
        self.assertEqual(adset['learning_badge']['label'], 'En apprentissage')
        self.assertTrue(adset['learning_badge']['is_learning'])
        ads = adset['ads']
        self.assertEqual(len(ads), 1)
        self.assertEqual(ads[0]['name'], 'Ad A')
        self.assertEqual(ads[0]['depense_mad'], '30.00')
        self.assertEqual(ads[0]['nb_leads'], 2)

    def test_campaign_hierarchy_scoped_to_company(self):
        other_campaign = AdCampaignMirror.objects.get(
            company=self.other, meta_id='other-cmp')
        resp = auth(self.viewer).get(
            f'{BASE}/campaigns/{other_campaign.pk}/hierarchie/')
        self.assertEqual(resp.status_code, 404)

    def test_campaign_hierarchy_requires_view_permission(self):
        resp = auth(self.nobody).get(
            f'{BASE}/campaigns/{self.campaign.pk}/hierarchie/')
        self.assertEqual(resp.status_code, 403)

    # ── ADSDEEP22 — Cockpit par ad ─────────────────────────────────────────────
    def test_ads_cockpit_shape_and_scoping(self):
        from apps.adsengine.models import MetaLeadMirror
        MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='lg-1', ad_id=self.ad.meta_id)

        resp = auth(self.viewer).get(f'{BASE}/metrics/ads-cockpit/')
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data
        self.assertIsInstance(rows, list)
        row = next(r for r in rows if r['meta_id'] == 'ad-1')
        self.assertEqual(row['nom'], 'Ad A')
        self.assertEqual(row['statut_display'], 'Active')
        self.assertEqual(row['learning_badge']['label'], 'En apprentissage')
        self.assertEqual(row['depense_mad'], '30.00')
        self.assertEqual(row['nb_leads'], 1)  # MetaLeadMirror réel
        self.assertEqual(row['cpl_mad'], '30.00')  # 30/1
        self.assertEqual(row['signatures'], 0)  # Odoo non configuré en test
        self.assertFalse(row['odoo_configured'])
        self.assertIn('fatigue', row)
        self.assertIn('conversations', row)

    def test_ads_cockpit_requires_view_permission(self):
        resp = auth(self.nobody).get(f'{BASE}/metrics/ads-cockpit/')
        self.assertEqual(resp.status_code, 403)

    # ── ENG27 — Variantes (à la demande) ─────────────────────────────────────
    def test_variantes_action_noop_without_key(self):
        resp = auth(self.manager).post(
            f'{BASE}/creatifs/{self.asset.pk}/variantes/')
        self.assertEqual(resp.status_code, 202, resp.data)
        self.assertIn('variants_created', resp.data)

    def test_variantes_requires_manage(self):
        resp = auth(self.viewer).post(
            f'{BASE}/creatifs/{self.asset.pk}/variantes/')
        self.assertEqual(resp.status_code, 403)

    # ── ENG39 — DecisionLog d'une expérience ─────────────────────────────────
    def test_experiences_decisions(self):
        resp = auth(self.viewer).get(
            f'{BASE}/experiences/{self.experiment.pk}/decisions/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['summary_fr'], 'Le bras B mène.')

    # ── ENG43 — Historique alertes ───────────────────────────────────────────
    def test_alertes_history(self):
        resp = auth(self.viewer).get(f'{BASE}/alertes/history/')
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data.get('results', resp.data)
        self.assertTrue(any(r['message'] == 'Anomalie détectée' for r in rows))

    # ── ENG43 — Dry-run d'un gabarit (projection, aucun effet) ───────────────
    def test_regles_dry_run(self):
        anomalies_before = DecisionLog.objects.count()
        resp = auth(self.viewer).post(
            f'{BASE}/regles/dry-run/', {'template': 'stop_loss_cpl'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('resume_fr', resp.data)
        self.assertIsInstance(resp.data['objets_touches'], list)
        # 'stop_loss_cpl' scope=campaign → touche la campagne existante.
        self.assertEqual(len(resp.data['objets_touches']), 1)
        # Aucun effet de bord.
        self.assertEqual(DecisionLog.objects.count(), anomalies_before)

    def test_regles_dry_run_unknown_template(self):
        resp = auth(self.viewer).post(
            f'{BASE}/regles/dry-run/', {'template': 'nope'}, format='json')
        self.assertEqual(resp.status_code, 400)

    # ── ENG40 — Plan de vol (actions) ────────────────────────────────────────
    def test_flightplan_templates(self):
        resp = auth(self.viewer).get(f'{BASE}/plans-vol/templates/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 3)
        self.assertTrue(all('phases' in t for t in resp.data))

    def test_flightplan_backlog_arms_is_list(self):
        resp = auth(self.viewer).get(f'{BASE}/plans-vol/backlog-arms/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsInstance(resp.data, list)

    def test_flightplan_preflight_shape(self):
        resp = auth(self.viewer).get(f'{BASE}/plans-vol/preflight/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('pret', resp.data)
        self.assertIsInstance(resp.data['portes'], list)

    def test_flightplan_validate_returns_reasons(self):
        resp = auth(self.manager).post(
            f'{BASE}/plans-vol/validate/',
            {'nom': 'P1', 'template': 'resid_ctwa',
             'phases': [{'key': 'hook', 'duree_mois': 1}], 'bras': [1, 2]},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('ok', resp.data)
        self.assertIsInstance(resp.data['raisons'], list)

    def test_flightplan_simulate_shell(self):
        resp = auth(self.manager).post(
            f'{BASE}/plans-vol/simulate/', {'scenario': 'clear_winner'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['scenarios'][0]['verdict'], 'converged')

    # ── ENG44 — Simulations (catalogue + shell) ──────────────────────────────
    def test_simulations_list_and_detail(self):
        api = auth(self.viewer)
        lst = api.get(f'{BASE}/simulations/')
        self.assertEqual(lst.status_code, 200, lst.data)
        self.assertEqual(len(lst.data), 4)
        det = api.get(f'{BASE}/simulations/clear_winner/')
        self.assertEqual(det.status_code, 200, det.data)
        self.assertEqual(det.data['scenarios'][0]['verdict'], 'converged')
        self.assertEqual(
            api.get(f'{BASE}/simulations/nope/').status_code, 404)

    # ── ENG41 — Backlog (liste + approbation lot + dépôt asset) ──────────────
    def test_backlog_list_shape(self):
        resp = auth(self.viewer).get(f'{BASE}/backlog/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        row = resp.data[0]
        for k in ('campagne', 'runway_jours', 'runway_cible',
                  'diversite_hooks', 'lots'):
            self.assertIn(k, row)

    def test_backlog_lot_approve(self):
        resp = auth(self.manager).post(
            f'{BASE}/backlog/lots/{self.batch.pk}/approuver/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.batch.refresh_from_db()
        self.assertEqual(
            self.batch.status, CreativeGenerationBatch.Statut.APPROUVEE)

    def test_backlog_lot_approve_other_company_404(self):
        other_batch = CreativeGenerationBatch.objects.create(
            company=self.other, visual_ids=[])
        resp = auth(self.manager).post(
            f'{BASE}/backlog/lots/{other_batch.pk}/approuver/')
        self.assertEqual(resp.status_code, 404)

    def test_backlog_drop_asset(self):
        upload = SimpleUploadedFile(
            'creative.png', b'\x89PNG\r\n\x1a\n binary', content_type='image/png')
        resp = auth(self.manager).post(
            f'{BASE}/backlog/{self.campaign.pk}/assets/',
            {'file': upload}, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            self.campaign.backlog_items.count(), 1)

    # ── ENG45 — Reporting reshaped pour les écrans (clés normalizer) ─────────
    def test_reports_variants_has_variantes_key(self):
        resp = auth(self.viewer).get(f'{BASE}/reporting/variantes/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('variantes', resp.data)
        self.assertIsInstance(resp.data['variantes'], list)

    def test_reports_funnel_has_etapes_key(self):
        resp = auth(self.viewer).get(f'{BASE}/reporting/entonnoir/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('etapes', resp.data)
        self.assertIsInstance(resp.data['etapes'], list)

    def test_reports_cohorts_is_list(self):
        resp = auth(self.viewer).get(f'{BASE}/reporting/cohortes/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsInstance(resp.data, list)

    # ── PUB40 — Sélecteur de période + comparaison ───────────────────────────
    def test_metrics_dashboard_windows_by_debut_fin(self):
        """``?debut=&fin=`` borne spend/cpl/frequency ; omis, comportement
        historique (somme de TOUT l'historique) inchangé."""
        old_day = datetime.date.today() - datetime.timedelta(days=10)
        ct = ContentType.objects.get_for_model(AdCampaignMirror)
        InsightSnapshot.objects.create(
            company=self.company, content_type=ct, object_id=self.campaign.pk,
            date=old_day, spend='999.00', results=1, frequency='3.00')
        today = datetime.date.today()
        resp = auth(self.viewer).get(
            f'{BASE}/metrics/dashboard/',
            {'debut': today.isoformat(), 'fin': today.isoformat()})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['spend'], '120.00')
        resp_all = auth(self.viewer).get(f'{BASE}/metrics/dashboard/')
        self.assertEqual(resp_all.status_code, 200, resp_all.data)
        self.assertEqual(resp_all.data['spend'], '1119.00')

    def test_metrics_dashboard_compare_previous_period_same_weekday(self):
        """PUB40 — une fenêtre d'UN jour compare au MÊME jour, semaine
        précédente (-7 j), le critère Done « hier vs même jour semaine
        passée »."""
        today = datetime.date.today()
        last_week = today - datetime.timedelta(days=7)
        ct = ContentType.objects.get_for_model(AdCampaignMirror)
        InsightSnapshot.objects.create(
            company=self.company, content_type=ct, object_id=self.campaign.pk,
            date=last_week, spend='40.00', results=2, frequency='1.00')
        resp = auth(self.viewer).get(
            f'{BASE}/metrics/dashboard/',
            {'debut': today.isoformat(), 'fin': today.isoformat(),
             'compare': '1'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['spend'], '120.00')
        self.assertIn('previous', resp.data)
        self.assertEqual(resp.data['previous']['spend'], '40.00')
        self.assertEqual(resp.data['previous']['debut'], last_week.isoformat())

    def test_metrics_dashboard_compare_without_range_is_noop(self):
        resp = auth(self.viewer).get(
            f'{BASE}/metrics/dashboard/', {'compare': '1'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertNotIn('previous', resp.data)

    def test_ads_cockpit_windows_spend_and_leads_together(self):
        """PUB40 — dépense (InsightSnapshot) ET leads (MetaLeadMirror) sont
        fenêtrés ENSEMBLE : le CPL affiché reste un ratio cohérent."""
        from django.utils import timezone

        from apps.adsengine.models import MetaLeadMirror
        today = datetime.date.today()
        old_day = today - datetime.timedelta(days=10)
        ad_ct = ContentType.objects.get_for_model(AdMirror)
        InsightSnapshot.objects.create(
            company=self.company, content_type=ad_ct, object_id=self.ad.pk,
            date=old_day, spend='500.00', results=9)
        MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='lg-old', ad_id=self.ad.meta_id,
            created_time=timezone.make_aware(
                datetime.datetime.combine(old_day, datetime.time(12, 0))))
        MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='lg-new', ad_id=self.ad.meta_id,
            created_time=timezone.now())
        resp = auth(self.viewer).get(
            f'{BASE}/metrics/ads-cockpit/',
            {'debut': today.isoformat(), 'fin': today.isoformat()})
        self.assertEqual(resp.status_code, 200, resp.data)
        row = next(r for r in resp.data if r['meta_id'] == 'ad-1')
        # Fixture setUpTestData (30.00/2) + le lead d'AUJOURD'HUI seulement —
        # l'instantané et le lead d'il y a 10 j sont hors fenêtre.
        self.assertEqual(row['depense_mad'], '30.00')
        self.assertEqual(row['nb_leads'], 1)
        self.assertEqual(row['cpl_mad'], '30.00')

    def test_ads_cockpit_without_range_unchanged(self):
        """Omis (défaut) : comportement byte-identique — pas de fenêtrage."""
        from apps.adsengine.models import MetaLeadMirror
        MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='lg-1', ad_id=self.ad.meta_id)
        resp = auth(self.viewer).get(f'{BASE}/metrics/ads-cockpit/')
        self.assertEqual(resp.status_code, 200, resp.data)
        row = next(r for r in resp.data if r['meta_id'] == 'ad-1')
        self.assertEqual(row['nb_leads'], 1)

    def test_campaigns_list_windows_depense_by_debut_fin(self):
        old_day = datetime.date.today() - datetime.timedelta(days=10)
        ct = ContentType.objects.get_for_model(AdCampaignMirror)
        InsightSnapshot.objects.create(
            company=self.company, content_type=ct, object_id=self.campaign.pk,
            date=old_day, spend='500.00', results=9)
        today = datetime.date.today()
        resp = auth(self.viewer).get(
            f'{BASE}/campaigns/',
            {'debut': today.isoformat(), 'fin': today.isoformat()})
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data.get('results', resp.data)
        row = next(r for r in rows if r['name'] == 'Campagne A')
        self.assertEqual(row['depense_mad'], '120.00')
        # Sans bornes : comportement historique (somme des deux).
        resp_all = auth(self.viewer).get(f'{BASE}/campaigns/')
        rows_all = resp_all.data.get('results', resp_all.data)
        row_all = next(r for r in rows_all if r['name'] == 'Campagne A')
        self.assertEqual(row_all['depense_mad'], '620.00')

    def test_actions_log_windows_by_debut_fin(self):
        from django.utils import timezone

        from apps.adsengine.models import EngineAction
        old_action = EngineAction.objects.create(
            company=self.company, kind=EngineAction.Kind.PAUSE,
            reason_fr='Ancienne action.')
        EngineAction.objects.filter(pk=old_action.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=10))
        new_action = EngineAction.objects.create(
            company=self.company, kind=EngineAction.Kind.PAUSE,
            reason_fr='Action récente.')
        today = datetime.date.today()
        resp = auth(self.viewer).get(
            f'{BASE}/actions/',
            {'debut': today.isoformat(), 'fin': today.isoformat()})
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data.get('results', resp.data)
        ids = {r['id'] for r in rows}
        self.assertIn(new_action.pk, ids)
        self.assertNotIn(old_action.pk, ids)
        # Sans bornes : les deux apparaissent (comportement historique).
        resp_all = auth(self.viewer).get(f'{BASE}/actions/')
        ids_all = {r['id'] for r in resp_all.data.get('results', resp_all.data)}
        self.assertIn(old_action.pk, ids_all)
        self.assertIn(new_action.pk, ids_all)
