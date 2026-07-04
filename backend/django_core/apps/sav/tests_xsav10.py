"""XSAV10 — Enquête de satisfaction (CSAT) à la clôture du ticket.

Couvre :
  * POST public validé par token, ticket résolu/clôturé → 201 ;
  * ticket pas encore résolu → 400, aucune ligne créée ;
  * doublon (2e réponse pour le même ticket) → 409 refusé ;
  * token inconnu → 404 sans fuite ;
  * aucune donnée interne (chatter, coût, infos client) sur la page publique ;
  * agrégat CSAT par technicien/mois correct.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav10 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Ticket, TicketSatisfaction
from apps.sav.selectors import csat_par_technicien

User = get_user_model()


def make_company(slug='sav-xsav10', nom='Sav Co XSAV10'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class XSAV10SatisfactionTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='xsav10_admin', password='x', role_legacy='admin',
            company=self.company)
        self.tech = User.objects.create_user(
            username='xsav10_tech', password='x', role_legacy='normal',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav10-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV10', client=self.client_obj)
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XSAV10-1',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.RESOLU,
            technicien_responsable=self.tech, cout=999, created_by=self.user)
        self.ticket.ensure_share_token()
        self.public_api = APIClient()

    def _url(self, token=None):
        token = token or self.ticket.share_token
        return f'/api/django/public/sav/ticket/{token}/satisfaction/'

    def test_post_valide_ticket_resolu(self):
        resp = self.public_api.post(
            self._url(), {'note': 5, 'commentaire': 'Très rapide, merci !'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(
            TicketSatisfaction.objects.filter(ticket=self.ticket).exists())

    def test_ticket_pas_encore_resolu_refuse(self):
        self.ticket.statut = Ticket.Statut.EN_COURS
        self.ticket.save(update_fields=['statut'])
        resp = self.public_api.post(self._url(), {'note': 4}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(
            TicketSatisfaction.objects.filter(ticket=self.ticket).exists())

    def test_doublon_refuse(self):
        resp1 = self.public_api.post(self._url(), {'note': 3}, format='json')
        self.assertEqual(resp1.status_code, 201, resp1.content)
        resp2 = self.public_api.post(self._url(), {'note': 5}, format='json')
        self.assertEqual(resp2.status_code, 409)
        self.assertEqual(
            TicketSatisfaction.objects.filter(ticket=self.ticket).count(), 1)

    def test_token_inconnu_404(self):
        resp = self.public_api.post(
            self._url(token='inconnu-xyz'), {'note': 4}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_note_hors_bornes_refusee(self):
        resp = self.public_api.post(self._url(), {'note': 7}, format='json')
        self.assertEqual(resp.status_code, 400)
        resp2 = self.public_api.post(self._url(), {'note': 0}, format='json')
        self.assertEqual(resp2.status_code, 400)

    def test_aucune_donnee_interne_dans_la_reponse(self):
        resp = self.public_api.post(
            self._url(), {'note': 5, 'commentaire': 'ok'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertNotIn('cout', str(resp.data))
        self.assertNotIn('999', str(resp.data))
        self.assertNotIn('client', str(resp.data).lower())

    def test_agregat_csat_par_technicien(self):
        TicketSatisfaction.objects.create(
            company=self.company, ticket=self.ticket, note=4)
        ticket2 = Ticket.objects.create(
            company=self.company, reference='SAV-XSAV10-2',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.CLOTURE,
            technicien_responsable=self.tech, created_by=self.user)
        TicketSatisfaction.objects.create(
            company=self.company, ticket=ticket2, note=2)

        rows = csat_par_technicien(self.company)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['technicien_id'], self.tech.id)
        self.assertEqual(row['nb_reponses'], 2)
        self.assertEqual(row['note_moyenne'], 3.0)
