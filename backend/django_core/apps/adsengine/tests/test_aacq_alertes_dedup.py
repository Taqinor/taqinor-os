"""AACQ22 — Toute alerte du moteur de règles est dédupliquée par clé d'entité,
et une cible non ACTIVE n'est plus évaluée.

Campagnes en pause : 0 alerte. Campagne ACTIVE hors bande : 1 ``EngineAlert``
(clé d'entité non vide) + 1 notification par destinataire au premier passage,
aucune nouvelle ligne aux passages suivants. Simulation : 0.
"""
import datetime

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import rules_engine
from apps.adsengine.models import (
    AdCampaignMirror, EngineAlert, InsightSnapshot, RulePolicy,
)

User = get_user_model()


def _notifications(user):
    from apps.notifications.models import Notification
    return Notification.objects.filter(recipient=user).count()


class AlertesDedupTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Dedup', slug='aacq22-dd')
        role = Role.objects.create(
            company=self.company, nom='aacq22-admin',
            permissions=['adsengine_view', 'adsengine_manage',
                         'adsengine_approve'])
        self.admin = User.objects.create_user(
            username='aacq22-admin', password='x', company=self.company,
            role_legacy='admin', role=role)
        for i in range(3):
            AdCampaignMirror.objects.create(
                company=self.company, meta_id=f'p-{i}', name=f'Pause {i}',
                status='PAUSED')
        self.active = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c-active', name='Active',
            status='ACTIVE')
        ct = ContentType.objects.get_for_model(AdCampaignMirror)
        self.today = timezone.now().date()
        for i in range(1, 14):
            InsightSnapshot.objects.create(
                company=self.company, content_type=ct,
                object_id=self.active.pk,
                date=self.today - datetime.timedelta(days=i),
                spend='100.00', results=1, cpl='100.00')
        InsightSnapshot.objects.create(
            company=self.company, content_type=ct, object_id=self.active.pk,
            date=self.today, spend='300.00', results=1, cpl='300.00')

    def _passes(self, n=3):
        for _ in range(n):
            RulePolicy.objects.filter(company=self.company).update(
                last_evaluated_at=None)
            rules_engine.evaluate_company(self.company, now=timezone.now())

    def _alertes(self, meta_id):
        return EngineAlert.objects.filter(
            company=self.company, entity_key__contains=meta_id)

    def test_paused_aucune_alerte(self):
        RulePolicy.objects.create(
            company=self.company, template_key='stop_loss_cpl', enabled=True,
            dry_run=False, mode=RulePolicy.Mode.PROPOSE)
        RulePolicy.objects.create(
            company=self.company, template_key='cpl_band', enabled=True,
            dry_run=False, mode=RulePolicy.Mode.PROPOSE)
        self._passes()
        for i in range(3):
            self.assertFalse(self._alertes(f'p-{i}').exists())

    def test_condition_persistante_une_alerte(self):
        RulePolicy.objects.create(
            company=self.company, template_key='cpl_band', enabled=True,
            dry_run=False, mode=RulePolicy.Mode.PROPOSE)
        RulePolicy.objects.filter(company=self.company).update(
            last_evaluated_at=None)
        rules_engine.evaluate_company(self.company, now=timezone.now())
        alertes = self._alertes('c-active')
        self.assertEqual(alertes.count(), 1)
        self.assertTrue(alertes.first().entity_key)
        notifs = _notifications(self.admin)
        self.assertGreaterEqual(notifs, 1)
        self._passes(2)
        self.assertEqual(self._alertes('c-active').count(), 1)
        self.assertEqual(_notifications(self.admin), notifs)

    def test_alerte_seule_dedupliquee(self):
        # stop-loss en données insuffisantes (aucun lead suffisant) sur la
        # campagne active : une seule alerte « insuffisant » ouverte.
        ct = ContentType.objects.get_for_model(AdCampaignMirror)
        InsightSnapshot.objects.filter(object_id=self.active.pk).delete()
        InsightSnapshot.objects.create(
            company=self.company, content_type=ct, object_id=self.active.pk,
            date=self.today, spend='10.00', results=0)
        RulePolicy.objects.create(
            company=self.company, template_key='stop_loss_cpl', enabled=True,
            dry_run=False, mode=RulePolicy.Mode.PROPOSE)
        self._passes()
        alertes = self._alertes('c-active')
        self.assertEqual(alertes.count(), 1)
        self.assertTrue(alertes.first().entity_key.endswith(':insuffisant'))

    def test_simulation_aucune_alerte(self):
        RulePolicy.objects.create(
            company=self.company, template_key='cpl_band', enabled=True,
            dry_run=True, mode=RulePolicy.Mode.PROPOSE)
        self._passes()
        self.assertFalse(EngineAlert.objects.filter(
            company=self.company).exists())
