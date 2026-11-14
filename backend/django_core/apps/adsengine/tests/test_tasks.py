"""ENG6 — Tests de la tâche Celery ``adsengine.sync_insights_daily``.

Prouve : NO-OP propre sans connexion active/token (aucun miroir, aucun réseau),
synchro + idempotence via un client Meta mocké, et joignabilité du beat (nom
planifié + routé vers la queue ``scheduled``).
"""
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine.models import (
    AdCampaignMirror, AdMirror, AdSetMirror, InsightSnapshot, MetaConnection,
)
from apps.adsengine.tasks import sync_insights_daily


class FakeMetaClient:
    """Client Meta mocké — renvoie des fixtures déterministes, aucun réseau."""

    def get_account(self, **kw):
        return {'currency': 'USD'}

    def get_campaigns(self, **kw):
        return [{'id': 'c1', 'name': 'Camp', 'status': 'PAUSED',
                 'objective': 'OUTCOME_LEADS'}]

    def get_adsets(self, **kw):
        return [{'id': 'as1', 'campaign_id': 'c1', 'name': 'AS',
                 'status': 'PAUSED'}]

    def get_ads(self, **kw):
        return [{'id': 'ad1', 'adset_id': 'as1', 'name': 'AD',
                 'status': 'PAUSED'}]

    insights_kw = None

    def get_insights(self, meta_id, **kw):
        self.insights_kw = kw  # capturé pour vérifier la fenêtre demandée
        return [{'date_start': '2026-07-16', 'spend': '10.00', 'results': 2,
                 'frequency': '1.2', 'cpl': '5.00'}]


class SyncInsightsNoOpTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Task Co', slug='task-co')

    def test_noop_without_any_connection(self):
        result = sync_insights_daily()
        self.assertEqual(result, {'companies_synced': 0})
        self.assertEqual(AdCampaignMirror.objects.count(), 0)

    def test_noop_when_connection_disabled(self):
        MetaConnection.objects.create(
            company=self.company, enabled=False,
            credentials={'access_token': 'tok-x'}, ad_account_id='act_1')
        result = sync_insights_daily()
        self.assertEqual(result, {'companies_synced': 0})
        self.assertEqual(AdCampaignMirror.objects.count(), 0)

    def test_noop_when_enabled_but_no_token(self):
        # Activée mais sans token → is_live False → sautée, aucun réseau.
        MetaConnection.objects.create(
            company=self.company, enabled=True, credentials={},
            ad_account_id='act_1')
        with patch('apps.adsengine.meta_client.MetaClient') as mock_cls:
            result = sync_insights_daily()
            mock_cls.from_connection.assert_not_called()
        self.assertEqual(result, {'companies_synced': 0})
        self.assertEqual(AdCampaignMirror.objects.count(), 0)


class SyncInsightsRunTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Live Co', slug='live-co')
        MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'tok-73951'}, ad_account_id='act_1')

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_sync_and_idempotent(self, mock_cls):
        mock_cls.from_connection.return_value = FakeMetaClient()

        first = sync_insights_daily()
        self.assertEqual(first, {'companies_synced': 1})
        self.assertEqual(AdCampaignMirror.objects.count(), 1)
        self.assertEqual(AdSetMirror.objects.count(), 1)
        self.assertEqual(AdMirror.objects.count(), 1)
        self.assertEqual(InsightSnapshot.objects.count(), 1)

        # Deuxième exécution : mêmes fixtures → aucun doublon (idempotent).
        second = sync_insights_daily()
        self.assertEqual(second, {'companies_synced': 1})
        self.assertEqual(AdCampaignMirror.objects.count(), 1)
        self.assertEqual(AdSetMirror.objects.count(), 1)
        self.assertEqual(AdMirror.objects.count(), 1)
        self.assertEqual(InsightSnapshot.objects.count(), 1)

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_sync_stores_account_currency(self, mock_cls):
        """La synchro mémorise la devise du COMPTE Meta (USD…) sur la connexion
        — Meta rapporte tous les montants dans cette devise, pas en MAD."""
        mock_cls.from_connection.return_value = FakeMetaClient()
        sync_insights_daily()
        conn = MetaConnection.objects.get(company=self.company)
        self.assertEqual(conn.currency, 'USD')

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_insights_pulled_over_full_history(self, mock_cls):
        """Régression ENG6 : les insights sont lus sur TOUT l'historique
        (``date_preset='maximum'``), ventilés par JOUR (``time_increment=1``).
        Sans fenêtre explicite, l'API Graph tronque la dépense à un défaut récent
        → coût-par-signature ~100x trop bas (bug remonté : 90 MAD au lieu de
        >10 000 pour >1000 $ dépensés)."""
        fake = FakeMetaClient()
        mock_cls.from_connection.return_value = fake
        sync_insights_daily()
        self.assertEqual(
            fake.insights_kw.get('params'),
            {'date_preset': 'maximum', 'time_increment': 1})

    def test_limite_douce_fait_echouer_la_tache(self):
        """ACEL71 — la limite douce Celery n'est jamais avalée par l'isolation
        par société : la tâche échoue au lieu de finir en « succès »."""
        from celery.exceptions import SoftTimeLimitExceeded

        from apps.adsengine.tasks import (
            pull_meta_leads, pull_meta_leads_recent, sync_ad_creatives,
        )

        with patch('apps.adsengine.tasks._sync_company',
                   side_effect=SoftTimeLimitExceeded()):
            with self.assertRaises(SoftTimeLimitExceeded):
                sync_insights_daily()
        for tache in (pull_meta_leads, pull_meta_leads_recent):
            with patch('apps.adsengine.tasks.pull_ad_leads_for_company',
                       side_effect=SoftTimeLimitExceeded()):
                with patch('apps.adsengine.meta_client.MetaClient'):
                    with self.assertRaises(SoftTimeLimitExceeded):
                        tache()
        # Scénario 2 : levée à la 2e annonce — aucune annonce suivante lue.
        for i in range(3):
            AdMirror.objects.create(company=self.company, meta_id=f'ad{i}')
        lus = []

        class Client:
            def get_ad_creative(self, meta_id):
                lus.append(meta_id)
                if len(lus) == 2:
                    raise SoftTimeLimitExceeded()
                return {}

        with self.assertRaises(SoftTimeLimitExceeded):
            sync_ad_creatives(self.company, Client())
        self.assertEqual(len(lus), 2)

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_autre_exception_garde_l_isolation(self, mock_cls):
        mock_cls.from_connection.return_value = FakeMetaClient()
        with patch('apps.adsengine.tasks._sync_company',
                   side_effect=RuntimeError('boom')):
            self.assertEqual(sync_insights_daily(), {'companies_synced': 0})

    def test_limite_douce_au_deuxieme_lead_fait_echouer_le_releve(self):
        """ACEL81 — la limite douce levée à la création du 2e lead n'est pas
        avalée par l'``except`` par lead de ``pull_ad_leads_for_company``."""
        from celery.exceptions import SoftTimeLimitExceeded

        from apps.adsengine.tasks import pull_meta_leads

        AdMirror.objects.create(company=self.company, meta_id='ad-acel81')

        class Client:
            def get_ad_leads(self, meta_id, **kw):
                return [{'id': 'lg1', 'field_data': []},
                        {'id': 'lg2', 'field_data': []}]

            def get_ad_targeting_ids(self, meta_id):
                return {'adset_id': 's1', 'campaign_id': 'c1'}

        with patch('apps.adsengine.meta_client.MetaClient') as mock_cls, \
                patch('apps.crm.services.create_lead_from_meta_lead_ads',
                      side_effect=[object(), SoftTimeLimitExceeded()]), \
                patch('core.events.meta_lead_captured'):
            mock_cls.from_connection.return_value = Client()
            with self.assertRaises(SoftTimeLimitExceeded):
                pull_meta_leads()

    def test_societe_suivante_synchronisee_apres_une_erreur(self):
        """ACEL81 — une ``RuntimeError`` d'une société reste isolée : la
        suivante est synchronisée."""
        autre = Company.objects.create(nom='Live Co 2', slug='live-co-2')
        MetaConnection.objects.create(
            company=autre, enabled=True,
            credentials={'access_token': 'tok-2'}, ad_account_id='act_2')

        def sync(conn):
            if conn.company_id == self.company.pk:
                raise RuntimeError('boom')

        with patch('apps.adsengine.tasks._sync_company', side_effect=sync):
            self.assertEqual(sync_insights_daily(), {'companies_synced': 1})


class EmitCapiCommandeManuelleTests(TestCase):
    """ACEL73 — ``manage.py emit_capi_signatures`` déclenche la tâche."""

    def setUp(self):
        Company.objects.create(nom='Capi Co', slug='capi-co')

    def test_commande_declenche_la_tache(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        with patch('apps.adsengine.capi_odoo.is_configured',
                   return_value=False), \
                patch('apps.adsengine.capi_odoo.emit_lead_received') as lead:
            call_command('emit_capi_signatures', stdout=out)
        self.assertIn('CRM Dataset non configuré', out.getvalue())
        lead.assert_not_called()

        out = StringIO()
        with patch('apps.adsengine.capi_odoo.is_configured',
                   return_value=True), \
                patch('apps.adsengine.capi_odoo.emit_lead_received',
                      return_value={'emitted': 1}), \
                patch('apps.adsengine.capi_odoo.emit_signed_deals',
                      return_value={'emitted': 2}):
            call_command('emit_capi_signatures', stdout=out)
        self.assertIn('1 reçu(s), 2 signé(s)', out.getvalue())
        from erp_agentique.celery import app
        planifiees = {e['task'] for e in app.conf.beat_schedule.values()}
        self.assertNotIn('adsengine.emit_capi_signatures', planifiees)


class BeatReachabilityTests(SimpleTestCase):
    def test_task_is_scheduled(self):
        from erp_agentique.celery import app
        names = {e['task'] for e in app.conf.beat_schedule.values()}
        self.assertIn('adsengine.sync_insights_daily', names)

    def test_task_is_routed_to_scheduled(self):
        route = settings.CELERY_TASK_ROUTES['adsengine.sync_insights_daily']
        self.assertEqual(route['queue'], 'scheduled')
