"""CAL111 — modèle thermique du module (NOCT / coefficients Uc-Uv).

ROUGE avant CAL111 : ``FicheTechnique`` ne portait aucun paramètre de
température de cellule (seuls les coefficients Voc/Pmax existaient) ; le
calcul solaire fixe la température cellule en dur faute de champ. VERT :
trois champs optionnels ``noct_c``/``uc_w_m2k``/``uv_w_m3sk``, vides par
défaut — et la preuve qu'une fiche vide de ces champs reste byte-identique
(rien ne les lit encore : ``specs_for_produit`` n'est étendu qu'à CAL114).

Run :
    docker compose exec django_core python manage.py test \
        apps.stock.tests.test_fiche_thermique -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.stock.models import FicheTechnique, Produit
from apps.stock.selectors import specs_for_produit
from apps.stock.serializers import FicheTechniqueSerializer
from authentication.models import Company


class FicheModeleThermiqueTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='cal111-stock-co', defaults={'nom': 'CAL111 Stock'})[0]
        self.produit = Produit.objects.create(
            company=self.co, nom='Module 550 Wc CAL111', sku='CAL111-MOD',
            prix_achat=Decimal('600'), prix_vente=Decimal('900'),
            quantite_stock=1)

    def test_champs_vides_par_defaut(self):
        """Une fiche module sans modèle thermique saisi rend les trois
        champs à ``None`` — jamais 0 (« zéro chiffre inventé »)."""
        fiche = FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='module')
        self.assertIsNone(fiche.noct_c)
        self.assertIsNone(fiche.uc_w_m2k)
        self.assertIsNone(fiche.uv_w_m3sk)

    def test_fiche_existante_byte_identique(self):
        """Les champs électriques historiques d'une fiche déjà saisie ne
        bougent pas quand le modèle thermique reste vide (migration
        purement additive)."""
        fiche = FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='module',
            pmax_wc=Decimal('550'), voc_v=Decimal('49.5'),
            temp_coeff_pmax_pct_c=Decimal('-0.350'))
        fiche.refresh_from_db()
        self.assertEqual(fiche.pmax_wc, Decimal('550.00'))
        self.assertEqual(fiche.voc_v, Decimal('49.50'))
        self.assertEqual(fiche.temp_coeff_pmax_pct_c, Decimal('-0.350'))
        self.assertIsNone(fiche.noct_c)

    def test_saisie_du_modele_thermique(self):
        """Les trois champs se saisissent et se relisent normalement."""
        fiche = FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='module',
            noct_c=Decimal('45.0'), uc_w_m2k=Decimal('29.0'),
            uv_w_m3sk=Decimal('0.0'))
        fiche.refresh_from_db()
        self.assertEqual(fiche.noct_c, Decimal('45.0'))
        self.assertEqual(fiche.uc_w_m2k, Decimal('29.0'))
        self.assertEqual(fiche.uv_w_m3sk, Decimal('0.0'))

    def test_champs_vides_naliment_aucun_calcul(self):
        """``specs_for_produit`` (le seul point de lecture partagé entre
        apps) n'expose PAS encore ces clés : un champ vide — ou même
        rempli, avant CAL114 — n'alimente aucun calcul aval."""
        FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='module',
            noct_c=Decimal('45.0'), uc_w_m2k=Decimal('29.0'),
            uv_w_m3sk=Decimal('1.2'))
        self.produit.refresh_from_db()
        specs = specs_for_produit(self.produit)
        self.assertNotIn('noct_c', specs)
        self.assertNotIn('uc_w_m2k', specs)
        self.assertNotIn('uv_w_m3sk', specs)

    def test_serializer_expose_les_champs(self):
        """L'API fiche existante sert les trois nouveaux champs."""
        fiche = FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='module',
            noct_c=Decimal('45.0'))
        data = FicheTechniqueSerializer(fiche).data
        self.assertIn('noct_c', data)
        self.assertIn('uc_w_m2k', data)
        self.assertIn('uv_w_m3sk', data)
        self.assertEqual(Decimal(data['noct_c']), Decimal('45.0'))
        self.assertIsNone(data['uc_w_m2k'])
