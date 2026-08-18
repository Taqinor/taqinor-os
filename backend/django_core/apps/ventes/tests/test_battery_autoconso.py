"""ORDRE FONDATEUR (18/08) — modèle d'économies « avec batterie » ADDITIF.

    sans batterie : autoconsommé = 60 % × production
    avec batterie : autoconsommé = 60 % × production
                    + capacité_kWh × 1 cycle/jour
    plafonds      : jamais plus que la production ; jamais plus que la
                    consommation réelle quand elle est connue.

Le forfait « 85 % avec batterie » ne survit QUE comme repli documenté
(capacité batterie inconnue, ou taux forcé par le vendeur dans
``etude_params['autoconso_avec']``).

Ce fichier est le VERROU DE DÉRIVE avec son jumeau JS
``frontend/src/features/ventes/solar.batterie.test.mjs`` : mêmes entrées,
mêmes valeurs attendues, DÉRIVÉES À LA MAIN des deux côtés (jamais copiées
d'une sortie de code).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_battery_autoconso -v 2
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine.pricing import (
    AUTOCONSO_AVEC,
    AUTOCONSO_SANS,
    DAYS_PER_YEAR,
    PRODUCTION_DERATE,
    PVGIS_BUILTIN_LOSS,
    SYSTEM_LOSS_TOTAL,
    autoconso_avec_ratio,
    calculate_savings_roi,
    two_bills_savings,
)

# ── Fixture MIROIR (identique côté JS) ───────────────────────────────────────
# 10 kWc à Casablanca : productible stocké 1651 (PVGIS, déjà net de 14 %) ramené
# aux 20 % de pertes TOTALES du fondateur → 1651 × 0,9302 = 1 535,81, soit
# 15 358 kWh/an pour 10 kWc. Batterie 10 kWh ; conso 15 000 kWh/an ; ONEE.
PROD = 15358
BATTERY = 10
CONSO = 15000
RATIO_ATTENDU = 0.8376611538   # 0,60 + 3 650/15 358 (dérivé à la main)


class TestAutoconsoAvecRatio(SimpleTestCase):
    """Le taux « avec batterie » est DÉRIVÉ, jamais forfaitaire."""

    def test_ratio_derive_60pct_plus_un_cycle_par_jour(self):
        # 10 kWh × 365 j = 3 650 kWh/an décalés ; 3 650/15 358 = 0,237661154…
        # → 0,60 + 0,237661154… = 0,837661154…
        ratio = autoconso_avec_ratio(PROD, BATTERY)
        self.assertAlmostEqual(ratio, RATIO_ATTENDU, places=9)
        self.assertEqual(ratio, AUTOCONSO_SANS + (BATTERY * DAYS_PER_YEAR) / PROD)
        # En kWh : 9 214,8 (60 %) + 3 650 (batterie) = 12 864,8 → 12 865.
        self.assertEqual(round(ratio * PROD), 12865)

    def test_plafond_production(self):
        # 30 kWh × 365 = 10 950 kWh > les 40 % de surplus (6 143) → plafond 1.
        self.assertEqual(autoconso_avec_ratio(PROD, 30), 1.0)

    def test_plafond_consommation(self):
        # conso 9 000 kWh/an sur 15 358 produits → 9 000/15 358 = 0,586014…
        ratio = autoconso_avec_ratio(PROD, BATTERY, conso_annuelle_kwh=9000)
        self.assertEqual(ratio, 9000 / PROD)
        self.assertLess(ratio, RATIO_ATTENDU)

    def test_repli_documente_quand_capacite_inconnue(self):
        self.assertEqual(autoconso_avec_ratio(PROD, 0), AUTOCONSO_AVEC)
        self.assertEqual(autoconso_avec_ratio(PROD, None), AUTOCONSO_AVEC)
        self.assertEqual(autoconso_avec_ratio(0, BATTERY), AUTOCONSO_AVEC)
        self.assertEqual(autoconso_avec_ratio("x", "y"), AUTOCONSO_AVEC)


class TestMiroirJs(SimpleTestCase):
    """VERROU DE DÉRIVE — mêmes chiffres que solar.batterie.test.mjs.

    Valeurs dérivées À LA MAIN du barème ONEE
    [[100, 0.9010], [250, 1.0258], [400, 1.2515], [null, 1.4017]] :

      facture sans solaire : 15 000/12 = 1 250 kWh/mois
        100 × 0,9010 = 90,10 | 150 × 1,0258 = 153,87 | 150 × 1,2515 = 187,725
        850 × 1,4017 = 1 191,445 → 1 623,14 MAD/mois × 12 = 19 477,68 → 19 478
      option SANS (60 %) : autoconsommé 9 214,8 → résiduel 5 785,2
        → 482,1 kWh/mois : 90,10 + 153,87 + 187,725 + 82,1 × 1,4017 (115,07957)
        = 546,77457 × 12 = 6 561,29 → 6 561
        ⇒ économie 19 478 − 6 561 = 12 917 MAD/an
      option AVEC (83,8 %) : autoconsommé 12 864,8 → résiduel 2 135,2
        → 177,9333 kWh/mois : 90,10 + 77,9333 × 1,0258 (79,944013)
        = 170,044013 × 12 = 2 040,528 → 2 041
        ⇒ économie 19 478 − 2 041 = 17 437 MAD/an
    """

    def test_miroir_js_meme_fixture_memes_chiffres(self):
        sans = two_bills_savings(PROD, CONSO, AUTOCONSO_SANS, utility="onee")
        avec = two_bills_savings(
            PROD, CONSO, autoconso_avec_ratio(PROD, BATTERY), utility="onee")
        self.assertEqual(sans["facture_sans"], 19478)
        self.assertEqual(sans["facture_avec"], 6561)
        self.assertEqual(sans["economie"], 12917)
        self.assertEqual(avec["autoconso_kwh"], 12865)
        self.assertEqual(avec["facture_avec"], 2041)
        self.assertEqual(avec["economie"], 17437)
        self.assertGreater(avec["economie"], sans["economie"])

    def test_miroir_js_bout_en_bout_meme_production_memes_economies(self):
        """Jumeau EXACT du test JS « computeROI (modèle deux factures) ».

        Mêmes entrées (10 kWc, productible 1651, batterie 10 kWh, conso
        15 000 kWh/an, ONEE) → MÊME production entière et MÊMES économies que
        solar.batterie.test.mjs. C'est la garantie écran = PDF au dirham.
        """
        roi = calculate_savings_roi(
            10.0, 100000, 140000, productible=1651, battery_kwh=BATTERY,
            utility="onee", conso_annuelle_kwh=CONSO)
        self.assertEqual(roi["savings_model"], "factures")
        self.assertEqual(roi["prod_kwh"], PROD)                 # 15 358
        self.assertAlmostEqual(roi["autoconso_avec"], RATIO_ATTENDU, places=9)
        self.assertEqual(roi["eco_s_ann"], 12917)
        self.assertEqual(roi["eco_a_ann"], 17437)


class TestPertesSysteme20Pct(SimpleTestCase):
    """Pertes système : 20 % AU TOTAL (ordre fondateur 18/08).

    Les productibles stockés (``productible.py`` : 1651 Casablanca…) sont des
    sorties PVGIS demandées à ``loss=14`` — 14 % sont DÉJÀ dedans. On applique
    donc le seul COMPLÉMENT (1 − 0,20)/(1 − 0,14) ≈ 0,9302. L'ancien 0,86
    retranchait 14 % une SECONDE fois (26 % cumulés).
    """

    def test_facteur_est_le_complement_pas_un_second_derate(self):
        self.assertEqual(SYSTEM_LOSS_TOTAL, 0.20)
        self.assertEqual(PVGIS_BUILTIN_LOSS, 0.14)
        self.assertEqual(PRODUCTION_DERATE, 0.8 / 0.86)
        self.assertAlmostEqual(PRODUCTION_DERATE, 0.9302325581395349, places=15)
        # Le total réellement subi par le productible BRUT vaut bien 20 %.
        self.assertAlmostEqual(
            (1 - PVGIS_BUILTIN_LOSS) * PRODUCTION_DERATE, 0.80, places=15)

    def test_production_10kwc_casablanca(self):
        """10 kWc × 1651 = 16 510 kWh (net 14 %) → 15 358 kWh (net 20 %)."""
        roi = calculate_savings_roi(
            10.0, 100000, 140000, productible=1651, tarif_kwh_override=1.75)
        self.assertEqual(roi["prod_kwh"], 15358)
        self.assertEqual(round(16510 * PRODUCTION_DERATE), 15358)


class TestCalculateSavingsRoiBattery(SimpleTestCase):
    """calculate_savings_roi dérive le taux dès qu'une capacité est fournie."""

    def test_battery_kwh_derive_le_taux_et_les_economies(self):
        # production = round(10 × 1651 × 0,9302325581) = 15 358 kWh/an
        # (20 % de pertes AU TOTAL — chiffre du PDF ET de l'écran).
        roi = calculate_savings_roi(
            10.0, 100000, 140000, productible=1651, battery_kwh=BATTERY,
            tarif_kwh_override=1.75)
        self.assertEqual(roi["prod_kwh"], PROD)
        # taux dérivé = 0,60 + 3 650/15 358 = 0,837661…
        self.assertAlmostEqual(roi["autoconso_avec"], RATIO_ATTENDU, places=9)
        self.assertNotEqual(roi["autoconso_avec"], AUTOCONSO_AVEC)
        # Dérivation à la main :
        #   option 1 : 15 358 × 0,60 = 9 214,8 kWh × 1,75 = 16 125,90 → 16 126
        #   option 2 : 9 214,8 + 3 650 = 12 864,8 kWh × 1,75 = 22 513,40 → 22 513
        #   écart = 6 387 MAD ≈ 3 650 kWh × 1,75 (arrondis compris)
        self.assertEqual(roi["eco_s_ann"], 16126)
        self.assertEqual(roi["eco_a_ann"], 22513)
        self.assertEqual(roi["eco_a_ann"] - roi["eco_s_ann"], 6387)

    def test_sans_battery_kwh_comportement_historique_inchange(self):
        """Aucune capacité → forfait 0,85 conservé (zéro régression)."""
        roi = calculate_savings_roi(
            10.0, 100000, 140000, productible=1651, tarif_kwh_override=1.75)
        self.assertEqual(roi["autoconso_avec"], AUTOCONSO_AVEC)
        # 15 358 × 0,85 = 13 054,3 kWh × 1,75 = 22 845,025 → 22 845
        self.assertEqual(roi["eco_a_ann"], 22845)

    def test_taux_force_par_le_vendeur_reste_souverain(self):
        """Un autoconso_avec explicite sert de repli — il n'est pas écrasé…

        …et quand une capacité EST fournie, c'est bien la dérivation qui parle
        (le builder n'envoie ``battery_kwh`` que si le vendeur n'a rien forcé).
        """
        roi = calculate_savings_roi(
            10.0, 100000, 140000, productible=1651, autoconso_avec=0.70,
            tarif_kwh_override=1.75)
        self.assertEqual(roi["autoconso_avec"], 0.70)

    def test_petite_installation_grosse_batterie_plafonnee(self):
        """3 kWc + 20 kWh : impossible de décaler plus que la production."""
        roi = calculate_savings_roi(
            3.0, 40000, 60000, productible=1651, battery_kwh=20,
            tarif_kwh_override=1.75)
        # production = round(3 × 1651 × 0,9302325581) = 4 607 kWh/an ;
        # 20 kWh × 365 = 7 300 kWh « décalables » → impossible : plafond 100 %.
        self.assertEqual(roi["prod_kwh"], 4607)
        self.assertEqual(roi["autoconso_avec"], 1.0)
        self.assertEqual(roi["eco_a_ann"], 8062)   # 4 607 × 1,75 = 8 062,25
