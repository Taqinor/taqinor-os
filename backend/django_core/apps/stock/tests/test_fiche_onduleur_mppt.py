"""CAL115 — chaînes par MPPT, entrées par MPPT, puissance apparente max.

ROUGE avant CAL115 : la fiche onduleur ne disait pas combien de chaînes une
entrée MPPT accepte, ni la puissance apparente (kVA), ni la puissance DC
maximale recommandée. VERT : quatre champs optionnels, exposés par
``specs_for_produit`` (bloc onduleur), sans changer un seul verdict pour une
fiche qui ne les porte pas.

Run :
    docker compose exec django_core python manage.py test \
        apps.stock.tests.test_fiche_onduleur_mppt -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.stock.models import FicheTechnique, Produit
from apps.stock.selectors import specs_for_produit
from authentication.models import Company


class FicheOnduleurMpptTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='cal115-stock-co', defaults={'nom': 'CAL115 Stock'})[0]
        self.produit = Produit.objects.create(
            company=self.co, nom='Onduleur CAL115', sku='CAL115-OND',
            prix_achat=Decimal('4000'), prix_vente=Decimal('6000'),
            quantite_stock=1)

    def test_champs_vides_par_defaut(self):
        fiche = FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='onduleur',
            ond_n_mppt=2)
        self.assertIsNone(fiche.ond_entrees_par_mppt)
        self.assertIsNone(fiche.ond_chaines_max_par_mppt)
        self.assertIsNone(fiche.ond_s_max_kva)
        self.assertIsNone(fiche.ond_dc_max_kwc)

    def test_saisie_des_quatre_champs(self):
        fiche = FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='onduleur',
            ond_n_mppt=2, ond_entrees_par_mppt=2,
            ond_chaines_max_par_mppt=2, ond_s_max_kva=Decimal('6.6'),
            ond_dc_max_kwc=Decimal('9.0'))
        fiche.refresh_from_db()
        self.assertEqual(fiche.ond_entrees_par_mppt, 2)
        self.assertEqual(fiche.ond_chaines_max_par_mppt, 2)
        self.assertEqual(fiche.ond_s_max_kva, Decimal('6.6'))
        self.assertEqual(fiche.ond_dc_max_kwc, Decimal('9.0'))

    def test_specs_for_produit_omet_les_cles_non_saisies(self):
        """Fiche sans les quatre nouvelles valeurs : aucun verdict de
        ``fenetre_onduleur_pour_produit`` (apps/ventes) ne change car les
        clés sont simplement absentes du dict — pas de calcul possible
        ici sans importer apps.ventes, donc on prouve l'absence des clés,
        contrat que ce consommateur observera."""
        FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='onduleur',
            ond_n_mppt=2, ond_ac_kw=Decimal('6.0'))
        self.produit.refresh_from_db()
        specs = specs_for_produit(self.produit)
        self.assertEqual(specs['n_mppt'], 2)
        self.assertEqual(specs['ac_kw'], Decimal('6.0'))
        for key in ('entrees_par_mppt', 'chaines_max_par_mppt',
                    's_max_kva', 'dc_max_kwc'):
            self.assertNotIn(key, specs)

    def test_specs_for_produit_expose_les_cles_saisies(self):
        FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='onduleur',
            ond_n_mppt=2, ond_entrees_par_mppt=2,
            ond_chaines_max_par_mppt=3, ond_s_max_kva=Decimal('6.6'),
            ond_dc_max_kwc=Decimal('9.0'))
        self.produit.refresh_from_db()
        specs = specs_for_produit(self.produit)
        self.assertEqual(specs['entrees_par_mppt'], 2)
        self.assertEqual(specs['chaines_max_par_mppt'], 3)
        self.assertEqual(specs['s_max_kva'], Decimal('6.6'))
        self.assertEqual(specs['dc_max_kwc'], Decimal('9.0'))
