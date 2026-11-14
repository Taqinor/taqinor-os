"""
XFAC25 — Envoi programmé des relevés de compte clients (mensuel, opt-in).

Un client opt-in avec encours reçoit EXACTEMENT un relevé le 1er du mois,
jamais deux ; les exclus (opt-out / sans email / solde nul) ne reçoivent
rien.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xfac25_releve_mensuel -v 2
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.ventes.models import EmailLog, Facture
from apps.ventes.scheduled import releve_mensuel_reminders

MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='xfac25-co', nom='XFAC25 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='xfac25@example.com', opt_in=True):
    return Client.objects.create(
        company=company, nom='Releve', prenom='Client',
        email=email, telephone='+212600000068', adresse='Casablanca',
        releve_mensuel_auto=opt_in,
    )


class XFAC25ReleveMensuelTests(TestCase):
    def setUp(self):
        self.company = make_company()

    def _facture_ouverte(self, client_obj, n=1, montant='3000'):
        return Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-6{n:03d}',
            client=client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal(montant),
        )

    def test_opt_in_with_encours_receives_exactly_one(self):
        client_obj = make_client(self.company, opt_in=True)
        self._facture_ouverte(client_obj)
        sent = releve_mensuel_reminders()
        self.assertEqual(sent, 1)
        logs = EmailLog.objects.filter(client=client_obj)
        self.assertEqual(logs.count(), 1)
        self.assertTrue(logs.first().reference.startswith('releve_mensuel-'))

    def test_never_sends_twice_same_month(self):
        client_obj = make_client(self.company, opt_in=True)
        self._facture_ouverte(client_obj)
        releve_mensuel_reminders()
        sent2 = releve_mensuel_reminders()
        self.assertEqual(sent2, 0)
        self.assertEqual(EmailLog.objects.filter(client=client_obj).count(), 1)

    def test_opt_out_receives_nothing(self):
        client_obj = make_client(self.company, opt_in=False)
        self._facture_ouverte(client_obj)
        sent = releve_mensuel_reminders()
        self.assertEqual(sent, 0)
        self.assertFalse(EmailLog.objects.filter(client=client_obj).exists())

    def test_no_email_receives_nothing(self):
        client_obj = Client.objects.create(
            company=self.company, nom='SansEmail', releve_mensuel_auto=True,
        )
        self._facture_ouverte(client_obj)
        sent = releve_mensuel_reminders()
        self.assertEqual(sent, 0)

    def test_zero_encours_receives_nothing(self):
        client_obj = make_client(
            self.company, email='xfac25b@example.com', opt_in=True)
        # Aucune facture ouverte → encours nul.
        sent = releve_mensuel_reminders()
        self.assertEqual(sent, 0)
        self.assertFalse(EmailLog.objects.filter(client=client_obj).exists())

    def test_paid_facture_does_not_count_as_encours(self):
        client_obj = make_client(
            self.company, email='xfac25c@example.com', opt_in=True)
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-6999',
            client=client_obj, statut=Facture.Statut.PAYEE,
            montant_ttc=Decimal('1000'),
        )
        sent = releve_mensuel_reminders()
        self.assertEqual(sent, 0)

    def test_jour_ferie_aucun_releve_rattrape_le_lendemain(self):
        """AMSG101 (C-AMSG-VER3-104, D-AMSG-1) — mardi 01/12/2026 férié de la
        société : aucun relevé pour elle (le témoin sans férié reçoit le
        sien) ; le 02/12 (fenêtre 1-3 du beat) son relevé part, une fois.
        Mutant : retirer le saut du férié ⇒ 2 envois le 01/12."""
        from apps.notifications.models import Holiday
        Holiday.objects.create(company=self.company, date=date(2026, 12, 1),
                               nom='Férié société')
        client_obj = make_client(self.company, email='xfac25f@example.com')
        self._facture_ouverte(client_obj, n=7)
        temoin = make_company(slug='xfac25-temoin', nom='XFAC25 Témoin')
        client_temoin = make_client(temoin, email='xfac25t@example.com')
        Facture.objects.create(
            company=temoin, reference=f'FAC-{MONTH}-6008', client=client_temoin,
            statut=Facture.Statut.EMISE, montant_ttc=Decimal('2000'))
        for jour, attendu in ((1, client_temoin), (2, client_obj)):
            with self.subTest(jour=jour), patch(
                    'apps.ventes.scheduled.casablanca_today',
                    return_value=date(2026, 12, jour)):
                self.assertEqual(releve_mensuel_reminders(), 1)
                self.assertTrue(EmailLog.objects.filter(
                    client=attendu, reference='releve_mensuel-202612',
                    statut=EmailLog.Statut.ENVOYE).exists())
        self.assertEqual(EmailLog.objects.filter(
            client=client_obj, reference='releve_mensuel-202612').count(), 1)
