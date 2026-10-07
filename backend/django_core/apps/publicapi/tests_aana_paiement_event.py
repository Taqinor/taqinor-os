"""AANA32 — ``paiement.recorded`` arrive dans le flux d'évènements.

Constat C-AANA-026 : la charge de ``paiement.recorded`` portait le
``Decimal`` brut de ``Paiement.montant`` : l'écriture JSON du journal
(``ApiEvent.payload``) levait ``TypeError`` et l'évènement était PERDU (0 dans
``/events/``, alors que ``facture.created`` y était). Désormais le montant est
un nombre (``signals._montant``, comme ``facture.*``) et le journal encode ses
charges avec ``DjangoJSONEncoder``.

Chaîne réelle : vraie ``Facture``, vrai ``Paiement``, vrais signaux et vrai
journal ; seule la frontière Celery (``delay``) est neutralisée.

Run :
    python manage.py test apps.publicapi.tests_aana_paiement_event -v2
"""
import datetime
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from apps.crm.models import Client
from apps.ventes.models import Facture, Paiement
from authentication.models import Company

from . import tasks
from .constants import EVENT_FACTURE_CREATED, EVENT_PAIEMENT_RECORDED
from .events_feed import enregistrer
from .models import ApiEvent


class PaiementDansLeFluxTest(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='aana32-co', defaults={'nom': 'AANA32'})
        self.client_obj = Client.objects.create(company=self.co, nom='Cli')

    def test_paiement_dans_le_flux(self):
        with mock.patch.object(tasks.deliver_webhook, 'delay'), \
                self.captureOnCommitCallbacks(execute=True):
            facture = Facture.objects.create(
                company=self.co, reference='FA-AANA32',
                client=self.client_obj, statut=Facture.Statut.EMISE)
            paiement = Paiement.objects.create(
                company=self.co, facture=facture, montant=Decimal('123.45'),
                date_paiement=datetime.date(2026, 10, 5))
        # Témoin : facture.created est bien journalisé.
        self.assertTrue(ApiEvent.objects.filter(
            company=self.co, type=EVENT_FACTURE_CREATED).exists())
        evenement = ApiEvent.objects.get(
            company=self.co, type=EVENT_PAIEMENT_RECORDED)
        evenement.refresh_from_db()
        self.assertEqual(evenement.payload['montant'], 123.45)
        self.assertEqual(evenement.payload['id'], paiement.pk)
        self.assertEqual(evenement.payload['facture_id'], facture.pk)

    def test_le_journal_encode_un_decimal(self):
        evenement = enregistrer(
            self.co.id, EVENT_PAIEMENT_RECORDED,
            {'montant': Decimal('10.50'), 'le': datetime.date(2026, 10, 5)})
        self.assertIsNotNone(evenement)
        evenement.refresh_from_db()
        self.assertEqual(evenement.payload['montant'], '10.50')
        self.assertEqual(evenement.payload['le'], '2026-10-05')
