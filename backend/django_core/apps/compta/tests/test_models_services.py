"""Tests modèles + services de la Comptabilité générale (FG107-FG114, FG121).

Couvre : seeding idempotent du plan CGNC & des journaux, garantie d'équilibre
de l'écriture en partie double (clean + service), auto-génération depuis les
documents (idempotence + toggle OFF par défaut), et les états de synthèse
(grand livre, balance, lettrage, CPC, bilan).
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    CompteComptable, CompteTresorerie, EcritureComptable, Journal,
    LigneEcriture, PlanComptable,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class PlanComptableSeedTests(TestCase):
    def setUp(self):
        self.co = make_company('compta-seed', 'Compta Seed')

    def test_seed_cree_plan_et_comptes_cles(self):
        plan = services.seed_plan_comptable(self.co)
        self.assertEqual(plan.code, 'CGNC')
        # Comptes clés exigés par FG107.
        for numero in ('3421', '4411', '4455', '7121', '6111', '5141', '5161'):
            self.assertTrue(
                CompteComptable.objects.filter(
                    company=self.co, numero=numero).exists(),
                f'compte {numero} manquant')

    def test_seed_classes_deduites(self):
        services.seed_plan_comptable(self.co)
        c = CompteComptable.objects.get(company=self.co, numero='7121')
        self.assertEqual(c.classe, 7)
        c2 = CompteComptable.objects.get(company=self.co, numero='3421')
        self.assertEqual(c2.classe, 3)
        self.assertTrue(c2.est_tiers)
        self.assertTrue(c2.lettrable)

    def test_seed_idempotent(self):
        services.seed_plan_comptable(self.co)
        n1 = CompteComptable.objects.filter(company=self.co).count()
        services.seed_plan_comptable(self.co)
        n2 = CompteComptable.objects.filter(company=self.co).count()
        self.assertEqual(n1, n2)
        self.assertEqual(PlanComptable.objects.filter(company=self.co).count(), 1)

    def test_seed_journaux_idempotent(self):
        services.seed_journaux(self.co)
        services.seed_journaux(self.co)
        self.assertEqual(Journal.objects.filter(company=self.co).count(), 5)
        for code in ('VTE', 'ACH', 'BNK', 'CSH', 'OD'):
            self.assertTrue(
                Journal.objects.filter(company=self.co, code=code).exists())


class EcritureEquilibreTests(TestCase):
    def setUp(self):
        self.co = make_company('compta-ecr', 'Compta Ecr')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.journal = Journal.objects.get(company=self.co, code='VTE')
        self.clients = services.get_compte(self.co, '3421')
        self.ventes = services.get_compte(self.co, '7121')
        self.tva = services.get_compte(self.co, '4455')

    def test_ecriture_equilibree_creee(self):
        ecr = services.creer_ecriture(
            self.co, self.journal, date(2026, 1, 10), 'Test équilibre',
            [
                {'compte': self.clients, 'debit': Decimal('120'),
                 'credit': Decimal('0')},
                {'compte': self.ventes, 'debit': Decimal('0'),
                 'credit': Decimal('100')},
                {'compte': self.tva, 'debit': Decimal('0'),
                 'credit': Decimal('20')},
            ])
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.total_debit, Decimal('120'))
        self.assertEqual(ecr.total_credit, Decimal('120'))
        self.assertEqual(ecr.lignes.count(), 3)

    def test_ecriture_desequilibree_rejetee(self):
        with self.assertRaises(ValidationError):
            services.creer_ecriture(
                self.co, self.journal, date(2026, 1, 10), 'Déséquilibrée',
                [
                    {'compte': self.clients, 'debit': Decimal('120'),
                     'credit': Decimal('0')},
                    {'compte': self.ventes, 'debit': Decimal('0'),
                     'credit': Decimal('90')},
                ])
        # Transaction atomique : rien n'a été créé.
        self.assertEqual(
            EcritureComptable.objects.filter(company=self.co).count(), 0)

    def test_clean_modele_rejette_desequilibre(self):
        ecr = EcritureComptable.objects.create(
            company=self.co, journal=self.journal,
            date_ecriture=date(2026, 1, 10), libelle='x')
        LigneEcriture.objects.create(
            company=self.co, ecriture=ecr, compte=self.clients,
            debit=Decimal('100'), credit=Decimal('0'))
        LigneEcriture.objects.create(
            company=self.co, ecriture=ecr, compte=self.ventes,
            debit=Decimal('0'), credit=Decimal('50'))
        with self.assertRaises(ValidationError):
            ecr.clean()

    def test_ligne_debit_et_credit_interdit(self):
        ligne = LigneEcriture(
            company=self.co,
            ecriture=EcritureComptable.objects.create(
                company=self.co, journal=self.journal,
                date_ecriture=date(2026, 1, 1), libelle='x'),
            compte=self.clients, debit=Decimal('10'), credit=Decimal('10'))
        with self.assertRaises(ValidationError):
            ligne.clean()


class _FakeDoc(SimpleNamespace):
    """Stub duck-typé d'un document ventes (lu par valeur, jamais importé)."""


