"""AMOT28 (C-AMOT-029) — la garde d'expiration du tarif d'excédent ANRE 04/26
est armée : sans date de signature prévue, la date du JOUR (Africa/Casablanca)
fait foi ; après le 28/02/2027 la revente C&I est OMISE avec son motif ; au
08/10/2026 rien ne change.

Horloge figée (freezegun) ; ``revente_ci`` réel (seul appelant).

Test-du-test : remettre « ``d is not None and d > fin`` » sans la date du jour
⇒ ``test_apres_echeance_tarif_omis`` échoue.
"""
from django.test import SimpleTestCase
from freezegun import freeze_time

from apps.ventes.economie_ci import revente_ci
from apps.ventes.quote_engine import constants_82_21 as c8221

APERCU = {'bilan': {'production_kwh': 100000}}


class AnreEcheanceTests(SimpleTestCase):

    def test_apres_echeance_tarif_omis(self):
        with freeze_time('2027-03-01 10:00:00'):
            tarif, motif = c8221.tarif_excedent_en_vigueur(None)
            revente = revente_ci(APERCU, tension='mt', revente_demandee=True)
        self.assertIsNone(tarif)
        self.assertIn('28/02/2027', motif)
        self.assertNotEqual((revente or {}).get('statut'), 'calculee')
        self.assertNotIn(c8221.MENTION_82_21,
                         (revente or {}).get('mentions') or [])

    def test_aujourdhui_inchange(self):
        with freeze_time('2026-10-08 10:00:00'):
            tarif, motif = c8221.tarif_excedent_en_vigueur(None)
        self.assertIsNotNone(tarif)
        self.assertIsNone(motif)
