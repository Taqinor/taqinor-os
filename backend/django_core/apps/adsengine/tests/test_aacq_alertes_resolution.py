"""AACQ23 — Une alerte gardée se RÉSOUT quand sa condition redevient fausse,
et une ré-occurrence repart d'une alerte neuve (compteur et sévérité initiaux).

``evaluate_company`` est le seul appelant de production de
``alerts.resolve_alert``.
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.adsengine import alerts, metrics, rules_engine
from apps.adsengine.models import (
    AdCampaignMirror, EngineAction, EngineAlert, InsightSnapshot, RulePolicy,
)

KEY = 'cost_per_lead_ceiling:campaign:c-aacq23'


class AlertesResolutionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Res', slug='aacq23-res')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c-aacq23', name='Lead form',
            status='ACTIVE')
        self.ct = ContentType.objects.get_for_model(AdCampaignMirror)
        self.today = timezone.now().date()
        RulePolicy.objects.create(
            company=self.company, template_key='stop_loss_cpl', enabled=True,
            dry_run=False, mode=RulePolicy.Mode.PROPOSE)

    def _cpl(self, value):
        InsightSnapshot.objects.filter(company=self.company).delete()
        for d in range(5):
            InsightSnapshot.objects.create(
                company=self.company, content_type=self.ct,
                object_id=self.camp.pk,
                date=self.today - datetime.timedelta(days=d),
                spend=str(value), results=1)

    def _evaluer(self):
        RulePolicy.objects.filter(company=self.company).update(
            last_evaluated_at=None)
        # Cooldown des actions écoulé entre deux épisodes.
        EngineAction.objects.filter(company=self.company).update(
            created_at=timezone.now() - datetime.timedelta(days=30))
        rules_engine.evaluate_company(self.company, now=timezone.now())

    def _ouvertes(self):
        return EngineAlert.objects.filter(
            company=self.company, entity_key=KEY, resolved=False)

    def test_condition_fausse_resout(self):
        self._cpl(300)
        self._evaluer()
        alerte = self._ouvertes().get()
        self._cpl(100)
        self._evaluer()
        alerte.refresh_from_db()
        self.assertTrue(alerte.resolved)
        self.assertFalse(self._ouvertes().exists())
        self.assertTrue(EngineAlert.objects.filter(
            company=self.company, entity_key=KEY + ':resolved',
            message__startswith='✅ Résolu').exists())
        ids = [i['id'] for i in metrics.today_queue(self.company)]
        self.assertNotIn(f'alerte-{alerte.pk}', ids)

    def test_reoccurrence_compteur_neuf(self):
        self._cpl(300)
        self._evaluer()
        premiere = self._ouvertes().get()
        severite_initiale = premiere.severity
        self._cpl(100)
        self._evaluer()
        self._cpl(300)
        self._evaluer()
        nouvelle = self._ouvertes().get()
        self.assertNotEqual(nouvelle.pk, premiere.pk)
        self.assertEqual(nouvelle.unresolved_cycles, 0)
        self.assertEqual(nouvelle.severity, severite_initiale)
        self.assertEqual(severite_initiale,
                         alerts.wa_template_severity('cost_per_lead_ceiling'))
