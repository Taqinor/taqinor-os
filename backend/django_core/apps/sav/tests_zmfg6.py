"""ZMFG6 — Feuilles de maintenance (worksheets) remplies par le technicien.

Couvre :
  * OFF (défaut) → l'action `worksheet/` répond 404 (comportement inchangé) ;
  * ON → création idempotente depuis un modèle, mise à jour des valeurs,
    complétion bloquée tant qu'un champ requis manque, complétion OK une fois
    tous les champs requis renseignés ;
  * migration additive (défaut OFF).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_zmfg6 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import (
    SavSlaSettings, Ticket, TicketWorksheet, WorksheetMaintenanceModele,
)

User = get_user_model()


def make_company(slug='sav-zmfg6', nom='Sav Co ZMFG6'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ZMFG6WorksheetTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='zmfg6_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ZMFG6',
            email='zmfg6-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ZMFG6', client=self.client_obj)
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-ZMFG6-1',
            client=self.client_obj, installation=self.inst,
            created_by=self.admin)
        self.modele = WorksheetMaintenanceModele.objects.create(
            company=self.company, nom='Contrôle onduleur',
            champs=[
                {'cle': 'pression_bar', 'libelle': 'Pression (bar)',
                 'type': 'nombre', 'requis': True},
                {'cle': 'nettoye', 'libelle': 'Nettoyé', 'type': 'case',
                 'requis': False},
            ])

    def _activer_toggle(self):
        sla = SavSlaSettings.get(self.company)
        sla.worksheets_maintenance_actifs = True
        sla.save(update_fields=['worksheets_maintenance_actifs'])

    def test_off_by_default_returns_404(self):
        resp = self.api.get(f'/api/django/sav/tickets/{self.ticket.pk}/worksheet/')
        self.assertEqual(resp.status_code, 404)

    def test_on_creates_worksheet_idempotently(self):
        self._activer_toggle()
        resp1 = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/worksheet/',
            {'modele_id': self.modele.pk}, format='json')
        self.assertEqual(resp1.status_code, 201)
        self.assertEqual(TicketWorksheet.objects.count(), 1)

        resp2 = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/worksheet/',
            {'modele_id': self.modele.pk}, format='json')
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(TicketWorksheet.objects.count(), 1)

    def test_required_field_missing_blocks_completion(self):
        self._activer_toggle()
        self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/worksheet/',
            {'modele_id': self.modele.pk}, format='json')
        resp = self.api.patch(
            f'/api/django/sav/tickets/{self.ticket.pk}/worksheet/',
            {'complete': True}, format='json')
        self.assertEqual(resp.status_code, 400)
        worksheet = TicketWorksheet.objects.get(ticket=self.ticket)
        self.assertFalse(worksheet.complete)

    def test_filling_required_field_allows_completion(self):
        self._activer_toggle()
        self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/worksheet/',
            {'modele_id': self.modele.pk}, format='json')
        resp = self.api.patch(
            f'/api/django/sav/tickets/{self.ticket.pk}/worksheet/',
            {'valeurs': {'pression_bar': 3.2}, 'complete': True}, format='json')
        self.assertEqual(resp.status_code, 200)
        worksheet = TicketWorksheet.objects.get(ticket=self.ticket)
        self.assertTrue(worksheet.complete)
        self.assertEqual(worksheet.complete_par, self.admin)
        self.assertIsNotNone(worksheet.complete_le)

    def test_values_are_rendered_in_pdf(self):
        self._activer_toggle()
        self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/worksheet/',
            {'modele_id': self.modele.pk}, format='json')
        self.api.patch(
            f'/api/django/sav/tickets/{self.ticket.pk}/worksheet/',
            {'valeurs': {'pression_bar': 3.2}}, format='json')

        from apps.sav.pdf import _worksheet_payload
        self.ticket.refresh_from_db()
        payload = _worksheet_payload(self.ticket)
        self.assertIsNotNone(payload)
        pression = next(
            c for c in payload['champs'] if c['libelle'] == 'Pression (bar)')
        self.assertEqual(pression['valeur'], 3.2)

    def test_no_worksheet_omits_pdf_section(self):
        from apps.sav.pdf import _worksheet_payload
        self.assertIsNone(_worksheet_payload(self.ticket))