class AutoGenerationTests(TestCase):
    def setUp(self):
        self.co = make_company('compta-auto', 'Compta Auto')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)

    def _facture(self, id=1):
        return _FakeDoc(
            id=id, company=self.co, reference='FAC-202601-0001',
            date_emission=date(2026, 1, 15), client_id=42,
            total_ht=Decimal('100'), total_tva=Decimal('20'),
            total_ttc=Decimal('120'))

    def test_off_par_defaut_aucune_ecriture(self):
        # COMPTA_AUTO_ECRITURES non posé → OFF → None, rien créé.
        self.assertFalse(services.auto_ecritures_actif())
        res = services.ecriture_pour_facture(self._facture())
        self.assertIsNone(res)
        self.assertEqual(
            EcritureComptable.objects.filter(company=self.co).count(), 0)

    def test_force_genere_ecriture_facture_equilibree(self):
        ecr = services.ecriture_pour_facture(self._facture(), force=True)
        self.assertIsNotNone(ecr)
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.total_debit, Decimal('120'))
        # Débit clients 120 ; crédit ventes 100 + TVA 20.
        clients = ecr.lignes.get(compte__numero='3421')
        self.assertEqual(clients.debit, Decimal('120'))
        self.assertEqual(clients.tiers_id, 42)
        self.assertEqual(
            ecr.lignes.get(compte__numero='7121').credit, Decimal('100'))
        self.assertEqual(
            ecr.lignes.get(compte__numero='4455').credit, Decimal('20'))

    def test_idempotent_meme_facture(self):
        a = services.ecriture_pour_facture(self._facture(id=7), force=True)
        b = services.ecriture_pour_facture(self._facture(id=7), force=True)
        self.assertEqual(a.id, b.id)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co, source_type='facture').count(), 1)

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_toggle_actif_genere_sans_force(self):
        self.assertTrue(services.auto_ecritures_actif())
        ecr = services.ecriture_pour_facture(self._facture(id=9))
        self.assertIsNotNone(ecr)

    def test_paiement_especes_va_en_caisse(self):
        facture = self._facture()
        paiement = _FakeDoc(
            id=1, company=self.co, montant=Decimal('120'),
            date_paiement=date(2026, 1, 20), mode='especes', facture=facture)
        ecr = services.ecriture_pour_paiement(paiement, force=True)
        self.assertTrue(ecr.est_equilibree)
        # Caisse 5161 débitée, clients 3421 crédités.
        self.assertEqual(
            ecr.lignes.get(compte__numero='5161').debit, Decimal('120'))
        self.assertEqual(
            ecr.lignes.get(compte__numero='3421').credit, Decimal('120'))

    def test_paiement_virement_va_en_banque(self):
        facture = self._facture()
        paiement = _FakeDoc(
            id=2, company=self.co, montant=Decimal('50'),
            date_paiement=date(2026, 1, 20), mode='virement', facture=facture)
        ecr = services.ecriture_pour_paiement(paiement, force=True)
        self.assertEqual(
            ecr.lignes.get(compte__numero='5141').debit, Decimal('50'))

    def test_avoir_contrepasse_la_vente(self):
        avoir = _FakeDoc(
            id=1, company=self.co, reference='AV-202601-0001',
            date_emission=date(2026, 1, 25), client_id=42,
            total_ht=Decimal('100'), total_tva=Decimal('20'),
            total_ttc=Decimal('120'))
        ecr = services.ecriture_pour_avoir(avoir, force=True)
        self.assertTrue(ecr.est_equilibree)
        # Inverse de la facture : ventes & TVA débitées, clients crédités.
        self.assertEqual(
            ecr.lignes.get(compte__numero='7121').debit, Decimal('100'))
        self.assertEqual(
            ecr.lignes.get(compte__numero='3421').credit, Decimal('120'))


