"""AACQ97 — décision fondateur du 08/10/2026 (D-AACQ) : la synchro Odoo est
MANUELLE, jamais automatique, et l'ERP fait toujours foi.

* aucune entrée du beat ne planifie ``crm.sync_odoo_leads`` ni la lecture
  Odoo des deals (``adsengine.emit_capi_signatures`` / capi_odoo) ;
* ``sync_odoo_leads`` lancée à la main n'écrit AUCUNE étape (rapport seul).

Test-du-test : remettre l'entrée beat ⇒ test_beat_sans_synchro_odoo rouge ;
remettre ``apply_changes=not dry_run`` ⇒ test_commande_n_ecrit_aucune_etape
rouge.
"""
from django.test import SimpleTestCase

from apps.crm import stages
from apps.crm.models import Lead, LeadActivity
from apps.crm.tests_odoo_sync import OdooSyncBase


class BeatSansSynchroOdooTests(SimpleTestCase):

    def test_beat_sans_synchro_odoo(self):
        from erp_agentique.celery import app
        taches = {e['task'] for e in app.conf.beat_schedule.values()}
        self.assertNotIn('crm.sync_odoo_leads', taches)
        self.assertNotIn('adsengine.emit_capi_signatures', taches)


class CommandeRapportSeulTests(OdooSyncBase):

    def test_commande_n_ecrit_aucune_etape(self):
        lead = Lead.objects.create(
            company=self.company, nom='Traité dans l’ERP',
            email='beta@example.test', stage=stages.CONTACTED)
        for _ in range(2):
            self._sync()
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)
        self.assertFalse(LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.MODIFICATION,
            field='stage').exists())
