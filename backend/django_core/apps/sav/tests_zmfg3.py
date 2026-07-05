"""ZMFG3 — Vue calendrier des tickets SAV (préventifs + correctifs planifiés).

Couvre l'action ``replanifier`` (un seul ticket, n'importe quel type, pose
``date_tournee``) qui alimente le glisser-déposer de la vue Calendrier de
``TicketsPage.jsx``. Distinct de FG88 (tournée groupée, PREVENTIF only) :
ici on replanifie EXACTEMENT le ticket ciblé, quel que soit son type.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_zmfg3 -v 2
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Ticket
from authentication.models import Company

User = get_user_model()


def _ticket(company, client, installation, ref, **kw):
    kw.setdefault('statut', Ticket.Statut.NOUVEAU)
    kw.setdefault('type', Ticket.Type.CORRECTIF)
    kw.setdefault('date_ouverture', date.today())
    return Ticket.objects.create(
        company=company, client=client, installation=installation,
        reference=ref, **kw)


class ZMFG3ReplanifierTicketTest(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='zmfg3-co', defaults={'nom': 'ZMFG3 Co'})[0]
        self.user = User.objects.create_user(
            username='zmfg3_u', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(company=self.company, nom='C')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT', client=self.client_obj)

    def _url(self, ticket_id):
        return f'/api/django/sav/tickets/{ticket_id}/replanifier/'

    def test_replanifier_sets_date_tournee_on_correctif(self):
        # Un ticket CORRECTIF (jamais autorisé dans la tournée FG88 groupée)
        # doit pouvoir être replanifié individuellement depuis le calendrier.
        t = _ticket(self.company, self.client_obj, self.inst, 'SAV-COR',
                    type=Ticket.Type.CORRECTIF)
        when = (date.today() + timedelta(days=5)).isoformat()
        r = self.api.post(
            self._url(t.id), {'date_tournee': when}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        t.refresh_from_db()
        self.assertEqual(t.date_tournee.isoformat(), when)

    def test_replanifier_sets_date_tournee_on_preventif(self):
        t = _ticket(self.company, self.client_obj, self.inst, 'SAV-PRE',
                    type=Ticket.Type.PREVENTIF)
        when = (date.today() + timedelta(days=2)).isoformat()
        r = self.api.post(
            self._url(t.id), {'date_tournee': when}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        t.refresh_from_db()
        self.assertEqual(t.date_tournee.isoformat(), when)

    def test_replanifier_does_not_change_statut_or_technicien(self):
        # Contrairement à FG88 planifier_tournee, cette action ne force
        # aucune transition de statut ni d'affectation.
        t = _ticket(self.company, self.client_obj, self.inst, 'SAV-1',
                    statut=Ticket.Statut.EN_COURS)
        when = date.today().isoformat()
        r = self.api.post(
            self._url(t.id), {'date_tournee': when}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        t.refresh_from_db()
        self.assertEqual(t.statut, Ticket.Statut.EN_COURS)
        self.assertIsNone(t.technicien_responsable_id)

    def test_invalid_date_returns_400(self):
        t = _ticket(self.company, self.client_obj, self.inst, 'SAV-1')
        r = self.api.post(
            self._url(t.id), {'date_tournee': 'pas-une-date'}, format='json')
        self.assertEqual(r.status_code, 400)
        t.refresh_from_db()
        self.assertIsNone(t.date_tournee)

    def test_company_isolation(self):
        # Un ticket d'une autre société est introuvable (404), jamais 200.
        other = Company.objects.get_or_create(
            slug='zmfg3-other', defaults={'nom': 'Other'})[0]
        other_client = Client.objects.create(company=other, nom='O')
        other_inst = Installation.objects.create(
            company=other, reference='CHT-O', client=other_client)
        foreign = _ticket(other, other_client, other_inst, 'SAV-OTHER')
        r = self.api.post(
            self._url(foreign.id),
            {'date_tournee': date.today().isoformat()}, format='json')
        self.assertEqual(r.status_code, 404)
