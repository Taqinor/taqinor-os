"""NTFPA19 — variance_budget_vs_reel : un département en dépassement de +10 %
sur une catégorie est visuellement distinct (drapeau depassement=True)."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.compta.models import (
    CompteComptable, EcritureComptable, Journal, LigneEcriture,
)
from apps.fpa.models import (
    Categorie, CycleBudgetaire, Departement, LigneBudgetDepartement,
    MappingCategorieCompte,
)
from apps.fpa.selectors import variance_budget_vs_reel


class TestVarianceBudgetVsReel(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa19-co', defaults={'nom': 'NTFPA19 Co'})
        self.cycle = CycleBudgetaire.objects.create(
            company=self.company, nom='Budget 2027',
            date_debut=date(2027, 1, 1), date_fin=date(2027, 12, 31))
        self.dept = Departement.objects.create(
            company=self.company, code='MKT', nom='Marketing')
        # Budget marketing janvier = 1000.
        LigneBudgetDepartement.objects.create(
            company=self.company, cycle=self.cycle, departement=self.dept,
            categorie=Categorie.MARKETING, mois=1, montant_prevu=Decimal('1000'))
        # Mapping marketing → 622.
        MappingCategorieCompte.objects.create(
            company=self.company, categorie=Categorie.MARKETING,
            compte_cgnc_prefixe='622')
        # Réel comptable janvier = 1500 (dépassement +50 %).
        self.journal = Journal.objects.create(
            company=self.company, code='OD', libelle='OD')
        self.c622 = CompteComptable.objects.create(
            company=self.company, numero='6226', intitule='Publicité')
        self.c701 = CompteComptable.objects.create(
            company=self.company, numero='7111', intitule='Ventes')
        ecr = EcritureComptable.objects.create(
            company=self.company, journal=self.journal,
            date_ecriture=date(2027, 1, 15), libelle='Pub')
        LigneEcriture.objects.create(
            company=self.company, ecriture=ecr, compte=self.c622,
            debit=Decimal('1500'), credit=Decimal('0'))
        LigneEcriture.objects.create(
            company=self.company, ecriture=ecr, compte=self.c701,
            debit=Decimal('0'), credit=Decimal('1500'))
        ecr.statut = EcritureComptable.Statut.VALIDEE
        ecr.save(update_fields=['statut'])

    def test_depassement_flague(self):
        rows = variance_budget_vs_reel(self.company, self.cycle, 1)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['prevu'], Decimal('1000'))
        self.assertEqual(row['reel'], Decimal('1500'))
        self.assertTrue(row['depassement'])
        self.assertEqual(row['ecart_prevu_reel_eur'], Decimal('500'))
