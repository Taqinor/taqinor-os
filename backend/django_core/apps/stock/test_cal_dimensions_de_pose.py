"""CAL119 — sélecteur stock « dimensions de pose ».

ROUGE avant CAL119 : ``core/calepinage`` travaille sur des ``Kit`` aux
dimensions écrites en dur et l'unique passerelle produit→kit vivait côté
``apps/ao`` (``kit_panneau_du_produit``) — inaccessible sans importer
``apps.ao``. VERT : ``dimensions_de_pose(produit)`` rend le sous-ensemble
utile depuis ``apps.stock.selectors`` seul, clé absente si non saisie.

Run :
    docker compose exec django_core python manage.py test \
        apps.stock.tests.test_dimensions_de_pose -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.stock.models import FicheTechnique, Produit
from apps.stock.selectors import dimensions_de_pose
from authentication.models import Company


class DimensionsDePoseTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='cal119-stock-co', defaults={'nom': 'CAL119 Stock'})[0]

    def test_produit_sans_fiche_dict_vide(self):
        produit = Produit.objects.create(
            company=self.co, nom='Sans fiche CAL119', sku='CAL119-NOFICHE',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'),
            quantite_stock=0)
        self.assertEqual(dimensions_de_pose(produit), {})

    def test_fiche_onduleur_dict_vide(self):
        """Un kit de pose se construit depuis un MODULE, jamais un
        onduleur/une batterie."""
        produit = Produit.objects.create(
            company=self.co, nom='Onduleur CAL119', sku='CAL119-OND',
            prix_achat=Decimal('4000'), prix_vente=Decimal('6000'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.co, produit=produit, type_fiche='onduleur',
            ond_ac_kw=Decimal('6.0'))
        produit.refresh_from_db()
        self.assertEqual(dimensions_de_pose(produit), {})

    def test_module_sans_dimensions_dict_vide_champ_manquant(self):
        """Produit module dont la fiche n'a AUCUNE dimension saisie : dict
        vide — un kit qui en dépendrait est refusé, le champ manquant est
        nommé par l'appelant (contrat CAL119), jamais un dict à moitié
        rempli avec des zéros implicites."""
        produit = Produit.objects.create(
            company=self.co, nom='Module sans dims', sku='CAL119-NODIMS',
            prix_achat=Decimal('500'), prix_vente=Decimal('700'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.co, produit=produit, type_fiche='module')
        produit.refresh_from_db()
        self.assertEqual(dimensions_de_pose(produit), {})

    def test_module_complet(self):
        produit = Produit.objects.create(
            company=self.co, nom='Module complet CAL119',
            sku='CAL119-COMPLET', prix_achat=Decimal('600'),
            prix_vente=Decimal('900'), quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.co, produit=produit, type_fiche='module',
            longueur_mm=2278, largeur_mm=1134, epaisseur_mm=35,
            poids_kg=Decimal('27.5'), pmax_wc=Decimal('550'))
        produit.refresh_from_db()
        dims = dimensions_de_pose(produit)
        self.assertEqual(dims, {
            'longueur_mm': 2278, 'largeur_mm': 1134, 'epaisseur_mm': 35,
            'poids_kg': Decimal('27.5'), 'puissance_wc': Decimal('550.00'),
        })

    def test_module_partiel_cle_manquante_omise(self):
        """Une dimension non saisie est OMISE, jamais rendue à ``None`` ou
        0 — le kit qui la consomme peut nommer précisément le champ
        manquant."""
        produit = Produit.objects.create(
            company=self.co, nom='Module partiel CAL119',
            sku='CAL119-PARTIEL', prix_achat=Decimal('600'),
            prix_vente=Decimal('900'), quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.co, produit=produit, type_fiche='module',
            longueur_mm=2278, largeur_mm=1134, pmax_wc=Decimal('550'))
        produit.refresh_from_db()
        dims = dimensions_de_pose(produit)
        self.assertNotIn('epaisseur_mm', dims)
        self.assertNotIn('poids_kg', dims)
        self.assertEqual(dims['longueur_mm'], 2278)

    def test_aucun_import_apps_ao_ni_apps_stock_models(self):
        """Garde-fou de frontière (CLAUDE.md) : le sélecteur ne dépend ni
        de ``apps.ao`` ni du module ``apps.stock.models`` importé par un
        appelant externe — ``apps.calepinage`` construit son kit via CE
        sélecteur seul."""
        import inspect

        import apps.stock.selectors as mod
        source = inspect.getsource(mod.dimensions_de_pose)
        self.assertNotIn('apps.ao', source)
        self.assertNotIn('import', source)
