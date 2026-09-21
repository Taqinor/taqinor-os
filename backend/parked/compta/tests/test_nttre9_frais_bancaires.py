"""Test NTTRE9 — analyse des frais bancaires dans le temps."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import CompteTresorerie, Journal


class AnalyseFraisBancairesTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='nttre9', defaults={'nom': 'NTTRE9 Co'})
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.banque = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE', compte_comptable=services.get_compte(self.co, '5141'))

    def _frais(self, montant, jour):
        journal = services._journal(self.co, Journal.Type.BANQUE)
        lignes = [
            {'compte': services.get_compte(self.co, '6147'),
             'debit': Decimal(montant), 'credit': Decimal('0')},
            {'compte': services.get_compte(self.co, '5141'),
             'debit': Decimal('0'), 'credit': Decimal(montant)},
        ]
        return services.creer_ecriture(
            self.co, journal, jour, 'Frais bancaires', lignes)

    def test_agrege_par_compte_et_par_mois(self):
        self._frais('120', date(2026, 1, 15))
        self._frais('80', date(2026, 1, 28))
        self._frais('150', date(2026, 2, 10))
        data = selectors.analyse_frais_bancaires(
            self.co, debut=date(2026, 1, 1), fin=date(2026, 2, 28))
        self.assertEqual(data['total'], Decimal('350'))
        self.assertEqual(len(data['par_compte']), 1)
        compte = data['par_compte'][0]
        self.assertEqual(compte['compte_id'], self.banque.id)
        self.assertEqual(compte['total'], Decimal('350'))
        mois = {m['mois']: m['montant'] for m in compte['mois']}
        self.assertEqual(mois['2026-01'], Decimal('200'))
        self.assertEqual(mois['2026-02'], Decimal('150'))

    def test_reglage_comptes_frais_pris_en_compte(self):
        # Par défaut ['6147'] : une écriture sur 6147 est comptée.
        self._frais('90', date(2026, 3, 5))
        params = services.get_parametres_tresorerie(self.co)
        params.comptes_frais_bancaires = ['6311']  # restreint : exclut 6147
        params.save()
        data = selectors.analyse_frais_bancaires(self.co)
        self.assertEqual(data['total'], Decimal('0'))