class EtatsTests(TestCase):
    """Grand livre / balance / lettrage / CPC / bilan (FG110-114)."""

    def setUp(self):
        self.co = make_company('compta-etats', 'Compta Etats')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        # Facture (vente 100 HT + 20 TVA) puis encaissement 120.
        facture = _FakeDoc(
            id=1, company=self.co, reference='FAC-1',
            date_emission=date(2026, 1, 10), client_id=1,
            total_ht=Decimal('100'), total_tva=Decimal('20'),
            total_ttc=Decimal('120'))
        services.ecriture_pour_facture(facture, force=True)
        paiement = _FakeDoc(
            id=1, company=self.co, montant=Decimal('120'),
            date_paiement=date(2026, 1, 15), mode='virement', facture=facture)
        services.ecriture_pour_paiement(paiement, force=True)

    def test_balance_equilibree(self):
        bal = selectors.balance_generale(self.co)
        self.assertTrue(bal['equilibree'])
        self.assertEqual(bal['total_debit'], bal['total_credit'])

    def test_grand_livre_solde_courant(self):
        gl = selectors.grand_livre(self.co)
        comptes = {b['numero']: b for b in gl}
        # 3421 clients : débit 120 (facture) puis crédit 120 (paiement) → solde 0.
        self.assertEqual(comptes['3421']['solde'], Decimal('0'))
        # 5141 banque : débit 120 → solde débiteur 120.
        self.assertEqual(comptes['5141']['solde'], Decimal('120'))

    def test_cpc_resultat(self):
        cpc = selectors.cpc(self.co)
        # 100 de produit, 0 charge → bénéfice 100.
        self.assertEqual(cpc['total_produits'], Decimal('100'))
        self.assertEqual(cpc['resultat'], Decimal('100'))

    def test_bilan_equilibre(self):
        bilan = selectors.bilan(self.co)
        # Actif = banque 120 ; passif = TVA 20 + résultat 100 → équilibré.
        self.assertTrue(bilan['equilibre'])
        self.assertEqual(bilan['total_actif'], Decimal('120'))

    def test_lettrage_equilibre_requis(self):
        clients = services.get_compte(self.co, '3421')
        lignes = selectors.lignes_non_lettrees(self.co, clients)
        ids = [l.id for l in lignes]
        # Les deux lignes 3421 (débit 120 / crédit 120) soldent → lettrables.
        n = selectors.lettrer(self.co, ids, 'A')
        self.assertEqual(n, 2)
        self.assertEqual(selectors.encours_tiers(self.co, clients), Decimal('0'))

    def test_lettrage_desequilibre_refuse(self):
        clients = services.get_compte(self.co, '3421')
        lignes = selectors.lignes_non_lettrees(self.co, clients)
        # Une seule ligne (débit 120) ne solde pas → refus.
        with self.assertRaises(ValueError):
            selectors.lettrer(self.co, [lignes[0].id], 'B')


class CompanyIsolationModelTests(TestCase):
    def test_comptes_isoles_par_societe(self):
        a = make_company('iso-a', 'Iso A')
        b = make_company('iso-b', 'Iso B')
        services.seed_plan_comptable(a)
        services.seed_plan_comptable(b)
        # Chaque société a son propre 3421 (numéro unique PAR société).
        self.assertEqual(
            CompteComptable.objects.filter(numero='3421').count(), 2)
        self.assertNotEqual(
            services.get_compte(a, '3421').id,
            services.get_compte(b, '3421').id)


class CompteTresorerieTests(TestCase):
    def test_compte_tresorerie_lie_classe_5(self):
        co = make_company('treso', 'Treso')
        services.seed_plan_comptable(co)
        banque = services.get_compte(co, '5141')
        ct = CompteTresorerie.objects.create(
            company=co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='Compte courant', banque='Attijari',
            compte_comptable=banque)
        self.assertEqual(ct.compte_comptable.classe, 5)
        self.assertEqual(str(ct), 'Banque — Compte courant')
