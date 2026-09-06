"""MRY0 — Consolidation de l'arrivée des leads (côté crm).

Couvre :
  * ``activity.log_creation`` nomme l'ORIGINE quand la création est système
    (« Lead créé via Meta Lead Ads (webhook) » au lieu de « créé par ? ») ;
  * ``create_lead_from_meta_lead_ads`` pose la VRAIE date d'arrivée, refuse
    une date aberrante (futur, > 90 j) et n'y touche JAMAIS sur un lead déjà
    capturé (idempotence webhook) ;
  * lot C — la tâche ``crm.sync_odoo_leads`` est un no-op propre sans config
    ni ``ODOO_SYNC_COMPANY_SLUG``, et son verrou empêche deux passes ;
  * ``--no-align`` saute l'alignement des étapes ;
  * les leads de TEST Meta sont ignorés par ``build_rows``.
"""
import datetime
import os
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm import activity, odoo_sync, services, tasks
from apps.crm.models import Lead, LeadActivity


def _field_data(nom='Aziz', telephone='+212651971400'):
    return [
        {'name': 'full_name', 'values': [nom]},
        {'name': 'phone_number', 'values': [telephone]},
    ]


class LogCreationOrigineTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Origine', slug='origine')
        self.lead = Lead.objects.create(company=self.company, nom='Test')

    def test_origine_nommee_quand_creation_systeme(self):
        activity.log_creation(self.lead, None,
                              origine='Meta Lead Ads (webhook)')
        ligne = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.CREATION).latest('id')
        self.assertEqual(ligne.body, 'Lead créé via Meta Lead Ads (webhook)')

    def test_comportement_historique_inchange_sans_origine(self):
        activity.log_creation(self.lead, None)
        ligne = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.CREATION).latest('id')
        self.assertEqual(ligne.body, 'Lead créé par ?')


class VraieDateArriveeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Date', slug='date-co')

    def _creer(self, leadgen_id, created_time):
        return services.create_lead_from_meta_lead_ads(
            company=self.company, leadgen_id=leadgen_id,
            field_data=_field_data(), created_time=created_time,
            origine='Meta Lead Ads (pull)')

    def test_iso_meta_posee_sur_date_creation(self):
        moment = timezone.now() - datetime.timedelta(hours=6)
        lead = self._creer('1', moment.strftime('%Y-%m-%dT%H:%M:%S+0000'))
        self.assertLess(
            abs((lead.date_creation - moment).total_seconds()), 90)

    def test_epoch_secondes_acceptee(self):
        moment = timezone.now() - datetime.timedelta(hours=3)
        lead = self._creer('2', int(moment.timestamp()))
        self.assertLess(
            abs((lead.date_creation - moment).total_seconds()), 90)

    def test_date_future_refusee(self):
        futur = timezone.now() + datetime.timedelta(days=2)
        lead = self._creer('3', futur.strftime('%Y-%m-%dT%H:%M:%S+0000'))
        self.assertLess(lead.date_creation, timezone.now()
                        + datetime.timedelta(minutes=1))

    def test_date_trop_ancienne_refusee(self):
        vieux = timezone.now() - datetime.timedelta(days=200)
        lead = self._creer('4', vieux.strftime('%Y-%m-%dT%H:%M:%S+0000'))
        self.assertGreater(lead.date_creation,
                           timezone.now() - datetime.timedelta(days=1))

    def test_lead_deja_capture_garde_sa_date(self):
        moment = timezone.now() - datetime.timedelta(hours=6)
        lead = self._creer('5', moment.strftime('%Y-%m-%dT%H:%M:%S+0000'))
        premiere = lead.date_creation
        autre = timezone.now() - datetime.timedelta(days=10)
        again = self._creer('5', autre.strftime('%Y-%m-%dT%H:%M:%S+0000'))
        self.assertEqual(again.pk, lead.pk)
        again.refresh_from_db()
        self.assertEqual(again.date_creation, premiere)

    def test_sans_created_time_comportement_inchange(self):
        lead = services.create_lead_from_meta_lead_ads(
            company=self.company, leadgen_id='6', field_data=_field_data())
        self.assertGreater(lead.date_creation,
                           timezone.now() - datetime.timedelta(minutes=5))


class TacheMiroirOdooTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_noop_sans_config_odoo(self):
        with mock.patch.dict(os.environ, {'ODOO_SYNC_URL': '',
                                          'ODOO_SYNC_API_KEY': ''},
                             clear=False):
            self.assertEqual(tasks.sync_odoo_leads_task(),
                             {'skipped': 'config'})

    def test_noop_sans_company_slug(self):
        env = {'ODOO_SYNC_URL': 'https://odoo.example',
               'ODOO_SYNC_API_KEY': 'k', 'ODOO_SYNC_COMPANY_SLUG': ''}
        with mock.patch.dict(os.environ, env, clear=False):
            self.assertEqual(tasks.sync_odoo_leads_task(),
                             {'skipped': 'company'})

    def test_verrou_empeche_deux_passes(self):
        env = {'ODOO_SYNC_URL': 'https://odoo.example',
               'ODOO_SYNC_API_KEY': 'k', 'ODOO_SYNC_COMPANY_SLUG': 'x'}
        cache.add(tasks._ODOO_SYNC_LOCK, 1, timeout=60)
        with mock.patch.dict(os.environ, env, clear=False):
            self.assertEqual(tasks.sync_odoo_leads_task(),
                             {'skipped': 'lock'})

    def test_transmet_no_align_quand_odoo_sync_align_vaut_zero(self):
        env = {'ODOO_SYNC_URL': 'https://odoo.example',
               'ODOO_SYNC_API_KEY': 'k', 'ODOO_SYNC_COMPANY_SLUG': 'x',
               'ODOO_SYNC_ALIGN': '0'}
        with mock.patch.dict(os.environ, env, clear=False), \
                mock.patch('django.core.management.call_command') as appel:
            tasks.sync_odoo_leads_task()
        self.assertTrue(appel.call_args.kwargs.get('no_align'))
        self.assertEqual(appel.call_args.kwargs.get('company'), 'x')


class LeadsDeTestIgnoresTests(TestCase):
    """Piège du 01/09/2026 : les leads de test Meta supprimés de l'ERP
    revenaient à chaque passe."""

    def _lead(self, **kw):
        base = {'id': 1, 'name': 'Vrai prospect', 'contact_name': 'Karim',
                'stage_id': [1, 'New'], 'active': True}
        base.update(kw)
        return base

    def test_test_lead_ignore_et_compte(self):
        rows = odoo_sync.build_rows([
            self._lead(id=1),
            self._lead(id=2, name='Test Lead', contact_name=''),
            self._lead(id=3, name='X', contact_name='Dummy Data'),
        ], {})
        self.assertEqual([r['id'] for r in rows], [1])
        self.assertEqual(rows.ignores_test, 2)

    def test_insensible_a_la_casse(self):
        rows = odoo_sync.build_rows(
            [self._lead(id=9, name='TEST LEAD 4')], {})
        self.assertEqual(list(rows), [])
        self.assertEqual(rows.ignores_test, 1)


class NoAlignTests(TestCase):
    def test_option_saute_lalignement(self):
        from django.core.management import call_command

        company = Company.objects.create(nom='NA', slug='na-co')
        env = {'ODOO_SYNC_URL': 'https://odoo.example',
               'ODOO_SYNC_API_KEY': 'k'}
        module = 'apps.crm.management.commands.sync_odoo_leads'
        with mock.patch.dict(os.environ, env, clear=False), \
                mock.patch(f'{module}.fetch_odoo_leads',
                           return_value=([], {})), \
                mock.patch(f'{module}.align_stages_from_rows') as aligne, \
                mock.patch(f'{module}.build_rows',
                           return_value=odoo_sync.LignesImport()):
            call_command('sync_odoo_leads', company=str(company.pk),
                         no_align=True, dry_run=True)
        aligne.assert_not_called()
