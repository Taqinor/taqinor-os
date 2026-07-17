"""NTFPA7 — dupliquer_cycle_precedent : recopie les lignes de budget d'un
cycle clos vers un nouveau cycle brouillon, montants identiques puis
modifiables."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.fpa.models import Categorie, CycleBudgetaire, Departement, LigneBudgetDepartement
from apps.fpa.services import dupliquer_cycle_precedent


class TestDupliquerCyclePrecedent(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa7-co', defaults={'nom': 'NTFPA7 Co'})
        self.cycle_2026 = CycleBudgetaire.objects.create(
            company=self.company, nom='Budget 2026',
            date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31),
            statut=CycleBudgetaire.Statut.CLOS)
        self.dept = Departement.objects.create(
            company=self.company, code='IT', nom='IT')
        for mois in range(1, 13):
            LigneBudgetDepartement.objects.create(
                company=self.company, cycle=self.cycle_2026, departement=self.dept,
                categorie=Categorie.IT, mois=mois, montant_prevu=Decimal('1000'))

    def test_duplique_les_12_mois_en_brouillon_editable(self):
        cycle_2027 = dupliquer_cycle_precedent(
            self.company, self.cycle_2026, 'Budget 2027')
        self.assertEqual(cycle_2027.statut, CycleBudgetaire.Statut.BROUILLON)
        lignes = LigneBudgetDepartement.objects.filter(cycle=cycle_2027)
        self.assertEqual(lignes.count(), 12)
        self.assertTrue(all(ligne.montant_prevu == Decimal('1000') for ligne in lignes))

        # Cycle 2027 est brouillon (jamais clos) : la ligne reste éditable.
        ligne = lignes.first()
        ligne.montant_prevu = Decimal('1500')
        ligne.save()
        ligne.refresh_from_db()
        self.assertEqual(ligne.montant_prevu, Decimal('1500'))

        # Le cycle source reste inchangé (jamais écrasé).
        source_lignes = LigneBudgetDepartement.objects.filter(cycle=self.cycle_2026)
        self.assertTrue(all(li.montant_prevu == Decimal('1000') for li in source_lignes))
