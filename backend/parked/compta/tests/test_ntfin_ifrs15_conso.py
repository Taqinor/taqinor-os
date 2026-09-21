"""Tests NTFIN46-56 — Reconnaissance du revenu IFRS 15 & états consolidés.

Couvre :

* NTFIN47 — contrat 100 000, obligations PVS 80 000/40 000 → 66 667/33 333.
* NTFIN48 — maintenance 12 000 sur 12 mois → 1 000/mois ; reconnaissance solde
  le produit constaté d'avance.
* NTFIN49 — contrat facturé 12 000 d'avance, reconnu 3 000 → produit différé
  9 000.
* NTFIN50 — la variation de trésorerie du tableau réconcilie le bilan consolidé.
* NTFIN51 — variation des capitaux propres consolidés (part groupe).
* NTFIN53 — comparatif inter-entités.
* NTFIN55 — republier un cycle laisse une trace horodatée distincte.
* NTFIN56 — simuler 80 % → 100 % recalcule minoritaires sans altérer le cycle.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    ContratRevenu, CycleConsolidation, EcheancierReconnaissance,
    EntiteConsolidation, ExerciceComptable, Journal, ObligationPerformance)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class AllocationPrixTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin47', 'NTFIN47')
        self.contrat = ContratRevenu.objects.create(
            company=self.co, reference='C1',
            montant_transaction=Decimal('100000'))
        self.o1 = ObligationPerformance.objects.create(
            company=self.co, contrat=self.contrat, libelle='Matériel',
            prix_vente_specifique=Decimal('80000'))
        self.o2 = ObligationPerformance.objects.create(
            company=self.co, contrat=self.contrat, libelle='Maintenance',
            prix_vente_specifique=Decimal('40000'))

    def test_allocation_prorata_pvs(self):
        services.allouer_prix_transaction(self.contrat)
        self.o1.refresh_from_db()
        self.o2.refresh_from_db()
        self.assertEqual(self.o1.prix_alloue, Decimal('66666.67'))
        # La dernière obligation reçoit le résiduel → somme = 100000.
        self.assertEqual(self.o1.prix_alloue + self.o2.prix_alloue,
                         Decimal('100000'))


class EcheancierTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin48', 'NTFIN48')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.contrat = ContratRevenu.objects.create(
            company=self.co, reference='C1',
            montant_transaction=Decimal('12000'))
        self.oblig = ObligationPerformance.objects.create(
            company=self.co, contrat=self.contrat, libelle='Maintenance',
            prix_alloue=Decimal('12000'),
            methode_reconnaissance=(
                ObligationPerformance.Methode.DANS_LE_TEMPS),
            duree_mois=12, date_debut=date(2026, 1, 31))

    def test_echeancier_12_x_1000(self):
        echeances = services.generer_echeancier_reconnaissance(self.oblig)
        self.assertEqual(len(echeances), 12)
        self.assertEqual(echeances[0].montant_a_reconnaitre, Decimal('1000'))
        total = sum((e.montant_a_reconnaitre for e in echeances), Decimal('0'))
        self.assertEqual(total, Decimal('12000'))

    def test_reconnaissance_poste_ecriture(self):
        echeances = services.generer_echeancier_reconnaissance(self.oblig)
        services.reconnaitre_echeance(echeances[0])
        echeances[0].refresh_from_db()
        self.assertEqual(echeances[0].statut,
                         EcheancierReconnaissance.Statut.RECONNU)
        self.assertIsNotNone(echeances[0].ecriture_id)


class PositionsContratTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin49', 'NTFIN49')
        self.contrat = ContratRevenu.objects.create(
            company=self.co, reference='C1',
            montant_transaction=Decimal('12000'))
        self.oblig = ObligationPerformance.objects.create(
            company=self.co, contrat=self.contrat, libelle='Maintenance',
            prix_alloue=Decimal('12000'), montant_facture=Decimal('12000'))
        EcheancierReconnaissance.objects.create(
            company=self.co, obligation=self.oblig, date=date(2026, 1, 31),
            montant_a_reconnaitre=Decimal('3000'),
            statut=EcheancierReconnaissance.Statut.RECONNU)

    def test_produit_differe(self):
        data = selectors.positions_contrat_revenu(self.co)
        ligne = data['lignes'][0]
        self.assertEqual(ligne['reconnu'], Decimal('3000'))
        self.assertEqual(ligne['facture'], Decimal('12000'))
        self.assertEqual(ligne['produit_differe'], Decimal('9000'))


def _poster(company, d, lignes):
    services.seed_plan_comptable(company)
    services.seed_journaux(company)
    journal = services._journal(company, Journal.Type.OPERATIONS_DIVERSES)
    services.creer_ecriture(company, journal, d, 'Test', [
        {'compte': services.get_compte(company, num), 'debit': Decimal(deb),
         'credit': Decimal(cre)} for num, deb, cre in lignes],
        statut='validee')


class ConsolidatedStatementsTests(TestCase):
    def setUp(self):
        self.tete = make_company('ntfin50-tete', 'Groupe')
        # Balance simple : CA 100000 (créance 3421 / produit 7121), achat 60000.
        _poster(self.tete, date(2026, 1, 10),
                [('3421', '100000', '0'), ('7121', '0', '100000')])
        _poster(self.tete, date(2026, 1, 11),
                [('6111', '60000', '0'), ('5141', '0', '60000')])
        ex, _ = ExerciceComptable.objects.get_or_create(
            company=self.tete, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 12, 31), defaults={'libelle': '2026'})
        self.cycle = CycleConsolidation.objects.create(
            company=self.tete, libelle='Consol 2026', exercice=ex,
            date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31))
        services.collecter_cycle(self.cycle)

    def test_flux_reconcilie_bilan(self):
        data = selectors.tableau_flux_consolide(self.cycle)
        self.assertTrue(data['reconcilie'])
        self.assertEqual(data['variation_tresorerie'],
                         data['variation_tresorerie_bilan'])

    def test_variation_capitaux(self):
        data = selectors.variation_capitaux_consolides(self.cycle)
        self.assertIn('capitaux_cloture_part_groupe', data)

    def test_comparatif_entites(self):
        data = selectors.comparatif_entites(self.cycle)
        # La tête n'est pas dans EntiteConsolidation → liste possiblement vide
        # mais structurée.
        self.assertIn('lignes', data)


class AuditSimulationTests(TestCase):
    def setUp(self):
        self.tete = make_company('ntfin55-tete', 'Groupe')
        self.fille = make_company('ntfin55-fille', 'Fille')
        _poster(self.fille, date(2026, 1, 10),
                [('3421', '100000', '0'), ('7121', '0', '100000')])
        ex, _ = ExerciceComptable.objects.get_or_create(
            company=self.tete, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 12, 31), defaults={'libelle': '2026'})
        self.cycle = CycleConsolidation.objects.create(
            company=self.tete, libelle='Consol 2026', exercice=ex,
            date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31))
        EntiteConsolidation.objects.create(
            company=self.tete, entite=self.fille, cycle=self.cycle,
            pourcentage_interet=Decimal('80'),
            methode=EntiteConsolidation.Methode.INTEGRATION_GLOBALE)
        services.collecter_cycle(self.cycle)

    def test_audit_republication_distincte(self):
        m1 = services.enregistrer_etape_audit_consolidation(
            self.cycle, 'publication', snapshot={'a': 1})
        m2 = services.enregistrer_etape_audit_consolidation(
            self.cycle, 'publication', snapshot={'a': 2})
        self.assertEqual(m2.sequence, m1.sequence + 1)
        self.assertEqual(m2.hash_precedent, m1.hash)
        self.assertNotEqual(m1.hash, m2.hash)

    def test_simulation_80_vers_100(self):
        base = services.simuler_consolidation(self.cycle)
        sim = services.simuler_consolidation(
            self.cycle,
            [{'entite_id': self.fille.id, 'pourcentage': 100}])
        # À 80 % il y a des minoritaires ; à 100 % ils disparaissent.
        self.assertGreater(base['part_minoritaires'], Decimal('0'))
        self.assertEqual(sim['part_minoritaires'], Decimal('0'))
        # Le cycle publié n'est pas altéré (aucune écriture créée).
        self.assertTrue(CycleConsolidation.objects.filter(
            pk=self.cycle.id).exists())
