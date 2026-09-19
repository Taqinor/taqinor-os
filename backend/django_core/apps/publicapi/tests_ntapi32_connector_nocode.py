"""NTAPI32 — connecteur no-code (Zapier / Make) : triggers sur le flux
d'évènements + actions d'écriture.

Critère d'acceptation, joué de bout en bout contre les VRAIS endpoints (jamais
contre une copie du manifeste) :
  * un Zap déclenché par `facture.paid` reçoit la charge COMPLÈTE — le trigger
    du manifeste est rejoué tel qu'il est déclaré (chemin, `?type=`, curseur) ;
  * l'action « créer ticket » du manifeste aboutit — elle est rejouée telle
    qu'elle est déclarée (méthode, chemin, scope).

Vérifie en plus ce qui rend un connecteur honnête : aucun trigger promis que le
flux ne peut pas servir, et le filtre `?type=` n'élargit JAMAIS ce qu'une clé a
le droit de voir.
"""
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import Ticket

from . import connector_nocode, delivery
from .constants import (
    ALL_EVENTS, EVENT_FACTURE_PAID, EVENT_LEAD_CREATED, EVENT_TICKET_RESOLVED,
    PUBLIC_API_BASE, SCOPE_READ_EVENTS, SCOPE_READ_FACTURES, SCOPE_READ_LEADS,
    SCOPE_WRITE_TICKETS,
)
from .models import ApiKey


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


def _trigger(code):
    for entree in connector_nocode.triggers():
        if entree['evenement'] == code:
            return entree
    return None


def _action(cle):
    for entree in connector_nocode.actions():
        if entree['cle'] == cle:
            return entree
    return None


class Ntapi32ManifesteTests(SimpleTestCase):
    """Le manifeste est DÉRIVÉ — jamais une liste tenue à la main."""

    def test_un_trigger_par_evenement_servable_et_aucun_autre(self):
        from .events_feed import SCOPE_PAR_EVENEMENT

        codes = {entree['evenement'] for entree in connector_nocode.triggers()}
        self.assertEqual(codes, set(SCOPE_PAR_EVENEMENT))

    def test_les_evenements_non_servables_sont_declares_indisponibles(self):
        """`ticket.*` n'a aucun scope de lecture : promis nulle part, motivé ici."""
        indisponibles = {
            entree['evenement']
            for entree in connector_nocode.triggers_indisponibles()
        }
        self.assertIn(EVENT_TICKET_RESOLVED, indisponibles)
        servables = {e['evenement'] for e in connector_nocode.triggers()}
        # Partition stricte du vocabulaire : aucun évènement oublié, aucun
        # évènement compté deux fois.
        self.assertEqual(servables | indisponibles, set(ALL_EVENTS))
        self.assertEqual(servables & indisponibles, set())

    def test_chaque_trigger_polle_le_flux_avec_son_type_et_un_curseur(self):
        trigger = _trigger(EVENT_FACTURE_PAID)
        self.assertIsNotNone(trigger)
        polling = trigger['polling']
        self.assertEqual(polling['methode'], 'GET')
        self.assertEqual(polling['chemin'], f'{PUBLIC_API_BASE}events/')
        self.assertEqual(polling['parametres']['type'], EVENT_FACTURE_PAID)
        self.assertIn(connector_nocode.CURSEUR_PARAM, polling['parametres'])
        self.assertEqual(polling['curseur_reponse'], 'next_after')
        self.assertEqual(polling['champ_dedup'], 'event_id')
        # Le canal ET la famille : un trigger déclare les DEUX scopes, sinon
        # l'utilisateur crée une clé qui lit un flux vide.
        self.assertEqual(
            trigger['scopes_requis'], [SCOPE_READ_EVENTS, SCOPE_READ_FACTURES])

    def test_les_actions_couvrent_les_ecritures_documentees(self):
        from .docs import public_api_reference

        chemins_manifeste = {a['chemin'] for a in connector_nocode.actions()}
        chemins_docs = {
            e['chemin']
            for e in public_api_reference()['endpoints_ecriture']['liste']
        }
        self.assertEqual(chemins_manifeste, chemins_docs)
        # NTAPI18 — les deux écritures visées par la tâche sont bien dedans.
        self.assertIn(f'{PUBLIC_API_BASE}devis-write/', chemins_manifeste)
        self.assertIn(f'{PUBLIC_API_BASE}tickets-write/', chemins_manifeste)

    def test_rendu_json_est_serialisable(self):
        import json

        charge = json.loads(connector_nocode.rendu_json())
        self.assertEqual(charge['base_url'], PUBLIC_API_BASE)
        self.assertTrue(charge['triggers'])
        self.assertTrue(charge['actions'])


