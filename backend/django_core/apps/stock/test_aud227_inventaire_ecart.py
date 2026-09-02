"""AUD227 — `apply_inventory_count` enregistre l'ÉCART, pas le niveau compté.

Défaut d'origine : `apply_inventory_count` (N16) écrivait
``MouvementStock.quantite = compte`` (une valeur ABSOLUE), contrairement à ses
deux fonctions sœurs du même fichier — `appliquer_ecarts_comptage` et
`valider_inventaire_session` — qui écrivent toutes deux ``abs(ecart)``. La
colonne « Quantité » d'`export_mouvements_xlsx` mélangeait donc deux
sémantiques selon la fonction d'origine du mouvement.

Run :
    python manage.py test apps.stock.test_aud227_inventaire_ecart -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.stock.models import MouvementStock, Produit
from apps.stock.services import apply_inventory_count


def make_company(slug='aud227-co', nom='AUD227 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TestInventaireEcart(TestCase):
    def setUp(self):
        self.company = make_company()
        self.produit = Produit.objects.create(
            company=self.company, nom='Câble AUD227', sku='AUD227-1',
            prix_achat=Decimal('50'), prix_vente=Decimal('80'),
            quantite_stock=100)

    def _compter(self, quantite):
        return apply_inventory_count(
            company=self.company, user=None, motif='Inventaire annuel',
            lignes=[{'produit': self.produit.id,
                     'quantite_comptee': quantite}])

    def _mouvement(self):
        return MouvementStock.objects.get(
            produit=self.produit, reference='INVENTAIRE')

    def test_ecart_negatif_enregistre_en_valeur_absolue(self):
        self._compter(95)

        mvt = self._mouvement()
        # Écart de 5 unités manquantes. Avant AUD227 : 95 (le niveau compté).
        self.assertEqual(mvt.quantite, 5)
        self.assertEqual(mvt.quantite_avant, 100)
        self.assertEqual(mvt.quantite_apres, 95)

    def test_ecart_positif_enregistre_en_valeur_absolue(self):
        self._compter(112)

        mvt = self._mouvement()
        self.assertEqual(mvt.quantite, 12)
        self.assertEqual(mvt.quantite_apres, 112)

    def test_semantique_identique_a_valider_inventaire_session(self):
        """Même écart, même `quantite` que la fonction sœur FG63."""
        from apps.stock.models import InventaireSession, LigneInventaire
        from apps.stock.services import valider_inventaire_session

        autre = Produit.objects.create(
            company=self.company, nom='Câble AUD227 bis', sku='AUD227-2',
            prix_achat=Decimal('50'), prix_vente=Decimal('80'),
            quantite_stock=100)
        session = InventaireSession.objects.create(
            company=self.company, reference='INV-AUD227')
        LigneInventaire.objects.create(
            session=session, produit=autre,
            quantite_theorique=100, quantite_comptee=95)
        valider_inventaire_session(session, None)

        self._compter(95)

        via_session = MouvementStock.objects.get(
            produit=autre, reference='INV-AUD227')
        self.assertEqual(self._mouvement().quantite, via_session.quantite)

    def test_stock_toujours_pose_au_niveau_compte(self):
        """Le comportement métier ne change pas : le stock devient le compté."""
        res = self._compter(95)

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 95)
        self.assertEqual(res['ajustes'], 1)

    def test_note_conserve_le_comptage_et_l_ecart(self):
        self._compter(95)
        note = self._mouvement().note
        self.assertIn('comptage 95', note)
        self.assertIn('-5', note)
