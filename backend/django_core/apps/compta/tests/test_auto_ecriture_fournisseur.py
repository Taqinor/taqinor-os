"""Tests COMPTA15/COMPTA16 — auto-écritures depuis facture & paiement fournisseur.

Symétrique de l'auto-génération côté vente (FG109) mais côté ACHAT :

  * COMPTA15 — facture fournisseur → débit 61xx (charge) + 3455 (TVA
    récupérable), crédit 4411 (fournisseurs).
  * COMPTA16 — paiement fournisseur → débit 4411 (on solde la dette), crédit
    trésorerie (banque 5141, ou caisse 5161 si mode espèces).

Les documents fournisseur vivent dans ``apps.stock`` ; la compta ne les importe
JAMAIS — les fonctions lisent les attributs publics d'un document dûck-typé
(``_FakeDoc``), exactement comme le posting côté vente. L'auto-génération reste
OFF par défaut (toggle ``COMPTA_AUTO_ECRITURES``) et idempotente.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase, override_settings

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    CompteComptable, EcritureComptable, MappingCompte, PlanComptable,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class _FakeDoc(SimpleNamespace):
    """Stub duck-typé d'un document stock (lu par valeur, jamais importé)."""


class AutoEcritureFactureFournisseurTests(TestCase):
    def setUp(self):
        self.co = make_company('compta-fn', 'Compta Fournisseur')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)

    def _facture(self, id=1):
        return _FakeDoc(
            id=id, company=self.co, reference='FF-202601-0001',
            date_facture=date(2026, 1, 15), fournisseur_id=77,
            montant_ht=Decimal('100'), montant_tva=Decimal('20'),
            montant_ttc=Decimal('120'))

    def test_off_par_defaut_aucune_ecriture(self):
        self.assertFalse(services.auto_ecritures_actif())
        res = services.ecriture_pour_facture_fournisseur(self._facture())
        self.assertIsNone(res)
        self.assertEqual(
            EcritureComptable.objects.filter(company=self.co).count(), 0)

    def test_force_genere_ecriture_achat_equilibree(self):
        ecr = services.ecriture_pour_facture_fournisseur(
            self._facture(), force=True)
        self.assertIsNotNone(ecr)
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.total_credit, Decimal('120'))
        # Charge 6111 débitée HT, TVA récupérable 3455 débitée, 4411 créditée.
        self.assertEqual(
            ecr.lignes.get(compte__numero='6111').debit, Decimal('100'))
        self.assertEqual(
            ecr.lignes.get(compte__numero='3455').debit, Decimal('20'))
        fourn = ecr.lignes.get(compte__numero='4411')
        self.assertEqual(fourn.credit, Decimal('120'))
        self.assertEqual(fourn.tiers_id, 77)
        self.assertEqual(fourn.tiers_type, 'fournisseur')

    def test_source_type_facture_fournisseur(self):
        ecr = services.ecriture_pour_facture_fournisseur(
            self._facture(), force=True)
        self.assertEqual(ecr.source_type, 'facture_fournisseur')

    def test_idempotent_meme_facture(self):
        a = services.ecriture_pour_facture_fournisseur(
            self._facture(id=7), force=True)
        b = services.ecriture_pour_facture_fournisseur(
            self._facture(id=7), force=True)
        self.assertEqual(a.id, b.id)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co,
                source_type='facture_fournisseur').count(), 1)

    def test_sans_tva_deux_jambes(self):
        f = self._facture(id=3)
        f.montant_tva = Decimal('0')
        f.montant_ttc = Decimal('100')
        ecr = services.ecriture_pour_facture_fournisseur(f, force=True)
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.lignes.count(), 2)  # pas de ligne TVA
        self.assertEqual(
            ecr.lignes.get(compte__numero='4411').credit, Decimal('100'))

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_toggle_actif_genere_sans_force(self):
        self.assertTrue(services.auto_ecritures_actif())
        ecr = services.ecriture_pour_facture_fournisseur(self._facture(id=9))
        self.assertIsNotNone(ecr)

    def test_mapping_dc22_route_la_charge(self):
        # DC22 : famille 'transport' → compte 6142 (mappé) plutôt que 6111.
        plan = PlanComptable.objects.get(company=self.co)
        compte_transport, _ = CompteComptable.objects.get_or_create(
            company=self.co, numero='6142',
            defaults={'intitule': 'Transports', 'classe': 6, 'plan': plan})
        MappingCompte.objects.create(
            company=self.co, type_clef=MappingCompte.TypeClef.FAMILLE,
            clef='transport', compte=compte_transport)
        ecr = services.ecriture_pour_facture_fournisseur(
            self._facture(id=11), force=True, famille_charge='transport')
        self.assertEqual(
            ecr.lignes.get(compte__numero='6142').debit, Decimal('100'))
        self.assertFalse(
            ecr.lignes.filter(compte__numero='6111').exists())


class AutoEcriturePaiementFournisseurTests(TestCase):
    def setUp(self):
        self.co = make_company('compta-fn-pay', 'Compta Fournisseur Pay')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)

    def _paiement(self, id=1, mode='virement', montant=Decimal('120')):
        facture = _FakeDoc(
            reference='FF-202601-0001', fournisseur_id=77)
        return _FakeDoc(
            id=id, company=self.co, montant=montant,
            date_paiement=date(2026, 1, 20), mode=mode, facture=facture)

    def test_off_par_defaut(self):
        self.assertIsNone(
            services.ecriture_pour_paiement_fournisseur(self._paiement()))

    def test_virement_va_en_banque(self):
        ecr = services.ecriture_pour_paiement_fournisseur(
            self._paiement(mode='virement'), force=True)
        self.assertTrue(ecr.est_equilibree)
        # 4411 débité (dette soldée), 5141 banque crédité.
        fourn = ecr.lignes.get(compte__numero='4411')
        self.assertEqual(fourn.debit, Decimal('120'))
        self.assertEqual(fourn.tiers_id, 77)
        self.assertEqual(
            ecr.lignes.get(compte__numero='5141').credit, Decimal('120'))

    def test_especes_va_en_caisse(self):
        ecr = services.ecriture_pour_paiement_fournisseur(
            self._paiement(id=2, mode='especes', montant=Decimal('50')),
            force=True)
        self.assertEqual(
            ecr.lignes.get(compte__numero='5161').credit, Decimal('50'))
        self.assertEqual(
            ecr.lignes.get(compte__numero='4411').debit, Decimal('50'))

    def test_idempotent(self):
        a = services.ecriture_pour_paiement_fournisseur(
            self._paiement(id=5), force=True)
        b = services.ecriture_pour_paiement_fournisseur(
            self._paiement(id=5), force=True)
        self.assertEqual(a.id, b.id)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co,
                source_type='paiement_fournisseur').count(), 1)
