"""Sync Odoo bidirectionnelle sans IA — `sync_odoo_leads` / `push_odoo_stages`.

Aucune donnée réelle ni réseau : l'appel JSON-2 (`odoo_sync.odoo_call`) est
remplacé par un faux serveur en mémoire ; fixtures 100 % synthétiques.

Run:
    docker compose exec django_core python manage.py test \
        apps.crm.tests_odoo_sync -v 2
"""
import io
import os
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.crm import odoo_sync, stages
from apps.crm.management.commands.import_odoo_leads import (
    _map_stage, _map_stage_connu)
from apps.crm.models import Lead, LeadActivity
from authentication.models import Company
from core.events import lead_stage_changed

ENV = {'ODOO_SYNC_URL': 'https://odoo.example.test',
       'ODOO_SYNC_API_KEY': 'cle-de-test'}

# Trois faux leads Odoo reproduisant les cas réels relevés le 2026-09-01 :
# formulaire Meta (email bouche-trou + « adresse » = réponses du formulaire),
# lead normal avec vraie adresse, lead archivé au téléphone factice.
ODOO_LEADS = [
    {'id': 11, 'name': 'SOLAIRE FORM-4.0', 'contact_name': 'Alpha Test',
     'partner_name': 'Facebook Lead', 'email_from': 'no-email@example.com',
     'phone': '+212600000001', 'street': ' entre_2000_dh_-_4000dh ',
     'street2': 'pour_mon_entreprise', 'city': 'Casablanca',
     'stage_id': [33, 'Cold Lead'], 'active': True, 'expected_revenue': 0,
     'create_date': '2026-01-01 10:00:00', 'user_id': [7, 'Testeuse'],
     'tag_ids': [1, 2], 'lost_reason_id': False,
     'description': '<p>Note&nbsp;<b>riche</b></p>'},
    {'id': 12, 'name': 'Devis pour X', 'contact_name': 'Beta Test',
     'partner_name': 'Beta SARL', 'email_from': 'beta@example.test',
     'phone': '+212600000002', 'street': '12 rue des Tests', 'street2': '',
     'city': 'Rabat', 'stage_id': [26, 'Quote Discussed'], 'active': True,
     'expected_revenue': 15000, 'create_date': '2026-02-01 10:00:00',
     'user_id': False, 'tag_ids': [], 'lost_reason_id': False,
     'description': ''},
    {'id': 13, 'name': 'Gamma', 'contact_name': 'Gamma Test',
     'partner_name': '', 'email_from': '',
     'phone': '<test lead: dummy data for phone_number>', 'street': '',
     'street2': '', 'city': '', 'stage_id': [9, 'Contract Signed + Deposit'],
     'active': False, 'expected_revenue': 0,
     'create_date': '2026-03-01 10:00:00', 'user_id': False, 'tag_ids': [],
     'lost_reason_id': [4, 'Trop cher'], 'description': ''},
]
ODOO_TAGS = [{'id': 1, 'name': 'NRP'}, {'id': 2, 'name': 'Residential'}]
# Colonnes du pipeline Odoo simulé (données côté Odoo, pas des étapes ERP).
COLONNES_ODOO = [
    {'id': 1, 'name': 'New'}, {'id': 2, 'name': 'Lead Qualified'},
    {'id': 5, 'name': 'prilimanary quote sent'},
    {'id': 26, 'name': 'Quote Discussed'},
    {'id': 9, 'name': 'Contract Signed + Deposit'},
    {'id': 33, 'name': 'Cold Lead'},
]


class FakeOdoo:
    """Faux point d'entrée JSON-2 : sert les fixtures, journalise les écrits."""

    def __init__(self):
        self.writes = []

    def __call__(self, config, model, method, payload, timeout=120):
        if (model, method) == ('crm.lead', 'search_read'):
            if payload.get('offset', 0):
                return []
            return [dict(r) for r in ODOO_LEADS]
        if (model, method) == ('crm.tag', 'search_read'):
            return [dict(r) for r in ODOO_TAGS]
        if (model, method) == ('crm.stage', 'search_read'):
            return [dict(r) for r in COLONNES_ODOO]
        if (model, method) == ('crm.lead', 'write'):
            self.writes.append(payload)
            return True
        raise AssertionError(f'appel inattendu : {model}.{method}')


class OdooSyncBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='odoo-sync-co', defaults={'nom': 'Odoo Sync Co'})[0]
        self.fake = FakeOdoo()
        patches = [
            patch('apps.crm.odoo_sync.odoo_call', self.fake),
            patch.dict(os.environ, ENV),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _sync(self, **kwargs):
        out = io.StringIO()
        call_command('sync_odoo_leads', company=self.company.slug,
                     stdout=out, **kwargs)
        return out.getvalue()

    def _push(self, **kwargs):
        out = io.StringIO()
        call_command('push_odoo_stages', company=self.company.slug,
                     stdout=out, **kwargs)
        return out.getvalue()


class TestStageMap(TestCase):
    def test_real_pipeline_names_map_to_canonical_keys(self):
        # Les 18 intitulés réels (2026-09-01) → clés STAGES.py, y compris
        # accents (« Dernière chance ») et tirets (« post-quote »).
        attendus = {
            'New': stages.NEW,
            '2eme appel+ message Whatsapp': stages.CONTACTED,
            'dernier appel+note odoo': stages.CONTACTED,
            'Lead Qualified': stages.CONTACTED,
            'Waiting for consumption bills': stages.CONTACTED,
            'prilimanary quote sent': stages.QUOTE_SENT,
            'final quote sent': stages.QUOTE_SENT,
            'Quote Discussed': stages.FOLLOW_UP,
            'site visite scheduled': stages.FOLLOW_UP,
            'Negotiation / Objection': stages.FOLLOW_UP,
            'Verbal Agreement': stages.FOLLOW_UP,
            'Dernière chance': stages.FOLLOW_UP,
            'no answer to post-quote call': stages.FOLLOW_UP,
            'Contract Signed + Deposit': stages.SIGNED,
            'Cold Lead': stages.COLD,
            'not convinced no quote': stages.COLD,
            'Devis Cold': stages.COLD,
            'lost': stages.COLD,
        }
        for intitule, cle in attendus.items():
            self.assertEqual(_map_stage(intitule), cle, intitule)

    def test_unknown_stage_none_for_alignment_but_new_for_creation(self):
        # CRX8/D-CRX3 — le repli NEW ne survit que pour la CRÉATION.
        for inconnu in ('Colonne Maison Inconnue', '', None, '   '):
            self.assertIsNone(_map_stage_connu(inconnu), repr(inconnu))
            self.assertEqual(_map_stage(inconnu), stages.NEW, repr(inconnu))


class TestBuildRows(TestCase):
    def setUp(self):
        self.rows = {r['id']: r for r in odoo_sync.build_rows(
            ODOO_LEADS, {t['id']: t['name'] for t in ODOO_TAGS})}

    def test_placeholder_email_purged_junk_street_to_note(self):
        alpha = self.rows[11]
        self.assertNotIn('email', alpha)      # bouche-trou purgé
        self.assertNotIn('adresse', alpha)    # réponses formulaire ≠ adresse
        self.assertNotIn('societe', alpha)    # « Facebook Lead » ≠ société
        self.assertIn('Formulaire Meta: entre_2000_dh_-_4000dh', alpha['note'])
        self.assertIn('Tags Odoo: NRP, Residential', alpha['note'])
        self.assertEqual(alpha['telephone'], '+212600000001')

    def test_real_fields_kept_and_html_stripped(self):
        beta = self.rows[12]
        self.assertEqual(beta['nom'], 'Beta Test')
        self.assertEqual(beta['societe'], 'Beta SARL')
        self.assertEqual(beta['email'], 'beta@example.test')
        self.assertEqual(beta['adresse'], '12 rue des Tests')
        self.assertEqual(beta['stage'], 'Quote Discussed')
        self.assertIn('Revenu attendu Odoo: 15000 DH', beta['note'])
        alpha = self.rows[11]
        self.assertIn('Note riche', alpha['note'])
        self.assertNotIn('<p>', alpha['note'])

    def test_invalid_phone_and_archive_traced_in_note(self):
        gamma = self.rows[13]
        self.assertNotIn('telephone', gamma)  # factice → jamais en base
        self.assertIn('Téléphone Odoo invalide: <test lead', gamma['note'])
        self.assertIn('Archivé dans Odoo', gamma['note'])
        self.assertIn('Motif de perte Odoo: Trop cher', gamma['note'])


class TestSyncCommand(OdooSyncBase):
    def test_creates_leads_with_mapped_stages_and_aligns(self):
        self._sync()
        leads = Lead.objects.filter(company=self.company)
        self.assertEqual(leads.count(), 3)
        self.assertEqual(leads.get(external_id='11').stage, stages.COLD)
        self.assertEqual(leads.get(external_id='12').stage, stages.FOLLOW_UP)
        self.assertEqual(leads.get(external_id='13').stage, stages.SIGNED)
        # Idempotent : re-lancer ne crée rien et ne déplace rien.
        sortie = self._sync()
        self.assertEqual(
            Lead.objects.filter(company=self.company).count(), 3)
        self.assertIn("0 écart(s) en avance côté Odoo", sortie)

    def test_aligns_existing_manual_lead_with_chatter_trace(self):
        # AACQ97 (D-AACQ, 08/10/2026) — la commande ne fait plus que
        # RAPPORTER l'écart : l'ERP fait foi, aucune étape n'est écrite.
        manuel = Lead.objects.create(
            company=self.company, nom='Copie Manuelle',
            email='beta@example.test', stage=stages.NEW)
        sortie = self._sync()
        manuel.refresh_from_db()
        # Rapproché par email → clé technique posée, étape INCHANGÉE.
        self.assertEqual(manuel.external_id, '12')
        self.assertEqual(manuel.stage, stages.NEW)
        self.assertFalse(LeadActivity.objects.filter(
            lead=manuel, kind=LeadActivity.Kind.MODIFICATION,
            field='stage').exists())
        self.assertFalse(LeadActivity.objects.filter(
            lead=manuel, kind=LeadActivity.Kind.NOTE,
            body='auto — alignement sur le pipeline Odoo').exists())
        self.assertIn('écart (non appliqué) — ERP NEW / Odoo FOLLOW_UP',
                      sortie)

    def test_dry_run_writes_nothing(self):
        sortie = self._sync(dry_run=True)
        self.assertEqual(
            Lead.objects.filter(company=self.company).count(), 0)
        self.assertIn('[dry-run]', sortie)

    def test_without_config_does_nothing(self):
        with patch.dict(os.environ,
                        {'ODOO_SYNC_URL': '', 'ODOO_SYNC_API_KEY': ''}):
            self._sync()
        self.assertEqual(Lead.objects.count(), 0)


class TestAlignementAvanceSeulement(OdooSyncBase):
    """CRX8 / D-CRX3 — Odoo → ERP AVANCE seulement, et rapporte le reste.

    Avant : l'alignement était un MIROIR — un pipeline Odoo tenu à la main
    pouvait faire RECULER le funnel de l'ERP, et une colonne Odoo hors table
    ramenait le lead à « Nouveau » (défaut de ``_map_stage``). L'écriture
    passait par un ``LeadActivity`` artisanal MUET : ni playbook ni séquence
    ne se déclenchait sur un mouvement venu d'Odoo.
    """

    def _lead(self, **kwargs):
        return Lead.objects.create(company=self.company, **kwargs)

    def _align(self, rows, apply_changes=True):
        return odoo_sync.align_stages_from_rows(
            self.company, rows, apply_changes=apply_changes)

    def _capturer_evenements(self):
        recus = []

        def _capture(sender, **kwargs):
            recus.append((kwargs['lead'].pk, kwargs['old_stage'],
                          kwargs['new_stage'], kwargs.get('user')))

        lead_stage_changed.connect(_capture, weak=False)
        self.addCleanup(lead_stage_changed.disconnect, _capture)
        return recus

    def test_advance_goes_through_canonical_path_and_emits_event(self):
        lead = self._lead(nom='À Avancer', external_system='odoo',
                          external_id='80', stage=stages.NEW)
        recus = self._capturer_evenements()

        rapport = self._align([{'id': 80, 'stage': 'Quote Discussed'}])

        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.FOLLOW_UP)
        self.assertEqual(rapport.moves[(stages.NEW, stages.FOLLOW_UP)], 1)
        self.assertEqual(rapport.regressions, [])
        # L'événement canonique part enfin (playbooks + séquences compta).
        self.assertEqual(
            recus, [(lead.pk, stages.NEW, stages.FOLLOW_UP, None)])
        self.assertTrue(LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.MODIFICATION,
            field='stage', bulk=True).exists())
        self.assertTrue(LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE,
            body='auto — alignement sur le pipeline Odoo').exists())

    def test_regression_is_reported_with_zero_write(self):
        lead = self._lead(nom='Plus Avancé', external_system='odoo',
                          external_id='78', stage=stages.SIGNED)
        recus = self._capturer_evenements()

        rapport = self._align([{'id': 78, 'stage': 'Quote Discussed'}])

        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.SIGNED)       # zéro écriture
        self.assertEqual(sum(rapport.moves.values()), 0)
        self.assertEqual(
            rapport.regressions,
            [(lead.pk, 'Plus Avancé', stages.SIGNED, 'Quote Discussed',
              stages.FOLLOW_UP)])
        self.assertEqual(recus, [])
        self.assertFalse(LeadActivity.objects.filter(lead=lead).exists())

    def test_cold_never_pulls_an_active_lead_backwards(self):
        # « Froid » est un PARKING classé SOUS « Nouveau » (rang -1) : Odoo ne
        # peut pas refroidir un lead que le commercial a fait avancer.
        lead = self._lead(nom='Actif', external_system='odoo',
                          external_id='79', stage=stages.CONTACTED)

        rapport = self._align([{'id': 79, 'stage': 'Cold Lead'}])

        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)
        self.assertEqual(sum(rapport.moves.values()), 0)
        self.assertEqual(len(rapport.regressions), 1)
        self.assertEqual(rapport.regressions[0][2:], (
            stages.CONTACTED, 'Cold Lead', stages.COLD))

    def test_cold_lead_is_still_reactivated_forward(self):
        # L'inverse reste vrai : depuis « Froid », toute étape active AVANCE.
        lead = self._lead(nom='Froid', external_system='odoo',
                          external_id='81', stage=stages.COLD)

        rapport = self._align([{'id': 81, 'stage': 'Lead Qualified'}])

        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)
        self.assertEqual(rapport.moves[(stages.COLD, stages.CONTACTED)], 1)

    def test_unknown_odoo_stage_leaves_the_lead_untouched(self):
        lead = self._lead(nom='Colonne Maison', external_system='odoo',
                          external_id='82', stage=stages.CONTACTED)
        recus = self._capturer_evenements()

        rapport = self._align([
            {'id': 82, 'stage': 'Colonne Maison Jamais Vue'},
        ])

        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)   # pas de repli NEW
        self.assertEqual(rapport.inconnus, 1)
        self.assertEqual(sum(rapport.moves.values()), 0)
        self.assertEqual(rapport.regressions, [])
        self.assertEqual(recus, [])
        self.assertFalse(LeadActivity.objects.filter(lead=lead).exists())

    def test_dry_run_counts_the_advance_but_writes_nothing(self):
        lead = self._lead(nom='À Blanc', external_system='odoo',
                          external_id='83', stage=stages.NEW)
        recus = self._capturer_evenements()

        rapport = self._align([{'id': 83, 'stage': 'Quote Discussed'}],
                              apply_changes=False)

        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.NEW)
        self.assertEqual(rapport.moves[(stages.NEW, stages.FOLLOW_UP)], 1)
        self.assertEqual(recus, [])

    def test_two_odoo_rows_on_the_same_erp_lead_are_counted(self):
        # CRX10 — le doublon INTERNE au pipeline Odoo était sauté en silence.
        lead = self._lead(nom='Un Seul', external_system='odoo',
                          external_id='90', email='dup@example.test',
                          stage=stages.NEW)

        rapport = self._align([
            {'id': 90, 'stage': 'Quote Discussed'},
            {'id': 91, 'stage': 'New', 'email': 'dup@example.test'},
        ])

        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.FOLLOW_UP)   # la 1re ligne gagne
        self.assertEqual(rapport.doublons_odoo, 1)

    def test_regression_reaches_the_command_report(self):
        # Le lead 12 d'Odoo est en « Quote Discussed » (FOLLOW_UP) ; côté ERP
        # il est déjà SIGNED — la sync le SIGNALE au lieu de le reculer.
        avance = Lead.objects.create(
            company=self.company, nom='Signé Chez Nous',
            email='beta@example.test', stage=stages.SIGNED)

        sortie = self._sync()

        avance.refresh_from_db()
        self.assertEqual(avance.stage, stages.SIGNED)
        self.assertIn('Régression NON appliquée', sortie)
        self.assertIn('ERP SIGNED / Odoo « Quote Discussed »', sortie)
        self.assertIn('1 régression(s) signalée(s)', sortie)


