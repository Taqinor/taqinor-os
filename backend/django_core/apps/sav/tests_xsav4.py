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
from django.test import TestCase, override_settings

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

    @override_settings(PUBLIC_BASE_URL='https://api.taqinor.ma')
    def test_lien_suivi_absolu_hors_requete(self):
        # ASOC26 — hors requête (maintenance, intervention terminée), le lien
        # /suivi/<jeton> du message client commence par la base publique.
        from apps.sav.notifications_client import build_ticket_transition_message
        wa_corps, email = build_ticket_transition_message(
            self.ticket, 'ticket_planifie')
        attendu = f'https://api.taqinor.ma/suivi/{self.ticket.share_token}'
        self.assertIn(attendu, wa_corps)
        self.assertIn(attendu, email['corps'])

    def test_client_arabe_recoit_le_message_arabe(self):
        # ASOC83 — client `langue_document='ar'` : sujet/corps e-mail et
        # WhatsApp du ticket dans l'arabe de la société ; client FR inchangé.
        from apps.parametres.models import MessageTemplate
        from apps.parametres.models_email import EmailTemplate
        from apps.sav.notifications_client import build_ticket_transition_message
        EmailTemplate.objects.create(
            company=self.company, cle='ticket_planifie',
            sujet='FR {reference}', corps='Corps FR {reference}',
            sujet_ar='تدخل {reference}', corps_ar='مبرمج {reference}')
        MessageTemplate.objects.create(
            company=self.company, cle='ticket_planifie',
            corps_fr='WA FR {reference}', corps_ar='واتساب {reference}')
        wa_fr, email_fr = build_ticket_transition_message(
            self.ticket, 'ticket_planifie')
        self.assertEqual(email_fr['sujet'], 'FR SAV-XSAV4-1')
        self.client_obj.langue_document = 'ar'
        self.client_obj.save(update_fields=['langue_document'])
        self.ticket.refresh_from_db()
        wa_corps, email = build_ticket_transition_message(
            self.ticket, 'ticket_planifie')
        self.assertEqual(email['sujet'], 'تدخل SAV-XSAV4-1')
        self.assertEqual(email['corps'], 'مبرمج SAV-XSAV4-1')
        self.assertEqual(wa_corps, 'واتساب SAV-XSAV4-1')
        self.assertEqual(wa_fr, 'WA FR SAV-XSAV4-1')

    @override_settings(ANYMAIL={'SENDGRID_API_KEY': 'sg-test-key'},
                       EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_transition_notifie_le_compte_portail(self):
        """ASOC27 (C-ASOC-136) — la transition « planifié » notifie le compte
        portail ACTIF du client (1 ``portail_ticket_maj``, sans e-mail : celui
        du SAV reste le seul) ; compte désactivé : 0."""
        from django.core import mail
        from apps.notifications.models import Notification
        sla = SavSlaSettings.get(self.company)
        sla.notifications_client_sav = True
        sla.save(update_fields=['notifications_client_sav'])
        compte = User.objects.create_user(
            username='xsav4_portail', password='x', company=self.company,
            email='xsav4-portail@example.invalid', portee='portail_client',
            portail_client_id=self.client_obj.id)
        User.objects.create_user(
            username='xsav4_portail_inactif', password='x', is_active=False,
            company=self.company, portee='portail_client',
            portail_client_id=self.client_obj.id)
        mail.outbox = []
        with self.captureOnCommitCallbacks(execute=True):
            result = notify_ticket_transition(self.ticket, 'planifie')
        self.assertTrue(result['email_sent'])
        lignes = Notification.objects.filter(event_type='portail_ticket_maj')
        self.assertEqual([n.recipient_id for n in lignes], [compte.id])
        self.assertEqual([m.to for m in mail.outbox],
                         [['xsav4-client@example.invalid']])

    def test_migration_defaut_off(self):
        """Migration additive : le champ existe, défaut False (comportement
        actuel inchangé pour toute société déjà en base)."""
        other = make_company(slug='sav-xsav4-other', nom='Sav Co XSAV4 Other')
        sla = SavSlaSettings.get(other)
        self.assertFalse(sla.notifications_client_sav)
