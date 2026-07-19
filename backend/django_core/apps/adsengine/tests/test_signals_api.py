"""SIG4 (PUB1) — Tests des endpoints ``signaux/`` + ``signaux/cohorte/``.

Vues MINCES sur les trois modules purs : ``health.py`` (deux scores),
``signal_guards.py`` (quadrant de garde-fous durs), ``cohorts.py`` (filigrane de
maturation). Ces tests prouvent que les modules « morts » (aucun consommateur de
prod avant SIG4) sont désormais RÉELLEMENT câblés et alimentés par des
InsightSnapshot de la société. Company-scopé + gaté ``adsengine_view``.
"""
import datetime
import inspect

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import views
from apps.adsengine.models import AdCampaignMirror, InsightSnapshot

User = get_user_model()
SIGNALS_URL = '/api/django/adsengine/signaux/'
COHORT_URL = '/api/django/adsengine/signaux/cohorte/'


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


def make_snapshot(company, campaign, *, days_ago, **metrics):
    """InsightSnapshot de CAMPAGNE daté à ``days_ago`` jours."""
    ct = ContentType.objects.get_for_model(AdCampaignMirror)
    date = timezone.now().date() - datetime.timedelta(days=days_ago)
    return InsightSnapshot.objects.create(
        company=company, content_type=ct, object_id=campaign.pk, date=date,
        **metrics)


class SignalsApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='SIG Co', slug='sig-co')
        self.viewer = make_user(self.company, 'viewer', ['adsengine_view'])
        self.campaign = AdCampaignMirror.objects.create(
            company=self.company, meta_id='camp-1', name='Camp 1',
            status='PAUSED')

    # ── Permissions / scoping ────────────────────────────────────────────────
    def test_requires_view_permission(self):
        nobody = make_user(self.company, 'nobody', [])
        self.assertEqual(auth(nobody).get(SIGNALS_URL).status_code, 403)

    def test_empty_company_returns_valid_shape(self):
        resp = auth(self.viewer).get(SIGNALS_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('creatif', resp.data)
        self.assertIn('operations', resp.data)
        # Deux scores présents (0..1) + bande FR.
        self.assertIn('score', resp.data['creatif'])
        self.assertIn('bande_display', resp.data['creatif'])
        # Le quadrant rend toujours les QUATRE garde-fous, même « OK ».
        self.assertEqual(len(resp.data['guardrails']), 4)
        keys = {g['key'] for g in resp.data['guardrails']}
        self.assertEqual(
            keys, {'frequence', 'classement_qualite', 'cpl', 'qualite_compte'})

    # ── Scores de santé sur données réelles ──────────────────────────────────
    def test_creative_score_high_on_good_ctr_and_freshness(self):
        # CTR 3 % (> 2 % sain → plein) + fréquence basse (fraîcheur haute).
        make_snapshot(self.company, self.campaign, days_ago=3,
                      impressions=10000, clicks=300, frequency='1.0',
                      spend='500.00', results=20)
        resp = auth(self.viewer).get(SIGNALS_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertGreaterEqual(resp.data['creatif']['score'], 0.66)
        self.assertEqual(resp.data['creatif']['bande'], 'vert')

    def test_cpl_guardrail_freine_when_cpl_far_above_target(self):
        # CPL = 10000/10 = 1000 MAD ≫ 1,5×100 sur une cohorte mûre (≥14 j).
        make_snapshot(self.company, self.campaign, days_ago=20,
                      impressions=5000, clicks=100, frequency='1.5',
                      spend='10000.00', results=10)
        resp = auth(self.viewer).get(SIGNALS_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        cpl = next(g for g in resp.data['guardrails'] if g['key'] == 'cpl')
        self.assertTrue(cpl['freine'])
        self.assertEqual(cpl['statut_display'], 'Freine')
        self.assertAlmostEqual(cpl['valeur'], 1000.0, places=2)

    def test_cpl_guardrail_ok_on_immature_cohort(self):
        # Même CPL élevé mais cohorte JEUNE (3 j < 14) → jamais de frein (SIG3).
        make_snapshot(self.company, self.campaign, days_ago=3,
                      impressions=5000, clicks=100, frequency='1.5',
                      spend='10000.00', results=10)
        resp = auth(self.viewer).get(SIGNALS_URL)
        cpl = next(g for g in resp.data['guardrails'] if g['key'] == 'cpl')
        self.assertFalse(cpl['freine'])

    def test_scores_scoped_to_company(self):
        other = Company.objects.create(nom='Autre', slug='autre-sig')
        other_camp = AdCampaignMirror.objects.create(
            company=other, meta_id='c-other', status='PAUSED')
        make_snapshot(other, other_camp, days_ago=3,
                      impressions=10000, clicks=900, frequency='1.0',
                      spend='100.00', results=50)
        # Notre société n'a AUCUN insight → scores 0 (les données d'autrui ne
        # fuient jamais).
        resp = auth(self.viewer).get(SIGNALS_URL)
        self.assertEqual(resp.data['creatif']['score'], 0.0)

    # ── Drill-down par cohorte (filigrane de maturation) ─────────────────────
    def test_cohort_drill_creatif_returns_windows(self):
        make_snapshot(self.company, self.campaign, days_ago=10,
                      impressions=10000, clicks=300, frequency='1.0',
                      spend='500.00', results=20)
        resp = auth(self.viewer).get(COHORT_URL, {'signal': 'creatif'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 2)
        self.assertEqual(resp.data[0]['fenetre'], 'CTR — proxy immédiat')
        for row in resp.data:
            self.assertIn('maturite_display', row)

    def test_cohort_drill_operations_signature_immature(self):
        # Cohorte de 10 j : la fenêtre signature (60 j) reste immature.
        make_snapshot(self.company, self.campaign, days_ago=10,
                      impressions=5000, clicks=100, frequency='1.2',
                      spend='400.00', results=8)
        resp = auth(self.viewer).get(COHORT_URL, {'signal': 'operations'})
        self.assertEqual(resp.status_code, 200, resp.data)
        signature = next(
            r for r in resp.data if r['fenetre'] == 'Signature 60-90j')
        self.assertFalse(signature['mure'])

    def test_cohort_unknown_signal_400(self):
        resp = auth(self.viewer).get(COHORT_URL, {'signal': 'inconnu'})
        self.assertEqual(resp.status_code, 400)

    def test_cohort_requires_view_permission(self):
        nobody = make_user(self.company, 'nobody-c', [])
        self.assertEqual(
            auth(nobody).get(COHORT_URL, {'signal': 'creatif'}).status_code,
            403)

    # ── Câblage intentionnel : les trois modules « morts » sont RÉELLEMENT
    # importés/consommés par la vue (le contraire de leur état pré-SIG4). ─────
    def test_views_wires_the_three_pure_modules(self):
        source = inspect.getsource(views)
        self.assertIn('from . import health', source)
        self.assertIn('signal_guards', source)
        self.assertIn('cohorts', source)