class Ntapi32TriggerFacturePaidTests(TestCase):
    """Le cœur du critère : un Zap sur `facture.paid` reçoit la charge complète."""

    def setUp(self):
        self.co = _company('ntapi32-trig', 'NTAPI32 trigger')
        _key, self.raw = ApiKey.issue(
            company=self.co, label='zap',
            scopes=[SCOPE_READ_EVENTS, SCOPE_READ_FACTURES])

    def _emettre(self, event, payload):
        with patch('apps.publicapi.tasks.deliver_webhook.delay'):
            delivery.dispatch_event(self.co.id, event, payload)

    def test_le_trigger_declare_renvoie_la_charge_complete(self):
        charge_emise = {
            'id': 4242, 'reference': 'FA-202609-0007',
            'montant_ttc': '61200.00', 'statut': 'payee',
        }
        self._emettre(EVENT_FACTURE_PAID, charge_emise)

        trigger = _trigger(EVENT_FACTURE_PAID)
        polling = trigger['polling']
        resp = _key_client(self.raw).get(
            polling['chemin'],
            {'type': polling['parametres']['type'],
             connector_nocode.CURSEUR_PARAM: 0})
        self.assertEqual(resp.status_code, 200, resp.content)
        corps = resp.json()
        resultats = corps[polling['collection']]
        self.assertEqual(len(resultats), 1)
        entree = resultats[0]
        self.assertEqual(entree['type'], EVENT_FACTURE_PAID)
        # « la charge complète » : le payload est rendu INTÉGRALEMENT, pas un
        # extrait d'identifiants.
        self.assertEqual(entree['payload'], charge_emise)
        self.assertTrue(entree[polling['champ_dedup']])
        self.assertEqual(corps[polling['curseur_reponse']], entree['sequence'])

    def test_le_curseur_rendu_evite_de_relire_le_meme_evenement(self):
        self._emettre(EVENT_FACTURE_PAID, {'id': 1})
        api = _key_client(self.raw)
        premier = api.get(f'{PUBLIC_API_BASE}events/',
                          {'type': EVENT_FACTURE_PAID, 'after': 0}).json()
        curseur = premier['next_after']
        second = api.get(f'{PUBLIC_API_BASE}events/',
                         {'type': EVENT_FACTURE_PAID, 'after': curseur}).json()
        self.assertEqual(second['results'], [])
        # Page vide : le client GARDE son curseur (jamais un 0 qui ferait tout
        # relire au prochain réveil du scénario).
        self.assertIsNone(second['next_after'])

    def test_le_filtre_type_ecarte_les_autres_evenements(self):
        self._emettre(EVENT_LEAD_CREATED, {'id': 1})
        self._emettre(EVENT_FACTURE_PAID, {'id': 2})
        _key, raw = ApiKey.issue(
            company=self.co, label='zap2',
            scopes=[SCOPE_READ_EVENTS, SCOPE_READ_FACTURES, SCOPE_READ_LEADS])
        corps = _key_client(raw).get(
            f'{PUBLIC_API_BASE}events/',
            {'type': EVENT_FACTURE_PAID, 'after': 0}).json()
        self.assertEqual([e['type'] for e in corps['results']],
                         [EVENT_FACTURE_PAID])

    def test_type_inconnu_renvoie_400(self):
        resp = _key_client(self.raw).get(
            f'{PUBLIC_API_BASE}events/', {'type': 'facture.payee'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error']['param'], 'type')

    def test_type_non_autorise_par_la_cle_ne_lelargit_jamais(self):
        """Demander un évènement dont la clé n'a pas le scope de lecture rend
        une page VIDE — jamais la donnée, jamais un indice sur son existence."""
        self._emettre(EVENT_LEAD_CREATED, {'id': 9, 'nom': 'Secret'})
        resp = _key_client(self.raw).get(
            f'{PUBLIC_API_BASE}events/',
            {'type': EVENT_LEAD_CREATED, 'after': 0})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['results'], [])


class Ntapi32ActionCreerTicketTests(TestCase):
    """Second volet du critère : l'action « créer ticket » aboutit."""

    def setUp(self):
        self.co = _company('ntapi32-act', 'NTAPI32 action')
        self.client_sav = Client.objects.create(
            company=self.co, nom='Client Zap')
        _key, self.raw = ApiKey.issue(
            company=self.co, label='zap-write',
            scopes=[SCOPE_WRITE_TICKETS])

    def test_laction_declaree_cree_bien_un_ticket(self):
        action = _action('post__tickets_write')
        self.assertIsNotNone(action)
        self.assertEqual(action['methode'], 'POST')
        self.assertEqual(action['scope_requis'], SCOPE_WRITE_TICKETS)
        resp = _key_client(self.raw).post(
            action['chemin'],
            {'client': self.client_sav.id,
             'description': 'Ouvert par un scénario no-code'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        ticket = Ticket.objects.get(pk=resp.json()['id'])
        self.assertEqual(ticket.company_id, self.co.id)
        self.assertEqual(ticket.client_id, self.client_sav.id)

    def test_lentete_didempotence_declaree_est_celle_qui_fonctionne(self):
        """Le plateau no-code retente une étape : l'en-tête que le manifeste
        annonce doit RÉELLEMENT dédupliquer, sinon chaque reprise crée un
        doublon chez le client."""
        action = _action('post__tickets_write')
        self.assertEqual(action['entete_idempotence'], 'Idempotency-Key')
        api = _key_client(self.raw)
        corps = {'client': self.client_sav.id, 'description': 'Reprise'}
        premier = api.post(action['chemin'], corps, format='json',
                           HTTP_IDEMPOTENCY_KEY='zap-step-1')
        second = api.post(action['chemin'], corps, format='json',
                          HTTP_IDEMPOTENCY_KEY='zap-step-1')
        self.assertEqual(premier.status_code, 201)
        self.assertEqual(second.json()['id'], premier.json()['id'])
        self.assertEqual(Ticket.objects.count(), 1)
