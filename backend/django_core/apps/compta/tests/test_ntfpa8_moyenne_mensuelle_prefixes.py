"""NTFPA8 — apps.compta.selectors.moyenne_mensuelle_par_prefixes : moyenne
glissante des N derniers mois réels pour un ensemble de préfixes CGNC."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.compta.models import (
    CompteComptable, EcritureComptable, Journal, LigneEcriture,
)
from apps.compta.selectors import moyenne_mensuelle_par_prefixes


class TestMoyenneMensuellleParPrefixes(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa8-co', defaults={'nom': 'NTFPA8 Co'})
        self.journal = Journal.objects.create(
            company=self.company, code='OD', libelle='Opérations diverses')
        self.compte_622 = CompteComptable.objects.create(
            company=self.company, numero='6226', intitule='Publicité')
        self.compte_701 = CompteComptable.objects.create(
            company=self.company, numero='7111', intitule='Ventes')

    def _ecriture(self, mois, montant_charge):
        ecr = EcritureComptable.objects.create(
            company=self.company, journal=self.journal,
            date_ecriture=date(2027, mois, 10), libelle=f'Charge M{mois}')
        LigneEcriture.objects.create(
            company=self.company, ecriture=ecr, compte=self.compte_622,
            libelle='Charge', debit=montant_charge, credit=Decimal('0'))
        LigneEcriture.objects.create(
            company=self.company, ecriture=ecr, compte=self.compte_701,
            libelle='Contrepartie', debit=Decimal('0'), credit=montant_charge)
        ecr.statut = EcritureComptable.Statut.VALIDEE
        ecr.save(update_fields=['statut'])

    def test_moyenne_3_derniers_mois(self):
        self._ecriture(1, Decimal('300'))
        self._ecriture(2, Decimal('600'))
        self._ecriture(3, Decimal('900'))
        moyenne = moyenne_mensuelle_par_prefixes(
            self.company, ['622'], date(2027, 4, 1), n_mois=3)
        self.assertEqual(moyenne, Decimal('600'))

    def test_zero_sans_mouvement(self):
        moyenne = moyenne_mensuelle_par_prefixes(
            self.company, ['622'], date(2027, 4, 1), n_mois=3)
        self.assertEqual(moyenne, Decimal('0'))

    def test_mois_reference_exclu(self):
        self._ecriture(4, Decimal('99999'))
        moyenne = moyenne_mensuelle_par_prefixes(
            self.company, ['622'], date(2027, 4, 1), n_mois=3)
        self.assertEqual(moyenne, Decimal('0'))
