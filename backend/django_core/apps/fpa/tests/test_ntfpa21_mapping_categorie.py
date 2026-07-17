"""NTFPA21 — MappingCategorieCompte : changer le mapping recalcule la variance
sans migration de code (les préfixes sont lus depuis la table, pas codés en
dur)."""
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
from apps.fpa.selectors import prefixes_categorie, variance_budget_vs_reel


class TestMappingCategorieCompte(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa21-co', defaults={'nom': 'NTFPA21 Co'})
        self.cycle = CycleBudgetaire.objects.create(
            company=self.company, nom='Budget 2027',
            date_debut=date(2027, 1, 1), date_fin=date(2027, 12, 31))
        self.dept = Departement.objects.create(
            company=self.company, code='MKT', nom='Marketing')
        LigneBudgetDepartement.objects.create(
            company=self.company, cycle=self.cycle, departement=self.dept,
            categorie=Categorie.MARKETING, mois=1, montant_prevu=Decimal('1000'))
        self.journal = Journal.objects.create(
            company=self.company, code='OD', libelle='OD')
        self.c701 = CompteComptable.objects.create(
            company=self.company, numero='7111', intitule='Ventes')
        # Charge sur compte 622 = 800.
        self.c622 = CompteComptable.objects.create(
            company=self.company, numero='6221', intitule='Annonces')
        self._charge(self.c622, Decimal('800'))

    def _charge(self, compte, montant):
        ecr = EcritureComptable.objects.create(
            company=self.company, journal=self.journal,
            date_ecriture=date(2027, 1, 10), libelle='X')
        LigneEcriture.objects.create(
            company=self.company, ecriture=ecr, compte=compte,
            debit=montant, credit=Decimal('0'))
        LigneEcriture.objects.create(
            company=self.company, ecriture=ecr, compte=self.c701,
            debit=Decimal('0'), credit=montant)
        ecr.statut = EcritureComptable.Statut.VALIDEE
        ecr.save(update_fields=['statut'])

    def test_repli_par_defaut_sur_622(self):
        # Sans ligne de mapping, le repli marketing = ('622',).
        self.assertEqual(prefixes_categorie(self.company, Categorie.MARKETING), ('622',))
        rows = variance_budget_vs_reel(self.company, self.cycle, 1)
        self.assertEqual(rows[0]['reel'], Decimal('800'))

    def test_changement_mapping_recalcule_sans_code(self):
        # Ajoute une charge sur 613 = 500, et map marketing → 613.
        c613 = CompteComptable.objects.create(
            company=self.company, numero='6135', intitule='Loc.')
        self._charge(c613, Decimal('500'))
        MappingCategorieCompte.objects.create(
            company=self.company, categorie=Categorie.MARKETING,
            compte_cgnc_prefixe='613')
        self.assertEqual(prefixes_categorie(self.company, Categorie.MARKETING), ('613',))
        rows = variance_budget_vs_reel(self.company, self.cycle, 1)
        self.assertEqual(rows[0]['reel'], Decimal('500'))
