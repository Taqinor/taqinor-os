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
    depuis le 01/01/2026 — cf. pricing.ONEE_TRANCHES) : progressif ≤ 150
    kWh/mois — 0,916272 puis 1,091388 ; au-delà, TOUTE la conso au tarif de SA
    tranche — 151-210 = 1,091388 · 211-310 = 1,187388 · 311-510 = 1,381704 ·
    > 510 = 1,622856) :

      facture sans solaire : 15 000/12 = 1 250 kWh/mois → tranche > 510
        1 250 × 1,622856 = 2 028,57 MAD/mois × 12 = 24 342,84 → 24 343 MAD/an
      option SANS (60 %) : autoconsommé 9 214,8 → résiduel 5 785,2
        → 482,1 kWh/mois → tranche 311-510 : 482,1 × 1,381704 = 666,1194984
        × 12 = 7 993,434 → 7 993
        ⇒ économie 24 343 − 7 993 = 16 350 MAD/an
      option AVEC (83,8 %) : autoconsommé 12 864,8 → résiduel 2 135,2
        → 177,9333 kWh/mois → tranche 151-210 : 177,9333 × 1,091388 = 194,19430
        × 12 = 2 330,33 → 2 330
        ⇒ économie 24 343 − 2 330 = 22 013 MAD/an

    La batterie fait franchir DEUX marches vers le bas (1,381704 → 1,091388 sur
    la TOTALITÉ du résiduel) : c'est là que le barème sélectif change tout.

    RECALAGE QJR26 / DÉCISION FONDATEUR D5 (29/08/2026) — le tarif T5 est passé
    de l'extrapolation « HT constant » à la valeur PROUVÉE par la facture SRM du
    08/05/2026 (1,15142 HT × 1,20 = 1,381704). SEULE l'option SANS traverse la
    tranche T5 : sa facture passe de 8 129 à 7 993 MAD/an et son économie de
    16 214 à 16 350 (le client payait moins cher que le repo ne le croyait, donc
    il économise plus en descendant vers 151-210). L'option AVEC retombe en
    151-210, hors T5 : ses 2 330 / 22 013 MAD sont INCHANGÉS — recalculés, pas
    supposés.

    ════════════════════════════════════════════════════════════════════════
    RECALAGE QJR157 (30/08/2026) — LA FACTURE N'EST PLUS QUE L'ÉNERGIE
    ════════════════════════════════════════════════════════════════════════
    Les chiffres ci-dessus restent la composante ÉNERGIE, exacte. Mais
    ``two_bills_savings`` tarife désormais les deux factures par
    ``bareme.facture_mad`` — lignes fixes (location + entretien) et TPPAN
    comprises — parce que le chemin ``savings_model='horaire'`` servait déjà
    cette vignette charges comprises et que le même client voyait donc deux
    « factures actuelles » différentes selon qu'un bloc horaire existait ou
    non. Les attentes deviennent, composante par composante (mois moyen,
    charges SOURCÉES des factures du fondateur) ::

        facture sans solaire  énergie 24 342,84 + fixes 479,23 + TPPAN 1 200,00
                              = 26 022,07 → 26 022 MAD/an
        résiduel option SANS  énergie  7 993,43 + fixes 479,23 + TPPAN   977,04
                              =  9 449,71 →  9 450 MAD/an
                              ⇒ économie 26 022 − 9 450 = 16 572 MAD/an
        résiduel option AVEC  énergie  2 330,33 + fixes 479,23 + TPPAN   260,28
                              =  3 069,84 →  3 070 MAD/an
                              ⇒ économie 26 022 − 3 070 = 22 952 MAD/an

    Les 479,23 MAD/an de lignes fixes s'ANNULENT dans l'économie (mêmes deux
    côtés) ; la TPPAN suit le kWh et ne s'annule donc PAS — c'est exactement
    d'où viennent les +222 (16 350 → 16 572) et +939 (22 013 → 22 952).

    QJR168 (30/08/2026) — LES DEUX FICHIERS SONT À NOUVEAU JUMEAUX. QJR157
    avait atterri côté serveur seul : ``solar.js twoBillsSavings`` était resté
    le modèle ÉNERGIE SEULE (``monthlyBillFromKwh``) et l'écran annonçait
    1 679 MAD/an de moins que le PDF sur la facture actuelle. Le barème
    (lignes fixes + TPPAN, SOURCÉS des factures du fondateur) est désormais
    porté dans ``solar.js`` : les six nombres ci-dessus sont les mêmes des
    deux côtés, au dirham.
    """

    def test_miroir_js_meme_fixture_memes_chiffres(self):
        sans = two_bills_savings(PROD, CONSO, AUTOCONSO_SANS, utility="onee")
        avec = two_bills_savings(
            PROD, CONSO, autoconso_avec_ratio(PROD, BATTERY), utility="onee")
        # QJR157 — charges fixes + TPPAN comprises (dérivation en docstring).
        self.assertEqual(sans["facture_sans"], 26022)
        self.assertEqual(sans["facture_avec"], 9450)
        self.assertEqual(sans["economie"], 16572)
        self.assertEqual(avec["autoconso_kwh"], 12865)
        self.assertEqual(avec["facture_avec"], 3070)
        self.assertEqual(avec["economie"], 22952)
        self.assertGreater(avec["economie"], sans["economie"])

    def test_miroir_js_bout_en_bout_meme_production_memes_economies(self):
        """Jumeau EXACT du test JS « computeROI (modèle deux factures) ».

        Mêmes entrées (10 kWc, productible 1651, batterie 10 kWh, conso
        15 000 kWh/an, ONEE) → MÊME production entière que
        solar.batterie.test.mjs. ``productible`` est passé EXPLICITEMENT : le
        recalage QJR158 (d) du repli ne touche donc pas ce cas.

        Les ÉCONOMIES aussi sont les mêmes des deux côtés : depuis QJR168 le
        modèle JS porte le barème complet (lignes fixes + TPPAN), donc la
        garantie « écran = PDF au dirham » vaut de nouveau sur cet axe.
        """
        roi = calculate_savings_roi(
            10.0, 100000, 140000, productible=1651, battery_kwh=BATTERY,
            utility="onee", conso_annuelle_kwh=CONSO)
        self.assertEqual(roi["savings_model"], "factures")
        self.assertEqual(roi["prod_kwh"], PROD)                 # 15 358
        self.assertAlmostEqual(roi["autoconso_avec"], RATIO_ATTENDU, places=9)
        self.assertEqual(roi["eco_s_ann"], 16572)
        self.assertEqual(roi["eco_a_ann"], 22952)


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

        RECALAGE QJR158 (d) — LE REPLI DE PRODUCTIBLE VAUT 1651, PAS 1240.
        Ce cas ne passe AUCUN ``productible`` : il tombe donc sur le repli de
        ``pricing``, qui était un 1240 codé en dur, divergent du productible
        canonique du dépôt (``productible.DEFAULT_PRODUCTIBLE`` = 1651
        Casablanca, déjà la valeur du jumeau ``solar.js``). QJR158 (d) a
        supprimé cette seconde source : la production dérivée MONTE, ce qui
        n'a rien changé aux deux économies (elles saturent la consommation).

        production   = round(8 × 1 651 × 0,80/0,86) = round(12 286,5116…)
                       = 12 287                        (avant : 9 228)
        tarif        = repli 1,20 MAD/kWh (aucune table, aucun override)
        conso/prod   = 5 000/12 287 = 0,4069341581…
        taux SANS    : AVANT min() → 0,60 ⇒ 12 287 × 0,60 × 1,20 = 8 846,64
                       → 8 847 MAD (on valorisait 7 372,2 kWh pour un client
                       qui n'en consomme que 5 000)
                       APRÈS  → min(0,60 ; 0,4069341581) = 0,4069341581
                       ⇒ 12 287 × 0,4069341581 × 1,20 = 6 000 MAD
        taux AVEC    : 0,60 + 3 650/12 287 = 0,8970619354 → plafonné par la
                       conso à 0,4069341581 ⇒ 6 000 MAD (inchangé)
        ⇒ l'inversion 8 847 > 6 000 disparaît ; l'invariant tient à l'égalité
          (les deux options saturent la MÊME consommation).

        LES 6 000 MAD SONT STRUCTURELS, PAS UNE COÏNCIDENCE : une fois le
        plafond mordu, l'économie vaut prod × (conso/prod) × tarif = conso ×
        tarif = 5 000 × 1,20 — elle ne dépend donc plus du productible. C'est
        exactement ce que ce verrou protège, et il le protège toujours.
        """
        roi = calculate_savings_roi(
            8.0, 100000, 140000, conso_annuelle_kwh=5000, battery_kwh=10)
        self.assertEqual(roi["savings_model"], "estimation")
        self.assertEqual(roi["prod_kwh"], 12287)
        self.assertEqual(roi["tarif_kwh"], 1.20)
        self.assertAlmostEqual(roi["autoconso_sans"], 5000 / 12287, places=12)
        self.assertAlmostEqual(roi["autoconso_avec"], 5000 / 12287, places=12)
        self.assertEqual(roi["eco_s_ann"], 6000)
        self.assertEqual(roi["eco_a_ann"], 6000)
        # Le chiffre FAUX d'avant correctif ne doit jamais revenir : c'est
        # « 0,60 non plafonné », donc il suit le productible (6 644 → 8 847).
        self.assertNotEqual(roi["eco_s_ann"], 8847)

    def test_sans_consommation_connue_comportement_historique(self):
        """Aucune conso → aucun plafond : les TAUX restent ceux d'avant.

        Ce que ce test verrouille est l'ABSENCE de plafond (``autoconso_sans``
        vaut exactement ``AUTOCONSO_SANS``), pas une valeur de production. Les
        deux montants suivent donc le repli de productible recalé par
        QJR158 (d) — 8 × 1 651 × 0,9302… = 12 287 kWh/an (avant : 9 228) :

        12 287 × 0,60 × 1,20 = 8 846,64 → 8 847  (avant 6 644) ; côté AVEC le
        taux dérivé 0,60 + 3 650/12 287 = 0,8970619354 (non plafonné, faute de
        conso) ⇒ 12 287 × 0,8970619354 × 1,20 = 13 226,64… → 13 227
        (avant 11 024).
        """
        roi = calculate_savings_roi(8.0, 100000, 140000, battery_kwh=10)
        self.assertEqual(roi["autoconso_sans"], AUTOCONSO_SANS)
        self.assertEqual(roi["eco_s_ann"], 8847)
        self.assertEqual(roi["eco_a_ann"], 13227)

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
        15 000 kWh/an, barème TTC 2026) : 16 572 / 22 952 MAD, inchangés par le
        plafond — ce que ce test verrouille est l'invariance, pas les montants
        eux-mêmes. Ils viennent du recalage T5 de QJR26 puis des charges fixes
        et de la TPPAN de QJR157 (16 350 → 16 572, 22 013 → 22 952 ; dérivation
        complète en tête de ``TestMiroirJs``), jamais du plafond.
        """
        roi = calculate_savings_roi(
            10.0, 100000, 140000, productible=1651, battery_kwh=BATTERY,
            utility="onee", conso_annuelle_kwh=CONSO)
        self.assertEqual(roi["savings_model"], "factures")
        # conso/prod = 15 000/15 358 = 0,9767… > 0,60 → le plafond ne mord pas.
        self.assertEqual(roi["autoconso_sans"], AUTOCONSO_SANS)
        self.assertEqual(roi["eco_s_ann"], 16572)
        self.assertEqual(roi["eco_a_ann"], 22952)
