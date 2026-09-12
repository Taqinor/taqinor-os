"""NTAPI18 — écriture publique étendue : devis brouillon + ticket SAV.

Critère d'acceptation, dans les deux sens :
  * une clé `devis:write` crée un devis BROUILLON rattaché à un lead existant ;
  * une clé read-only → 403.

Vérifie en plus les garanties structurantes : société forcée depuis la clé
(aucune écriture cross-tenant possible), `Idempotency-Key` réutilisé tel quel
(un rejeu ne crée pas un second devis), et RÈGLE #4 — l'API ne change JAMAIS un
statut aval, le devis reste `brouillon`.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.sav.models import Ticket
from apps.ventes.models import Devis

from .constants import (
    SCOPE_READ_LEADS, SCOPE_WRITE_DEVIS, SCOPE_WRITE_TICKETS,
)
from .models import ApiKey


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


class Ntapi18DevisWriteTests(TestCase):
    def setUp(self):
        self.co = _company('ntapi18', 'NTAPI18')
        self.lead = Lead.objects.create(
            company=self.co, nom='Client API',
            email='client.api@exemple.test')
        _key, self.raw = ApiKey.issue(
            company=self.co, label='devis', scopes=[SCOPE_WRITE_DEVIS])
        _ro, self.raw_ro = ApiKey.issue(
            company=self.co, label='ro', scopes=[SCOPE_READ_LEADS])

    # ── Le cœur du critère ────────────────────────────────────────────────
    def test_cle_devis_write_cree_un_brouillon_rattache_au_lead(self):
        resp = _key_client(self.raw).post(
            '/api/public/v1/devis-write/', {'lead': self.lead.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        corps = resp.json()
        devis = Devis.objects.get(pk=corps['id'])
        self.assertEqual(devis.company_id, self.co.id)
        self.assertEqual(devis.lead_id, self.lead.id)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        # Le client est résolu SERVEUR depuis le lead, jamais fourni par
        # l'appelant ni dupliqué.
        self.assertIsNotNone(devis.client_id)

    def test_cle_read_only_est_refusee(self):
        resp = _key_client(self.raw_ro).post(
            '/api/public/v1/devis-write/', {'lead': self.lead.id},
            format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Devis.objects.count(), 0)

    # ── Règle #4 et garde-fous ────────────────────────────────────────────
    def test_le_devis_reste_brouillon_sans_ligne(self):
        resp = _key_client(self.raw).post(
            '/api/public/v1/devis-write/',
            {'lead': self.lead.id, 'statut': 'accepte', 'montant_ttc': 50000},
            format='json')
        devis = Devis.objects.get(pk=resp.json()['id'])
        # Un `statut` envoyé dans le corps est IGNORÉ : l'API ne change aucun
        # statut aval (règle #4).
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertEqual(devis.lignes.count(), 0)

    def test_lead_obligatoire(self):
        resp = _key_client(self.raw).post(
            '/api/public/v1/devis-write/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error']['param'], 'lead')

    def test_lead_dune_autre_societe_renvoie_404(self):
        autre = _company('ntapi18-autre', 'NTAPI18 autre')
        lead_autre = Lead.objects.create(company=autre, nom='Pas à moi')
        resp = _key_client(self.raw).post(
            '/api/public/v1/devis-write/', {'lead': lead_autre.id},
            format='json')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(Devis.objects.count(), 0)

    def test_idempotency_key_ne_cree_pas_un_second_devis(self):
        api = _key_client(self.raw)
        corps = {'lead': self.lead.id}
        premier = api.post('/api/public/v1/devis-write/', corps, format='json',
                           HTTP_IDEMPOTENCY_KEY='cle-1')
        second = api.post('/api/public/v1/devis-write/', corps, format='json',
                          HTTP_IDEMPOTENCY_KEY='cle-1')
        self.assertEqual(premier.status_code, 201)
        self.assertEqual(second.json()['id'], premier.json()['id'])
        self.assertEqual(Devis.objects.count(), 1)

    def test_idempotency_key_rejouee_avec_un_autre_corps_est_un_conflit(self):
        autre_lead = Lead.objects.create(company=self.co, nom='Autre lead')
        api = _key_client(self.raw)
        api.post('/api/public/v1/devis-write/', {'lead': self.lead.id},
                 format='json', HTTP_IDEMPOTENCY_KEY='cle-2')
        conflit = api.post('/api/public/v1/devis-write/',
                           {'lead': autre_lead.id}, format='json',
                           HTTP_IDEMPOTENCY_KEY='cle-2')
        self.assertEqual(conflit.status_code, 409)
        self.assertEqual(conflit.json()['error']['code'],
                         'idempotency_conflict')


class Ntapi18TicketWriteTests(TestCase):
    def setUp(self):
        self.co = _company('ntapi18-sav', 'NTAPI18 SAV')
        self.client_sav = Client.objects.create(
            company=self.co, nom='Client SAV')
        _key, self.raw = ApiKey.issue(
            company=self.co, label='tickets', scopes=[SCOPE_WRITE_TICKETS])
        _ro, self.raw_ro = ApiKey.issue(
            company=self.co, label='ro', scopes=[SCOPE_READ_LEADS])

    def test_cle_tickets_write_ouvre_un_ticket(self):
        resp = _key_client(self.raw).post(
            '/api/public/v1/tickets-write/',
            {'client': self.client_sav.id, 'description': 'Onduleur en défaut'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        ticket = Ticket.objects.get(pk=resp.json()['id'])
        self.assertEqual(ticket.company_id, self.co.id)
        self.assertEqual(ticket.client_id, self.client_sav.id)
        self.assertEqual(ticket.description, 'Onduleur en défaut')
        self.assertTrue(ticket.reference)

    def test_cle_read_only_est_refusee(self):
        resp = _key_client(self.raw_ro).post(
            '/api/public/v1/tickets-write/',
            {'client': self.client_sav.id, 'description': 'x'}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_description_obligatoire(self):
        resp = _key_client(self.raw).post(
            '/api/public/v1/tickets-write/',
            {'client': self.client_sav.id}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error']['param'], 'description')

    def test_client_dune_autre_societe_renvoie_404(self):
        autre = _company('ntapi18-sav-autre', 'NTAPI18 SAV autre')
        client_autre = Client.objects.create(company=autre, nom='Pas à moi')
        resp = _key_client(self.raw).post(
            '/api/public/v1/tickets-write/',
            {'client': client_autre.id, 'description': 'x'}, format='json')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_client_inconnu_renvoie_404(self):
        resp = _key_client(self.raw).post(
            '/api/public/v1/tickets-write/',
            {'client': 999999, 'description': 'x'}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_idempotency_key_ne_cree_pas_un_second_ticket(self):
        api = _key_client(self.raw)
        corps = {'client': self.client_sav.id, 'description': 'Panne'}
        premier = api.post('/api/public/v1/tickets-write/', corps,
                           format='json', HTTP_IDEMPOTENCY_KEY='t-1')
        second = api.post('/api/public/v1/tickets-write/', corps,
                          format='json', HTTP_IDEMPOTENCY_KEY='t-1')
        self.assertEqual(premier.status_code, 201)
        self.assertEqual(second.json()['id'], premier.json()['id'])
        self.assertEqual(Ticket.objects.count(), 1)


class Ntapi18ScopesTests(TestCase):
    """Les deux nouveaux scopes sont bien déclarés (garde NTAPI42)."""

    def test_scopes_declares_dans_le_catalogue(self):
        from .constants import ALL_SCOPES

        self.assertIn(SCOPE_WRITE_DEVIS, ALL_SCOPES)
        self.assertIn(SCOPE_WRITE_TICKETS, ALL_SCOPES)

    def test_une_cle_devis_write_ne_donne_pas_tickets_write(self):
        co = _company('ntapi18-sc', 'NTAPI18 scopes')
        _key, raw = ApiKey.issue(
            company=co, label='d', scopes=[SCOPE_WRITE_DEVIS])
        client_sav = Client.objects.create(company=co, nom='C')
        resp = _key_client(raw).post(
            '/api/public/v1/tickets-write/',
            {'client': client_sav.id, 'description': 'x'}, format='json')
        self.assertEqual(resp.status_code, 403)
