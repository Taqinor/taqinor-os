"""NTGRC31 — recherche e-discovery transverse + séquestre des résultats.

Garanties : une recherche retourne les objets correspondants GROUPÉS PAR APP
et peut créer un séquestre couvrant ces résultats ; les périmètres qu'un
séquestre ne sait pas réellement geler sont DITS, jamais tus ; aucune lecture
cross-société. Horloge FIGÉE.
"""
from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.selectors import rechercher_journal
from apps.crm.models import Client, Lead
from apps.grc.models import LegalHold
from apps.grc.selectors import APPS_E_DISCOVERY, rechercher_e_discovery
from apps.grc.services import placer_resultats_sous_hold
from authentication.models import Company
from testkit.base import TenantAPITestCase
from testkit.time import frozen

INSTANT = '2026-09-12 13:00:00+00:00'
CIBLE = 'personne@exemple.ma'


def _peupler(company):
    client = Client.objects.create(
        company=company, nom='Personne Cible', email=CIBLE)
    lead = Lead.objects.create(
        company=company, nom='Personne Cible', email=CIBLE)
    AuditLog.objects.create(
        company=company, action=AuditLog.Action.UPDATE,
        actor_username='dpo', object_repr=f'Client {CIBLE}',
        detail='Email modifié')
    return client, lead


class RechercheEDiscoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC31 SA', slug='ntgrc31')

    def test_la_recherche_groupe_par_app(self):
        with frozen(INSTANT):
            client, lead = _peupler(self.company)
            resultat = rechercher_e_discovery(self.company, CIBLE)
        self.assertEqual(
            [ligne['id'] for ligne in resultat['resultats']['crm_client']],
            [client.pk])
        self.assertEqual(
            [ligne['id'] for ligne in resultat['resultats']['crm_lead']],
            [lead.pk])
        self.assertEqual(len(resultat['resultats']['audit_log']), 1)
        self.assertEqual(resultat['total'], 3)
        self.assertEqual(resultat['genere_le'], '2026-09-12T13:00:00+00:00')

    def test_un_perimetre_restreint_ne_fouille_que_lui(self):
        with frozen(INSTANT):
            _peupler(self.company)
            resultat = rechercher_e_discovery(
                self.company, CIBLE, apps=['crm_client'])
        self.assertEqual(list(resultat['resultats']), ['crm_client'])
        self.assertEqual(resultat['apps'], ['crm_client'])

    def test_une_app_inconnue_ne_declenche_aucun_scan_sauvage(self):
        with frozen(INSTANT):
            _peupler(self.company)
            resultat = rechercher_e_discovery(
                self.company, CIBLE, apps=['compta_tout'])
        self.assertEqual(resultat['apps'], list(APPS_E_DISCOVERY))

    def test_sans_utilisateur_la_ged_est_omise_et_le_dit(self):
        with frozen(INSTANT):
            _peupler(self.company)
            resultat = rechercher_e_discovery(self.company, CIBLE)
        self.assertEqual(resultat['perimetres_omis'], ['ged_document'])
        self.assertEqual(resultat['resultats']['ged_document'], [])

    def test_un_terme_vide_ne_ramene_rien(self):
        with frozen(INSTANT):
            _peupler(self.company)
            resultat = rechercher_e_discovery(self.company, '   ')
        self.assertEqual(resultat['total'], 0)

    def test_la_recherche_est_bornee_a_la_societe(self):
        autre = Company.objects.create(nom='Autre', slug='ntgrc31-autre')
        with frozen(INSTANT):
            _peupler(autre)
            resultat = rechercher_e_discovery(self.company, CIBLE)
        self.assertEqual(resultat['total'], 0)

    def test_la_periode_borne_le_journal(self):
        with frozen(INSTANT):
            _peupler(self.company)
        with frozen('2026-10-20 13:00:00+00:00'):
            resultat = rechercher_e_discovery(
                self.company, CIBLE,
                periode={'debut': timezone.now(), 'fin': None})
        self.assertEqual(resultat['resultats']['audit_log'], [])

    def test_le_selector_audit_ignore_un_terme_vide(self):
        with frozen(INSTANT):
            _peupler(self.company)
            self.assertEqual(
                list(rechercher_journal(self.company, '')), [])


class SequestreDesResultatsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC31 H', slug='ntgrc31-h')

    def test_le_sequestre_couvre_les_resultats_gelables(self):
        with frozen(INSTANT):
            client, lead = _peupler(self.company)
            resultat = rechercher_e_discovery(self.company, CIBLE)
            hold, ignores = placer_resultats_sous_hold(
                self.company, resultat['resultats'], nom='Contentieux X')
        self.assertIsNotNone(hold)
        self.assertEqual(hold.company, self.company)
        self.assertEqual(hold.statut, LegalHold.STATUT_ACTIF)
        perimetre = {e['type_objet']: e['filtre']['ids']
                     for e in hold.perimetre}
        self.assertEqual(perimetre['crm_client'], [client.pk])
        self.assertEqual(perimetre['crm_lead'], [lead.pk])

    def test_le_journal_n_est_jamais_pretendu_gele(self):
        with frozen(INSTANT):
            _peupler(self.company)
            resultat = rechercher_e_discovery(self.company, CIBLE)
            hold, ignores = placer_resultats_sous_hold(
                self.company, resultat['resultats'], nom='Contentieux X')
        self.assertNotIn(
            'audit_log', {e['type_objet'] for e in hold.perimetre})
        self.assertEqual(ignores, ['audit_log'])

    def test_aucun_resultat_gelable_ne_cree_pas_de_sequestre_vide(self):
        with frozen(INSTANT):
            hold, _ = placer_resultats_sous_hold(
                self.company, {'crm_client': []}, nom='Vide')
        self.assertIsNone(hold)
        self.assertEqual(LegalHold.objects.count(), 0)


class EndpointEDiscoveryTests(TenantAPITestCase):
    URL = '/api/django/grc/e-discovery/'

    def _admin(self):
        return self.client_as(role='admin')

    def test_recherche_get(self):
        with frozen(INSTANT):
            client, _ = _peupler(self.company)
            r = self._admin().get(self.URL, {'terme': CIBLE})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(
            [ligne['id'] for ligne in r.data['resultats']['crm_client']],
            [client.pk])

    def test_un_terme_manquant_nomme_le_champ(self):
        r = self._admin().get(self.URL)
        self.assertEqual(r.status_code, 400)
        self.assertIn('terme', r.data)

    def test_post_cree_le_sequestre(self):
        with frozen(INSTANT):
            _peupler(self.company)
            r = self._admin().post(
                self.URL,
                {'terme': CIBLE,
                 'legal_hold': {'nom': 'Contentieux Y', 'motif': 'litige'}},
                format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIsNotNone(r.data['legal_hold'])
        self.assertEqual(r.data['types_ignores'], ['audit_log'])
        hold = LegalHold.objects.get(pk=r.data['legal_hold']['id'])
        self.assertEqual(hold.company, self.company)
        self.assertEqual(hold.nom, 'Contentieux Y')

    def test_post_sans_legal_hold_ne_cree_rien(self):
        with frozen(INSTANT):
            _peupler(self.company)
            r = self._admin().post(
                self.URL, {'terme': CIBLE}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(LegalHold.objects.count(), 0)

    def test_une_periode_illisible_ne_fait_pas_echouer_la_recherche(self):
        with frozen(INSTANT):
            _peupler(self.company)
            r = self._admin().get(
                self.URL, {'terme': CIBLE, 'debut': 'pas-une-date'})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(r.data['periode']['debut'])

    def test_la_recherche_ne_franchit_pas_la_frontiere_societe(self):
        with frozen(INSTANT):
            _peupler(self.other_company)
            r = self._admin().get(self.URL, {'terme': CIBLE})
        self.assertEqual(r.data['total'], 0)
