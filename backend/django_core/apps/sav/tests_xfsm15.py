"""XFSM15 — Suivi des récidives (callbacks / retour sur panne).

Couvre :
  * un ticket ouvert sur un chantier ayant une intervention TERMINÉE/VALIDÉE
    récente (< fenêtre paramétrable, défaut 30 j) est marqué récidive avec le
    lien d'origine + motif, et devient non-facturable par défaut ;
  * hors fenêtre (ou aucune intervention), aucune suggestion (comportement
    actuel inchangé) ;
  * un ticket récidive est exclu de XFSM1 (`generer-facture` → 403) sauf
    override responsable/admin explicite.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xfsm15 -v 2
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from apps.sav.models import PieceConsommee, SavSlaSettings, Ticket
from apps.stock.models import Produit

User = get_user_model()


def make_company(slug='sav-xfsm15', nom='Sav Co XFSM15'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XFSM15RecidiveTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='xfsm15_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xfsm15-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XFSM15', client=self.client_obj)

    def _intervention(self, date_realisee, statut=Intervention.Statut.TERMINEE):
        return Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention=Intervention.Type.DEPANNAGE,
            statut=statut, date_realisee=date_realisee)

    def test_ticket_marque_recidive_dans_la_fenetre(self):
        self._intervention(date.today() - timedelta(days=10))
        api = auth(self.admin)
        resp = api.post('/api/django/sav/tickets/', {
            'client': self.client_obj.id, 'installation': self.inst.id,
            'type': Ticket.Type.CORRECTIF,
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        ticket = Ticket.objects.get(pk=resp.data['id'])
        self.assertTrue(ticket.est_recidive)
        self.assertIsNotNone(ticket.intervention_origine_id)
        self.assertTrue(ticket.motif_recidive)
        self.assertTrue(ticket.non_facturable)

    def test_hors_fenetre_aucune_suggestion(self):
        self._intervention(date.today() - timedelta(days=60))
        api = auth(self.admin)
        resp = api.post('/api/django/sav/tickets/', {
            'client': self.client_obj.id, 'installation': self.inst.id,
            'type': Ticket.Type.CORRECTIF,
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        ticket = Ticket.objects.get(pk=resp.data['id'])
        self.assertFalse(ticket.est_recidive)
        self.assertIsNone(ticket.intervention_origine_id)
        self.assertFalse(ticket.non_facturable)

    def test_intervention_non_terminee_ignoree(self):
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention=Intervention.Type.DEPANNAGE,
            statut=Intervention.Statut.SUR_SITE,
            date_realisee=date.today() - timedelta(days=5))
        api = auth(self.admin)
        resp = api.post('/api/django/sav/tickets/', {
            'client': self.client_obj.id, 'installation': self.inst.id,
            'type': Ticket.Type.CORRECTIF,
        })
        ticket = Ticket.objects.get(pk=resp.data['id'])
        self.assertFalse(ticket.est_recidive)

    def test_fenetre_configurable_a_zero_desactive(self):
        sla = SavSlaSettings.get(self.company)
        sla.recidive_fenetre_jours = 0
        sla.save(update_fields=['recidive_fenetre_jours'])
        self._intervention(date.today() - timedelta(days=1))
        api = auth(self.admin)
        resp = api.post('/api/django/sav/tickets/', {
            'client': self.client_obj.id, 'installation': self.inst.id,
            'type': Ticket.Type.CORRECTIF,
        })
        ticket = Ticket.objects.get(pk=resp.data['id'])
        self.assertFalse(ticket.est_recidive)

    def test_recidive_exclue_de_facturation_sauf_override(self):
        self._intervention(date.today() - timedelta(days=5))
        api = auth(self.admin)
        resp = api.post('/api/django/sav/tickets/', {
            'client': self.client_obj.id, 'installation': self.inst.id,
            'type': Ticket.Type.CORRECTIF,
        })
        ticket_id = resp.data['id']
        ticket = Ticket.objects.get(pk=ticket_id)
        ticket.heures_main_oeuvre = Decimal('1')
        ticket.save(update_fields=['heures_main_oeuvre'])
        piece = Produit.objects.create(
            company=self.company, nom='Pièce X', sku='PX-XFSM15',
            prix_achat=Decimal('5'), prix_vente=Decimal('50'))
        PieceConsommee.objects.create(
            company=self.company, ticket=ticket, produit=piece,
            quantite=Decimal('1'), created_by=self.admin)

        resp = api.post(
            f'/api/django/sav/tickets/{ticket_id}/generer-facture/')
        self.assertEqual(resp.status_code, 403, resp.content)

        resp = api.post(
            f'/api/django/sav/tickets/{ticket_id}/generer-facture/',
            {'override': 'true'})
        self.assertEqual(resp.status_code, 201, resp.content)
