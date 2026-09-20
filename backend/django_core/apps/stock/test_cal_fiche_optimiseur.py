"""CAL116 — type de fiche « optimiseur / micro-onduleur ».

ROUGE avant CAL116 : ``FicheTechnique.TypeFiche`` n'offrait que
module/onduleur/batterie/autre — aucun composant « optimiseur de puissance »
possible (``composition_deux_optimiseurs`` est un comparateur de
dimensionnement sans rapport). VERT : un nouveau choix ``'optimiseur'`` + six
champs optionnels, rendus par ``specs_for_produit``, sans effet sur les
fiches existantes.

Run :
    docker compose exec django_core python manage.py test \
        apps.stock.tests.test_fiche_optimiseur -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.stock.models import FicheTechnique, Produit
from apps.stock.selectors import specs_for_produit
from authentication.models import Company


class FicheOptimiseurTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='cal116-stock-co', defaults={'nom': 'CAL116 Stock'})[0]
        self.produit = Produit.objects.create(
            company=self.co, nom='Optimiseur CAL116', sku='CAL116-OPT',
            prix_achat=Decimal('300'), prix_vente=Decimal('450'),
            quantite_stock=1)

    def test_type_fiche_optimiseur_disponible(self):
        self.assertIn(
            'optimiseur',
            [c[0] for c in FicheTechnique.TypeFiche.choices])

    def test_champs_vides_par_defaut(self):
        fiche = FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='optimiseur')
        self.assertIsNone(fiche.opt_pmax_in_w)
        self.assertIsNone(fiche.opt_v_in_min)
        self.assertIsNone(fiche.opt_v_in_max)
        self.assertIsNone(fiche.opt_i_in_max_a)
        self.assertIsNone(fiche.opt_rendement_pct)
        self.assertIsNone(fiche.opt_modules_par_optimiseur)

    def test_saisie_des_six_champs(self):
        fiche = FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='optimiseur',
            opt_pmax_in_w=Decimal('700'), opt_v_in_min=Decimal('8'),
            opt_v_in_max=Decimal('80'), opt_i_in_max_a=Decimal('15'),
            opt_rendement_pct=Decimal('99.5'),
            opt_modules_par_optimiseur=2)
        fiche.refresh_from_db()
        self.assertEqual(fiche.opt_pmax_in_w, Decimal('700.00'))
        self.assertEqual(fiche.opt_modules_par_optimiseur, 2)

    def test_specs_for_produit_bloc_optimiseur(self):
        FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='optimiseur',
            opt_pmax_in_w=Decimal('700'), opt_rendement_pct=Decimal('99.5'))
        self.produit.refresh_from_db()
        specs = specs_for_produit(self.produit)
        self.assertEqual(specs['pmax_in_w'], Decimal('700.00'))
        self.assertEqual(specs['rendement_pct'], Decimal('99.5'))
        self.assertNotIn('v_in_min', specs)
        self.assertNotIn('modules_par_optimiseur', specs)

    def test_fiches_existantes_non_affectees(self):
        """Une fiche module ou onduleur ne récupère aucune clé
        ``opt_*`` (comportement inchangé)."""
        module_produit = Produit.objects.create(
            company=self.co, nom='Module témoin', sku='CAL116-MOD',
            prix_achat=Decimal('500'), prix_vente=Decimal('700'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.co, produit=module_produit, type_fiche='module',
            pmax_wc=Decimal('550'))
        module_produit.refresh_from_db()
        specs = specs_for_produit(module_produit)
        self.assertNotIn('pmax_in_w', specs)
