"""NTMFG10 — Sous-traitance d'opération générique (au-delà de la
sous-traitance chantier existante).

Critère : une opération marquée sous-traitée transfère puis consomme au bon
emplacement, coût intègre la façon, jamais client-facing."""
from decimal import Decimal

from django.test import TestCase

from apps.mrp.models import Gamme, OperationGamme, OrdreFabrication, PosteDeCharge
from apps.mrp.services import (
    confirmer_of, cout_operation_sous_traitee, demarrer_operation, terminer_operation,
)
from apps.stock.models import (
    Fournisseur, KitComposant, KitProduit, Produit, StockEmplacement, TransfertStock,
)
from apps.stock.services import ensure_emplacements, get_or_create_emplacement_soustraitant

from ._fixtures import make_company


def make_produit(company, nom, quantite_stock=0, prix_achat=0):
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=0, tva=20,
        quantite_stock=quantite_stock, prix_achat=prix_achat)


class SousTraitanceTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-ost-1', 'MRP OST 1')
        self.sous_traitant = Fournisseur.objects.create(
            company=self.company, nom='Atelier Façon SARL',
            type=Fournisseur.Type.SERVICE)
        self.composant = make_produit(
            self.company, 'Tôle brute', quantite_stock=100, prix_achat=Decimal('10'))
        self.composite = make_produit(self.company, 'Coffret anodisé')
        self.kit = KitProduit.objects.create(company=self.company, nom='Kit anodisation')
        KitComposant.objects.create(
            kit=self.kit, produit=self.composant, quantite=Decimal('1'))
        self.poste_ost = PosteDeCharge.objects.create(
            company=self.company, code='P-OST', nom='Anodisation',
            type_poste=PosteDeCharge.TypePoste.SOUS_TRAITE,
            sous_traitant=self.sous_traitant)
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme anodisation', produit=self.composite,
            kit_source=self.kit)
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=1, poste_charge=self.poste_ost,
            libelle='Anodisation externe', temps_unitaire_min=Decimal('1'))
        self.of = OrdreFabrication.objects.create(
            company=self.company, produit=self.composite, quantite=5,
            gamme=self.gamme)
        confirmer_of(self.of)
        self.of.refresh_from_db()
        self.operation = self.of.operations.first()

    def test_demarrer_transfere_les_composants_chez_le_sous_traitant(self):
        demarrer_operation(self.operation)
        destination = get_or_create_emplacement_soustraitant(
            self.company, self.sous_traitant.nom)
        self.assertTrue(
            TransfertStock.objects.filter(
                company=self.company, produit=self.composant,
                destination=destination).exists())
        se = StockEmplacement.objects.get(
            produit=self.composant, emplacement=destination)
        self.assertEqual(se.quantite, 5)  # 5 unités x 1 tôle/unité.
        # Le total canonique NE bouge JAMAIS lors d'un simple transfert.
        self.composant.refresh_from_db()
        self.assertEqual(self.composant.quantite_stock, 100)

    def test_terminer_rapatrie_les_composants_et_enregistre_le_cout_facon(self):
        demarrer_operation(self.operation)
        terminer_operation(
            self.operation, quantite_bonne=5, cout_faconnage=Decimal('150'))
        self.operation.refresh_from_db()
        self.assertEqual(self.operation.cout_faconnage, Decimal('150'))

        destination = get_or_create_emplacement_soustraitant(
            self.company, self.sous_traitant.nom)
        se = StockEmplacement.objects.get(
            produit=self.composant, emplacement=destination)
        self.assertEqual(se.quantite, 0)  # Rapatrié -> plus rien chez le sous-traitant.

    def test_cout_operation_inclut_composants_et_faconnage(self):
        demarrer_operation(self.operation)
        terminer_operation(
            self.operation, quantite_bonne=5, cout_faconnage=Decimal('150'))
        self.operation.refresh_from_db()
        # 5 réservées x 10 (prix_achat) = 50 de composants + 150 de façon.
        cout = cout_operation_sous_traitee(self.operation)
        self.assertEqual(cout, Decimal('200'))

    def test_operation_non_sous_traitee_ne_transfere_rien(self):
        poste_normal = PosteDeCharge.objects.create(
            company=self.company, code='P-NORM', nom='Poste normal')
        gamme2 = Gamme.objects.create(
            company=self.company, nom='Gamme normale', produit=self.composite,
            kit_source=self.kit, version=2)
        OperationGamme.objects.create(
            gamme=gamme2, ordre=1, poste_charge=poste_normal, libelle='Op normale',
            temps_unitaire_min=Decimal('1'))
        of2 = OrdreFabrication.objects.create(
            company=self.company, produit=self.composite, quantite=3, gamme=gamme2)
        confirmer_of(of2)
        of2.refresh_from_db()
        op2 = of2.operations.first()
        demarrer_operation(op2)
        self.assertFalse(
            TransfertStock.objects.filter(
                company=self.company, note__icontains='Sous-traitance').exists())


class EmplacementBootstrapTests(TestCase):
    def test_ensure_emplacements_idempotent_pour_le_test(self):
        # Sanity : garantit que le fixture principal existe avant tout
        # transfert (même appel que les services testés ci-dessus).
        company = make_company('mrp-ost-2', 'MRP OST 2')
        principal = ensure_emplacements(company)
        self.assertTrue(principal.is_principal)
