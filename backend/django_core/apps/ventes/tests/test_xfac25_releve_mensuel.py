"""
XFAC25 — Envoi programmé des relevés de compte clients (mensuel, opt-in).

Un client opt-in avec encours reçoit EXACTEMENT un relevé le 1er du mois,
jamais deux ; les exclus (opt-out / sans email / solde nul) ne reçoivent
rien.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xfac25_releve_mensuel -v 2
"""
from decimal import Decimal

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