class TestAllowlistEcrituresOdoo(TestCase):
    """CRX11 — règle #1 : `odoo_call` refuse toute écriture non déclarée.

    Ce transport est GÉNÉRIQUE (`model` et `method` sont des paramètres) :
    sans cette garde, n'importe quel appelant futur pouvait écrire ce qu'il
    voulait dans la base Odoo du fondateur. Le refus tombe AVANT le réseau.
    """

    def setUp(self):
        self.config = odoo_sync.OdooConfig(
            url='https://odoo.example.test', api_key='cle-de-test')

    def test_only_one_write_is_allowed_in_the_whole_repo(self):
        self.assertEqual(odoo_sync._WRITE_ALLOWED,
                         frozenset({('crm.lead', 'write')}))

    def test_undeclared_write_is_refused_before_any_http(self):
        with patch('urllib.request.urlopen') as reseau:
            for model, method in (('crm.lead', 'unlink'),
                                  ('crm.lead', 'create'),
                                  ('res.partner', 'write'),
                                  ('account.move', 'create')):
                with self.assertRaises(odoo_sync.OdooSyncError) as ctx:
                    odoo_sync.odoo_call(self.config, model, method, {})
                self.assertIn('allowlist', str(ctx.exception))
            reseau.assert_not_called()

    def test_reads_and_the_single_declared_write_reach_the_transport(self):
        class _Reponse:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b'[]'

        with patch('urllib.request.urlopen',
                   return_value=_Reponse()) as reseau:
            odoo_sync.odoo_call(self.config, 'crm.lead', 'search_read', {})
            odoo_sync.odoo_call(self.config, 'crm.stage', 'search_read', {})
            odoo_sync.odoo_call(self.config, 'crm.lead', 'write',
                                {'ids': [1], 'vals': {'stage_id': 2}})
        self.assertEqual(reseau.call_count, 3)


