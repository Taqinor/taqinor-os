"""ADSENG18 — Tests des 8 gabarits d'alerte WhatsApp FR + dédup/cooldown/escalade.

Prouve : les 8 gabarits rendent (emoji + cause + reco + deep link) ; l'émission
gardée déduplique par (société, gabarit, cible), respecte le cooldown de la
sévérité (6/24/72 h), escalade WARNING→CRITICAL après 3 cycles non résolus, et
la résolution d'une CRITICAL émet un suivi « ✅ Résolu ».
"""
import datetime
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from authentication.models import Company
from apps.adsengine import alerts
from apps.adsengine.models import EngineAlert
from apps.adsengine.rules import (
    SEVERITY_CRITICAL, SEVERITY_INFO, SEVERITY_WARNING,
)


class RenderTests(SimpleTestCase):
    def test_all_eight_templates_render(self):
        self.assertEqual(len(alerts.WA_TEMPLATES), 8)
        ctx = {
            'campaign_name': 'Solaire', 'ad_name': 'Ad1', 'adset_name': 'Set1',
            'value': 300, 'window_days': 7, 'threshold': 250, 'spend': 40,
            'hours': 48, 'frequency': 3.6, 'ceiling': 3.0,
            'rejection_reason': 'Texte non conforme', 'spend_today': 5,
            'ratio': 4.2, 'median': 30, 'template_label_fr': 'Fréquence',
            'error_summary': 'timeout',
        }
        for key in alerts.WA_TEMPLATES:
            msg = alerts.render_whatsapp(key, ctx)
            self.assertTrue(msg, f'{key} rend vide')
            # Emoji de sévérité + deep link ERP présents.
            self.assertIn('/publicite/', msg, f'{key} sans deep link')
            self.assertIn('→', msg, f'{key} sans flèche CTA')

    def test_unknown_template_renders_empty(self):
        self.assertEqual(alerts.render_whatsapp('inconnu'), '')

    def test_missing_context_never_raises(self):
        # Une clé manquante rend « ? », jamais un KeyError.
        msg = alerts.render_whatsapp('cost_per_signature_ceiling', {})
        self.assertIn('?', msg)

    def test_deep_link_relative_then_absolute(self):
        with mock.patch.dict('os.environ', {}, clear=False):
            import os
            os.environ.pop('ADSENGINE_APP_BASE_URL', None)
            self.assertTrue(
                alerts.deep_link('approvals').startswith('/publicite/'))
        with mock.patch.dict(
                'os.environ', {'ADSENGINE_APP_BASE_URL': 'https://erp.x'}):
            self.assertEqual(
                alerts.deep_link('approvals'),
                'https://erp.x/publicite/approbations')


class EmitGuardedAlertTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='EG Co', slug='eg-co')

    def _emit(self, key='frequency_runaway', **kw):
        defaults = dict(template_key=key, target_type='adset', target_id='as1',
                        context={'adset_name': 'as1', 'frequency': 3.6,
                                 'ceiling': 3.0})
        defaults.update(kw)
        return alerts.emit_guarded_alert(self.company, **defaults)

    def test_fresh_alert_created_and_sent(self):
        alert = self._emit()
        self.assertTrue(alert._sent)
        self.assertEqual(alert.severity, SEVERITY_WARNING)
        self.assertEqual(alert.entity_key, 'frequency_runaway:adset:as1')
        self.assertIsNotNone(alert.detail['last_sent_at'])
        self.assertEqual(EngineAlert.objects.filter(
            company=self.company).count(), 1)

    def test_dry_run_created_but_not_sent(self):
        alert = self._emit(dry_run=True)
        self.assertFalse(alert._sent)
        self.assertIsNone(alert.detail['last_sent_at'])

    def test_dedup_within_cooldown_no_resend(self):
        self._emit()
        again = self._emit()  # rejoué dans le cooldown
        self.assertFalse(again._sent)  # pas de renvoi (anti-spam)
        self.assertEqual(EngineAlert.objects.filter(
            company=self.company).count(), 1)  # jamais un doublon
        again.refresh_from_db()
        self.assertEqual(again.unresolved_cycles, 1)

    def test_resend_after_cooldown_elapsed(self):
        alert = self._emit(key='zero_delivery', target_type='campaign',
                           target_id='c1',
                           context={'campaign_name': 'c1', 'spend': 40,
                                    'hours': 48})
        # Cooldown critique = 6 h ; on antidate le dernier envoi de 7 h.
        old = (timezone.now() - datetime.timedelta(hours=7)).isoformat()
        alert.detail['last_sent_at'] = old
        alert.save(update_fields=['detail'])
        again = alerts.emit_guarded_alert(
            self.company, template_key='zero_delivery',
            target_type='campaign', target_id='c1',
            context={'campaign_name': 'c1', 'spend': 40, 'hours': 55})
        self.assertTrue(again._sent)  # cooldown écoulé → renvoi
        self.assertNotEqual(again.detail['last_sent_at'], old)

    def test_escalation_warning_to_critical_after_three_cycles(self):
        self._emit()             # création (cycle 0)
        self._emit()             # cycle 1
        self._emit()             # cycle 2
        self._emit()             # cycle 3 → escalade
        alert = EngineAlert.objects.get(
            company=self.company, entity_key='frequency_runaway:adset:as1')
        self.assertEqual(alert.severity, SEVERITY_CRITICAL)
        self.assertEqual(alert.unresolved_cycles, 3)

    def test_distinct_targets_are_separate_alerts(self):
        self._emit(target_id='as1')
        self._emit(target_id='as2')
        self.assertEqual(EngineAlert.objects.filter(
            company=self.company).count(), 2)


class ResolveAlertTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='RA Co', slug='ra-co')

    def test_resolve_critical_emits_followup(self):
        alerts.emit_guarded_alert(
            self.company, template_key='zero_delivery',
            target_type='campaign', target_id='c1',
            context={'campaign_name': 'c1', 'spend': 40, 'hours': 48})
        followup = alerts.resolve_alert(
            self.company, template_key='zero_delivery',
            target_type='campaign', target_id='c1')
        self.assertIsNotNone(followup)
        self.assertIn('✅ Résolu', followup.message)
        self.assertEqual(followup.severity, SEVERITY_INFO)
        # L'originale est marquée résolue.
        original = EngineAlert.objects.get(
            entity_key='zero_delivery:campaign:c1')
        self.assertTrue(original.resolved)

    def test_resolve_warning_no_followup(self):
        alerts.emit_guarded_alert(
            self.company, template_key='frequency_runaway',
            target_type='adset', target_id='as1',
            context={'adset_name': 'as1', 'frequency': 3.6, 'ceiling': 3.0})
        result = alerts.resolve_alert(
            self.company, template_key='frequency_runaway',
            target_type='adset', target_id='as1')
        self.assertTrue(result.resolved)
        # Pas de suivi ✅ pour une WARNING.
        self.assertFalse(EngineAlert.objects.filter(
            company=self.company, message__startswith='✅').exists())
        self.assertEqual(EngineAlert.objects.filter(
            company=self.company).count(), 1)

    def test_resolve_nothing_open_returns_none(self):
        self.assertIsNone(alerts.resolve_alert(
            self.company, template_key='zero_delivery',
            target_type='campaign', target_id='ghost'))
