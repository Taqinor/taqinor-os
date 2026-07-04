"""Tests XACC20 — Ventilation analytique en % multi-sections & règles
d'auto-imputation.

Couvre : une écriture ventilée 60/40 sort dans les rapports par centre au
prorata, une règle sur le compte 6111 s'applique automatiquement aux
nouvelles écritures, et l'ancien champ ``centre_cout`` simple reste intact
(rétro-compatible).
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import CentreCout, EcritureComptable, Journal


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_centre(company, code, libelle='Chantier'):
    return CentreCout.objects.create(company=company, code=code, libelle=libelle)


class VentilationAnalytiqueTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc20-vent', 'XACC20 Vent')
        self.cc_a = make_centre(self.co, 'CH-A')
        self.cc_b = make_centre(self.co, 'CH-B')

    def _poster_charge(self, montant):
        journal = services._journal(self.co, Journal.Type.OPERATIONS_DIVERSES)
        if journal is None:
            services.seed_journaux(self.co)
            journal = services._journal(self.co, Journal.Type.OPERATIONS_DIVERSES)
        compte_charge = services._assurer_compte(self.co, '6111')
        compte_tresorerie = services._assurer_compte(self.co, '5141')
        ecriture = services.creer_ecriture(
            self.co, journal, date(2026, 3, 1), 'Charge test',
            [
                {'compte': compte_charge, 'debit': Decimal(montant),
                 'credit': Decimal('0'), 'libelle': 'Charge'},
                {'compte': compte_tresorerie, 'debit': Decimal('0'),
                 'credit': Decimal(montant), 'libelle': 'Charge'},
            ],
            statut=EcritureComptable.Statut.VALIDEE)
        return ecriture.lignes.get(compte__numero='6111')

    def test_ventilation_60_40_somme_100(self):
        ligne = self._poster_charge(1000)
        ventilation = services.ventiler_ligne_ecriture(ligne, [
            {'centre_cout': self.cc_a, 'pourcentage': Decimal('60')},
            {'centre_cout': self.cc_b, 'pourcentage': Decimal('40')},
        ])
        self.assertEqual(ventilation.total_pourcentage, Decimal('100'))

    def test_ventilation_refuse_si_total_different_100(self):
        ligne = self._poster_charge(1000)
        with self.assertRaises(ValidationError):
            services.ventiler_ligne_ecriture(ligne, [
                {'centre_cout': self.cc_a, 'pourcentage': Decimal('60')},
                {'centre_cout': self.cc_b, 'pourcentage': Decimal('30')},
            ])

    def test_rapport_par_centre_au_prorata(self):
        ligne = self._poster_charge(1000)
        services.ventiler_ligne_ecriture(ligne, [
            {'centre_cout': self.cc_a, 'pourcentage': Decimal('60')},
            {'centre_cout': self.cc_b, 'pourcentage': Decimal('40')},
        ])
        rapport = selectors.resultat_analytique(self.co)
        centre_a = [c for c in rapport['centres'] if c['code'] == 'CH-A'][0]
        centre_b = [c for c in rapport['centres'] if c['code'] == 'CH-B'][0]
        self.assertEqual(centre_a['charges'], Decimal('600.00'))
        self.assertEqual(centre_b['charges'], Decimal('400.00'))

    def test_ancien_champ_centre_cout_reste_intact_sans_ventilation(self):
        ligne = self._poster_charge(500)
        ligne.centre_cout = self.cc_a
        ligne.save(update_fields=['centre_cout'])
        rapport = selectors.resultat_analytique(self.co)
        centre_a = [c for c in rapport['centres'] if c['code'] == 'CH-A'][0]
        self.assertEqual(centre_a['charges'], Decimal('500.00'))


class RegleImputationTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc20-regle', 'XACC20 Regle')
        self.cc_a = make_centre(self.co, 'CH-X')
        self.cc_b = make_centre(self.co, 'CH-Y')

    def test_regle_sur_compte_6111_applique_automatiquement(self):
        services.creer_regle_imputation(
            self.co, libelle='Charges chantier X/Y',
            prefixe_compte='6111',
            distributions=[
                {'centre_cout': self.cc_a, 'pourcentage': Decimal('70')},
                {'centre_cout': self.cc_b, 'pourcentage': Decimal('30')},
            ])
        journal = services._journal(self.co, Journal.Type.OPERATIONS_DIVERSES)
        if journal is None:
            services.seed_journaux(self.co)
            journal = services._journal(self.co, Journal.Type.OPERATIONS_DIVERSES)
        compte_charge = services._assurer_compte(self.co, '6111')
        compte_tresorerie = services._assurer_compte(self.co, '5141')
        ecriture = services.creer_ecriture(
            self.co, journal, date(2026, 4, 1), 'Charge auto-imputée',
            [
                {'compte': compte_charge, 'debit': Decimal('1000'),
                 'credit': Decimal('0'), 'libelle': 'Charge'},
                {'compte': compte_tresorerie, 'debit': Decimal('0'),
                 'credit': Decimal('1000'), 'libelle': 'Charge'},
            ],
            statut=EcritureComptable.Statut.VALIDEE)
        ligne = ecriture.lignes.get(compte__numero='6111')
        ventilation = getattr(ligne, 'ventilation_analytique', None)
        self.assertIsNotNone(ventilation)
        self.assertEqual(ventilation.total_pourcentage, Decimal('100'))

    def test_regle_refuse_si_total_different_100(self):
        with self.assertRaises(ValidationError):
            services.creer_regle_imputation(
                self.co, libelle='Règle invalide', prefixe_compte='6111',
                distributions=[
                    {'centre_cout': self.cc_a, 'pourcentage': Decimal('50')},
                ])

    def test_aucune_regle_ne_touche_pas_les_ecritures_existantes(self):
        journal = services._journal(self.co, Journal.Type.OPERATIONS_DIVERSES)
        if journal is None:
            services.seed_journaux(self.co)
            journal = services._journal(self.co, Journal.Type.OPERATIONS_DIVERSES)
        compte_charge = services._assurer_compte(self.co, '6222')
        compte_tresorerie = services._assurer_compte(self.co, '5141')
        ecriture = services.creer_ecriture(
            self.co, journal, date(2026, 4, 1), 'Charge sans règle',
            [
                {'compte': compte_charge, 'debit': Decimal('500'),
                 'credit': Decimal('0'), 'libelle': 'Charge'},
                {'compte': compte_tresorerie, 'debit': Decimal('0'),
                 'credit': Decimal('500'), 'libelle': 'Charge'},
            ],
            statut=EcritureComptable.Statut.VALIDEE)
        ligne = ecriture.lignes.get(compte__numero='6222')
        self.assertIsNone(getattr(ligne, 'ventilation_analytique', None))