class TestPushCommand(OdooSyncBase):
    def _lead(self, **kwargs):
        return Lead.objects.create(company=self.company, **kwargs)

    def test_moves_only_six_level_inconsistencies(self):
        # NEW côté ERP vs « Cold Lead » (COLD) côté Odoo → à déplacer.
        self._lead(nom='Alpha', external_system='odoo', external_id='11',
                   stage=stages.NEW)
        # FOLLOW_UP vs « Quote Discussed » (FOLLOW_UP) → cohérent, intouché.
        self._lead(nom='Beta', email='beta@example.test',
                   stage=stages.FOLLOW_UP)
        moves, coherents, non_rapproches = odoo_sync.compute_push_moves(
            self.company, ODOO_LEADS)
        self.assertEqual(moves, {'New': [11]})
        self.assertEqual(coherents, 1)
        self.assertEqual(non_rapproches, 1)  # gamma : ni clé ni email ni tél

    def test_dry_by_default_and_writes_stage_id_only_with_apply(self):
        self._lead(nom='Alpha', external_system='odoo', external_id='11',
                   stage=stages.NEW)
        sortie = self._push()
        self.assertEqual(self.fake.writes, [])      # à blanc par défaut
        self.assertIn('À blanc', sortie)
        self._push(apply=True)
        self.assertEqual(self.fake.writes,
                         [{'ids': [11], 'vals': {'stage_id': 1}}])

    def test_missing_target_stage_fails_loudly(self):
        self._lead(nom='Alpha', external_system='odoo', external_id='11',
                   stage=stages.NEW)
        with patch.object(odoo_sync, 'PUSH_STAGE_TARGETS',
                          {**odoo_sync.PUSH_STAGE_TARGETS,
                           stages.NEW: 'Colonne Disparue'}):
            from django.core.management.base import CommandError
            with self.assertRaises(CommandError):
                self._push(apply=True)
        self.assertEqual(self.fake.writes, [])

    def test_without_config_does_nothing(self):
        with patch.dict(os.environ,
                        {'ODOO_SYNC_URL': '', 'ODOO_SYNC_API_KEY': ''}):
            sortie = self._push(apply=True)
        self.assertEqual(self.fake.writes, [])
        self.assertIn('Config Odoo absente', sortie)


