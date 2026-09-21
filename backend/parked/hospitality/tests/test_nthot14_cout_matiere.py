"""NTHOT14 — Coût matière théorique vs réel.

Done = le food cost théorique d'un plat se recalcule si le prix d'achat d'un
ingrédient change, l'écart théorique/réel se calcule sur une période sans
exposer de prix d'achat sans permission, tests.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from apps.hospitality import selectors
from apps.hospitality.models import IngredientRecette, Recette

from .helpers import make_company, make_user


class CoutMatiereTheoriqueTests(TestCase):
    def setUp(self):
        from apps.stock.models import Produit

        self.co = make_company('hot-food', 'Hôtel')
        self.farine = Produit.objects.create(
            company=self.co, nom='Farine', prix_achat=Decimal('5'),
            prix_vente=Decimal('8'))
        self.beurre = Produit.objects.create(
            company=self.co, nom='Beurre', prix_achat=Decimal('20'),
            prix_vente=Decimal('30'))
        self.recette = Recette.objects.create(
            company=self.co, nom_plat='Tarte', prix_vente_ht=Decimal('100'))
        IngredientRecette.objects.create(
            recette=self.recette, produit=self.farine,
            quantite=Decimal('0.5'), unite='kg')
        IngredientRecette.objects.create(
            recette=self.recette, produit=self.beurre,
            quantite=Decimal('0.2'), unite='kg')

    def test_cout_theorique_somme_quantite_fois_prix_achat(self):
        # 0.5 * 5 + 0.2 * 20 = 2.5 + 4 = 6.5
        self.assertEqual(
            selectors.cout_matiere_theorique(self.recette), Decimal('6.5'))

    def test_cout_theorique_se_recalcule_si_prix_achat_change(self):
        self.assertEqual(
            selectors.cout_matiere_theorique(self.recette), Decimal('6.5'))
        self.farine.prix_achat = Decimal('10')
        self.farine.save(update_fields=['prix_achat'])
        # 0.5 * 10 + 0.2 * 20 = 5 + 4 = 9
        self.assertEqual(
            selectors.cout_matiere_theorique(self.recette), Decimal('9'))

    def test_pourcentage_food_cost(self):
        pct = selectors.pourcentage_food_cost(self.recette)
        self.assertEqual(pct, Decimal('6.5') / Decimal('100'))

    def test_pourcentage_food_cost_sans_prix_vente_ne_divise_pas_par_zero(self):
        recette_sans_prix = Recette.objects.create(
            company=self.co, nom_plat='Sans prix', prix_vente_ht=Decimal('0'))
        self.assertEqual(
            selectors.pourcentage_food_cost(recette_sans_prix), Decimal('0'))

    def test_jamais_de_prix_achat_brut_dans_la_sortie(self):
        # Discipline « rule prix_achat » : la sortie ne doit JAMAIS exposer un
        # prix_achat unitaire, seulement des coûts déjà agrégés.
        payload = selectors.ecart_theorique_reel(
            self.co, datetime.date.today() - datetime.timedelta(days=1),
            datetime.date.today() + datetime.timedelta(days=1))
        self.assertNotIn('prix_achat', payload)
        reel_payload = selectors.cout_matiere_reel(
            self.co, datetime.date.today() - datetime.timedelta(days=1),
            datetime.date.today() + datetime.timedelta(days=1))
        self.assertNotIn('prix_achat', reel_payload)
        for ligne in reel_payload['par_produit']:
            self.assertNotIn('prix_achat', ligne)


class CoutMatiereReelTests(TestCase):
    def setUp(self):
        from apps.stock.models import Produit
        from apps.stock.models import MouvementStock

        self.co = make_company('hot-food-reel', 'Hôtel')
        self.user = make_user(self.co, 'hot-food-reel-user')
        self.farine = Produit.objects.create(
            company=self.co, nom='Farine Reel', prix_achat=Decimal('5'),
            prix_vente=Decimal('8'), quantite_stock=100)
        self.recette = Recette.objects.create(
            company=self.co, nom_plat='Pain', prix_vente_ht=Decimal('20'))
        IngredientRecette.objects.create(
            recette=self.recette, produit=self.farine,
            quantite=Decimal('0.3'), unite='kg')

        MouvementStock.objects.create(
            company=self.co, produit=self.farine,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE,
            quantite=10, quantite_avant=100, quantite_apres=90,
            created_by=self.user,
        )

    def test_cout_reel_valorise_les_sorties_au_prix_achat_courant(self):
        debut = datetime.date.today() - datetime.timedelta(days=1)
        fin = datetime.date.today() + datetime.timedelta(days=1)
        result = selectors.cout_matiere_reel(self.co, debut, fin)
        # 10 unités sorties * 5 (prix_achat) = 50
        self.assertEqual(result['total'], Decimal('50'))
        self.assertEqual(len(result['par_produit']), 1)
        self.assertEqual(result['par_produit'][0]['produit'], 'Farine Reel')
        self.assertEqual(result['par_produit'][0]['valeur'], Decimal('50'))

    def test_cout_reel_vide_hors_periode(self):
        lointain_debut = datetime.date.today() - datetime.timedelta(days=60)
        lointain_fin = datetime.date.today() - datetime.timedelta(days=30)
        result = selectors.cout_matiere_reel(self.co, lointain_debut, lointain_fin)
        self.assertEqual(result['total'], Decimal('0'))

    def test_ecart_theorique_reel_sans_ventes_tracees_theorique_nul(self):
        debut = datetime.date.today() - datetime.timedelta(days=1)
        fin = datetime.date.today() + datetime.timedelta(days=1)
        result = selectors.ecart_theorique_reel(self.co, debut, fin)
        self.assertEqual(result['theorique'], Decimal('0'))
        self.assertEqual(result['reel'], Decimal('50'))
        self.assertIsNone(result['ecart_pct'])

    def test_ecart_theorique_reel_avec_ventes_calcule_pct(self):
        debut = datetime.date.today() - datetime.timedelta(days=1)
        fin = datetime.date.today() + datetime.timedelta(days=1)
        # 20 pains vendus * 0.3kg farine * 5 = 30 théorique ; réel = 50.
        result = selectors.ecart_theorique_reel(
            self.co, debut, fin, ventes_par_recette={self.recette.pk: 20})
        self.assertEqual(result['theorique'], Decimal('30'))
        self.assertEqual(result['reel'], Decimal('50'))
        self.assertEqual(result['ecart'], Decimal('20'))
        self.assertEqual(result['ecart_pct'], Decimal('20') / Decimal('30'))

    def test_cout_matiere_reel_sans_recette_associee_renvoie_zero(self):
        autre_co = make_company('hot-food-reel-vide', 'Sans recette')
        debut = datetime.date.today() - datetime.timedelta(days=1)
        fin = datetime.date.today() + datetime.timedelta(days=1)
        result = selectors.cout_matiere_reel(autre_co, debut, fin)
        self.assertEqual(result, {'total': Decimal('0'), 'par_produit': []})
