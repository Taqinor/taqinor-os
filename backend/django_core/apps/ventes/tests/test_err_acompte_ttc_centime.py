"""ERR-QAH-VENTES-ACOMPTE-TTC-CENTIME — une facture d'acompte (tranche
d'échéancier) s'additionne au centime : HT + TVA = TTC.

FAC-202606-0003 (acompte 30 %, taux mixte 17,15 %) imprimait un TTC supérieur
d'un centime à HT + TVA : ``next_tranche`` arrondissait séparément les trois
montants. La TVA est désormais le complément (TTC − HT) ; le TTC annoncé
(acompte des conditions publiques / e-mails) ne bouge pas.

Aucune base : ``option_totaux``/``factures_actives``/``tranches_normalisees``
sont remplacés par des doubles.

Run : ``python manage.py test apps.ventes.tests.test_err_acompte_ttc_centime``
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.ventes.utils import echeancier
from apps.ventes.utils.echeancier import UNITE_MONTANT, UNITE_PCT, next_tranche

# HT 10 000,05 + TVA 1 715,05 = TTC 11 715,10 : à 30 %, les trois arrondis
# séparés donnaient 3 000,02 + 514,52 = 3 514,54 pour un TTC de 3 514,53.
TOTAUX = {'ht': Decimal('10000.05'), 'tva': Decimal('1715.05'),
          'ttc': Decimal('11715.10')}


def _tranche(devis, tranches):
    with mock.patch.object(echeancier, 'tranches_normalisees',
                           return_value=tranches), \
            mock.patch.object(echeancier, 'factures_actives',
                              return_value=[]), \
            mock.patch('apps.ventes.utils.options.option_totaux',
                       return_value=TOTAUX):
        return next_tranche(devis)


class AcompteAuCentimeTests(SimpleTestCase):

    def test_acompte_pourcentage_ht_plus_tva_egale_ttc(self):
        tr = _tranche(SimpleNamespace(), [
            {'key': 'acompte', 'valeur': 30, 'unite': UNITE_PCT,
             'libelle': 'Acompte'},
            {'key': 'solde', 'valeur': 70, 'unite': UNITE_PCT,
             'libelle': 'Solde'},
        ])
        # Le TTC annoncé est inchangé (30 % du TTC, arrondi au centime).
        self.assertEqual(tr['ttc'], Decimal('3514.53'))
        self.assertEqual(tr['ht'], Decimal('3000.02'))
        self.assertEqual(tr['ht'] + tr['tva'], tr['ttc'])
        self.assertEqual(tr['tva'], Decimal('514.51'))

    def test_acompte_montant_declare_ht_plus_tva_egale_ttc(self):
        tr = _tranche(SimpleNamespace(), [
            {'key': 'acompte', 'valeur': 3514.53, 'unite': UNITE_MONTANT,
             'libelle': 'Acompte'},
            {'key': 'solde', 'valeur': 100, 'unite': UNITE_PCT,
             'libelle': 'Solde'},
        ])
        self.assertEqual(tr['ttc'], Decimal('3514.53'))
        self.assertEqual(tr['ht'] + tr['tva'], tr['ttc'])
