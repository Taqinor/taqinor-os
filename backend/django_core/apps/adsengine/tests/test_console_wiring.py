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
    AdCampaignMirror, CreativeAsset, CreativeGenerationBatch, DecisionLog,
    EngineAlert, Experiment, GuardrailConfig, InsightSnapshot, MetaConnection,
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
        # Invariant #3 : jamais d'activation depuis l'ERP.
        self.assertFalse(conn.enabled)

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
