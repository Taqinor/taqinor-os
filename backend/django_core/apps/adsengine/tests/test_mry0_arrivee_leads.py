"""MRY0 — Consolidation de l'arrivée des leads (côté adsengine).

Couvre :
  * lot A — ``etat_webhook_leadgen`` sur un faux Graph : KO (Page non abonnée,
    permission absente) puis OK ; ``abonner_page_leadgen`` poste bien sur
    ``/{page_id}/subscribed_apps`` ; la commande ``meta_webhook_status``
    sort en code 1 tant que le câblage n'est pas complet ;
  * ``MetaLeadMirror.origine`` posée d'après le ``sender`` de l'événement, un
    pull n'écrasant JAMAIS une origine « webhook » ;
  * lot B — ``since_unix`` transmis à ``get_ad_leads`` par le filet 15 min ;
  * lot D — l'alerte « lead rattrapé » part une seule fois, et JAMAIS quand le
    lead était déjà miroité (webhook OK) ;
  * beat + routes des deux tâches.
"""
import datetime
import json
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from authentication.models import Company

from apps.adsengine import tasks, webhook_leadgen
from apps.adsengine.models import AdMirror, MetaConnection, MetaLeadMirror

PAGE_ID = '784992588041621'
APP_ID = '1708624427128028'


class BeatRegistrationTests(SimpleTestCase):
    """Les deux nouvelles tâches sont planifiées ET routées vers `scheduled`."""

    def test_pull_recent_scheduled_and_routed(self):
        from erp_agentique.celery import app
        names = {e['task'] for e in app.conf.beat_schedule.values()}
        self.assertIn('adsengine.pull_meta_leads_recent', names)
        self.assertEqual(
            settings.CELERY_TASK_ROUTES[
                'adsengine.pull_meta_leads_recent']['queue'], 'scheduled')

    def test_sync_odoo_leads_scheduled_and_routed(self):
        from erp_agentique.celery import app
        names = {e['task'] for e in app.conf.beat_schedule.values()}
        self.assertIn('crm.sync_odoo_leads', names)
        self.assertEqual(
            settings.CELERY_TASK_ROUTES['crm.sync_odoo_leads']['queue'],
            'scheduled')


class FauxGraph:
    """Faux Graph API : ``_graph_get``/``_graph_post`` remplacés en mémoire."""

    def __init__(self, *, scopes=None, page_subscribed=True,
                 app_subscribed=True, page_error=None):
        self.scopes = scopes if scopes is not None else [
            'leads_retrieval', 'pages_manage_metadata']
        self.page_subscribed = page_subscribed
        self.app_subscribed = app_subscribed
        self.page_error = page_error
        self.posts = []

    def get(self, path, params):
        if path == 'debug_token':
            return {'data': {'app_id': APP_ID, 'scopes': self.scopes,
                             'is_valid': True}}
        if path.endswith('/subscriptions'):
            if not self.app_subscribed:
                return {'data': []}
            return {'data': [{
                'object': 'page', 'active': True,
                # SCA29 — le chemin est le contrat ; l'hôte varie
                # légitimement (staging, domaine d'un autre installeur).
                'callback_url': ('https://exemple.test'
                                 + webhook_leadgen.CALLBACK_PATH),
                'fields': [{'name': 'leadgen'}]}]}
        if path.endswith('/subscribed_apps'):
            if self.page_error is not None:
                raise self.page_error
            if not self.page_subscribed:
                return {'data': []}
            return {'data': [{'id': APP_ID,
                              'subscribed_fields': ['leadgen']}]}
        if path == PAGE_ID:
            return {'access_token': 'jeton-de-page'}
        raise AssertionError(f'chemin Graph inattendu : {path}')

    def post(self, path, params):
        self.posts.append((path, params))
        return {'success': True}


class EtatWebhookLeadgenTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='MRY0 Co', slug='mry0-co')
        MetaConnection.objects.create(
            company=self.company, enabled=True, page_id=PAGE_ID,
            ad_account_id='act_1',
            credentials={'access_token': 'jeton', 'app_id': APP_ID,
                         'app_secret': 'secret'})
        cache.clear()

    def _patch(self, faux):
        return mock.patch.multiple(
            webhook_leadgen, _graph_get=faux.get, _graph_post=faux.post)

    def test_page_non_abonnee_est_signalee_en_francais(self):
        faux = FauxGraph(page_subscribed=False)
        with self._patch(faux):
            etat = webhook_leadgen.etat_webhook_leadgen(self.company)
        self.assertTrue(etat['app_subscribed'])
        self.assertIs(etat['page_subscribed'], False)
        self.assertFalse(etat['ok'])
        self.assertIn('Abonner la Page', etat['detail'])

    def test_permission_absente_rend_etat_page_illisible(self):
        faux = FauxGraph(scopes=['leads_retrieval'],
                         page_error=RuntimeError('(#200) permission manquante'))
        with self._patch(faux):
            etat = webhook_leadgen.etat_webhook_leadgen(self.company)
        self.assertIsNone(etat['page_subscribed'])
        self.assertFalse(etat['has_pages_manage_metadata'])
        self.assertIn('pages_manage_metadata', etat['detail'])

    def test_cablage_complet_mais_silencieux_pointe_le_gestionnaire(self):
        faux = FauxGraph()
        with self._patch(faux):
            etat = webhook_leadgen.etat_webhook_leadgen(self.company)
        # Aucun miroir d'origine webhook → silence → jamais « OK ».
        self.assertFalse(etat['ok'])
        self.assertIn("accès aux prospects", etat['detail'])

    def test_ok_quand_un_lead_webhook_recent_existe(self):
        MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='1',
            origine=MetaLeadMirror.Origine.WEBHOOK)
        faux = FauxGraph()
        with self._patch(faux):
            etat = webhook_leadgen.etat_webhook_leadgen(self.company)
        self.assertTrue(etat['ok'])
        self.assertIn('temps réel', etat['detail'])

    def test_abonner_page_poste_subscribed_fields_leadgen(self):
        faux = FauxGraph(page_subscribed=False)
        with self._patch(faux):
            resultat = webhook_leadgen.abonner_page_leadgen(self.company)
        self.assertTrue(resultat['ok'])
        chemin, params = faux.posts[0]
        self.assertEqual(chemin, f'{PAGE_ID}/subscribed_apps')
        self.assertEqual(params['subscribed_fields'], 'leadgen')

    def test_erreur_meta_renvoyee_telle_quelle_jamais_levee(self):
        faux = FauxGraph(page_subscribed=False)
        faux.post = mock.Mock(side_effect=RuntimeError('(#200) refus Meta'))
        with mock.patch.multiple(webhook_leadgen, _graph_get=faux.get,
                                 _graph_post=faux.post):
            resultat = webhook_leadgen.abonner_page_leadgen(self.company)
        self.assertFalse(resultat['ok'])
        self.assertIn('#200', resultat['detail'])

    def test_commande_sort_en_erreur_quand_le_cablage_est_incomplet(self):
        faux = FauxGraph(page_subscribed=False)
        with self._patch(faux):
            with self.assertRaises(SystemExit):
                call_command('meta_webhook_status', company='mry0-co')


