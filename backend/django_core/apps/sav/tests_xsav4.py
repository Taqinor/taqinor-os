"""XSAV4 — Notifications client aux transitions du ticket SAV.

Couvre :
  * OFF par défaut (notifications_client_sav=False) → aucune notification à
    la transition de statut (comportement actuel inchangé) ;
  * ON → message généré (wa_draft_url et/ou email) avec le contenu du
    template effectif (défaut ou personnalisé société) ;
  * jamais de prix interne (cout) dans le corps du message ;
  * migration additive (le champ existe avec le défaut correct).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav4 -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import SavSlaSettings, Ticket
from apps.sav.notifications_client import notify_ticket_transition

User = get_user_model()


def make_company(slug='sav-xsav4', nom='Sav Co XSAV4'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class XSAV4NotificationsClientTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='xsav4_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav4-client@example.invalid',
            telephone='0612345678')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV4', client=self.client_obj)
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XSAV4-1',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.NOUVEAU,
            created_by=self.user)

    def test_off_par_defaut_aucune_notification(self):
        sla = SavSlaSettings.get(self.company)
        self.assertFalse(sla.notifications_client_sav)
        result = notify_ticket_transition(self.ticket, 'resolu')
        self.assertFalse(result['sent'])
        self.assertIsNone(result['wa_draft_url'])
        self.assertFalse(result['email_sent'])

    def test_on_genere_message_avec_lien_client(self):
        sla = SavSlaSettings.get(self.company)
        sla.notifications_client_sav = True
        sla.save(update_fields=['notifications_client_sav'])

        result = notify_ticket_transition(self.ticket, 'resolu')
        self.assertTrue(result['sent'])
        self.assertIsNotNone(result['wa_draft_url'])
        self.assertIn('wa.me', result['wa_draft_url'])
        self.ticket.refresh_from_db()
        self.assertTrue(self.ticket.share_token)

    def test_statut_sans_cle_associee_no_op(self):
        sla = SavSlaSettings.get(self.company)
        sla.notifications_client_sav = True
        sla.save(update_fields=['notifications_client_sav'])
        result = notify_ticket_transition(self.ticket, 'en_cours')
        self.assertFalse(result['sent'])

    def test_jamais_de_prix_interne_dans_le_message(self):
        self.ticket.cout = Decimal('1234.56')
        self.ticket.save(update_fields=['cout'])
        sla = SavSlaSettings.get(self.company)
        sla.notifications_client_sav = True
        sla.save(update_fields=['notifications_client_sav'])
        from apps.sav.notifications_client import build_ticket_transition_message
        wa_corps, email = build_ticket_transition_message(
            self.ticket, 'ticket_resolu')
        self.assertNotIn('1234.56', wa_corps)
        self.assertNotIn('1234.56', email['corps'])
        self.assertNotIn('1234.56', email['sujet'])

    def test_migration_defaut_off(self):
        """Migration additive : le champ existe, défaut False (comportement
        actuel inchangé pour toute société déjà en base)."""
        other = make_company(slug='sav-xsav4-other', nom='Sav Co XSAV4 Other')
        sla = SavSlaSettings.get(other)
        self.assertFalse(sla.notifications_client_sav)
