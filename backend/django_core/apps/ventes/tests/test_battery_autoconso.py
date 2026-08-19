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

    Valeurs dérivées À LA MAIN du barème ONEE SÉLECTIF **TTC 2026** (TVA 20 %
    depuis le 01/01/2026, bases HT inchangées — cf. pricing.ONEE_TRANCHES) :
    progressif ≤ 150 kWh/mois — 0,916272 puis 1,091388 ; au-delà, TOUTE la
    conso au tarif de SA tranche — 151-210 = 1,091388 · 211-310 = 1,187388 ·
    311-510 = 1,405116 · > 510 = 1,622856) :

      facture sans solaire : 15 000/12 = 1 250 kWh/mois → tranche > 510
        1 250 × 1,622856 = 2 028,57 MAD/mois × 12 = 24 342,84 → 24 343 MAD/an
      option SANS (60 %) : autoconsommé 9 214,8 → résiduel 5 785,2
        → 482,1 kWh/mois → tranche 311-510 : 482,1 × 1,405116 = 677,40642
        × 12 = 8 128,877 → 8 129
        ⇒ économie 24 343 − 8 129 = 16 214 MAD/an
      option AVEC (83,8 %) : autoconsommé 12 864,8 → résiduel 2 135,2
        → 177,9333 kWh/mois → tranche 151-210 : 177,9333 × 1,091388 = 194,19432
        × 12 = 2 330,33 → 2 330
        ⇒ économie 24 343 − 2 330 = 22 013 MAD/an

    La batterie fait franchir DEUX marches vers le bas (1,405116 → 1,091388 sur
    la TOTALITÉ du résiduel) : c'est là que le barème sélectif change tout.
    """

    def test_miroir_js_meme_fixture_memes_chiffres(self):
        sans = two_bills_savings(PROD, CONSO, AUTOCONSO_SANS, utility="onee")
        avec = two_bills_savings(
            PROD, CONSO, autoconso_avec_ratio(PROD, BATTERY), utility="onee")
        self.assertEqual(sans["facture_sans"], 24343)
        self.assertEqual(sans["facture_avec"], 8129)
        self.assertEqual(sans["economie"], 16214)
        self.assertEqual(avec["autoconso_kwh"], 12865)
        self.assertEqual(avec["facture_avec"], 2330)
        self.assertEqual(avec["economie"], 22013)
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
        self.assertEqual(roi["eco_s_ann"], 16214)
        self.assertEqual(roi["eco_a_ann"], 22013)


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


class TestPlafondConsoModeleEstimation(SimpleTestCase):
    """VERROU DE DÉRIVE — plafond consommation du côté « SANS » (18/08).

    Le côté AVEC batterie était déjà borné par la consommation réelle
    (``autoconso_avec_ratio``) ; le côté SANS restait un pourcentage de la
    seule PRODUCTION. Résultat sur une petite conso face à une grosse
    production : l'option BATTERIE économisait MOINS que l'option sans
    batterie sur le PDF CLIENT — l'inverse de ce qu'on lui vend.

    Jumeau JS : ``solar.batterie.test.mjs`` (« plafond consommation »), mêmes
    entrées, mêmes 6 000 MAD des deux côtés.
    """

    def test_repro_8kwc_conso_5000_batterie_10kwh(self):
        """Le cas exact du défaut, dérivé À LA MAIN.

        production   = round(8 × 1 240 × 0,80/0,86) = round(9 227,906…) = 9 228
        tarif        = repli 1,20 MAD/kWh (aucune table, aucun override)
        conso/prod   = 5 000/9 228 = 0,5418292154…
        taux SANS    : AVANT min() → 0,60 ⇒ 9 228 × 0,60 × 1,20 = 6 644,16
                       → 6 644 MAD (on valorisait 5 536,8 kWh pour un client
                       qui n'en consomme que 5 000)
                       APRÈS  → min(0,60 ; 0,5418292154) = 0,5418292154
                       ⇒ 9 228 × 0,5418292154 × 1,20 = 6 000 MAD
        taux AVEC    : 0,60 + 3 650/9 228 = 0,9955353273 → plafonné par la
                       conso à 0,5418292154 ⇒ 6 000 MAD (inchangé)
        ⇒ l'inversion 6 644 > 6 000 disparaît ; l'invariant tient à l'égalité
          (les deux options saturent la MÊME consommation).
        """
        roi = calculate_savings_roi(
            8.0, 100000, 140000, conso_annuelle_kwh=5000, battery_kwh=10)
        self.assertEqual(roi["savings_model"], "estimation")
        self.assertEqual(roi["prod_kwh"], 9228)
        self.assertEqual(roi["tarif_kwh"], 1.20)
        self.assertAlmostEqual(roi["autoconso_sans"], 5000 / 9228, places=12)
        self.assertAlmostEqual(roi["autoconso_avec"], 5000 / 9228, places=12)
        self.assertEqual(roi["eco_s_ann"], 6000)
        self.assertEqual(roi["eco_a_ann"], 6000)
        # Le chiffre FAUX d'avant correctif ne doit jamais revenir.
        self.assertNotEqual(roi["eco_s_ann"], 6644)

    def test_sans_consommation_connue_comportement_historique(self):
        """Aucune conso → aucun plafond : chiffres BYTE-IDENTIQUES à avant.

        9 228 × 0,60 × 1,20 = 6 644,16 → 6 644 ; côté AVEC le taux dérivé
        0,9955353273 (non plafonné, faute de conso) ⇒ 9 228 × 0,9955353273
        × 1,20 = 11 024,4… → 11 024.
        """
        roi = calculate_savings_roi(8.0, 100000, 140000, battery_kwh=10)
        self.assertEqual(roi["autoconso_sans"], AUTOCONSO_SANS)
        self.assertEqual(roi["eco_s_ann"], 6644)
        self.assertEqual(roi["eco_a_ann"], 11024)

    def test_invariant_avec_toujours_superieur_ou_egal_a_sans(self):
        """INVARIANT ABSOLU : une batterie ne peut jamais économiser MOINS.

        Balayage des combinaisons qui faisaient basculer le modèle : petite et
        grosse conso, avec/sans batterie, tarif plat vendeur, distributeur
        (modèle « factures ») et repli sans aucune donnée tarifaire.
        """
        for kwc in (3.0, 8.0, 20.0):
            for conso in (None, 1000, 5000, 30000):
                for battery in (None, 0, 5, 10, 40):
                    for utility, tarif in ((None, None), ("onee", None),
                                           (None, 1.75), ("onee", 1.75)):
                        roi = calculate_savings_roi(
                            kwc, 100000, 140000,
                            conso_annuelle_kwh=conso, battery_kwh=battery,
                            utility=utility, tarif_kwh_override=tarif)
                        self.assertGreaterEqual(
                            roi["eco_a_ann"], roi["eco_s_ann"],
                            f"inversion : kwc={kwc} conso={conso} "
                            f"batterie={battery} utility={utility} "
                            f"tarif={tarif}")
                        self.assertGreaterEqual(
                            roi["autoconso_avec"], roi["autoconso_sans"],
                            f"taux inversés : kwc={kwc} conso={conso} "
                            f"batterie={battery}")

    def test_plafond_est_un_no_op_sur_le_modele_factures(self):
        """Sur le modèle « factures », le plafond ne change AUCUN chiffre.

        ``two_bills_savings`` borne déjà les kWh autoconsommés à la conso
        (``min(prod × ratio, conso)``) : plafonner le TAUX en amont donne le
        même minimum. Fixture du verrou JS (10 kWc, 15 358 kWh, ONEE,
        15 000 kWh/an, barème TTC 2026) : 16 214 / 22 013 MAD, inchangés.
        """
        roi = calculate_savings_roi(
            10.0, 100000, 140000, productible=1651, battery_kwh=BATTERY,
            utility="onee", conso_annuelle_kwh=CONSO)
        self.assertEqual(roi["savings_model"], "factures")
        # conso/prod = 15 000/15 358 = 0,9767… > 0,60 → le plafond ne mord pas.
        self.assertEqual(roi["autoconso_sans"], AUTOCONSO_SANS)
        self.assertEqual(roi["eco_s_ann"], 16214)
        self.assertEqual(roi["eco_a_ann"], 22013)
