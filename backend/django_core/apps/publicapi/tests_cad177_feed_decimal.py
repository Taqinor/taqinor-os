"""CAD177 - un payload portant un Decimal (``Paiement.montant``) doit entrer
dans le flux public ; avant, l'INSERT du JSONField levait « Object of type
Decimal is not JSON serializable » et l'evenement ``paiement.recorded`` etait
perdu (vu dans les logs e2e de la verification nocturne)."""
import datetime
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from . import events_feed
from .constants import EVENT_PAIEMENT_RECORDED
from .models import ApiEvent


class FluxPayloadDecimalTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='cad177-feed', defaults={'nom': 'CAD177 feed'})

    def test_payload_json_sur_convertit_decimal_et_date(self):
        sortie = events_feed.payload_json_sur({
            'montant': Decimal('1200.50'),
            'le': datetime.date(2026, 10, 7),
            'n': 3,
        })
        self.assertEqual(
            sortie, {'montant': '1200.50', 'le': '2026-10-07', 'n': 3})

    def test_enregistrer_accepte_un_payload_avec_decimal(self):
        ev = events_feed.enregistrer(
            self.company.pk, EVENT_PAIEMENT_RECORDED,
            {'event': EVENT_PAIEMENT_RECORDED, 'id': 1,
             'montant': Decimal('250.00'), 'mode': 'virement'})
        self.assertIsNotNone(ev)
        relu = ApiEvent.objects.get(pk=ev.pk)
        self.assertEqual(relu.payload['montant'], '250.00')
        self.assertEqual(relu.type, EVENT_PAIEMENT_RECORDED)
