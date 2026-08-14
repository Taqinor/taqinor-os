"""NTMOB1 — tests du moteur offline-first généralisé (`apps.offlinesync`).

Couvre le critère d'acceptation du plan : une action CRM créée hors-ligne est
mise en file, puis appliquée UNE SEULE FOIS à la reconnexion — même si le flush
est rejoué deux fois. Plus : société posée serveur (jamais du corps), isolation
multi-société, op_type inconnu, refus journalisé et rejouable après correction,
plafond de lot, journal en lecture seule et scopé.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead, LeadActivity

from .models import OfflineOperation

User = get_user_model()

BATCH = '/api/django/offlinesync/operations/batch/'
JOURNAL = '/api/django/offlinesync/operations/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role_legacy='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def op(client_op_id, op_type, payload):
    return {'client_op_id': client_op_id, 'op_type': op_type, 'payload': payload}


class OfflineSyncBatchTests(TestCase):
    def setUp(self):
        self.co_a = make_company('ofs-a', 'Société A')
        self.co_b = make_company('ofs-b', 'Société B')
        self.user = make_user(self.co_a, 'ofs-resp-a')
        self.autre = make_user(self.co_b, 'ofs-resp-b')
        self.api = auth(self.user)
        self.lead = Lead.objects.create(company=self.co_a, nom='Alaoui')

    def notes(self, lead=None):
        return LeadActivity.objects.filter(
            lead=lead or self.lead, kind=LeadActivity.Kind.NOTE)

    # ── Critère d'acceptation NTMOB1 ────────────────────────────────────────
    def test_note_hors_ligne_appliquee_une_seule_fois_meme_rejouee(self):
        lot = {'ops': [op('cle-1', 'crm.lead.noter',
                          {'lead': self.lead.id, 'body': 'Client rappelé'})]}

        premier = self.api.post(BATCH, lot, format='json')
        self.assertEqual(premier.status_code, 200)
        self.assertEqual(premier.data['applied'], 1)
        self.assertEqual(premier.data['results'][0]['status'], 'applied')
        self.assertEqual(premier.data['results'][0]['module'], 'crm')

        # Rejeu EXACT du même lot (réponse perdue, onglet rechargé…).
        second = self.api.post(BATCH, lot, format='json')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data['replayed'], 1)
        self.assertEqual(second.data['applied'], 0)
        self.assertEqual(second.data['results'][0]['status'], 'replayed')

        self.assertEqual(self.notes().count(), 1, 'un seul effet métier')
        self.assertEqual(OfflineOperation.objects.filter(
            company=self.co_a, client_op_id='cle-1').count(), 1)
        journal = OfflineOperation.objects.get(client_op_id='cle-1')
        self.assertEqual(journal.statut, OfflineOperation.Statut.APPLIQUEE)
        self.assertEqual(journal.module, 'crm')
        self.assertEqual(journal.user, self.user)
        self.assertIsNotNone(journal.date_traitement)

    def test_note_porte_l_utilisateur_acteur(self):
        self.api.post(BATCH, {'ops': [op('cle-acteur', 'crm.lead.noter',
                                         {'lead': self.lead.id, 'body': 'Hop'})]},
                      format='json')
        note = self.notes().get()
        self.assertEqual(note.user, self.user)
        self.assertEqual(note.body, 'Hop')

    def test_tag_pose_hors_ligne(self):
        resp = self.api.post(BATCH, {'ops': [op('cle-tag', 'crm.lead.tag',
                                                {'lead': self.lead.id,
                                                 'tag': 'chaud'})]},
                             format='json')
        self.assertEqual(resp.data['applied'], 1)
        self.lead.refresh_from_db()
        self.assertIn('chaud', self.lead.tags)

    # ── Multi-tenant ────────────────────────────────────────────────────────
    def test_lead_d_une_autre_societe_est_refuse(self):
        etranger = Lead.objects.create(company=self.co_b, nom='Bennani')
        resp = self.api.post(BATCH, {'ops': [op('cle-x', 'crm.lead.noter',
                                                {'lead': etranger.id,
                                                 'body': 'fuite ?'})]},
                             format='json')
        self.assertEqual(resp.data['errors'], 1)
        self.assertEqual(resp.data['results'][0]['status'], 'error')
        self.assertEqual(resp.data['results'][0]['error'], 'Lead inconnu.')
        self.assertEqual(self.notes(etranger).count(), 0)
        # …et le refus est JOURNALISÉ (rien ne disparaît en silence).
        journal = OfflineOperation.objects.get(client_op_id='cle-x')
        self.assertEqual(journal.statut, OfflineOperation.Statut.REJETEE)
        self.assertEqual(journal.company, self.co_a)

    def test_company_du_corps_est_ignoree(self):
        self.api.post(BATCH, {'company': self.co_b.id,
                              'ops': [op('cle-co', 'crm.lead.noter',
                                         {'lead': self.lead.id,
                                          'company': self.co_b.id,
                                          'body': 'Note'})]},
                      format='json')
        journal = OfflineOperation.objects.get(client_op_id='cle-co')
        self.assertEqual(journal.company, self.co_a)

    def test_meme_cle_dans_deux_societes_ne_collisionne_pas(self):
        lead_b = Lead.objects.create(company=self.co_b, nom='Bennani')
        self.api.post(BATCH, {'ops': [op('cle-partagee', 'crm.lead.noter',
                                         {'lead': self.lead.id, 'body': 'A'})]},
                      format='json')
        auth(self.autre).post(BATCH, {'ops': [op('cle-partagee', 'crm.lead.noter',
                                                 {'lead': lead_b.id, 'body': 'B'})]},
                              format='json')
        self.assertEqual(
            OfflineOperation.objects.filter(client_op_id='cle-partagee').count(), 2)
        self.assertEqual(self.notes().count(), 1)
        self.assertEqual(self.notes(lead_b).count(), 1)

    # ── Robustesse du lot ───────────────────────────────────────────────────
    def test_op_type_inconnu_refuse_sans_interrompre_le_lot(self):
        resp = self.api.post(BATCH, {'ops': [
            op('cle-inconnue', 'crm.lead.teleporter', {'lead': self.lead.id}),
            op('cle-ok', 'crm.lead.noter', {'lead': self.lead.id, 'body': 'Suite'}),
        ]}, format='json')
        self.assertEqual(resp.data['errors'], 1)
        self.assertEqual(resp.data['applied'], 1)
        self.assertIn('op_type inconnu', resp.data['results'][0]['error'])
        self.assertEqual(self.notes().count(), 1)
        # Un op_type inconnu n'invente pas de ligne de journal (rien n'a été tenté).
        self.assertFalse(
            OfflineOperation.objects.filter(client_op_id='cle-inconnue').exists())

    def test_op_refusee_est_rejouable_apres_correction(self):
        refus = self.api.post(BATCH, {'ops': [op('cle-corr', 'crm.lead.noter',
                                                 {'lead': self.lead.id,
                                                  'body': '   '})]},
                              format='json')
        self.assertEqual(refus.data['errors'], 1)
        journal = OfflineOperation.objects.get(client_op_id='cle-corr')
        self.assertEqual(journal.statut, OfflineOperation.Statut.REJETEE)
        self.assertTrue(journal.erreur)

        corrige = self.api.post(BATCH, {'ops': [op('cle-corr', 'crm.lead.noter',
                                                   {'lead': self.lead.id,
                                                    'body': 'Corrigée'})]},
                                format='json')
        self.assertEqual(corrige.data['applied'], 1)
        journal.refresh_from_db()
        self.assertEqual(journal.statut, OfflineOperation.Statut.APPLIQUEE)
        self.assertEqual(journal.erreur, '')
        self.assertEqual(self.notes().count(), 1)

    def test_client_op_id_manquant_refuse(self):
        resp = self.api.post(BATCH, {'ops': [
            {'op_type': 'crm.lead.noter', 'payload': {'lead': self.lead.id,
                                                      'body': 'x'}}]},
            format='json')
        self.assertEqual(resp.data['errors'], 1)
        self.assertEqual(self.notes().count(), 0)

    def test_ops_absent_ou_invalide_repond_400(self):
        self.assertEqual(self.api.post(BATCH, {}, format='json').status_code, 400)
        self.assertEqual(
            self.api.post(BATCH, {'ops': 'nope'}, format='json').status_code, 400)

    def test_lot_trop_grand_refuse(self):
        ops = [op(f'cle-{i}', 'crm.lead.noter',
                  {'lead': self.lead.id, 'body': 'x'}) for i in range(201)]
        resp = self.api.post(BATCH, {'ops': ops}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.notes().count(), 0)

    def test_horodatage_terminal_conserve(self):
        lot = {'ops': [dict(op('cle-h', 'crm.lead.noter',
                               {'lead': self.lead.id, 'body': 'x'}),
                            queued_at='2026-08-10T09:30:00Z')]}
        self.api.post(BATCH, lot, format='json')
        journal = OfflineOperation.objects.get(client_op_id='cle-h')
        self.assertIsNotNone(journal.date_creation)
        self.assertEqual(journal.date_creation.year, 2026)

    def test_anonyme_refuse(self):
        self.assertIn(APIClient().post(BATCH, {'ops': []},
                                       format='json').status_code, (401, 403))


class OfflineOperationJournalTests(TestCase):
    def setUp(self):
        self.co_a = make_company('ofs-j-a', 'Société A')
        self.co_b = make_company('ofs-j-b', 'Société B')
        self.user = make_user(self.co_a, 'ofs-j-resp')
        self.api = auth(self.user)
        OfflineOperation.objects.create(
            company=self.co_a, module='crm', op_type='crm.lead.noter',
            client_op_id='j-a', statut=OfflineOperation.Statut.APPLIQUEE)
        OfflineOperation.objects.create(
            company=self.co_b, module='crm', op_type='crm.lead.noter',
            client_op_id='j-b', statut=OfflineOperation.Statut.REJETEE)

    def rows(self, resp):
        data = resp.data
        return data['results'] if isinstance(data, dict) and 'results' in data else data

    def test_journal_scope_societe(self):
        resp = self.api.get(JOURNAL)
        self.assertEqual(resp.status_code, 200)
        cles = {ligne['client_op_id'] for ligne in self.rows(resp)}
        self.assertEqual(cles, {'j-a'})

    def test_journal_filtre_par_statut(self):
        vide = self.rows(self.api.get(JOURNAL, {'statut': 'rejetee'}))
        self.assertEqual(len(vide), 0)
        plein = self.rows(self.api.get(JOURNAL, {'statut': 'appliquee'}))
        self.assertEqual(len(plein), 1)

    def test_journal_en_lecture_seule(self):
        resp = self.api.post(JOURNAL, {'module': 'crm', 'op_type': 'x',
                                       'client_op_id': 'z'}, format='json')
        self.assertIn(resp.status_code, (403, 405))


class RegistryTests(TestCase):
    def test_module_inconnu_refuse_a_l_enregistrement(self):
        from . import registry

        with self.assertRaises(ValueError):
            registry.register('marketing.campagne.creer', 'marketing', lambda *a: {})
        self.assertIn('crm.lead.noter', registry.registered_op_types())
        self.assertIn('crm', registry.modules_actifs())
