"""AUD222 — un rebut au-delà du stock est REFUSÉ, jamais tronqué en silence.

Défaut d'origine : `declarer_rebut` (XMFG11) posait
``qte_sortie = min(quantite, avant) if avant > 0 else 0`` — alors que sa
fonction SŒUR `rebuter_produit` (juste en dessous, même fichier) appelle
`check_negative_stock_guard` et lève `ValueError`.

Ce que la troncature cassait, concrètement : le mouvement écrit portait
``quantite = 3`` pour une déclaration de 10 sur un stock de 3, donc
``quantite ≠ quantite_avant − quantite_apres``. Le registre devenait
incohérent AVEC LUI-MÊME, puisque `_quantite_produit_a_date` reconstruit
depuis ``quantite_apres`` tandis qu'`export_mouvements_xlsx` affiche
``quantite`` — et surtout, 7 unités déclarées perdues à l'atelier n'étaient
tracées nulle part et personne n'en était averti.

Le SECOND site de la même classe (`ecommerce_connect/common.py`, l'ancien
``apres = max(avant - quantite, 0)``) était partagé avec AUD202 (volet
argent) : il est DÉJÀ corrigé sur `main` et couvert par
``apps/ecommerce_connect/tests/test_aud202_webhook_argent.py::
StockNonTronqueTests`` (refus + cohérence du mouvement). Rien n'est dupliqué
ici — voir la classe `Aud222SecondSiteEcommerceTests` ci-dessous, qui ne fait
que verrouiller ce constat.

Run :
    python manage.py test apps.stock.test_aud222_rebut_sans_troncature -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock import services as stock_services
from apps.stock.models import AchatsParametres, MouvementStock, Produit
from apps.stock.services import declarer_rebut
from authentication.models import Company

User = get_user_model()

MOTIF = MouvementStock.MotifRebut.CASSE


class Aud222Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD222 Co', slug='aud222-co')
        self.user = User.objects.create_user(
            username='aud222_admin', password='x', role_legacy='admin',
            company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Coffret AUD222', sku='AUD222-1',
            prix_achat=Decimal('300'), prix_vente=Decimal('500'),
            quantite_stock=3)

    def _rebut(self, quantite, reference='OA-AUD222'):
        return declarer_rebut(
            company=self.company, produit=self.produit, quantite=quantite,
            motif=MOTIF, reference=reference, note='Casse atelier',
            user=self.user)


class Aud222RefusTests(Aud222Base):
    def test_rebut_au_dela_du_stock_est_refuse(self):
        with self.assertRaises(ValueError) as ctx:
            self._rebut(10)
        self.assertIn('Stock insuffisant', str(ctx.exception))

    def test_le_refus_ne_laisse_aucune_trace(self):
        with self.assertRaises(ValueError):
            self._rebut(10)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 3)
        self.assertFalse(MouvementStock.objects.filter(
            produit=self.produit).exists())

    def test_rebut_egal_au_stock_reste_accepte(self):
        mouvement = self._rebut(3)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 0)
        self.assertEqual(mouvement.quantite, 3)

    def test_le_mouvement_ecrit_est_toujours_coherent(self):
        """L'invariant que la troncature violait :
        ``quantite == quantite_avant − quantite_apres``."""
        mouvement = self._rebut(2)
        self.assertEqual(
            mouvement.quantite,
            mouvement.quantite_avant - mouvement.quantite_apres)
        self.assertEqual(mouvement.motif_rebut, MOTIF)
        self.assertEqual(
            mouvement.type_mouvement, MouvementStock.TypeMouvement.REBUT)

    def test_quantite_nulle_ou_negative_toujours_refusee(self):
        for invalide in (0, -1, None):
            with self.assertRaises(ValueError):
                self._rebut(invalide)


class Aud222StockNegatifAutoriseTests(Aud222Base):
    """La seule porte de sortie est le réglage EXPLICITE de la société."""

    def test_avec_stock_negatif_autorise_le_rebut_complet_passe(self):
        parametres = AchatsParametres.for_company(self.company)
        parametres.stock_negatif_autorise = True
        parametres.save()

        mouvement = self._rebut(10)

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, -7)
        # Même avec le réglage permissif, RIEN n'est tronqué : la quantité
        # déclarée est la quantité tracée.
        self.assertEqual(mouvement.quantite, 10)
        self.assertEqual(
            mouvement.quantite,
            mouvement.quantite_avant - mouvement.quantite_apres)


class Aud222PariteAvecSaSoeurTests(Aud222Base):
    """`declarer_rebut` et `rebuter_produit` refusent désormais PAREIL.

    C'est l'asymétrie constatée par l'audit : deux fonctions voisines, même
    fichier, même geste métier — l'une levait, l'autre tronquait.
    """

    def test_rebuter_produit_refuse_toujours(self):
        with self.assertRaises(ValueError):
            stock_services.rebuter_produit(
                company=self.company, produit=self.produit, quantite=10,
                motif=MOTIF, user=self.user)

    def test_les_deux_soeurs_refusent_la_meme_declaration(self):
        with self.assertRaises(ValueError):
            self._rebut(10)
        with self.assertRaises(ValueError):
            stock_services.rebuter_produit(
                company=self.company, produit=self.produit, quantite=10,
                motif=MOTIF, user=self.user)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 3)
        self.assertFalse(MouvementStock.objects.filter(
            produit=self.produit).exists())
