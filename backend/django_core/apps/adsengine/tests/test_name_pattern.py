"""ADSDEEP39 — Tests du Selection Filter (ciblage dynamique par motif de nom).

Prouve : une ``RulePolicy`` portant un ``name_pattern`` ne surveille QUE les
objets dont le nom matche (glob insensible à la casse), un objet non-matchant est
ignoré, un motif vide couvre toute la société, et — le cœur Bïrch — une campagne
créée APRÈS la règle et matchant le motif est automatiquement COUVERTE (le moteur
relit les miroirs à chaque évaluation, jamais un ciblage figé par id).
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company
from apps.adsengine import rules_engine
from apps.adsengine.models import (
    AdSetMirror, EngineAction, InsightSnapshot, RulePolicy,
)

TODAY = datetime.date(2026, 7, 16)


def _seed_freq(company, adset, *, freq=4.0, days=4):
    ct = ContentType.objects.get_for_model(AdSetMirror)
    for i in range(days):
        InsightSnapshot.objects.create(
            company=company, content_type=ct, object_id=adset.pk,
            date=TODAY - datetime.timedelta(days=i),
            spend='10.00', results=1, frequency=str(freq))


class NamePatternMatchTests(TestCase):
    def test_name_matches_helper(self):
        self.assertTrue(rules_engine._name_matches('PROSP*', 'prospection-01'))
        self.assertTrue(rules_engine._name_matches('prosp*', 'PROSP-A'))
        self.assertFalse(rules_engine._name_matches('PROSP*', 'brand-01'))
        # Motif vide = matche tout (aucune restriction).
        self.assertTrue(rules_engine._name_matches('', 'anything'))


class SelectionFilterTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='SF Co', slug='sf-co')

    def _rule(self, **kw):
        defaults = dict(company=self.company, template_key='frequency_high',
                        enabled=True, dry_run=False,
                        mode=RulePolicy.Mode.PROPOSE)
        defaults.update(kw)
        return RulePolicy.objects.create(**defaults)

    def _actions(self):
        return EngineAction.objects.filter(company=self.company)

    def test_pattern_restricts_to_matching_objects(self):
        match = AdSetMirror.objects.create(
            company=self.company, meta_id='m1', name='PROSPECTION-A',
            status='PAUSED')
        other = AdSetMirror.objects.create(
            company=self.company, meta_id='m2', name='BRAND-B',
            status='PAUSED')
        _seed_freq(self.company, match)
        _seed_freq(self.company, other)
        self._rule(name_pattern='PROSPECTION*')
        rules_engine.evaluate_company(self.company, now=TODAY)
        # Seul l'objet matchant produit une proposition ; l'autre est ignoré.
        actions = self._actions()
        self.assertEqual(actions.count(), 1)
        self.assertEqual(actions.first().payload['target_meta_id'], 'm1')

    def test_empty_pattern_covers_all(self):
        a = AdSetMirror.objects.create(
            company=self.company, meta_id='m1', name='PROSPECTION-A',
            status='PAUSED')
        b = AdSetMirror.objects.create(
            company=self.company, meta_id='m2', name='BRAND-B',
            status='PAUSED')
        _seed_freq(self.company, a)
        _seed_freq(self.company, b)
        self._rule(name_pattern='')
        rules_engine.evaluate_company(self.company, now=TODAY)
        self.assertEqual(self._actions().count(), 2)

    def test_future_campaign_matching_pattern_is_covered(self):
        # La règle existe AVANT que l'objet matchant soit créé.
        rule = self._rule(name_pattern='PROSPECTION*')
        rules_engine.evaluate_company(self.company, now=TODAY)
        self.assertEqual(self._actions().count(), 0)  # rien à surveiller encore

        # Un ad set matchant est créé PLUS TARD (campagne « future »).
        future = AdSetMirror.objects.create(
            company=self.company, meta_id='future1',
            name='PROSPECTION-NOUVEAU', status='PAUSED')
        _seed_freq(self.company, future)
        # Cooldown écoulé côté test : on relance sur une évaluation neuve.
        rule.refresh_from_db()
        rules_engine.evaluate_company(self.company, now=TODAY)
        actions = self._actions()
        self.assertEqual(actions.count(), 1)
        self.assertEqual(actions.first().payload['target_meta_id'], 'future1')
