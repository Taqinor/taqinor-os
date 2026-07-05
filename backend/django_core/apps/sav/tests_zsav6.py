"""ZSAV6 — Vue « activité » : file d'action suivante par ticket.

Couvre :
  * chaque ticket tombe dans EXACTEMENT un bucket ;
  * comptes exacts sur fixtures datées ;
  * réservé au tier responsable/admin ;
  * cross-tenant exclu.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_zsav6 -v 2
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Ticket
from apps.sav.selectors import file_action

User = get_user_model()


def make_company(slug='sav-zsav6', nom='Sav Co ZSAV6'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ZSAV6FileActionTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='zsav6_admin', password='x', role_legacy='admin',
            company=self.company)
        self.viewer = User.objects.create_user(
            username='zsav6_viewer', password='x', role_legacy='normal',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ZSAV6',
            email='zsav6-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ZSAV6', client=self.client_obj)
        self.today = date(2026, 6, 15)

    def _ticket(self, **kwargs):
        defaults = dict(
            company=self.company, client=self.client_obj,
            installation=self.inst, created_by=self.admin,
            reference=f'SAV-ZSAV6-{Ticket.objects.count()}')
        defaults.update(kwargs)
        return Ticket.objects.create(**defaults)

    def test_a_repondre_sans_premiere_reponse(self):
        t = self._ticket(statut=Ticket.Statut.NOUVEAU)
        rows = file_action(self.company, today=self.today)
        self.assertIn(t.id, rows['buckets']['a_repondre']['ids'])

    def test_a_planifier_sans_date_tournee(self):
        t = self._ticket(
            statut=Ticket.Statut.PLANIFIE,
            date_premiere_reponse='2026-06-01T10:00:00Z')
        rows = file_action(self.company, today=self.today)
        self.assertIn(t.id, rows['buckets']['a_planifier']['ids'])

    def test_a_relancer_au_dela_de_la_moitie_du_sla(self):
        t = self._ticket(
            statut=Ticket.Statut.EN_COURS,
            date_premiere_reponse='2026-06-01T10:00:00Z',
            date_ouverture=date(2026, 6, 1),
            sla_due_at=date(2026, 6, 11))  # 10 jours -> moitié = J+5 = 6 juin
        rows = file_action(self.company, today=self.today)  # 15 juin > 6 juin
        self.assertIn(t.id, rows['buckets']['a_relancer']['ids'])

    def test_pas_a_relancer_avant_la_moitie_du_sla(self):
        t = self._ticket(
            statut=Ticket.Statut.EN_COURS,
            date_premiere_reponse='2026-06-01T10:00:00Z',
            date_ouverture=date(2026, 6, 14),
            sla_due_at=date(2026, 6, 24))
        rows = file_action(self.company, today=self.today)
        self.assertNotIn(t.id, rows['buckets']['a_relancer']['ids'])

    def test_a_cloturer_resolu_dormant(self):
        t = self._ticket(
            statut=Ticket.Statut.RESOLU,
            date_premiere_reponse='2026-05-01T10:00:00Z',
            date_resolution=date(2026, 6, 1))  # 14 jours avant `today`
        rows = file_action(self.company, today=self.today)
        self.assertIn(t.id, rows['buckets']['a_cloturer']['ids'])

    def test_chaque_ticket_dans_exactement_un_bucket(self):
        t1 = self._ticket(statut=Ticket.Statut.NOUVEAU)
        t2 = self._ticket(
            statut=Ticket.Statut.PLANIFIE,
            date_premiere_reponse='2026-06-01T10:00:00Z')
        rows = file_action(self.company, today=self.today)
        all_ids = [
            i for bucket in rows['buckets'].values() for i in bucket['ids']]
        self.assertEqual(len(all_ids), len(set(all_ids)))
        self.assertIn(t1.id, all_ids)
        self.assertIn(t2.id, all_ids)

    def test_ticket_annule_exclu(self):
        t = self._ticket(statut=Ticket.Statut.NOUVEAU, annule=True)
        rows = file_action(self.company, today=self.today)
        all_ids = [
            i for bucket in rows['buckets'].values() for i in bucket['ids']]
        self.assertNotIn(t.id, all_ids)

    def test_endpoint_reserve_responsable_admin(self):
        r_viewer = auth(self.viewer).get(
            '/api/django/sav/tickets/file-action/')
        self.assertEqual(r_viewer.status_code, 403, r_viewer.data)

        r_admin = auth(self.admin).get(
            '/api/django/sav/tickets/file-action/')
        self.assertEqual(r_admin.status_code, 200, r_admin.data)

    def test_isolation_multitenant(self):
        other_company = make_company(slug='sav-zsav6-other', nom='Other')
        other_client = Client.objects.create(
            company=other_company, nom='Autre', prenom='Client',
            email='zsav6-other@example.invalid')
        other_inst = Installation.objects.create(
            company=other_company, reference='CHT-OTHER', client=other_client)
        Ticket.objects.create(
            company=other_company, client=other_client,
            installation=other_inst, reference='SAV-OTHER-1',
            statut=Ticket.Statut.NOUVEAU)
        rows = file_action(self.company, today=self.today)
        all_ids = [
            i for bucket in rows['buckets'].values() for i in bucket['ids']]
        for tid in all_ids:
            self.assertEqual(
                Ticket.objects.get(pk=tid).company_id, self.company.id)
