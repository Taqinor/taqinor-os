"""Tests NTFIN20-25 — Moteur d'allocations & comptabilité d'engagement.

Couvre :

* NTFIN20 — une clé de répartition 50/30/20 valide (Σ = 100 %) ; une clé
  déséquilibrée est refusée.
* NTFIN21 — 90 000 déversés sur clé 50/30/20 postent 45 000/27 000/18 000 aux
  centres cibles, réversible.
* NTFIN22 — la commande d'allocations récurrentes est idempotente par période.
* NTFIN23 — engager 100 000 puis liquider 60 000 laisse un résiduel de 40 000.
* NTFIN24 — le disponible intègre les engagements ; un dépassement bloquant est
  refusé.
* NTFIN25 — engagé + réalisé + disponible = budget par ligne.
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    AllocationRecurrente, Budget, BudgetLigne, CentreCout, CleRepartition,
    EngagementComptable, LigneCleRepartition, RunAllocation)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class CleRepartitionTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin20', 'NTFIN20')
        self.c1 = CentreCout.objects.create(company=self.co, code='A', libelle='A')
        self.c2 = CentreCout.objects.create(company=self.co, code='B', libelle='B')
        self.c3 = CentreCout.objects.create(company=self.co, code='C', libelle='C')

    def _cle_50_30_20(self):
        cle = CleRepartition.objects.create(
            company=self.co, code='EFF', libelle='Effectifs',
            type_cle=CleRepartition.Type.STATISTIQUE,
            base=CleRepartition.Base.EFFECTIF)
        for centre, coef in ((self.c1, 50), (self.c2, 30), (self.c3, 20)):
            LigneCleRepartition.objects.create(
                company=self.co, cle=cle, centre_cout=centre,
                coefficient=Decimal(coef))
        return cle

    def test_cle_valide_somme_100(self):
        cle = self._cle_50_30_20()
        self.assertEqual(cle.total_coefficients, Decimal('100'))
        self.assertIs(services.valider_cle_repartition(cle), cle)

    def test_cle_desequilibree_refusee(self):
        cle = CleRepartition.objects.create(
            company=self.co, code='X', libelle='X')
        LigneCleRepartition.objects.create(
            company=self.co, cle=cle, centre_cout=self.c1,
            coefficient=Decimal('60'))
        with self.assertRaises(ValidationError):
            services.valider_cle_repartition(cle)


class AllocationEngineTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin21', 'NTFIN21')
        self.c1 = CentreCout.objects.create(company=self.co, code='A', libelle='A')
        self.c2 = CentreCout.objects.create(company=self.co, code='B', libelle='B')
        self.c3 = CentreCout.objects.create(company=self.co, code='C', libelle='C')
        self.cle = CleRepartition.objects.create(
            company=self.co, code='FG', libelle='Frais généraux')
        for centre, coef in ((self.c1, 50), (self.c2, 30), (self.c3, 20)):
            LigneCleRepartition.objects.create(
                company=self.co, cle=self.cle, centre_cout=centre,
                coefficient=Decimal(coef))
        services.seed_journaux(self.co)
        services._assurer_compte(self.co, '6111')

    def test_executer_allocation_repartit_50_30_20(self):
        run = services.executer_allocation(
            self.co, '6111', self.cle, date(2026, 3, 31),
            montant=Decimal('90000'))
        self.assertEqual(run.montant_reparti, Decimal('90000'))
        # Les lignes débitrices par centre = 45000/27000/18000.
        parts = {}
        for lg in run.ecriture.lignes.all():
            if lg.debit and lg.centre_cout_id:
                parts[lg.centre_cout.code] = lg.debit
        self.assertEqual(parts['A'], Decimal('45000.00'))
        self.assertEqual(parts['B'], Decimal('27000.00'))
        self.assertEqual(parts['C'], Decimal('18000.00'))
        # L'écriture est équilibrée.
        total_debit = sum((lg.debit for lg in run.ecriture.lignes.all()),
                          Decimal('0'))
        total_credit = sum((lg.credit for lg in run.ecriture.lignes.all()),
                           Decimal('0'))
        self.assertEqual(total_debit, total_credit)

    def test_allocation_reversible(self):
        run = services.executer_allocation(
            self.co, '6111', self.cle, date(2026, 3, 31),
            montant=Decimal('90000'))
        services.reverser_allocation(run)
        run.refresh_from_db()
        self.assertEqual(run.statut, RunAllocation.Statut.REVERSEE)


class AllocationRecurrenteTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin22', 'NTFIN22')
        self.c1 = CentreCout.objects.create(company=self.co, code='A', libelle='A')
        self.c2 = CentreCout.objects.create(company=self.co, code='B', libelle='B')
        self.cle = CleRepartition.objects.create(
            company=self.co, code='FG', libelle='FG')
        LigneCleRepartition.objects.create(
            company=self.co, cle=self.cle, centre_cout=self.c1,
            coefficient=Decimal('60'))
        LigneCleRepartition.objects.create(
            company=self.co, cle=self.cle, centre_cout=self.c2,
            coefficient=Decimal('40'))
        services.seed_journaux(self.co)
        services._assurer_compte(self.co, '6111')
        self.rec = AllocationRecurrente.objects.create(
            company=self.co, cle=self.cle, compte_source='6111',
            periodicite=AllocationRecurrente.Periodicite.MENSUELLE,
            prochaine_echeance=date(2026, 1, 31))

    def test_idempotent_par_periode(self):
        # Premier passage : exécute janvier.
        r1 = services.generer_allocations_recurrentes(
            self.co, jusqua=date(2026, 1, 31))
        # Pas de solde → montant nul → ignorée (pas d'écriture), mais l'échéance
        # avance. On force un solde débiteur pour janvier via une allocation
        # avec montant explicite : on teste plutôt la dédup directement.
        RunAllocation.objects.create(
            company=self.co, cle=self.cle, compte_source='6111',
            periode=date(2026, 2, 28), montant_reparti=Decimal('1000'),
            statut=RunAllocation.Statut.EXECUTEE)
        self.rec.prochaine_echeance = date(2026, 2, 28)
        self.rec.save(update_fields=['prochaine_echeance'])
        r2 = services.generer_allocations_recurrentes(
            self.co, jusqua=date(2026, 2, 28))
        # Février déjà exécuté → ignoré (idempotent), aucun doublon.
        ignorees_fev = [i for i in r2['ignorees']
                        if i['periode'] == '2026-02-28']
        self.assertTrue(ignorees_fev)
        self.assertEqual(
            RunAllocation.objects.filter(
                compte_source='6111', periode=date(2026, 2, 28)).count(), 1)
        self.assertIsInstance(r1, dict)


class EngagementTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin23', 'NTFIN23')
        self.cc = CentreCout.objects.create(
            company=self.co, code='CH1', libelle='Chantier 1')
        self.compte = services._assurer_compte(self.co, '6111')

    def test_engager_puis_liquider_residuel(self):
        eng = services.engager(
            self.co, compte=self.compte, montant=Decimal('100000'),
            date_engagement=date(2026, 3, 1), centre_cout=self.cc)
        self.assertEqual(eng.statut, EngagementComptable.Statut.ENGAGE)
        services.liquider(eng, Decimal('60000'))
        eng.refresh_from_db()
        self.assertEqual(eng.montant_residuel, Decimal('40000'))
        self.assertEqual(eng.statut,
                         EngagementComptable.Statut.PARTIELLEMENT_LIQUIDE)

    def test_liquidation_totale_solde(self):
        eng = services.engager(
            self.co, compte=self.compte, montant=Decimal('100000'),
            date_engagement=date(2026, 3, 1))
        services.liquider(eng, Decimal('100000'))
        eng.refresh_from_db()
        self.assertEqual(eng.statut, EngagementComptable.Statut.SOLDE)

    def test_liquidation_depassement_refusee(self):
        eng = services.engager(
            self.co, compte=self.compte, montant=Decimal('100000'),
            date_engagement=date(2026, 3, 1))
        with self.assertRaises(ValidationError):
            services.liquider(eng, Decimal('120000'))


class DisponibleBudgetaireTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin24', 'NTFIN24')
        self.cc = CentreCout.objects.create(
            company=self.co, code='CH1', libelle='Chantier 1')
        self.compte = services._assurer_compte(self.co, '6111')

    def _budget(self, controle=Budget.Controle.WARNING, montant=Decimal('12000')):
        budget = Budget.objects.create(
            company=self.co, annee=2026, libelle='B2026', controle=controle)
        BudgetLigne.objects.create(
            company=self.co, budget=budget, compte=self.compte,
            centre_cout=self.cc, m01=montant)
        return budget

    def test_disponible_integre_engagement(self):
        self._budget(montant=Decimal('12000'))
        services.engager(
            self.co, compte=self.compte, montant=Decimal('5000'),
            date_engagement=date(2026, 3, 1), centre_cout=self.cc)
        bl = BudgetLigne.objects.get(compte=self.compte, centre_cout=self.cc)
        d = selectors.disponible_budgetaire(bl)
        self.assertEqual(d['budget'], Decimal('12000'))
        self.assertEqual(d['engage'], Decimal('5000'))
        self.assertEqual(d['disponible'], Decimal('7000'))

    def test_engagement_bloquant_depassement_refuse(self):
        self._budget(controle=Budget.Controle.BLOQUANT, montant=Decimal('1000'))
        check = services.verifier_disponible_engagement(
            self.co, compte=self.compte, centre_cout=self.cc,
            montant=Decimal('5000'), periode=date(2026, 3, 1))
        self.assertEqual(check['statut'], 'blocage')

    def test_execution_budgetaire_invariant(self):
        self._budget(montant=Decimal('12000'))
        services.engager(
            self.co, compte=self.compte, montant=Decimal('5000'),
            date_engagement=date(2026, 3, 1), centre_cout=self.cc)
        etat = selectors.execution_budgetaire(self.co, 2026)
        ligne = etat['lignes'][0]
        self.assertEqual(
            ligne['engage'] + ligne['realise'] + ligne['disponible'],
            ligne['budget'])
