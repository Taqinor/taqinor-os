"""XCTR3 — Droits inclus (entitlements) du contrat de maintenance.

Couvre :
  * compteurs corrects (bornes d'année civile) ;
  * NULL = jamais d'avertissement (illimité) ;
  * consommation/quota atteint → avertissement non bloquant à la création ;
  * multi-tenant : un ticket d'une autre société n'entre jamais dans le compte.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xctr3 -v 2
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import ContratMaintenance, Ticket, TicketActivity
from apps.sav.selectors import droits_restants

User = get_user_model()


def make_company(slug='sav-xctr3', nom='Sav Co XCTR3'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XCTR3DroitsRestantsTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other_company = make_company(slug='sav-xctr3-other', nom='Autre Co')
        self.admin = User.objects.create_user(
            username='xctr3_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='XCTR3',
            email='xctr3-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XCTR3', client=self.client_obj)
        self.contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst, date_debut=date(2026, 1, 1), actif=True,
            visites_incluses_an=2, deplacements_inclus_an=1)

    def _ticket(self, type_, ref, d=None, company=None, installation=None):
        return Ticket.objects.create(
            company=company or self.company, reference=ref,
            client=self.client_obj, installation=installation or self.inst,
            type=type_, date_ouverture=d or date(2026, 3, 1),
            created_by=self.admin)

    def test_compteurs_bornes_annee_civile(self):
        self._ticket(Ticket.Type.PREVENTIF, 'SAV-XCTR3-1', date(2026, 1, 15))
        self._ticket(Ticket.Type.PREVENTIF, 'SAV-XCTR3-2', date(2025, 12, 31))
        droits = droits_restants(self.contrat, 2026)
        self.assertEqual(droits['visites_consommees'], 1)
        self.assertEqual(droits['visites_restantes'], 1)

    def test_null_illimite_jamais_avertissement(self):
        contrat_illimite = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst, date_debut=date(2026, 1, 1), actif=True)
        droits = droits_restants(contrat_illimite, 2026)
        self.assertIsNone(droits['visites_restantes'])
        self.assertIsNone(droits['deplacements_restants'])

    def test_multi_tenant_isole(self):
        self._ticket(Ticket.Type.PREVENTIF, 'SAV-XCTR3-OTHER', date(2026, 2, 1),
                     company=self.other_company)
        droits = droits_restants(self.contrat, 2026)
        # Aucun ticket de other_company ne doit compter (autre société).
        self.assertEqual(droits['visites_consommees'], 0)

    def test_quota_atteint_avertissement_non_bloquant(self):
        # Consomme les 2 visites incluses.
        self._ticket(Ticket.Type.PREVENTIF, 'SAV-XCTR3-Q1', date(2026, 1, 1))
        self._ticket(Ticket.Type.PREVENTIF, 'SAV-XCTR3-Q2', date(2026, 2, 1))
        api = auth(self.admin)
        resp = api.post('/api/django/sav/tickets/', {
            'client': self.client_obj.pk, 'installation': self.inst.pk,
            'type': 'preventif', 'date_ouverture': '2026-03-01',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        notes = TicketActivity.objects.filter(
            ticket_id=resp.data['id'], kind=TicketActivity.Kind.NOTE)
        self.assertTrue(
            any('quota' in (n.body or '').lower() for n in notes))
