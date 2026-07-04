"""
XFSM4 — Priorité sur l'Intervention (urgence/normale) pilotant le dispatch.

Couvre :
  * champ `priorite` (défaut NORMALE) éditable + filtre `?priorite=` ;
  * héritage depuis le ticket SAV lié quand `ticket` est fourni sans
    `priorite` explicite (mapping BASSE→NORMALE, Intervention n'a pas BASSE) ;
  * tri par priorité puis date dans la liste (défaut) et le calendrier FG68 ;
  * ne touche ni le statut d'intervention ni STAGES.py.

Run :
    python manage.py test apps.installations.tests_xfsm4_priorite -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.installations.models import Intervention
from apps.installations.services import create_installation_from_devis
from apps.sav.models import Ticket

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xfsm4-co-{n}', defaults={'nom': nom or f'XFSM4 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xfsm4-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_chantier(company, user):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'xfsm4-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-XFSM4-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel')
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst, client


class TestPrioriteChampEtFiltre(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst, self.client_obj = make_chantier(self.company, self.user)

    def test_defaut_normale(self):
        interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user)
        self.assertEqual(interv.priorite, Intervention.Priorite.NORMALE)

    def test_creation_priorite_urgente_explicite(self):
        resp = self.api.post(f'{BASE}/interventions/', {
            'installation': self.inst.id, 'type_intervention': 'depannage',
            'priorite': 'urgente',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['priorite'], 'urgente')

    def test_filtre_priorite(self):
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user,
            priorite=Intervention.Priorite.URGENTE)
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='controle', created_by=self.user,
            priorite=Intervention.Priorite.NORMALE)
        resp = self.api.get(f'{BASE}/interventions/?priorite=urgente')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['priorite'], 'urgente')

    def test_tri_par_defaut_priorite_puis_date(self):
        normale = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user,
            priorite=Intervention.Priorite.NORMALE, date_prevue='2026-08-01')
        urgente = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='depannage', created_by=self.user,
            priorite=Intervention.Priorite.URGENTE, date_prevue='2026-07-20')
        resp = self.api.get(f'{BASE}/interventions/')
        self.assertEqual(resp.status_code, 200, resp.content)
        ids = [row['id'] for row in resp.data]
        self.assertLess(ids.index(urgente.id), ids.index(normale.id))


class TestPrioriteHeritageTicket(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst, self.client_obj = make_chantier(self.company, self.user)

    def test_heritage_priorite_haute_du_ticket(self):
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XFSM4-1',
            client=self.client_obj, installation=self.inst,
            priorite='haute')
        resp = self.api.post(f'{BASE}/interventions/', {
            'installation': self.inst.id, 'type_intervention': 'depannage',
            'ticket': ticket.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['priorite'], 'haute')

    def test_heritage_priorite_basse_replie_sur_normale(self):
        # sav.Ticket a une valeur BASSE que Intervention n'a pas : repli.
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XFSM4-2',
            client=self.client_obj, installation=self.inst,
            priorite='basse')
        resp = self.api.post(f'{BASE}/interventions/', {
            'installation': self.inst.id, 'type_intervention': 'depannage',
            'ticket': ticket.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['priorite'], 'normale')

    def test_priorite_explicite_prevaut_sur_heritage_ticket(self):
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XFSM4-3',
            client=self.client_obj, installation=self.inst,
            priorite='urgente')
        resp = self.api.post(f'{BASE}/interventions/', {
            'installation': self.inst.id, 'type_intervention': 'depannage',
            'ticket': ticket.id, 'priorite': 'normale',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['priorite'], 'normale')

    def test_statut_intervention_non_touche(self):
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XFSM4-4',
            client=self.client_obj, installation=self.inst,
            priorite='urgente')
        resp = self.api.post(f'{BASE}/interventions/', {
            'installation': self.inst.id, 'type_intervention': 'depannage',
            'ticket': ticket.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['statut'], Intervention.Statut.A_PREPARER)


class TestCalendrierTriPriorite(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst, _ = make_chantier(self.company, self.user)

    def test_calendrier_trie_par_priorite_puis_date(self):
        normale = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user, technicien=self.user,
            priorite=Intervention.Priorite.NORMALE, date_prevue='2026-08-01')
        urgente = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='depannage', created_by=self.user,
            technicien=self.user,
            priorite=Intervention.Priorite.URGENTE, date_prevue='2026-08-02')
        resp = self.api.get(f'{BASE}/interventions/calendrier/')
        self.assertEqual(resp.status_code, 200, resp.content)
        row = next(r for r in resp.data if r['technicien']['id'] == self.user.id)
        ids = [iv['id'] for iv in row['interventions']]
        self.assertLess(ids.index(urgente.id), ids.index(normale.id))
