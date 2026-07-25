# -*- coding: utf-8 -*-
"""``odoo_import_notes`` — les notes de Meryem (chatter Odoo) rejoignent le
chatter du lead ERP correspondant.

Client Odoo simulé (aucun réseau) ; matching par téléphone normalisé via le
service crm sanctionné ; idempotence par id de message Odoo (une repasse ne
duplique jamais) ; les fiches sans correspondance ERP ne créent RIEN.
"""
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Lead, LeadActivity


class _FakeOdooClient:
    """search_read_all simulé : 2 fiches Odoo (une matchée, une inconnue)."""

    def search_read_all(self, model, domain=None, *, fields=None, order=None,
                        page_size=None):
        if model == 'crm.lead':
            return [
                {'id': 501, 'phone': '+212600000201', 'mobile': False,
                 'email_from': False,
                 'description': '<p>Facture ~1800 DH, toiture terrasse</p>'},
                {'id': 502, 'phone': '+212699999999', 'mobile': False,
                 'email_from': False, 'description': False},
            ]
        if model == 'mail.message':
            return [
                {'id': 11, 'res_id': 501,
                 'body': '<p>Rappelé 2x — préfère être appelé après 18h</p>',
                 'date': '2026-06-10 14:05:00',
                 'author_id': [7, 'Meryem Hida']},
                {'id': 12, 'res_id': 501, 'body': '<p></p>',
                 'date': '2026-06-11 09:00:00',
                 'author_id': [7, 'Meryem Hida']},
                {'id': 13, 'res_id': 502,
                 'body': '<p>Fiche sans équivalent ERP</p>',
                 'date': '2026-06-12 10:00:00', 'author_id': False},
            ]
        return []


class OdooImportNotesCommandTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor Notes', slug='taqinor-notes')
        self.lead = Lead.objects.create(
            company=self.company, nom='Client Matché',
            telephone='+212600000201')

    def _run(self, *args):
        out = StringIO()
        with mock.patch(
                'apps.adsengine.odoo_client.OdooClient.from_env',
                return_value=_FakeOdooClient()):
            call_command('odoo_import_notes', *args, stdout=out)
        return out.getvalue()

    def test_notes_and_description_land_in_matching_lead_chatter(self):
        out = self._run()
        notes = LeadActivity.objects.filter(lead=self.lead)
        bodies = list(notes.values_list('body', flat=True))
        self.assertTrue(
            any(b.startswith('[Odoo note 11]') for b in bodies), bodies)
        note11 = next(b for b in bodies if b.startswith('[Odoo note 11]'))
        # HTML aplati, auteur et date préservés dans le texte.
        self.assertIn('Meryem Hida', note11)
        self.assertIn('après 18h', note11)
        self.assertNotIn('<p>', note11)
        self.assertTrue(
            any(b.startswith('[Odoo] Description') for b in bodies), bodies)
        # Le message 12 (corps vide une fois le HTML retiré) est ignoré.
        self.assertFalse(any('[Odoo note 12]' in b for b in bodies))
        self.assertIn('sans correspondance : 1', out)

    def test_rerun_is_idempotent(self):
        self._run()
        before = LeadActivity.objects.filter(lead=self.lead).count()
        self._run()
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead).count(), before)

    def test_unmatched_odoo_lead_creates_nothing(self):
        self._run()
        # Une seule fiche matchée : aucun lead créé pour la fiche 502.
        self.assertEqual(
            Lead.objects.filter(company=self.company).count(), 1)

    def test_dry_run_writes_nothing(self):
        out = self._run('--dry-run')
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead).count(), 0)
        self.assertIn('seraient importées', out)
