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
    autoconso_avec_ratio,
    calculate_savings_roi,
    two_bills_savings,
)

# ── Fixture MIROIR (identique côté JS) ───────────────────────────────────────
# 10 kWc, productible PVGIS 1651 → 16 510 kWh/an ; batterie 10 kWh ;
# consommation réelle 15 000 kWh/an ; barème ONEE.
PROD = 16510
BATTERY = 10
CONSO = 15000
RATIO_ATTENDU = 0.8210781344639613   # 0,60 + 3 650/16 510 (dérivé à la main)


class TestAutoconsoAvecRatio(SimpleTestCase):
    """Le taux « avec batterie » est DÉRIVÉ, jamais forfaitaire."""

    def test_ratio_derive_60pct_plus_un_cycle_par_jour(self):
        # 10 kWh × 365 j = 3 650 kWh/an décalés ; 3 650/16 510 = 0,221078134…
        # → 0,60 + 0,221078134… = 0,821078134…
        ratio = autoconso_avec_ratio(PROD, BATTERY)
        self.assertAlmostEqual(ratio, RATIO_ATTENDU, places=12)
        self.assertEqual(ratio, AUTOCONSO_SANS + (BATTERY * DAYS_PER_YEAR) / PROD)
        # En kWh : 9 906 (60 %) + 3 650 (batterie) = 13 556 autoconsommés.
        self.assertEqual(round(ratio * PROD), 13556)

    def test_plafond_production(self):
        # 30 kWh × 365 = 10 950 kWh > les 40 % de surplus (6 604) → plafond 1.
        self.assertEqual(autoconso_avec_ratio(PROD, 30), 1.0)

    def test_plafond_consommation(self):
        # conso 9 000 kWh/an sur 16 510 produits → 9 000/16 510 = 0,545124…
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
      option SANS (60 %) : autoconsommé 9 906 → résiduel 5 094 → 424,5 kWh/mois
        90,10 + 153,87 + 187,725 + 24,5 × 1,4017 (34,34165) = 466,03665
        × 12 = 5 592,44 → 5 592   ⇒ économie 19 478 − 5 592 = 13 886 MAD/an
      option AVEC (82,1 %) : autoconsommé 13 556 → résiduel 1 444
        → 120,3333 kWh/mois : 90,10 + 20,3333 × 1,0258 (20,857933)
        = 110,957933 × 12 = 1 331,4952 → 1 331
        ⇒ économie 19 478 − 1 331 = 18 147 MAD/an
    """

    def test_miroir_js_meme_fixture_memes_chiffres(self):
        sans = two_bills_savings(PROD, CONSO, AUTOCONSO_SANS, utility="onee")
        avec = two_bills_savings(
            PROD, CONSO, autoconso_avec_ratio(PROD, BATTERY), utility="onee")
        self.assertEqual(sans["facture_sans"], 19478)
        self.assertEqual(sans["facture_avec"], 5592)
        self.assertEqual(sans["economie"], 13886)
        self.assertEqual(avec["autoconso_kwh"], 13556)
        self.assertEqual(avec["facture_avec"], 1331)
        self.assertEqual(avec["economie"], 18147)
        self.assertGreater(avec["economie"], sans["economie"])


class TestCalculateSavingsRoiBattery(SimpleTestCase):
    """calculate_savings_roi dérive le taux dès qu'une capacité est fournie."""

    def test_battery_kwh_derive_le_taux_et_les_economies(self):
        # productible 1651 mais PRODUCTION_DERATE 0,86 côté moteur :
        # production = round(10 × 1651 × 0,86) = 14 199 kWh/an (chiffre du PDF).
        roi = calculate_savings_roi(
            10.0, 100000, 140000, productible=1651, battery_kwh=BATTERY,
            tarif_kwh_override=1.75)
        self.assertEqual(roi["prod_kwh"], 14199)
        # taux dérivé = 0,60 + 3 650/14 199 = 0,857032…
        attendu = AUTOCONSO_SANS + (BATTERY * DAYS_PER_YEAR) / 14199
        self.assertAlmostEqual(roi["autoconso_avec"], attendu, places=12)
        self.assertNotEqual(roi["autoconso_avec"], AUTOCONSO_AVEC)
        # Dérivation à la main :
        #   option 1 : 14 199 × 0,60 = 8 519,4 kWh × 1,75 = 14 908,95 → 14 909
        #   option 2 : 8 519,4 + 3 650 = 12 169,4 kWh × 1,75 = 21 296,45 → 21 296
        #   écart = 6 387 MAD ≈ 3 650 kWh × 1,75 (arrondis compris)
        self.assertEqual(roi["eco_s_ann"], 14909)
        self.assertEqual(roi["eco_a_ann"], 21296)
        self.assertEqual(roi["eco_a_ann"] - roi["eco_s_ann"], 6387)

    def test_sans_battery_kwh_comportement_historique_inchange(self):
        """Aucune capacité → forfait 0,85 conservé (zéro régression)."""
        roi = calculate_savings_roi(
            10.0, 100000, 140000, productible=1651, tarif_kwh_override=1.75)
        self.assertEqual(roi["autoconso_avec"], AUTOCONSO_AVEC)
        # 14 199 × 0,85 = 12 069,15 kWh × 1,75 = 21 121,0125 → 21 121
        self.assertEqual(roi["eco_a_ann"], 21121)

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
        # production = round(3 × 1651 × 0,86) = 4 260 kWh/an ;
        # 20 kWh × 365 = 7 300 kWh « décalables » → impossible : plafond 100 %.
        self.assertEqual(roi["prod_kwh"], 4260)
        self.assertEqual(roi["autoconso_avec"], 1.0)
        self.assertEqual(roi["eco_a_ann"], 7455)   # 4 260 × 1,75
