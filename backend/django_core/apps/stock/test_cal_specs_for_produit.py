"""CAL114 — bloc module COMPLET dans ``specs_for_produit``.

ROUGE avant CAL114 : ``specs_for_produit`` ne rendait que 9 clés du bloc
module et OMETTAIT ``bifacial``, ``techno_cellule``, ``epaisseur_mm``,
``poids_kg``, ``rendement_pct`` — pourtant déjà présents sur la fiche — ainsi
que les clés neuves de CAL111-113 (modèle thermique, bifacialité,
dégradation/garantie). VERT : le dict est étendu, une fiche non renseignée
rend toujours le dict inchangé pour les champs non saisis (équivalence).

Run :
    docker compose exec django_core python manage.py test \
        apps.stock.tests.test_specs_for_produit -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.stock.models import FicheTechnique, Produit
from apps.stock.selectors import specs_for_produit
from authentication.models import Company


class SpecsForProduitBlocModuleTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='cal114-stock-co', defaults={'nom': 'CAL114 Stock'})[0]
        self.produit = Produit.objects.create(
            company=self.co, nom='Module 550 Wc CAL114', sku='CAL114-MOD',
            prix_achat=Decimal('600'), prix_vente=Decimal('900'),
            quantite_stock=1)

    def test_fiche_non_renseignee_dict_equivalent(self):
        """Une fiche module sans aucun des champs étendus saisis rend un
        dict SANS ces clés (sauf ``bifacial``, booléen jamais NULL) — donc
        équivalent au comportement d'avant CAL114 pour tout appelant qui
        fait ``{**DEFAUT, **specs_for_produit(p)}``."""
        FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='module')
        self.produit.refresh_from_db()
        specs = specs_for_produit(self.produit)
        for key in ('epaisseur_mm', 'poids_kg', 'rendement_pct',
                    'techno_cellule', 'noct_c', 'uc_w_m2k', 'uv_w_m3sk',
                    'bifacialite_pct', 'degradation_annuelle_pct',
                    'degradation_annee1_pct', 'garantie_pct_a_10_ans',
                    'garantie_pct_a_25_ans'):
            self.assertNotIn(key, specs)
        # bifacial est un booléen jamais NULL (default=False) — présent,
        # comportement inchangé (False = « pas bifacial », pas une absence).
        self.assertEqual(specs['bifacial'], False)

    def test_champs_nouvellement_saisis_sont_presents(self):
        FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='module',
            epaisseur_mm=35, poids_kg=Decimal('27.5'),
            rendement_pct=Decimal('21.3'), techno_cellule='N-type TOPCon',
            bifacial=True, noct_c=Decimal('45.0'), uc_w_m2k=Decimal('29.0'),
            uv_w_m3sk=Decimal('0.0'), bifacialite_pct=Decimal('80.0'),
            degradation_annuelle_pct=Decimal('0.45'),
            degradation_annee1_pct=Decimal('1.00'),
            garantie_pct_a_10_ans=Decimal('92.0'),
            garantie_pct_a_25_ans=Decimal('84.8'))
        self.produit.refresh_from_db()
        specs = specs_for_produit(self.produit)
        self.assertEqual(specs['epaisseur_mm'], 35)
        self.assertEqual(specs['poids_kg'], Decimal('27.5'))
        self.assertEqual(specs['rendement_pct'], Decimal('21.3'))
        self.assertEqual(specs['techno_cellule'], 'N-type TOPCon')
        self.assertTrue(specs['bifacial'])
        self.assertEqual(specs['noct_c'], Decimal('45.0'))
        self.assertEqual(specs['uc_w_m2k'], Decimal('29.0'))
        self.assertEqual(specs['uv_w_m3sk'], Decimal('0.0'))
        self.assertEqual(specs['bifacialite_pct'], Decimal('80.0'))
        self.assertEqual(specs['degradation_annuelle_pct'], Decimal('0.45'))
        self.assertEqual(specs['degradation_annee1_pct'], Decimal('1.00'))
        self.assertEqual(specs['garantie_pct_a_10_ans'], Decimal('92.0'))
        self.assertEqual(specs['garantie_pct_a_25_ans'], Decimal('84.8'))

    def test_techno_cellule_vide_omise(self):
        """Chaîne vide (défaut du champ) = non saisie ⇒ omise, jamais une
        chaîne vide rendue au consommateur."""
        FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='module',
            techno_cellule='')
        self.produit.refresh_from_db()
        specs = specs_for_produit(self.produit)
        self.assertNotIn('techno_cellule', specs)

    def test_produit_sans_fiche_dict_vide(self):
        autre = Produit.objects.create(
            company=self.co, nom='Sans fiche', sku='CAL114-NOFICHE',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'),
            quantite_stock=0)
        self.assertEqual(specs_for_produit(autre), {})

    def test_aucun_import_de_modele_stock_hors_de_lapp(self):
        """Garde-fou de frontière (CLAUDE.md) : ``apps.calepinage`` n'existe
        pas encore dans ce dépôt — ce test documente que le sélecteur ne
        dépend que de ``apps.stock.models``, jamais d'une autre app."""
        import inspect

        import apps.stock.selectors as mod
        source = inspect.getsource(mod)
        self.assertNotIn('apps.calepinage', source)
        self.assertNotIn('apps.ventes.models', source)