class PushSelectionTests(OdooSyncBase):
    """AACQ32 — ``push_odoo_stages`` choisit les leads à déplacer avec les
    MÊMES règles que l'alignement : colonne Odoo inconnue/vide = intouchée
    (« inconnus ») ; rapprochement ambigu = non poussé (« ambigus »)."""

    def _lead(self, **kwargs):
        return Lead.objects.create(company=self.company, **kwargs)

    def _odoo(self, odoo_id, stage, *, email='', phone=''):
        return {'id': odoo_id, 'email_from': email, 'phone': phone,
                'stage_id': stage}

    def test_unknown_odoo_stage_not_pushed(self):
        self._lead(nom='Maison', external_system='odoo', external_id='99',
                   stage=stages.CONTACTED)
        resultat = odoo_sync.compute_push_moves(
            self.company, [self._odoo(99, [99, 'Colonne Maison'])])
        moves, coherents, non_rapproches = resultat
        self.assertEqual(moves, {})
        self.assertEqual(resultat.inconnus, 1)

    def test_empty_odoo_stage_not_pushed(self):
        self._lead(nom='Sans etape', external_system='odoo',
                   external_id='98', stage=stages.CONTACTED)
        resultat = odoo_sync.compute_push_moves(
            self.company, [self._odoo(98, False)])
        self.assertEqual(resultat.moves, {})
        self.assertEqual(resultat.inconnus, 1)

    def test_ambiguous_email_not_pushed(self):
        self._lead(nom='A ancien', email='double@example.test',
                   stage=stages.NEW)
        self._lead(nom='B recent', email='double@example.test',
                   stage=stages.SIGNED)
        resultat = odoo_sync.compute_push_moves(self.company, [
            self._odoo(97, [1, 'New'], email='double@example.test')])
        self.assertEqual(resultat.moves, {})
        self.assertEqual(resultat.ambigus, 1)

    def test_nominal_lead_still_pushed(self):
        self._lead(nom='Nominal', external_system='odoo', external_id='96',
                   stage=stages.NEW)
        resultat = odoo_sync.compute_push_moves(
            self.company, [self._odoo(96, [33, 'Cold Lead'])])
        self.assertEqual(resultat.moves, {'New': [96]})
        self.assertEqual((resultat.inconnus, resultat.ambigus), (0, 0))

    def test_command_prints_both_counters(self):
        self._lead(nom='Alpha', external_system='odoo', external_id='11',
                   stage=stages.NEW)
        sortie = self._push()
        self.assertIn('inconnus : 0', sortie)
        self.assertIn('ambigus : 0', sortie)


