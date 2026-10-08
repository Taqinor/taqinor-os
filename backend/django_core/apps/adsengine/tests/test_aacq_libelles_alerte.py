"""AACQ7 — L'alerte du stop-loss dit « coût par lead », le NOM de la campagne et
la devise réelle du compte ; aucun « MAD » en dur dans les textes serveur qui
portent une dépense Meta (gabarits frères, brief, file Aujourd'hui).
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company
from apps.adsengine import alerts, brief as brief_mod, metrics, rules_engine
from apps.adsengine.models import (
    AdCampaignMirror, EngineAction, EngineAlert, InsightSnapshot,
    MetaConnection, RulePolicy, WeeklyBrief,
)

TODAY = datetime.date(2026, 7, 16)
NOM = 'Résidentiel Casablanca — Lead form'


def _snap(company, obj, *, day, spend, results):
    ct = ContentType.objects.get_for_model(type(obj))
    InsightSnapshot.objects.create(
        company=company, content_type=ct, object_id=obj.pk,
        date=TODAY - datetime.timedelta(days=day),
        spend=str(spend), results=results)


class LibellesAlerteTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Lib', slug='aacq7-lib')
        MetaConnection.objects.create(
            company=self.company, ad_account_id='act_aacq7', currency='MAD',
            enabled=True, credentials={'access_token': 'tok'})
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='120123456', name=NOM,
            status='ACTIVE')
        for d in range(5):
            _snap(self.company, self.camp, day=d, spend='312.5', results=1)
        RulePolicy.objects.create(
            company=self.company, template_key='stop_loss_cpl', enabled=True,
            dry_run=False, mode=RulePolicy.Mode.PROPOSE)

    def _alerte(self):
        rules_engine.evaluate_company(self.company, now=TODAY)
        alert = EngineAlert.objects.filter(
            company=self.company,
            entity_key__startswith='cost_per_lead_ceiling:').first()
        self.assertIsNotNone(alert, list(
            EngineAlert.objects.values_list('entity_key', 'message')))
        alert.refresh_from_db()
        return alert

    def test_stop_loss_dit_cout_par_lead(self):
        msg = self._alerte().message
        self.assertIn('coût par lead', msg)
        self.assertNotIn('coût par signature', msg)

    def test_nom_de_campagne(self):
        msg = self._alerte().message
        self.assertIn(NOM, msg)
        self.assertNotIn('« 120123456 »', msg)

    def test_devise_du_compte(self):
        msg = self._alerte().message
        self.assertIn('MAD', msg)
        # Rendu direct du gabarit pour un compte USD.
        ctx = alerts.context_from_computed(
            NOM, {'value': 312.5, 'threshold': 250.0, 'window_days': 7},
            currency='USD')
        rendu = alerts.render_whatsapp('cost_per_lead_ceiling', ctx)
        self.assertIn('coût par lead = 312.5 USD', rendu)
        self.assertIn('plafond 250.0 USD', rendu)
        self.assertNotIn('MAD', rendu)
        for key in ('zero_delivery', 'spend_spike', 'spend_collapse'):
            with self.subTest(gabarit=key):
                rendu = alerts.render_whatsapp(key, {
                    'campaign_name': NOM, 'spend': 40, 'hours': 48,
                    'spend_today': 3, 'ratio': 4.2, 'median': 30,
                    'currency': 'USD'})
                self.assertIn('USD', rendu)
                self.assertNotIn('MAD', rendu)

    def test_alerte_et_action_concordent(self):
        alert = self._alerte()
        action = EngineAction.objects.get(
            company=self.company, kind=EngineAction.Kind.PAUSE)
        self.assertIn('coût par lead', alert.message)
        self.assertIn('coût par lead', action.reason_fr.lower())

    def test_brief_et_file_devise(self):
        usd = Company.objects.create(nom='LibUSD', slug='aacq7-usd')
        MetaConnection.objects.create(
            company=usd, ad_account_id='act_aacq7_usd', currency='USD',
            enabled=True, credentials={'access_token': 'tok'})
        brief = brief_mod.build_brief(usd, create_proposals=False)
        self.assertEqual(brief.data['devise'], 'USD')
        self.assertIn('USD', brief.markdown)
        self.assertNotIn(' MAD', brief.markdown)
        WeeklyBrief.objects.filter(pk=brief.pk).update(
            data={**brief.data, 'cout_par_signature_cumule': '150.00'})
        items = metrics.today_queue(usd)
        digest = [i for i in items if i['categorie'] == 'digest']
        self.assertTrue(digest, items)
        self.assertEqual(digest[0]['detail'], '150.00 USD/signature (cumulé)')
