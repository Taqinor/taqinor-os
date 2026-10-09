"""AACQ8 — Les évaluateurs de règles sont SANS effet de bord.

``_eval_cpl_band`` rend la détection ; seul ``evaluate_company`` l'enregistre
en ``AnomalyEvent``, hors simulation et une fois par (règle, cible) et par
fenêtre de cooldown. Un backtest GET (``adsengine_view``) n'écrit rien.
"""
import datetime

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import rule_backtest, rules_engine
from apps.adsengine.models import (
    AdCampaignMirror, AnomalyEvent, InsightSnapshot, RulePolicy,
)

User = get_user_model()


class EvaluateurSansEffetTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Pur', slug='aacq8-pur')
        self.today = timezone.now().date()
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c-aacq8', name='CAMP',
            status='ACTIVE')
        ct = ContentType.objects.get_for_model(AdCampaignMirror)
        # 13 jours à CPL 100, le jour même à 300 (3× la médiane).
        for i in range(1, 14):
            InsightSnapshot.objects.create(
                company=self.company, content_type=ct, object_id=self.camp.pk,
                date=self.today - datetime.timedelta(days=i),
                spend='100.00', results=1, cpl='100.00')
        InsightSnapshot.objects.create(
            company=self.company, content_type=ct, object_id=self.camp.pk,
            date=self.today, spend='300.00', results=1, cpl='300.00')
        self.policy = RulePolicy.objects.create(
            company=self.company, template_key='cpl_band', enabled=False,
            dry_run=True, mode=RulePolicy.Mode.PROPOSE)

    def _anomalies(self):
        return AnomalyEvent.objects.filter(company=self.company).count()

    def test_backtest_get_n_ecrit_rien(self):
        role = Role.objects.create(
            company=self.company, nom='aacq8-view',
            permissions=['adsengine_view'])
        viewer = User.objects.create_user(
            username='aacq8-viewer', password='x', company=self.company,
            role_legacy='normal', role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(viewer)}')
        url = f'/api/django/adsengine/regles/{self.policy.pk}/backtest/?jours=30'
        first = api.get(url)
        self.assertEqual(first.status_code, 200, first.data)
        second = api.get(url)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(first.data['summary']['would_propose'],
                         second.data['summary']['would_propose'])
        self.assertGreaterEqual(first.data['summary']['would_propose'], 1)
        self.assertEqual(self._anomalies(), 0)

    def test_simulation_n_ecrit_rien(self):
        RulePolicy.objects.filter(pk=self.policy.pk).update(enabled=True)
        now = timezone.now()
        rules_engine.evaluate_company(self.company, now=now)
        rules_engine.evaluate_company(self.company, now=now)
        self.assertEqual(self._anomalies(), 0)

    def test_anomalie_une_fois_par_fenetre(self):
        RulePolicy.objects.filter(pk=self.policy.pk).update(
            enabled=True, dry_run=False)
        now = timezone.now()
        rules_engine.evaluate_company(self.company, now=now)
        self.assertEqual(self._anomalies(), 1)
        rules_engine.evaluate_company(self.company, now=now)
        self.assertEqual(self._anomalies(), 1)
        event = AnomalyEvent.objects.get(company=self.company)
        self.assertEqual(event.entity_meta_id, 'c-aacq8')
        self.assertEqual(event.rule_policy_id, self.policy.pk)

    def test_tout_evaluateur_sans_effet_de_bord(self):
        modeles = list(django_apps.get_app_config('adsengine').get_models())

        def compte():
            return {m.__name__: m.objects.count() for m in modeles}

        for key in rules_engine._EVALUATORS:
            with self.subTest(regle=key):
                policy, _ = RulePolicy.objects.get_or_create(
                    company=self.company, template_key=key,
                    defaults={'enabled': False, 'dry_run': True})
                avant = compte()
                rule_backtest.backtest_rule(policy, days=14)
                self.assertEqual(compte(), avant)