class AlignementGelTests(OdooSyncBase):
    """AACQ33 — l'alignement Odoo n'avance JAMAIS un lead perdu, archivé ou
    « ne plus contacter » (aucune écriture d'étape, aucun signal) ; il le
    compte « gelé »."""

    def _lead(self, **kwargs):
        return Lead.objects.create(company=self.company, **kwargs)

    def _align(self, rows, apply_changes=True):
        return odoo_sync.align_stages_from_rows(
            self.company, rows, apply_changes=apply_changes)

    def _capturer_evenements(self):
        recus = []

        def _capture(sender, **kwargs):
            recus.append((kwargs['lead'].pk, kwargs['old_stage'],
                          kwargs['new_stage']))

        lead_stage_changed.connect(_capture, weak=False)
        self.addCleanup(lead_stage_changed.disconnect, _capture)
        return recus

    def test_perdu_archive_npc_jamais_avances(self):
        geles = [
            self._lead(nom='Perdu', external_system='odoo', external_id='60',
                       stage=stages.CONTACTED, perdu=True),
            self._lead(nom='Archive', external_system='odoo',
                       external_id='61', stage=stages.CONTACTED,
                       is_archived=True),
            self._lead(nom='NPC', external_system='odoo', external_id='62',
                       stage=stages.CONTACTED, ne_plus_contacter=True),
        ]
        vivant = self._lead(nom='Vivant', external_system='odoo',
                            external_id='63', stage=stages.NEW)
        recus = self._capturer_evenements()

        rapport = self._align([
            {'id': 60, 'stage': 'Quote Discussed'},
            {'id': 61, 'stage': 'Quote Discussed'},
            {'id': 62, 'stage': 'Quote Discussed'},
            {'id': 63, 'stage': 'Quote Discussed'},
        ])

        for lead in geles:
            lead.refresh_from_db()
            self.assertEqual(lead.stage, stages.CONTACTED)
            self.assertFalse(LeadActivity.objects.filter(lead=lead).exists())
        self.assertEqual(rapport.geles, 3)
        vivant.refresh_from_db()
        self.assertEqual(vivant.stage, stages.FOLLOW_UP)
        self.assertEqual([r[0] for r in recus], [vivant.pk])

    def test_perdu_signe_odoo_reste_gele(self):
        lead = self._lead(nom='Perdu signe', external_system='odoo',
                          external_id='64', stage=stages.QUOTE_SENT,
                          perdu=True)
        recus = self._capturer_evenements()
        rapport = self._align(
            [{'id': 64, 'stage': 'Contract Signed + Deposit'}])
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.QUOTE_SENT)
        self.assertTrue(lead.perdu)
        self.assertEqual(rapport.geles, 1)
        self.assertEqual(recus, [])

    def test_commande_affiche_les_geles(self):
        self._lead(nom='Beta perdu', email='beta@example.test',
                   stage=stages.NEW, perdu=True)
        sortie = self._sync()
        self.assertIn('gelé(s) :', sortie)
        beta = Lead.objects.get(company=self.company, nom='Beta perdu')
        self.assertEqual(beta.stage, stages.NEW)


