# -*- coding: utf-8 -*-
"""QJR156 — un prix du kWh non dérivable est ÉTIQUETÉ « estimation ».

Deux cas du même patron, tous deux dans le sens qui présente un forfait comme
un tarif relevé.

(a) Consommation absente + distributeur renseigné :
    ``_weighted_kwh_price(0.0, table)`` rend, par construction, le tarif LE PLUS
    BAS de la grille (la tranche 0-100 kWh) et le tuple sortait
    ``is_estimated=False``. Le document imprimait alors « Tarif électricité
    retenu : 0,92 MAD/kWh (Lydec) » SANS le mot « estimation », et les économies
    étaient calculées à ce prix. Le cas est atteignable : l'écran ne neutralise
    le distributeur sans consommation que pour ONEE. La ligne juste au-dessus
    (``return _FALLBACK_KWH_PRICE, True``) prouvait que le chemin honnête
    existait déjà.
(b) Grille société dont TOUS les paliers ont un plafond fini : la bande
    sélective est vide et le ``_FALLBACK_KWH_PRICE`` codé en dur (1,20) est
    présenté comme le barème du client, ``is_estimated=False``. Rien ne
    l'interdisait à la saisie.

Tests purs — aucune base, aucun réseau.
"""
from django.test import SimpleTestCase
from rest_framework import serializers as drf_serializers

from apps.parametres.serializers_tariff import TariffSettingsSerializer
from apps.ventes.quote_engine.builder import ligne_tarif_hypothese
from apps.ventes.quote_engine.pricing import (
    UTILITY_TABLES,
    _avg_kwh_price_from_tranches,
    _FALLBACK_KWH_PRICE,
    _monthly_bill_from_kwh,
    _weighted_kwh_price,
    calculate_savings_roi,
)


class SansConsommationLePrixEstEstimeTests(SimpleTestCase):
    """(a) La grille du client sert encore, mais elle est ÉTIQUETÉE."""

    TABLE = UTILITY_TABLES['onee']

    def test_sans_consommation_le_drapeau_estimation_se_leve(self):
        for conso in (None, 0, 0.0):
            _prix, estime = _avg_kwh_price_from_tranches(
                conso, 'onee', None)
            self.assertTrue(estime, msg=repr(conso))

    def test_le_prix_rendu_reste_celui_de_la_grille_du_client(self):
        """Mieux qu'un forfait sans rapport avec son distributeur."""
        prix, _estime = _avg_kwh_price_from_tranches(None, 'onee', None)
        self.assertAlmostEqual(prix, self.TABLE[0][1], places=9)
        self.assertNotAlmostEqual(prix, _FALLBACK_KWH_PRICE, places=4)

    def test_c_est_bien_le_tarif_LE_PLUS_BAS_de_la_grille(self):
        """La raison pour laquelle il ne peut pas passer pour un prix moyen."""
        prix, _estime = _avg_kwh_price_from_tranches(None, 'onee', None)
        self.assertAlmostEqual(prix, min(p for _c, p in self.TABLE), places=9)

    def test_avec_consommation_rien_ne_change(self):
        prix, estime = _avg_kwh_price_from_tranches(6000.0, 'onee', None)
        self.assertFalse(estime)
        self.assertAlmostEqual(prix, _weighted_kwh_price(500.0, self.TABLE),
                               places=9)

    def test_une_surcharge_appelant_suit_la_meme_regle(self):
        table = [(100, 1.0), (None, 2.0)]
        prix, estime = _avg_kwh_price_from_tranches(None, None, table)
        self.assertTrue(estime)
        self.assertAlmostEqual(prix, 1.0, places=9)

    def test_sans_aucune_table_le_repli_honnete_est_conserve(self):
        prix, estime = _avg_kwh_price_from_tranches(None, 'inconnu', None)
        self.assertTrue(estime)
        self.assertAlmostEqual(prix, _FALLBACK_KWH_PRICE, places=9)


