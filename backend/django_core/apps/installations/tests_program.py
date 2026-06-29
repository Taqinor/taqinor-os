"""
FG291 — Programme / Projet multi-chantiers.

Couvre :
  * la création d'un ``Projet`` (référence anti-collision posée côté serveur,
    société + créateur côté serveur, statut PROPRE jamais lu du corps) ;
  * le regroupement chantiers + devis + tickets sous un même programme via les
    actions `attacher_chantier` / `attacher_devis` / `attacher_ticket`
    (idempotentes) et les payloads imbriqués ;
  * le scope société (isolation + refus d'un objet cross-company).

Run :
    python manage.py test apps.installations.tests_program -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.sav.models import Ticket
from apps.installations.models import (
    Projet, ProjetChantier, ProjetDevis, ProjetTicket,
)
from apps.installations.services import create_installation_from_devis

User = get_user_model()
_seq = itertools.count(1)

BASE = '/api/django/installations'


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    slug = slug or f'prg-co-{n}'
    nom = nom or f'Prg Co {n}'
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Ferme', prenom='Client',
        email=f'prg-{company.id}-{n}@example.invalid')


def make_chantier(company, user, client=None, type_installation='agricole'):
    n = next(_seq)
    client = client or make_client(company)
    lead = Lead.objects.create(
        company=company, nom='Ferme', prenom='Client', stage='SIGNED',
        type_installation=type_installation)
    devis = Devis.objects.create(
        company=company, reference=f'DEV-PRG-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation=type_installation)
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst, devis


def make_ticket(company, client):
    n = next(_seq)
    return Ticket.objects.create(
        company=company, reference=f'TKT-PRG-{company.id}-{n}', client=client,
        description='Panne onduleur')


# ── Création du programme ────────────────────────────────────────────────────

class TestFG291ProjetCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username=f'prg-{next(_seq)}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = auth(self.user)
        self.client_obj = make_client(self.company)

    def test_create_sets_company_reference_and_creator_server_side(self):
        """FG291 — le programme porte la société du user, une référence générée
        côté serveur (jamais count()+1) et le créateur, même si le corps tente
        d'imposer une autre société/référence."""
        other = make_company()
        r = self.api.post(f'{BASE}/programmes/', {
            'nom': 'Ferme 4 forages',
            'client': self.client_obj.id,
            'site_ville': 'Berrechid',
            'reference': 'HACK-1',     # ignoré (read-only)
            'company': other.id,        # ignoré côté serveur
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        projet = Projet.objects.get(id=r.data['id'])
        self.assertEqual(projet.company_id, self.company.id)
        self.assertEqual(projet.created_by_id, self.user.id)
        self.assertTrue(projet.reference.startswith('PRG-'))
        self.assertNotEqual(projet.reference, 'HACK-1')
        # Statut PROPRE par défaut (jamais l'entonnoir commercial).
        self.assertEqual(projet.statut, Projet.Statut.BROUILLON)

    def test_reference_increments_per_company(self):
        """FG291 — deux programmes successifs ont des références distinctes."""
        r1 = self.api.post(f'{BASE}/programmes/',
                           {'nom': 'P1'}, format='json')
        r2 = self.api.post(f'{BASE}/programmes/',
                           {'nom': 'P2'}, format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        self.assertEqual(r2.status_code, 201, r2.data)
        self.assertNotEqual(r1.data['reference'], r2.data['reference'])

    def test_cross_company_client_rejected(self):
        """FG291 — impossible de rattacher un client d'une autre société."""
        other = make_company()
        client_b = make_client(other)
        r = self.api.post(f'{BASE}/programmes/', {
            'nom': 'Intrus', 'client': client_b.id,
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_company_isolation(self):
        """FG291 — la société B ne voit pas les programmes de A."""
        Projet.objects.create(
            company=self.company, reference='PRG-X-1', nom='Secret A')
        company_b = make_company()
        user_b = User.objects.create_user(
            username=f'prgb-{next(_seq)}', password='x',
            role_legacy='responsable', company=company_b)
        r = auth(user_b).get(f'{BASE}/programmes/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 0)

    def test_filter_by_statut(self):
        """FG291 — la liste se filtre par statut PROPRE du programme."""
        Projet.objects.create(
            company=self.company, reference='PRG-A-1', nom='Actif',
            statut=Projet.Statut.ACTIF)
        Projet.objects.create(
            company=self.company, reference='PRG-B-1', nom='Brouillon',
            statut=Projet.Statut.BROUILLON)
        r = self.api.get(f'{BASE}/programmes/', {'statut': 'actif'})
        self.assertEqual(r.status_code, 200)
        noms = [p['nom'] for p in r.data['results']]
        self.assertIn('Actif', noms)
        self.assertNotIn('Brouillon', noms)


# ── Regroupement chantiers + devis + tickets ─────────────────────────────────

class TestFG291Grouping(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username=f'prgg-{next(_seq)}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = auth(self.user)
        self.client_obj = make_client(self.company)
        self.projet = Projet.objects.create(
            company=self.company, reference='PRG-G-1', nom='Ferme 4 forages',
            client=self.client_obj)

    def test_attacher_chantier_devis_ticket(self):
        """FG291 — un même programme regroupe N chantiers + leurs devis + leurs
        tickets (ferme à 4 forages)."""
        inst1, devis1 = make_chantier(self.company, self.user, self.client_obj)
        inst2, devis2 = make_chantier(self.company, self.user, self.client_obj)
        ticket = make_ticket(self.company, self.client_obj)

        r = self.api.post(
            f'{BASE}/programmes/{self.projet.id}/attacher_chantier/',
            {'installation': inst1.id, 'libelle': 'Forage 1'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        r = self.api.post(
            f'{BASE}/programmes/{self.projet.id}/attacher_chantier/',
            {'installation': inst2.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        r = self.api.post(
            f'{BASE}/programmes/{self.projet.id}/attacher_devis/',
            {'devis': devis1.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        r = self.api.post(
            f'{BASE}/programmes/{self.projet.id}/attacher_ticket/',
            {'ticket': ticket.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)

        self.assertEqual(
            ProjetChantier.objects.filter(projet=self.projet).count(), 2)
        self.assertEqual(
            ProjetDevis.objects.filter(projet=self.projet).count(), 1)
        self.assertEqual(
            ProjetTicket.objects.filter(projet=self.projet).count(), 1)
        # Les liaisons portent la société côté serveur.
        link = ProjetChantier.objects.filter(projet=self.projet).first()
        self.assertEqual(link.company_id, self.company.id)
        # Le statut du devis/ticket n'est PAS touché par le rattachement.
        devis1.refresh_from_db()
        ticket.refresh_from_db()
        self.assertEqual(devis1.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(ticket.statut, Ticket.Statut.NOUVEAU)

    def test_nested_payload_exposes_groups(self):
        """FG291 — la fiche du programme imbrique chantiers/devis/tickets."""
        inst, devis = make_chantier(self.company, self.user, self.client_obj)
        ticket = make_ticket(self.company, self.client_obj)
        ProjetChantier.objects.create(
            company=self.company, projet=self.projet, installation=inst)
        ProjetDevis.objects.create(
            company=self.company, projet=self.projet, devis=devis)
        ProjetTicket.objects.create(
            company=self.company, projet=self.projet, ticket=ticket)
        r = self.api.get(f'{BASE}/programmes/{self.projet.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['nb_chantiers'], 1)
        self.assertEqual(len(r.data['chantiers']), 1)
        self.assertEqual(len(r.data['devis']), 1)
        self.assertEqual(len(r.data['tickets']), 1)
        self.assertEqual(
            r.data['chantiers'][0]['installation_reference'], inst.reference)

    def test_attacher_chantier_is_idempotent(self):
        """FG291 — rattacher deux fois le même chantier ne crée pas de doublon."""
        inst, _ = make_chantier(self.company, self.user, self.client_obj)
        r1 = self.api.post(
            f'{BASE}/programmes/{self.projet.id}/attacher_chantier/',
            {'installation': inst.id}, format='json')
        r2 = self.api.post(
            f'{BASE}/programmes/{self.projet.id}/attacher_chantier/',
            {'installation': inst.id}, format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(
            ProjetChantier.objects.filter(projet=self.projet).count(), 1)

    def test_attacher_chantier_requires_field(self):
        """FG291 — l'action exige le champ `installation`."""
        r = self.api.post(
            f'{BASE}/programmes/{self.projet.id}/attacher_chantier/', {},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_attacher_rejects_cross_company_chantier(self):
        """FG291 — on ne peut pas rattacher le chantier d'une autre société."""
        company_b = make_company()
        user_b = User.objects.create_user(
            username=f'prggb-{next(_seq)}', password='x',
            role_legacy='responsable', company=company_b)
        inst_b, _ = make_chantier(company_b, user_b)
        r = self.api.post(
            f'{BASE}/programmes/{self.projet.id}/attacher_chantier/',
            {'installation': inst_b.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_attacher_rejects_cross_company_ticket(self):
        """FG291 — on ne peut pas rattacher le ticket d'une autre société."""
        company_b = make_company()
        client_b = make_client(company_b)
        ticket_b = make_ticket(company_b, client_b)
        r = self.api.post(
            f'{BASE}/programmes/{self.projet.id}/attacher_ticket/',
            {'ticket': ticket_b.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)


# ── Vues de liaison (CRUD direct) ────────────────────────────────────────────

class TestFG291LinkViewSets(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username=f'prgl-{next(_seq)}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = auth(self.user)
        self.client_obj = make_client(self.company)
        self.projet = Projet.objects.create(
            company=self.company, reference='PRG-L-1', nom='Toiture tranches',
            client=self.client_obj)

    def test_create_link_sets_company_server_side(self):
        """FG291 — la table de liaison pose la société côté serveur, jamais du
        corps, et filtre par programme."""
        inst, _ = make_chantier(self.company, self.user, self.client_obj)
        other = make_company()
        r = self.api.post(f'{BASE}/programme-chantiers/', {
            'projet': self.projet.id, 'installation': inst.id,
            'libelle': 'Tranche A', 'company': other.id,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        link = ProjetChantier.objects.get(id=r.data['id'])
        self.assertEqual(link.company_id, self.company.id)
        r = self.api.get(f'{BASE}/programme-chantiers/',
                         {'projet': self.projet.id})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 1)

    def test_link_company_isolation(self):
        """FG291 — la société B ne voit pas les liaisons de A."""
        inst, _ = make_chantier(self.company, self.user, self.client_obj)
        ProjetChantier.objects.create(
            company=self.company, projet=self.projet, installation=inst)
        company_b = make_company()
        user_b = User.objects.create_user(
            username=f'prglb-{next(_seq)}', password='x',
            role_legacy='responsable', company=company_b)
        r = auth(user_b).get(f'{BASE}/programme-chantiers/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 0)
