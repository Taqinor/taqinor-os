"""XSAV24 — Auto-clôture des tickets résolus dormants.

Couvre :
  * OFF par défaut (auto_cloture_jours=0) -> rien ne change ;
  * activité récente -> pas de clôture même si le ticket est vieux ;
  * franchissement du délai sans activité -> clôture + note automatique ;
  * sweep idempotent (un second passage ne reclôture pas / ne double pas la note).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav24 -v 2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import SavSlaSettings, Ticket, TicketActivity
from apps.sav.views import scan_auto_cloture_tickets_resolus

User = get_user_model()


def make_company(slug='sav-xsav24', nom='Sav Co XSAV24'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class XSAV24AutoClotureTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='xsav24_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav24-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV24', client=self.client_obj)

    def _ticket_resolu(self):
        t = Ticket.objects.create(
            company=self.company, reference=f'SAV-XSAV24-{Ticket.objects.count()}',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.RESOLU,
            created_by=self.admin)
        # Recule l'horodatage de la dernière activité pour simuler le passé.
        TicketActivity.objects.filter(ticket=t).update(
            created_at=timezone.now() - timedelta(days=30))
        return t

    def test_off_par_defaut_rien_ne_change(self):
        ticket = self._ticket_resolu()
        n = scan_auto_cloture_tickets_resolus()
        self.assertEqual(n, 0)
        ticket.refresh_from_db()
        self.assertEqual(ticket.statut, Ticket.Statut.RESOLU)

    def test_activite_recente_pas_de_cloture(self):
        SavSlaSettings.objects.create(company=self.company, auto_cloture_jours=10)
        ticket = self._ticket_resolu()
        # Une note récente réinitialise l'horloge d'inactivité.
        TicketActivity.objects.create(
            company=self.company, ticket=ticket, kind=TicketActivity.Kind.NOTE,
            body='Suivi récent', user=self.admin)
        n = scan_auto_cloture_tickets_resolus()
        self.assertEqual(n, 0)
        ticket.refresh_from_db()
        self.assertEqual(ticket.statut, Ticket.Statut.RESOLU)

    def test_franchissement_delai_cloture_avec_note(self):
        SavSlaSettings.objects.create(company=self.company, auto_cloture_jours=10)
        ticket = self._ticket_resolu()
        n = scan_auto_cloture_tickets_resolus()
        self.assertEqual(n, 1)
        ticket.refresh_from_db()
        self.assertEqual(ticket.statut, Ticket.Statut.CLOTURE)
        notes = ticket.activites.filter(kind=TicketActivity.Kind.NOTE)
        self.assertTrue(
            any('Clôturé automatiquement' in (a.body or '') for a in notes))

    def test_sweep_idempotent(self):
        SavSlaSettings.objects.create(company=self.company, auto_cloture_jours=10)
        ticket = self._ticket_resolu()
        scan_auto_cloture_tickets_resolus()
        nb_notes_apres_premier = ticket.activites.filter(
            kind=TicketActivity.Kind.NOTE).count()
        n2 = scan_auto_cloture_tickets_resolus()
        self.assertEqual(n2, 0)
        nb_notes_apres_second = ticket.activites.filter(
            kind=TicketActivity.Kind.NOTE).count()
        self.assertEqual(nb_notes_apres_premier, nb_notes_apres_second)

    def test_sous_le_delai_pas_de_cloture(self):
        SavSlaSettings.objects.create(company=self.company, auto_cloture_jours=60)
        ticket = self._ticket_resolu()  # dernière activité il y a 30 jours.
        n = scan_auto_cloture_tickets_resolus()
        self.assertEqual(n, 0)
        ticket.refresh_from_db()
        self.assertEqual(ticket.statut, Ticket.Statut.RESOLU)
