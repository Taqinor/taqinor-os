"""ASTK43 (C-ASTK-008) — toute lecture de coût passe par l'accesseur unique.

Constat MVT-15 : `fifo_cost_with_source` ignorait la couche de
revalorisation (coût FIFO 1 000,00 avant ET après une revalorisation validée
à 600, quand le coût moyen disait 600,00) ; `creer_revalorisation`,
`rebuter_produit`, `rapport_pertes` et `decouper_produit` appelaient
`average_cost_with_source` en direct et ignoraient donc la méthode FIFO.

Aucun réglage société FIFO n'existe (CompanyProfile n'a pas de
`stock_valuation_method`) : la société FIFO est SIMULÉE PAR PARAMÈTRE
(`method='fifo'`) — jamais par un mock ni un test de grep. Chaque fonction est
appelée sur un produit où FIFO (200) et coût moyen (150) divergent.

Run :
    python manage.py test apps.stock.test_astk_accesseur_cout
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    Produit, RevalorisationStock,
)
from apps.stock.services import (
    average_cost_with_source, creer_revalorisation, decouper_produit,
    fifo_cost_with_source, rapport_pertes, rebuter_produit,
    valider_revalorisation,
)

User = get_user_model()


class AccesseurCoutTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ASTK43 Co', slug='astk43-co')
        self.user = User.objects.create_user(
            username='astk43-user', password='x', company=self.company,
            role_legacy='admin')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK43')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASTK43', sku='OND-ASTK43',
            prix_vente=Decimal('3000'), prix_achat=Decimal('999'),
            quantite_stock=0)
        self.aujourdhui = timezone.localdate()

    def _recu(self, quantite, prix, il_y_a_jours, produit=None):
        produit = produit or self.produit
        bc = BonCommandeFournisseur.objects.create(
            company=self.company,
            reference=f'BCF-ASTK43-{produit.pk}-{il_y_a_jours}-{prix}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        jour = self.aujourdhui - datetime.timedelta(days=il_y_a_jours)
        BonCommandeFournisseur.objects.filter(pk=bc.pk).update(
            date_creation=timezone.make_aware(
                datetime.datetime.combine(jour, datetime.time(10, 0))))
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=produit, quantite=quantite,
            prix_achat_unitaire=Decimal(prix), quantite_recue=quantite)

    def _stock(self, quantite, produit=None):
        produit = produit or self.produit
        produit.quantite_stock = quantite
        produit.save(update_fields=['quantite_stock'])

    def _divergent(self):
        # 10 @ 100 (ancien) puis 10 @ 200 (récent), 10 en stock :
        # FIFO = 200 (il reste les dernières entrées), coût moyen = 150.
        self._recu(10, '100', 20)
        self._recu(10, '200', 10)
        self._stock(10)
        self.assertEqual(
            fifo_cost_with_source(self.produit)[0], Decimal('200.00'))
        self.assertEqual(
            average_cost_with_source(self.produit)[0], Decimal('150.00'))

    # ── Volet FIFO latent (MVT-15) ────────────────────────────────────────
    def test_fifo_revalo(self):
        self._recu(10, '1000', 10)
        self._stock(10)
        self.assertEqual(
            fifo_cost_with_source(self.produit)[0], Decimal('1000.00'))
        revalo = creer_revalorisation(
            company=self.company, produit=self.produit, nouveau_cout='600',
            motif='Baisse du marché', user=self.user)
        valider_revalorisation(revalo)
        cout, source = fifo_cost_with_source(self.produit)
        self.assertEqual(cout, Decimal('600.00'))
        self.assertEqual(source, 'revalorisation')
        self.assertEqual(
            average_cost_with_source(self.produit)[0], Decimal('600.00'))

    def test_fifo_revalo_puis_reception_posterieure(self):
        self._recu(10, '1000', 10)
        self._stock(10)
        revalo = creer_revalorisation(
            company=self.company, produit=self.produit, nouveau_cout='600',
            motif='Baisse du marché', user=self.user)
        valider_revalorisation(revalo)
        RevalorisationStock.objects.filter(pk=revalo.pk).update(
            date_validation=timezone.now() - datetime.timedelta(days=5))
        self._recu(5, '800', 2)
        self._stock(15)
        # 5 @ 800 (récent) + 10 @ 600 (couche revalorisée) = 10 000 / 15.
        self.assertEqual(
            fifo_cost_with_source(self.produit)[0], Decimal('666.67'))

    # ── Chaque lecture de coût passe par l'accesseur ──────────────────────
    def test_rebut_valorise_par_l_accesseur(self):
        self._divergent()
        resultat = rebuter_produit(
            company=self.company, produit=self.produit, quantite=1,
            motif='casse', user=self.user, method='fifo')
        self.assertEqual(resultat['valeur_perdue'], Decimal('200.00'))
        # Méthode société (coût moyen par défaut) : 150.
        resultat = rebuter_produit(
            company=self.company, produit=self.produit, quantite=1,
            motif='casse', user=self.user)
        self.assertEqual(resultat['valeur_perdue'], Decimal('150.00'))

    def test_rapport_pertes_par_l_accesseur(self):
        self._divergent()
        rebuter_produit(
            company=self.company, produit=self.produit, quantite=1,
            motif='casse', user=self.user)
        lignes = rapport_pertes(self.company, method='fifo')
        self.assertEqual(lignes[0]['valeur_totale'], Decimal('200.00'))
        lignes = rapport_pertes(self.company)
        self.assertEqual(lignes[0]['valeur_totale'], Decimal('150.00'))

    def test_creer_revalorisation_par_l_accesseur(self):
        self._divergent()
        revalo = creer_revalorisation(
            company=self.company, produit=self.produit, nouveau_cout='180',
            motif='Test FIFO', user=self.user, method='fifo')
        self.assertEqual(revalo.ancien_cout, Decimal('200.00'))
        self.assertEqual(revalo.delta_valeur, Decimal('-200.00'))

    def test_decoupe_par_l_accesseur(self):
        self._divergent()
        cible = Produit.objects.create(
            company=self.company, nom='Coupe ASTK43', sku='CIB-ASTK43',
            prix_vente=Decimal('10'), prix_achat=Decimal('1'),
            quantite_stock=0)
        resultat = decouper_produit(
            company=self.company, produit_source=self.produit,
            quantite_consommee=2, produit_cible=cible, quantite_produite=2,
            user=self.user, method='fifo')
        self.assertEqual(resultat['cout_unitaire'], Decimal('200.00'))
        self.assertEqual(resultat['valeur_transferee'], Decimal('400.00'))
