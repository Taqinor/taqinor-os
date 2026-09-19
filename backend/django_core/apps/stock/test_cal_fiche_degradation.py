"""CAL113 — dégradation annuelle et paliers de garantie du module.

ROUGE avant CAL113 : ces valeurs vivaient en constantes de code
(``apps/ventes/solar_design.py``) alors que la datasheet les publie. VERT :
quatre champs optionnels sur ``FicheTechnique`` (type_fiche='module'), vides
par défaut, servant de source quand le fondateur les saisit et laissant le
moteur ventes retomber explicitement sur son hypothèse de référence sinon.

Run :
    docker compose exec django_core python manage.py test \
        apps.stock.tests.test_fiche_degradation -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.stock.models import FicheTechnique, Produit
from apps.stock.selectors import specs_for_produit
from authentication.models import Company


class FicheDegradationGarantieTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='cal113-stock-co', defaults={'nom': 'CAL113 Stock'})[0]
        self.produit = Produit.objects.create(
            company=self.co, nom='Module 550 Wc CAL113', sku='CAL113-MOD',
            prix_achat=Decimal('600'), prix_vente=Decimal('900'),
            quantite_stock=1)

    def test_champs_vides_par_defaut(self):
        fiche = FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='module')
        self.assertIsNone(fiche.degradation_annuelle_pct)
        self.assertIsNone(fiche.degradation_annee1_pct)
        self.assertIsNone(fiche.garantie_pct_a_10_ans)
        self.assertIsNone(fiche.garantie_pct_a_25_ans)

    def test_saisie_des_quatre_champs(self):
        fiche = FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='module',
            degradation_annuelle_pct=Decimal('0.45'),
            degradation_annee1_pct=Decimal('1.00'),
            garantie_pct_a_10_ans=Decimal('92.0'),
            garantie_pct_a_25_ans=Decimal('84.8'))
        fiche.refresh_from_db()
        self.assertEqual(fiche.degradation_annuelle_pct, Decimal('0.45'))
        self.assertEqual(fiche.degradation_annee1_pct, Decimal('1.00'))
        self.assertEqual(fiche.garantie_pct_a_10_ans, Decimal('92.0'))
        self.assertEqual(fiche.garantie_pct_a_25_ans, Decimal('84.8'))

    def test_vide_pas_encore_lu_par_specs_for_produit(self):
        """Chemin « sans fiche source » : ``specs_for_produit`` n'expose pas
        encore ces clés (CAL114) — un consommateur doit donc encore retomber
        sur son hypothèse de référence et le dire, jamais lire un 0 muet."""
        FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='module')
        self.produit.refresh_from_db()
        specs = specs_for_produit(self.produit)
        for key in ('degradation_annuelle_pct', 'degradation_annee1_pct',
                    'garantie_pct_a_10_ans', 'garantie_pct_a_25_ans'):
            self.assertNotIn(key, specs)
