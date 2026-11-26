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


class FicheDegradationServieParApiTests(TestCase):
    """ACAL1600 — les champs que la simulation lit (dégradation, garanties,
    entrées et rendement de l'optimiseur) se relisent après un PATCH ; ROUGE
    avant : absents de ``FicheTechniqueSerializer.Meta.fields``, le PATCH
    rendait 200 puis les ignorait en silence."""

    URL = '/api/django/stock/fiches-techniques/'

    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        self.co = Company.objects.get_or_create(
            slug='acal1600-co', defaults={'nom': 'ACAL1600'})[0]
        user = get_user_model().objects.create_user(
            username='acal1600', password='x', company=self.co,
            is_staff=True, is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(user)

        def fiche(sku, type_fiche):
            produit = Produit.objects.create(
                company=self.co, nom=sku, sku=sku, prix_achat=Decimal('1'),
                prix_vente=Decimal('2'), quantite_stock=1)
            return FicheTechnique.objects.create(
                company=self.co, produit=produit, type_fiche=type_fiche)
        self.module = fiche('ACAL1600-MOD', 'module')
        self.optimiseur = fiche('ACAL1600-OPT', 'optimiseur')

    def _url(self, fiche):
        return f'{self.URL}{fiche.pk}/'

    def _patch_puis_get(self, fiche, corps):
        resp = self.client.patch(self._url(fiche), corps, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        return self.client.get(self._url(fiche)).data

    def test_patch_puis_get_relit_la_degradation(self):
        avant = self.client.get(self._url(self.module)).data
        data = self._patch_puis_get(self.module, {
            'degradation_annuelle_pct': 0.45, 'degradation_annee1_pct': 1.0,
            'garantie_pct_a_10_ans': 92, 'garantie_pct_a_25_ans': 84.8})
        self.assertEqual(Decimal(data['degradation_annuelle_pct']), Decimal('0.45'))
        self.assertEqual(Decimal(data['degradation_annee1_pct']), Decimal('1.00'))
        self.assertEqual(Decimal(data['garantie_pct_a_10_ans']), Decimal('92.0'))
        self.assertEqual(Decimal(data['garantie_pct_a_25_ans']), Decimal('84.8'))
        # Rien d'autre ne change dans la réponse.
        modifies = {'degradation_annuelle_pct', 'degradation_annee1_pct',
                    'garantie_pct_a_10_ans', 'garantie_pct_a_25_ans',
                    'date_mise_a_jour'}
        self.assertEqual({k: v for k, v in data.items() if k not in modifies},
                         {k: v for k, v in avant.items() if k not in modifies})

    def test_patch_puis_get_relit_l_optimiseur(self):
        data = self._patch_puis_get(self.optimiseur, {
            'opt_rendement_pct': 99, 'opt_modules_par_optimiseur': 2,
            'opt_pmax_in_w': 600, 'opt_v_in_min': 8, 'opt_v_in_max': 80,
            'opt_i_in_max_a': 15})
        self.assertEqual(Decimal(data['opt_rendement_pct']), Decimal('99.0'))
        self.assertEqual(data['opt_modules_par_optimiseur'], 2)
        self.assertEqual(Decimal(data['opt_pmax_in_w']), Decimal('600'))
        self.assertEqual(Decimal(data['opt_v_in_min']), Decimal('8'))
        self.assertEqual(Decimal(data['opt_v_in_max']), Decimal('80'))
        self.assertEqual(Decimal(data['opt_i_in_max_a']), Decimal('15'))

    def test_valeur_hors_bornes_du_modele_refusee_en_400_nommee(self):
        """Bornes = celles du modèle (``max_digits``, entier positif) : aucune
        seconde validation ; le refus nomme le champ et rien n'est écrit."""
        for champ, valeur in (('degradation_annuelle_pct', 150),
                              ('opt_rendement_pct', 1000),
                              ('opt_modules_par_optimiseur', -1)):
            fiche = (self.optimiseur if champ.startswith('opt_')
                     else self.module)
            resp = self.client.patch(self._url(fiche), {champ: valeur},
                                     format='json')
            self.assertEqual(resp.status_code, 400, (champ, resp.content))
            self.assertIn(champ, resp.data, resp.data)
            fiche.refresh_from_db()
            self.assertIsNone(getattr(fiche, champ))