class LeDocumentDitEstimationTests(SimpleTestCase):
    """La mention « (estimation) » atteint réellement le document."""

    def _roi(self, **kwargs):
        base = dict(puissance_kwc=6.0, total_sans=90000, total_avec=140000,
                    utility='onee')
        base.update(kwargs)
        return calculate_savings_roi(**base)

    def test_sans_consommation_le_roi_se_declare_estime(self):
        self.assertTrue(self._roi()['savings_estimated'])

    def test_avec_consommation_le_roi_ne_se_declare_plus_estime(self):
        self.assertFalse(self._roi(conso_annuelle_kwh=6000.0)
                         ['savings_estimated'])

    def test_la_ligne_du_bloc_hypotheses_porte_le_mot_estimation(self):
        """La fonction PURE que le document appelle, avec le drapeau réel."""
        roi = self._roi()
        ligne = ligne_tarif_hypothese(
            '0,92', 'ONEE', roi['savings_estimated'])
        self.assertIn('(estimation)', ligne)
        self.assertNotIn('Tarif électricité retenu', ligne)

    def test_avec_consommation_la_ligne_annonce_un_tarif_retenu(self):
        roi = self._roi(conso_annuelle_kwh=6000.0)
        ligne = ligne_tarif_hypothese(
            '1,38', 'ONEE', roi['savings_estimated'])
        self.assertIn('Tarif électricité retenu', ligne)
        self.assertNotIn('(estimation)', ligne)

    def test_le_tarif_societe_ne_remplace_que_le_repli_sans_table(self):
        """DC2 garde son périmètre : sans TABLE, pas « sans consommation »."""
        sans_table = calculate_savings_roi(
            puissance_kwc=6.0, total_sans=90000, total_avec=140000,
            utility='inconnu', fallback_tarif_kwh=1.75)
        self.assertAlmostEqual(sans_table['tarif_kwh'], 1.75, places=6)
        # Avec une grille réelle mais sans consommation, c'est la grille du
        # client qui parle — étiquetée, mais la sienne.
        avec_table = calculate_savings_roi(
            puissance_kwc=6.0, total_sans=90000, total_avec=140000,
            utility='onee', fallback_tarif_kwh=1.75)
        self.assertTrue(avec_table['savings_estimated'])
        self.assertNotAlmostEqual(avec_table['tarif_kwh'], 1.75, places=4)


class GrilleSansPalierOuvertTests(SimpleTestCase):
    """(b) Une grille entièrement fermée est refusée À LA SAISIE."""

    def _valider(self, tiers):
        return TariffSettingsSerializer().validate_residential_tiers(tiers)

    def test_une_grille_entierement_fermee_est_refusee(self):
        with self.assertRaises(drf_serializers.ValidationError):
            self._valider([
                {'max_kwh': 100, 'prix_kwh_ttc': '1.0000'},
                {'max_kwh': 150, 'prix_kwh_ttc': '1.2000'},
            ])

    def test_un_palier_ferme_apres_le_palier_ouvert_est_refuse(self):
        with self.assertRaises(drf_serializers.ValidationError):
            self._valider([
                {'max_kwh': 100, 'prix_kwh_ttc': '1.0000'},
                {'max_kwh': None, 'prix_kwh_ttc': '1.6000'},
                {'max_kwh': 500, 'prix_kwh_ttc': '1.8000'},
            ])

    def test_deux_paliers_ouverts_sont_refuses(self):
        with self.assertRaises(drf_serializers.ValidationError):
            self._valider([
                {'max_kwh': None, 'prix_kwh_ttc': '1.0000'},
                {'max_kwh': None, 'prix_kwh_ttc': '1.6000'},
            ])

    def test_une_grille_bien_formee_passe(self):
        propre = self._valider([
            {'max_kwh': 100, 'prix_kwh_ttc': '1.0000'},
            {'max_kwh': 150, 'prix_kwh_ttc': '1.2000'},
            {'max_kwh': None, 'prix_kwh_ttc': '1.6000'},
        ])
        self.assertEqual(len(propre), 3)
        self.assertIsNone(propre[-1]['max_kwh'])

    def test_le_repli_vide_reste_accepte(self):
        for vide in (None, '', []):
            self.assertIsNone(self._valider(vide))

    def test_pourquoi_on_refuse_ce_forfait_se_faisait_passer_pour_le_bareme(self):
        """Le danger, montré : sans palier ouvert, 1,20 tarife le client."""
        from apps.ventes.quote_engine.pricing import TrancheTable
        fermee = TrancheTable([(100, 1.0), (150, 1.2)],
                              selective_threshold=150, boundary_tolerance=10)
        facture = _monthly_bill_from_kwh(400, fermee)
        self.assertAlmostEqual(facture, 400 * _FALLBACK_KWH_PRICE, places=6)
