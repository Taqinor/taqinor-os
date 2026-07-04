"""XSTK8 — Contrôle du stock négatif (garde configurable).

Couvre :
  * un retour fournisseur qui ferait passer le stock sous zéro est refusé
    par défaut (`AchatsParametres.stock_negatif_autorise=False`) ;
  * le même retour passe si le réglage l'autorise explicitement ;
  * la consommation d'assemblage (kitting, `consommer_et_produire_
    assemblage`) respecte le même garde sur les composants ;
  * `transfer_stock` garde EXACTEMENT son comportement existant (refuse déjà
    une quantité insuffisante, avec ou sans le nouveau réglage) — pas de
    régression ;
  * `check_negative_stock_guard` ne fait rien quand le résultat reste ≥ 0
    (comportement historique inchangé, y compris pour du stock déjà négatif
    en lecture).

Run:
    python manage.py test apps.stock.test_xstk8_stock_negatif -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    AchatsParametres, EmplacementStock, Fournisseur, LigneRetourFournisseur,
    Produit, RetourFournisseur,
)
from apps.stock.services import (
    apply_retour_fournisseur, check_negative_stock_guard,
    consommer_et_produire_assemblage, ensure_emplacements, transfer_stock,
)

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


class Xstk8Base(TestCase):
    def setUp(self):
        self.company = _company('xstk8-co')
        self.user = _user(self.company, 'xstk8-user')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur X8')


class TestGuardHelper(Xstk8Base):
    def test_resultat_positif_ne_leve_rien(self):
        check_negative_stock_guard(self.company, 10, 5)  # ne doit pas lever

    def test_resultat_negatif_refuse_par_defaut(self):
        with self.assertRaises(ValueError):
            check_negative_stock_guard(self.company, 3, -2)

    def test_resultat_negatif_autorise_si_flag_actif(self):
        parametres = AchatsParametres.for_company(self.company)
        parametres.stock_negatif_autorise = True
        parametres.save()
        check_negative_stock_guard(self.company, 3, -2)  # ne doit pas lever


class TestRetourFournisseurGuard(Xstk8Base):
    def _retour(self, produit, qte):
        retour = RetourFournisseur.objects.create(
            company=self.company, reference='RF-XSTK8-1',
            fournisseur=self.fournisseur)
        LigneRetourFournisseur.objects.create(
            retour=retour, produit=produit, quantite=qte,
            motif='défectueux')
        return retour

    def test_retour_au_dela_du_stock_refuse_par_defaut(self):
        produit = Produit.objects.create(
            company=self.company, nom='Câble X8', sku='CAB-X8',
            prix_vente=Decimal('15'), quantite_stock=3)
        retour = self._retour(produit, 5)
        with self.assertRaises(ValueError):
            apply_retour_fournisseur(retour, self.user)
        produit.refresh_from_db()
        self.assertEqual(produit.quantite_stock, 3)  # inchangé

    def test_retour_au_dela_du_stock_autorise_si_flag_actif(self):
        parametres = AchatsParametres.for_company(self.company)
        parametres.stock_negatif_autorise = True
        parametres.save()
        produit = Produit.objects.create(
            company=self.company, nom='Câble X8b', sku='CAB-X8B',
            prix_vente=Decimal('15'), quantite_stock=3)
        retour = self._retour(produit, 5)
        apply_retour_fournisseur(retour, self.user)
        produit.refresh_from_db()
        self.assertEqual(produit.quantite_stock, -2)

    def test_retour_dans_la_limite_du_stock_reste_ok(self):
        produit = Produit.objects.create(
            company=self.company, nom='Câble X8c', sku='CAB-X8C',
            prix_vente=Decimal('15'), quantite_stock=10)
        retour = self._retour(produit, 4)
        apply_retour_fournisseur(retour, self.user)
        produit.refresh_from_db()
        self.assertEqual(produit.quantite_stock, 6)


class TestAssemblageGuard(Xstk8Base):
    def test_consommation_composant_insuffisant_refusee(self):
        composant = Produit.objects.create(
            company=self.company, nom='Vis X8', sku='VIS-X8',
            prix_vente=Decimal('1'), quantite_stock=2)
        composite = Produit.objects.create(
            company=self.company, nom='Kit X8', sku='KIT-X8',
            prix_vente=Decimal('100'), quantite_stock=0)

        class _Ligne:
            def __init__(self, produit, quantite):
                self.produit = produit
                self.quantite = quantite

        with self.assertRaises(ValueError):
            consommer_et_produire_assemblage(
                company=self.company, kit=type('K', (), {'id': 1})(),
                composants=[_Ligne(composant, 5)],
                produit_compose=composite, quantite_produite=1,
                reference='ASM-X8-1', user=self.user)
        composant.refresh_from_db()
        self.assertEqual(composant.quantite_stock, 2)  # inchangé

    def test_consommation_suffisante_reste_ok(self):
        composant = Produit.objects.create(
            company=self.company, nom='Vis X8b', sku='VIS-X8B',
            prix_vente=Decimal('1'), quantite_stock=10)
        composite = Produit.objects.create(
            company=self.company, nom='Kit X8b', sku='KIT-X8B',
            prix_vente=Decimal('100'), quantite_stock=0)

        class _Ligne:
            def __init__(self, produit, quantite):
                self.produit = produit
                self.quantite = quantite

        consommer_et_produire_assemblage(
            company=self.company, kit=type('K', (), {'id': 2})(),
            composants=[_Ligne(composant, 3)],
            produit_compose=composite, quantite_produite=1,
            reference='ASM-X8-2', user=self.user)
        composant.refresh_from_db()
        composite.refresh_from_db()
        self.assertEqual(composant.quantite_stock, 7)
        self.assertEqual(composite.quantite_stock, 1)


class TestTransferStockUnchanged(Xstk8Base):
    def test_transfer_stock_insuffisant_toujours_refuse(self):
        # Non-régression : transfer_stock a DÉJÀ son propre garde, inchangé
        # que stock_negatif_autorise soit actif ou non.
        ensure_emplacements(self.company)
        depot_b = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt B X8', is_principal=False,
            ordre=20)
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur X8', sku='OND-X8',
            prix_vente=Decimal('2000'), quantite_stock=2)
        principal = EmplacementStock.objects.get(
            company=self.company, is_principal=True)
        parametres = AchatsParametres.for_company(self.company)
        parametres.stock_negatif_autorise = True
        parametres.save()
        with self.assertRaises(ValueError):
            transfer_stock(
                company=self.company, user=self.user, produit_id=produit.id,
                source_id=principal.id, destination_id=depot_b.id,
                quantite=99)
