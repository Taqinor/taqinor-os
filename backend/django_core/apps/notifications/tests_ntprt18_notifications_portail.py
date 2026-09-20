"""NTPRT18 — notifications portail (email + in-portail).

Avant NTPRT18, les rares notifications client-facing envoyaient un email
DIRECTEMENT (ex. `apps.installations.livraison_client_notify`), hors du
canal `notify()`/`NotificationPreference` — un second moteur, l'exact
anti-patron que ce ticket referme. Les 4 nouveaux `EventType` portail
réutilisent `notify()` TEL QUEL : un compte portail (`CustomUser
portee=portail_client/portail_fournisseur/portail_partenaire`, NTPRT1/2)
reçoit la ligne in-app (cloche) ET, si SendGrid/Brevo est configuré,
l'email — exactement comme un compte interne.

Couverture :
  - les 4 EventType existent ;
  - `notify()` vers un compte portail crée TOUJOURS la ligne in-app ;
  - sans clé SendGrid/Brevo configurée : in-app créée, AUCUN email tenté ;
  - avec une clé SendGrid configurée : l'email part aussi, ON PAR DÉFAUT
    (override NTPRT18, sans `NotificationPreference` explicite) — un compte
    portail ne vit pas connecté à l'ERP comme un collaborateur interne.
"""
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from authentication.models import Company, CustomUser

from .models import EventType, Notification, NotificationPreference
from .services import notify

User = get_user_model()

PORTAIL_EVENT_TYPES = (
    EventType.PORTAIL_DEVIS_PRET,
    EventType.PORTAIL_FACTURE_ECHUE,
    EventType.PORTAIL_JALON_CHANTIER_ATTEINT,
    EventType.PORTAIL_TICKET_MAJ,
)

SENDGRID_CONFIGURED = dict(
    ANYMAIL={'SENDGRID_API_KEY': 'sg-test-key'},
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='portail@taqinor.ma',
)


class PortailEventTypesExistTests(TestCase):
    def test_les_quatre_event_types_existent(self):
        for event_type in PORTAIL_EVENT_TYPES:
            with self.subTest(event_type=event_type):
                self.assertIn(event_type, EventType.values)


class PortailClientNotifyTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='NTPRT18 Co', slug='ntprt18-co')
        self.compte_client = CustomUser.objects.create_user(
            username='ntprt18-client', password='x', company=self.company,
            email='client@example.com',
            portee=CustomUser.PORTEE_PORTAIL_CLIENT, portail_client_id=1)
        mail.outbox = []

    def test_notify_cree_toujours_la_ligne_in_app(self):
        notif = notify(
            self.compte_client, EventType.PORTAIL_DEVIS_PRET,
            'Votre devis DV-1 est prêt',
            body='Consultez-le et acceptez-le en ligne.',
            link='/portail/devis')
        self.assertIsNotNone(notif)
        self.assertTrue(Notification.objects.filter(
            recipient=self.compte_client,
            event_type=EventType.PORTAIL_DEVIS_PRET).exists())

    def test_sans_sendgrid_aucun_email_tente(self):
        # Comportement identique au canal interne existant : sans clé
        # (ANYMAIL vide, réglage de test par défaut), l'email est un no-op
        # silencieux — l'in-app reste créée.
        with override_settings(ANYMAIL={}):
            notif = notify(
                self.compte_client, EventType.PORTAIL_FACTURE_ECHUE,
                'Facture FA-1 échue')
        self.assertIsNotNone(notif)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(**SENDGRID_CONFIGURED)
    def test_avec_sendgrid_configure_email_part_par_defaut(self):
        # Aucune NotificationPreference explicite : l'email part grâce à
        # l'override NTPRT18 (email ON par défaut pour les 4 événements
        # portail), pas grâce à un opt-in.
        self.assertFalse(NotificationPreference.objects.filter(
            user=self.compte_client,
            event_type=EventType.PORTAIL_JALON_CHANTIER_ATTEINT).exists())

        notify(
            self.compte_client, EventType.PORTAIL_JALON_CHANTIER_ATTEINT,
            'Jalon atteint sur votre chantier',
            body='La pose des panneaux est terminée.')

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['client@example.com'])

    @override_settings(**SENDGRID_CONFIGURED)
    def test_les_quatre_evenements_portail_emailent_par_defaut(self):
        for event_type in PORTAIL_EVENT_TYPES:
            with self.subTest(event_type=event_type):
                mail.outbox = []
                notify(self.compte_client, event_type, 'Titre', body='x')
                self.assertEqual(len(mail.outbox), 1)


class PortailFournisseurEtPartenaireNotifyTests(TestCase):
    """NTPRT18 couvre les TROIS portées portail, pas seulement le client."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='NTPRT18 Multi', slug='ntprt18-multi')

    def test_compte_fournisseur_recoit_bien_la_notification(self):
        compte = CustomUser.objects.create_user(
            username='ntprt18-fournisseur', password='x',
            company=self.company, email='fournisseur@example.com',
            portee=CustomUser.PORTEE_PORTAIL_FOURNISSEUR,
            portail_fournisseur_id=1)
        notif = notify(
            compte, EventType.PORTAIL_TICKET_MAJ, 'Ticket mis à jour')
        self.assertIsNotNone(notif)
        self.assertTrue(Notification.objects.filter(
            recipient=compte, event_type=EventType.PORTAIL_TICKET_MAJ).exists())

    def test_compte_partenaire_recoit_bien_la_notification(self):
        compte = CustomUser.objects.create_user(
            username='ntprt18-partenaire', password='x',
            company=self.company, email='partenaire@example.com',
            portee=CustomUser.PORTEE_PORTAIL_PARTENAIRE,
            portail_partenaire_id=1)
        notif = notify(
            compte, EventType.PORTAIL_FACTURE_ECHUE, 'Facture échue')
        self.assertIsNotNone(notif)
        self.assertTrue(Notification.objects.filter(
            recipient=compte, event_type=EventType.PORTAIL_FACTURE_ECHUE).exists())
