"""CAL112 — facteur de bifacialité publié.

ROUGE avant CAL112 : ``FicheTechnique.bifacial`` n'est qu'un booléen —
impossible d'en tirer un gain face arrière chiffré. VERT : un champ
optionnel ``bifacialite_pct``, vide par défaut ; le booléen reste inchangé.

Run :
    docker compose exec django_core python manage.py test \
        apps.stock.tests.test_fiche_bifacial -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.stock.models import FicheTechnique, Produit
from apps.stock.selectors import specs_for_produit
from authentication.models import Company


class FicheBifacialiteTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='cal112-stock-co', defaults={'nom': 'CAL112 Stock'})[0]
        self.produit = Produit.objects.create(
            company=self.co, nom='Module 550 Wc CAL112', sku='CAL112-MOD',
            prix_achat=Decimal('600'), prix_vente=Decimal('900'),
            quantite_stock=1)

    def test_vide_par_defaut(self):
        fiche = FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='module')
        self.assertIsNone(fiche.bifacialite_pct)
        self.assertFalse(fiche.bifacial)

    def test_booleen_bifacial_conserve(self):
        """Le booléen historique reste porté, indépendant du nouveau
        facteur — ni supprimé, ni recalculé à partir de lui."""
        fiche = FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='module',
            bifacial=True)
        fiche.refresh_from_db()
        self.assertTrue(fiche.bifacial)
        self.assertIsNone(fiche.bifacialite_pct)

    def test_saisie_du_facteur(self):
        fiche = FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='module',
            bifacial=True, bifacialite_pct=Decimal('80.0'))
        fiche.refresh_from_db()
        self.assertEqual(fiche.bifacialite_pct, Decimal('80.0'))

    def test_vide_naliment_aucun_gain_bifacial(self):
        """``specs_for_produit`` n'expose pas encore la clé (CAL114) — un
        facteur vide ou saisi n'alimente donc aucun calcul aval pour
        l'instant, et un facteur vide ne doit jamais devenir un 0 implicite
        quelque part dans la chaîne."""
        FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='module')
        self.produit.refresh_from_db()
        specs = specs_for_produit(self.produit)
        self.assertNotIn('bifacialite_pct', specs)