class OrigineMiroirTests(TestCase):
    """L'origine distingue webhook et pull — sans elle, « webhook muet » est
    indétectable (les deux chemins convergent sur la même ligne)."""

    def setUp(self):
        self.company = Company.objects.create(nom='Org Co', slug='org-co')

    def _emettre(self, sender):
        from apps.adsengine.receivers import on_meta_lead_captured
        on_meta_lead_captured(
            sender, lead=None, company=self.company, leadgen_id='42')

    def test_webhook_pose_origine_webhook(self):
        self._emettre('crm.meta_lead_ads_webhook')
        self.assertEqual(
            MetaLeadMirror.objects.get(leadgen_id='42').origine, 'webhook')

    def test_pull_pose_origine_pull(self):
        self._emettre('adsengine.pull_ad_leads')
        self.assertEqual(
            MetaLeadMirror.objects.get(leadgen_id='42').origine, 'pull')

    def test_pull_necrase_pas_une_origine_webhook(self):
        self._emettre('crm.meta_lead_ads_webhook')
        self._emettre('adsengine.pull_ad_leads')
        self.assertEqual(
            MetaLeadMirror.objects.get(leadgen_id='42').origine, 'webhook')


class FauxClient:
    def __init__(self, leads):
        self._leads = leads
        self.since_recu = 'jamais-appele'

    def get_ad_leads(self, ad_id, since_unix=None):
        self.since_recu = since_unix
        return self._leads

    def get_ad_targeting_ids(self, ad_id):
        return {'adset_id': 'as1', 'campaign_id': 'c1'}


class FiletRattrapageTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Filet', slug='filet')
        self.conn = MetaConnection.objects.create(
            company=self.company, enabled=True, page_id=PAGE_ID,
            ad_account_id='act_1', credentials={'access_token': 'jeton'})
        AdMirror.objects.create(company=self.company, meta_id='ad1',
                                name='Ad 1', status='PAUSED')
        cache.clear()

    def _row(self, minutes_avant):
        moment = timezone.now() - datetime.timedelta(minutes=minutes_avant)
        return {
            'id': '9001',
            'created_time': moment.strftime('%Y-%m-%dT%H:%M:%S+0000'),
            'form_id': 'f1',
            'field_data': [
                {'name': 'full_name', 'values': ['Aziz Test']},
                {'name': 'phone_number', 'values': ['+212651971400']},
            ],
        }

    def test_since_unix_transmis_au_client(self):
        client = FauxClient([])
        tasks.pull_ad_leads_for_company(
            self.company, self.conn, client, since_unix=1234567)
        self.assertEqual(client.since_recu, 1234567)

    def test_pull_quotidien_nutilise_pas_de_fenetre(self):
        client = FauxClient([])
        tasks.pull_ad_leads_for_company(self.company, self.conn, client)
        self.assertEqual(client.since_recu, 'jamais-appele')

    def test_alerte_emise_une_seule_fois_pour_un_lead_ancien(self):
        client = FauxClient([self._row(120)])
        with mock.patch(
                'apps.notifications.services.notify_many') as notifier:
            tasks.pull_ad_leads_for_company(
                self.company, self.conn, client, alerter_rattrapage=True)
            # Deuxième passe : le lead est déjà miroité → plus aucune alerte.
            tasks.pull_ad_leads_for_company(
                self.company, self.conn, client, alerter_rattrapage=True)
        self.assertEqual(notifier.call_count, 1)
        self.assertIn('rattrapé', notifier.call_args.kwargs['title'])

    def test_aucune_alerte_pour_un_lead_frais(self):
        client = FauxClient([self._row(2)])
        with mock.patch(
                'apps.notifications.services.notify_many') as notifier:
            tasks.pull_ad_leads_for_company(
                self.company, self.conn, client, alerter_rattrapage=True)
        notifier.assert_not_called()

    def test_created_time_pose_la_vraie_date_darrivee(self):
        client = FauxClient([self._row(120)])
        tasks.pull_ad_leads_for_company(
            self.company, self.conn, client, alerter_rattrapage=False)
        from apps.crm.models import Lead
        lead = Lead.objects.get(external_id='9001')
        ecart = abs((timezone.now() - lead.date_creation).total_seconds())
        self.assertGreater(ecart, 3600, json.dumps(str(lead.date_creation)))