class AlignementReculHumainTests(OdooSyncBase):
    """AACQ31 — un recul confirmé par un humain dans l'ERP, plus récent que
    le dernier changement d'étape Odoo, survit à l'alignement (l'ERP fait
    foi, D-AACQ 08/10/2026) et est rapporté en « divergence assumée »."""

    def setUp(self):
        super().setUp()
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        from apps.roles.models import Role
        from apps.roles.permissions_registre import RESPONSABLE_PERMISSIONS
        role, _ = Role.objects.get_or_create(
            company=self.company, nom='Responsable',
            defaults={'permissions': RESPONSABLE_PERMISSIONS,
                      'est_systeme': True})
        self.resp = get_user_model().objects.create_user(
            username='aacq31-resp', password='x', company=self.company,
            role=role, role_legacy='responsable')
        self.lead = Lead.objects.create(
            company=self.company, nom='Recul', external_system='odoo',
            external_id='12', email='beta@example.test',
            stage=stages.FOLLOW_UP, owner=self.resp)
        api = APIClient()
        api.force_authenticate(self.resp)
        resp = api.patch(f'/api/django/crm/leads/{self.lead.pk}/',
                         {'stage': stages.CONTACTED, 'confirme_recul': True},
                         format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.CONTACTED)

    def _ligne(self, date_odoo):
        return [{'id': 12, 'stage': 'Quote Discussed',
                 'date_last_stage_update_odoo': date_odoo}]

    def test_recul_humain_recent_survit_a_l_alignement(self):
        for _ in range(2):
            rapport = odoo_sync.align_stages_from_rows(
                self.company, self._ligne('2020-01-01 10:00:00'),
                apply_changes=True)
            self.assertEqual(rapport.divergences_assumees, 1)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.CONTACTED)
        self.assertFalse(LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE,
            body='auto — alignement sur le pipeline Odoo').exists())
        sortie = self._sync()
        self.assertIn('divergence(s) assumée(s) : 1', sortie)

    def test_odoo_plus_recent_avance_toujours(self):
        rapport = odoo_sync.align_stages_from_rows(
            self.company, self._ligne('2099-01-01 10:00:00'),
            apply_changes=True)
        self.assertEqual(rapport.divergences_assumees, 0)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.FOLLOW_UP)


