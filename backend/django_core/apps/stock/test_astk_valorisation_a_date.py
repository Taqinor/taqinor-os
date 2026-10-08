"""ASTK40 (C-ASTK-008) — la valorisation à date utilise le MÊME coût que l'écran.

Constat MVT-4 : un produit reçu 10 @ 1 000 puis revalorisé et validé à 600
valait 6 000,00 à l'écran Valorisation (`stock_valuation_by_location`) mais
10 000,00 dans `valorisation_a_date` (donc dans l'inventaire annuel FIGÉ) :
`_cout_moyen_produit_a_date` recalculait sa propre moyenne en ignorant les
revalorisations validées. Désormais il appelle l'accesseur unique
`valuation_cost_with_source(..., a_la_date=...)` : revalorisations validées
≤ date incluses, postérieures exclues.

Run :
    python manage.py test apps.stock.test_astk_valorisation_a_date
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, InventaireAnnuel,
    LigneBonCommandeFournisseur, MouvementStock, Produit, RevalorisationStock,
)
from apps.stock.services import (
    creer_revalorisation, figer_inventaire_annuel,
    stock_valuation_by_location, valider_revalorisation, valorisation_a_date,
)

User = get_user_model()


class ValorisationADateTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ASTK40 Co', slug='astk40-co')
        self.user = User.objects.create_user(
            username='astk40-admin', password='x', company=self.company,
            role_legacy='admin')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK40')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASTK40', sku='OND-ASTK40',
            prix_vente=Decimal('3000'), prix_achat=Decimal('1500'),
            quantite_stock=0)

    def _recu(self, quantite, prix, jour):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-ASTK40-{jour}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        moment = timezone.make_aware(
            datetime.datetime.combine(jour, datetime.time(12, 0)))
        BonCommandeFournisseur.objects.filter(pk=bc.pk).update(
            date_creation=moment)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=quantite,
            prix_achat_unitaire=Decimal(prix), quantite_recue=quantite)
        avant = self.produit.quantite_stock
        mvt = MouvementStock.objects.create(
            company=self.company, produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE,
            quantite=quantite, quantite_avant=avant,
            quantite_apres=avant + quantite, reference=bc.reference)
        MouvementStock.objects.filter(pk=mvt.pk).update(date=moment)
        self.produit.quantite_stock = avant + quantite
        self.produit.save(update_fields=['quantite_stock'])

    def _revaloriser(self, nouveau_cout, jour=None):
        revalo = creer_revalorisation(
            company=self.company, produit=self.produit,
            nouveau_cout=nouveau_cout, motif='Baisse du marché',
            user=self.user)
        valider_revalorisation(revalo)
        if jour is not None:
            RevalorisationStock.objects.filter(pk=revalo.pk).update(
                date_validation=timezone.make_aware(
                    datetime.datetime.combine(jour, datetime.time(15, 0))))
        return revalo

    def test_egalite_ecran_a_date_aujourdhui(self):
        aujourdhui = timezone.localdate()
        self._recu(10, '1000', aujourdhui - datetime.timedelta(days=10))
        self._revaloriser('600')
        ecran = stock_valuation_by_location(self.company)['total']
        a_date = valorisation_a_date(self.company, aujourdhui)['total']
        self.assertEqual(ecran, Decimal('6000.00'))
        self.assertEqual(a_date, Decimal('6000.00'))
        self.assertEqual(a_date, ecran)

    def test_revalo_posterieure_exclue(self):
        aujourdhui = timezone.localdate()
        self._recu(10, '1000', aujourdhui - datetime.timedelta(days=10))
        self._revaloriser('600')
        veille = aujourdhui - datetime.timedelta(days=1)
        rapport = valorisation_a_date(self.company, veille)
        self.assertEqual(rapport['total'], Decimal('10000.00'))
        self.assertEqual(rapport['lignes'][0]['cout_moyen'],
                         Decimal('1000.00'))

    def test_inventaire_annuel_fige_inclut_la_revalo_de_l_exercice(self):
        exercice = timezone.localdate().year - 1
        self._recu(10, '1000', datetime.date(exercice, 6, 1))
        self._revaloriser('600', jour=datetime.date(exercice, 9, 1))
        inventaire = figer_inventaire_annuel(self.company, exercice, self.user)
        relu = InventaireAnnuel.objects.get(pk=inventaire.pk)
        self.assertEqual(relu.total_valeur, Decimal('6000.00'))

    def test_revalo_validee_apres_l_exercice_exclue_du_figement(self):
        exercice = timezone.localdate().year - 1
        self._recu(10, '1000', datetime.date(exercice, 6, 1))
        # Validée APRÈS le 31/12 de l'exercice : n'entre pas dans son bilan.
        self._revaloriser('600', jour=datetime.date(exercice + 1, 1, 15))
        inventaire = figer_inventaire_annuel(self.company, exercice, self.user)
        relu = InventaireAnnuel.objects.get(pk=inventaire.pk)
        self.assertEqual(relu.total_valeur, Decimal('10000.00'))
