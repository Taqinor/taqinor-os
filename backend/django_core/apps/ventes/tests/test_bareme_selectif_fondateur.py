"""ORDRE FONDATEUR (18/08) — ÉCONOMIES RÉELLES, AU BARÈME SÉLECTIF.

« The client will go down in the price per kWh because he will be below 500 kWh
  per month — I want the new price per kWh to be used so the savings are real. »

Le barème résidentiel marocain n'est pas un tarif moyen : il est PROGRESSIF
jusqu'à 150 kWh/mois, puis SÉLECTIF — franchir une marche re-tarife la TOTALITÉ
de la consommation du mois au prix de sa tranche. Un foyer à 700 kWh/mois paie
donc 1,622856 MAD/kWh sur ses 700 kWh ; une fois le solaire posé, son résiduel
de 280 kWh/mois retombe dans la tranche 211-310 et se facture 1,187388 MAD/kWh
— sur la totalité lui aussi. L'économie réelle = facture(avant) − facture(après),
mois par mois (jamais annualisée avant d'être tarifée : le seuil est MENSUEL).

ORDRE FONDATEUR (19/08/2026) — TVA 20 % depuis le 01/01/2026 (16 % en 2024,
18 % en 2025) : les six prix ci-dessous ont été re-dérivés HT × 1,20 (voir
pricing.py ONEE_TRANCHES pour la dérivation complète) ; l'ancre est la tranche
>500 kWh, confirmée par le fondateur à 1,622856 MAD/kWh TTC (facture réelle).

VERROU DE DÉRIVE À TROIS BRANCHES. Ce fichier est le jumeau EXACT de :
  · frontend/src/features/ventes/solar.test.mjs (écran ERP, mêmes fixtures) ;
  · apps/web/tests/savingsTranchesFondateur.test.ts (estimateur public).
Les trois portent les MÊMES entrées et les MÊMES attendus, tous DÉRIVÉS À LA
MAIN de la grille officielle — jamais copiés d'une sortie de code. Si l'un des
trois bouge sans les autres, l'ERP et le site cesseraient d'annoncer la même
économie au même client : c'est précisément ce que ce verrou interdit.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_bareme_selectif_fondateur -v 2
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine.pricing import (
    ONEE_TRANCHES,
    _monthly_bill_from_kwh,
    _weighted_kwh_price,
    kwh_from_bill,
    two_bills_savings,
)

# Grille officielle (TTC, 2026 — TVA 20 %) : progressif 0-100 = 0,916272 ·
# 101-150 = 1,091388 ; sélectif (toute la conso au tarif de sa tranche,
# tolérance 10 kWh) : 151-210 = 1,091388 · 211-310 = 1,187388 ·
# 311-510 = 1,405116 · > 510 = 1,622856.
TARIF_HAUT = 1.622856    # > 510 kWh/mois
TARIF_310 = 1.187388     # 211-310 kWh/mois
TARIF_510 = 1.405116     # 311-510 kWh/mois

# (conso mensuelle kWh, facture mensuelle MAD) — chaque marche du barème,
# dérivée À LA MAIN. Le jumeau JS (solar.test.mjs, BAREME_FIXTURE) porte la
# MÊME table.
BAREME_FIXTURE = [
    (100, 91.6272),     # progressif : 100 × 0,916272
    (150, 146.1966),    # progressif : 91,6272 + 50 × 1,091388 (= 54,5694)
    (151, 164.799588),  # 1re marche sélective : 151 × 1,091388
    (210, 229.19148),   # haut de bande (tolérance) : 210 × 1,091388
    (211, 250.538868),  # bande suivante, TOUTE la conso : 211 × 1,187388
    (310, 368.09028),   # 310 × 1,187388
    (311, 436.991076),  # 311 × 1,405116
    (499, 701.152884),  # 499 × 1,405116
    (500, 702.558),     # 500 × 1,405116 — le seuil « 500 » du fondateur
    (501, 703.963116),  # 501 × 1,405116 (encore dans sa bande : borne eff. 510)
    (510, 716.60916),   # 510 × 1,405116
    (511, 829.279416),  # 511 × 1,622856 — la marche du haut de grille
    (700, 1135.9992),   # 700 × 1,622856
]


class TestBaremeSelectif(SimpleTestCase):
    """La grille porte bien les marches, et chacune vaut son montant."""

    def test_la_table_declare_la_regle_selective(self):
        self.assertEqual([c for c, _ in ONEE_TRANCHES],
                         [100, 150, 200, 300, 500, None])
        self.assertEqual(ONEE_TRANCHES.selective_threshold, 150)
        self.assertEqual(ONEE_TRANCHES.boundary_tolerance, 10)
        self.assertEqual(ONEE_TRANCHES[-1][1], TARIF_HAUT)

    def test_chaque_marche_vaut_le_montant_derive_a_la_main(self):
        for kwh, mad in BAREME_FIXTURE:
            self.assertAlmostEqual(
                _monthly_bill_from_kwh(kwh, ONEE_TRANCHES), mad, places=9,
                msg=f"{kwh} kWh/mois")

    def test_la_facture_ne_decroit_jamais_quand_la_conso_monte(self):
        for i in range(1, len(BAREME_FIXTURE)):
            self.assertGreater(BAREME_FIXTURE[i][1], BAREME_FIXTURE[i - 1][1])
        # 511 kWh coûte 112,670256 MAD de plus que 510 kWh pour UN kWh de plus :
        # 829,279416 − 716,60916 — c'est la marche sélective, pas un arrondi.
        self.assertAlmostEqual(829.279416 - 716.60916, 112.670256, places=9)

    def test_le_prix_effectif_du_kwh_chute_sous_la_marche(self):
        # C'est LA phrase du fondateur : le prix du kWh baisse, pas seulement
        # le volume facturé.
        self.assertAlmostEqual(
            _weighted_kwh_price(700, ONEE_TRANCHES), TARIF_HAUT, places=9)
        self.assertAlmostEqual(
            _weighted_kwh_price(280, ONEE_TRANCHES), TARIF_310, places=9)
        self.assertLess(_weighted_kwh_price(280, ONEE_TRANCHES),
                        _weighted_kwh_price(700, ONEE_TRANCHES))


class TestInverseExact(SimpleTestCase):
    """kwh_from_bill est le vrai inverse — trous du barème compris."""

    def test_aller_retour_sur_toute_la_grille(self):
        for kwh, _mad in BAREME_FIXTURE:
            bill = _monthly_bill_from_kwh(kwh, ONEE_TRANCHES)
            self.assertAlmostEqual(
                kwh_from_bill(bill, utility="onee")["kwh_mensuel"], kwh,
                places=1, msg=f"aller-retour {kwh} kWh")

    def test_un_montant_dans_un_trou_se_resout_a_la_borne_basse(self):
        # À 210 kWh la facture vaut 210 × 1,091388 = 229,19148 ; au premier kWh
        # au-dessus elle SAUTE à 211 × 1,187388 = 250,538868. Aucune
        # consommation ne produit 235 MAD → on renvoie la borne basse du saut
        # (210 kWh) : jamais une conso que le barème ne peut pas produire, et
        # toujours le côté prudent (moins de kWh ⇒ système plus petit). Miroir
        # JS identique.
        self.assertAlmostEqual(
            kwh_from_bill(235, utility="onee")["kwh_mensuel"], 210.0, places=1)
        # Même règle au raccord progressif → sélectif (146,1966 → 164,799588).
        self.assertAlmostEqual(
            kwh_from_bill(150.5, utility="onee")["kwh_mensuel"], 150.0,
            places=1)

    def test_une_grosse_facture_ne_fabrique_pas_des_kwh_inexistants(self):
        # 1 135,9992 MAD → 700 kWh au vrai barème. Un diviseur « moyen » à 1,20
        # (l'ancien repli plat) aurait annoncé 947 kWh — 35 % de trop, donc un
        # système surdimensionné et des économies surévaluées.
        self.assertAlmostEqual(
            kwh_from_bill(1135.9992, utility="onee")["kwh_mensuel"], 700.0,
            places=1)
        self.assertAlmostEqual(1135.9992 / 1.20, 946.666, places=2)


class TestScenarioFondateur(SimpleTestCase):
    """700 kWh/mois → résiduel 280 kWh/mois : les chiffres verrouillés.

    Dérivation à la main (TVA 20 % depuis 01/01/2026) :
      conso           700 kWh/mois → 700 × 1,622856 = 1 135,9992 MAD
      autoconsommé    420 kWh/mois (60 % — l'ordre de grandeur solaire)
      résiduel        280 kWh/mois → 280 × 1,187388 =   332,46864 MAD
      économie réelle 1 135,9992 − 332,46864          =   803,53056 MAD/mois
                                             × 12 = 9 642,3672 MAD/an
    Ce sont EXACTEMENT les chiffres du site (savingsTranchesFondateur.test.ts).
    """

    def test_economie_mensuelle_au_barème(self):
        avant = _monthly_bill_from_kwh(700, ONEE_TRANCHES)
        apres = _monthly_bill_from_kwh(280, ONEE_TRANCHES)
        self.assertAlmostEqual(avant, 1135.9992, places=9)
        self.assertAlmostEqual(apres, 332.46864, places=9)
        self.assertAlmostEqual(avant - apres, 803.53056, places=9)
        self.assertEqual(round((avant - apres) * 12), 9642)

    def test_passer_sous_le_seuil_vaut_plus_que_les_kwh_effaces(self):
        # 420 kWh × 1,622856 = 681,59952 MAD si l'on valorisait « à l'ancien
        # prix ». L'économie réelle est de 803,53056 MAD, soit 1,179× plus : en
        # descendant sous 510 kWh, le client ne fait pas qu'effacer 420 kWh —
        # il RE-TARIFE les 280 kWh qui restent (1,622856 → 1,187388).
        au_marginal = 420 * TARIF_HAUT
        self.assertAlmostEqual(au_marginal, 681.59952, places=9)
        reel = (_monthly_bill_from_kwh(700, ONEE_TRANCHES)
                - _monthly_bill_from_kwh(280, ONEE_TRANCHES))
        self.assertGreater(reel, au_marginal)
        self.assertAlmostEqual(reel / au_marginal, 1.17889, places=5)

    def test_deux_factures_annuelles_meme_chaine(self):
        # 8 400 kWh/an (= 700/mois), production 8 400 kWh/an autoconsommée à
        # 60 % → 5 040 kWh effacés, résiduel 3 360 kWh/an = 280 kWh/mois.
        #   facture sans : 1 135,9992 × 12 = 13 631,9904 → 13 632
        #   facture avec :   332,46864 × 12 =  3 989,62368 →  3 990
        #   économie      : 13 632 − 3 990 = 9 642 MAD/an
        out = two_bills_savings(8400, 8400, 0.60, utility="onee")
        self.assertEqual(out["facture_sans"], 13632)
        self.assertEqual(out["facture_avec"], 3990)
        self.assertEqual(out["economie"], 9642)
        self.assertEqual(out["autoconso_kwh"], 5040)
        self.assertFalse(out["approximatif"])

    def test_le_residuel_sous_311_retombe_encore_plus_bas(self):
        # Borne basse du site (autoconsommation 75 % réellement synchrone) :
        # résiduel 385 kWh/mois → tranche 311-510 → 385 × 1,405116 = 540,96966
        # → économie 1 135,9992 − 540,96966 = 595,02954 MAD/mois (7 140,35/an).
        self.assertAlmostEqual(
            _monthly_bill_from_kwh(385, ONEE_TRANCHES), 540.96966, places=9)
        self.assertAlmostEqual(
            _monthly_bill_from_kwh(700, ONEE_TRANCHES) - 540.96966,
            595.02954, places=9)


class TestLydecRedalRestentProgressifs(SimpleTestCase):
    """Aucune grille sélective vérifiée pour les délégataires → progressif +
    drapeau « approximatif », exactement comme avant (zéro régression)."""

    def test_lydec_reste_progressif_et_approximatif(self):
        # 200 kWh/mois : 100 × 0,9500 + 100 × 1,1500 = 95 + 115 = 210 MAD
        # (cumulé, PAS 200 × 1,1500 = 230 — Lydec n'est pas sélectif ici).
        from apps.ventes.quote_engine.pricing import LYDEC_TRANCHES
        self.assertAlmostEqual(
            _monthly_bill_from_kwh(200, LYDEC_TRANCHES), 210.0, places=9)
        self.assertIsNone(getattr(LYDEC_TRANCHES, "selective_threshold", None))
        out = kwh_from_bill(210, utility="lydec")
        self.assertTrue(out["approximatif"])
        self.assertAlmostEqual(out["kwh_mensuel"], 200.0, places=1)

    def test_un_bareme_colle_par_le_vendeur_reste_progressif(self):
        # 150 kWh → 100 × 2,0 + 50 × 3,0 = 350 MAD (cumulé).
        custom = [(100, 2.0), (None, 3.0)]
        self.assertAlmostEqual(
            _monthly_bill_from_kwh(150, custom), 350.0, places=9)
        self.assertAlmostEqual(
            kwh_from_bill(350, tranches_override=custom)["kwh_mensuel"], 150.0,
            places=1)