def _lead_odoo(odoo_id, nom, **kwargs):
    base = {
        'id': odoo_id, 'name': nom, 'contact_name': nom, 'partner_name': '',
        'email_from': f'{nom.lower()}@example.test', 'phone': '+2126%08d' % odoo_id,
        'street': '', 'street2': '', 'city': '',
        'stage_id': [1, 'New'], 'active': True, 'expected_revenue': 0,
        'create_date': '2026-10-05 10:00:00', 'user_id': False, 'tag_ids': [],
        'lost_reason_id': False, 'description': '',
    }
    base.update(kwargs)
    return base


class GardeCreationPerduOdooTests(OdooSyncBase):
    """AACQ34 [TRANCHÉ 10/10/2026] — garde À LA CRÉATION seulement : un lead
    NEUF déjà perdu/archivé dans Odoo ne démarre aucune cadence ; un lead ERP
    existant n'est JAMAIS modifié par une perte côté Odoo."""

    def _passer(self, leads):
        cible = ('apps.crm.management.commands.sync_odoo_leads.'
                 'fetch_odoo_leads')
        with patch(cible, return_value=(leads, {})):
            return self._sync()

    def test_build_rows_porte_active_et_motif_en_lecture_seule(self):
        rows = {r['id']: r for r in odoo_sync.build_rows(ODOO_LEADS, {})}
        self.assertTrue(rows[12]['active'])
        self.assertNotIn('lost_reason_id', rows[12])
        self.assertFalse(rows[13]['active'])
        self.assertEqual(rows[13]['lost_reason_id'], 'Trop cher')

    def test_lead_neuf_deja_perdu_sans_cadence(self):
        from apps.crm import services
        leads = [
            _lead_odoo(71, 'Vivant'),
            _lead_odoo(72, 'Archive', active=False),
            _lead_odoo(73, 'Perdu', lost_reason_id=[4, 'Trop cher']),
        ]
        with patch.object(services, 'demarrer_cadence_contact',
                          wraps=services.demarrer_cadence_contact) as spy:
            sortie = self._passer(leads)
        appeles = {c.args[0].external_id for c in spy.call_args_list}
        self.assertEqual(appeles, {'71'})
        for ext in ('72', '73'):
            lead = Lead.objects.get(company=self.company, external_id=ext)
            self.assertFalse(lead.relance_etapes.exists())
            self.assertFalse(lead.perdu)  # l'ERP ne change rien d'autre
        self.assertIn('cadence non démarrée', sortie)
        self.assertIn('Trop cher', sortie)

    def test_lead_existant_perdu_dans_odoo_inchange(self):
        from apps.crm import cadence_plan
        from apps.crm import cadence_reponses
        existant = Lead.objects.create(
            company=self.company, nom='Existant', external_system='odoo',
            external_id='80', stage=stages.NEW)
        avant = (existant.stage, existant.perdu, existant.is_archived)
        nb_activites = LeadActivity.objects.filter(lead=existant).count()
        perdu = _lead_odoo(80, 'Existant', active=False,
                           lost_reason_id=[4, 'Trop cher'])
        with patch.object(cadence_reponses, 'marquer_lead_perdu') as perdre, \
                patch.object(cadence_plan, 'arreter_cadence') as arreter:
            self._passer([perdu])
            self._passer([perdu])
        perdre.assert_not_called()
        arreter.assert_not_called()
        existant.refresh_from_db()
        self.assertEqual(
            (existant.stage, existant.perdu, existant.is_archived), avant)
        self.assertEqual(
            LeadActivity.objects.filter(lead=existant).count(), nb_activites)
