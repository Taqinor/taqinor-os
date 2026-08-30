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

ÉCART TEMPORAIRE ASSUMÉ ET DATÉ (QJR26, 29/08/2026). La correction du tarif T5
(décision fondateur D5 — voir plus bas) a été portée sur les DEUX branches ERP
(ce fichier + solar.test.mjs), pas sur la branche SITE : la moitié
``apps/web/**`` est une tâche séparée (QJW) et ce périmètre lui est interdit.
Tant qu'elle n'a pas atterri, ``savingsTranchesFondateur.test.ts`` reste sur
1,405116 et l'estimateur public annonce une facture T5 ~1,7 % plus haute que
l'ERP. Le verrou à trois branches se referme quand QJW est mergée.

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
# 311-510 = 1,381704 · > 510 = 1,622856.
#
# DÉCISION FONDATEUR D5 (29/08/2026) — TARIF T5 RECALÉ SUR LA FACTURE. La
# tranche 311-510 vaut 1,381704 et non l'extrapolation « HT constant » de
# 2025 : la facture SRM n° 643769639 du 08/05/2026 (359 kWh × 1,15142 HT =
# 496,03 TTC) donne 1,15142 × 1,20 = 1,381704, et la facture du 20/01/2026
# corrobore (T5 2025 = 1,3817 TTC : au passage TVA 18 → 20 % c'est le TTC qui
# est resté constant, pas le HT). TOUS les attendus T5 ci-dessous ont donc été
# RE-DÉRIVÉS À LA MAIN de 1,381704 — jamais recopiés d'une sortie de code.
TARIF_HAUT = 1.622856    # > 510 kWh/mois
TARIF_310 = 1.187388     # 211-310 kWh/mois
TARIF_510 = 1.381704     # 311-510 kWh/mois — prouvé facture (D5)

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
    (311, 429.709944),  # 311 × 1,381704
    (499, 689.470296),  # 499 × 1,381704
    (500, 690.852),     # 500 × 1,381704 — le seuil « 500 » du fondateur
    (501, 692.233704),  # 501 × 1,381704 (encore dans sa bande : borne eff. 510)
    (510, 704.66904),   # 510 × 1,381704
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
        # 511 kWh coûte 124,610376 MAD de plus que 510 kWh pour UN kWh de plus :
        # 829,279416 − 704,66904 — c'est la marche sélective, pas un arrondi.
        # (La marche a GRANDI avec la correction D5 : le bas de la marche est
        #  descendu à 1,381704 alors que le haut, 1,622856, n'a pas bougé.)
        self.assertAlmostEqual(829.279416 - 704.66904, 124.610376, places=9)

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
        # résiduel 385 kWh/mois → tranche 311-510 → 385 × 1,381704 = 531,95604
        # → économie 1 135,9992 − 531,95604 = 604,04316 MAD/mois (7 248,52/an).
        self.assertAlmostEqual(
            _monthly_bill_from_kwh(385, ONEE_TRANCHES), 531.95604, places=9)
        self.assertAlmostEqual(
            _monthly_bill_from_kwh(700, ONEE_TRANCHES) - 531.95604,
            604.04316, places=9)


class TestUnSeulBaremeNational(SimpleTestCase):
    """Q7 (décision fondateur du 20/08/2026) — LES TROIS DISTRIBUTEURS LISENT
    LA MÊME GRILLE.

    Les grilles « approximatives » Lydec/Redal (trois paliers ronds jamais
    vérifiés, marqués « à confirmer ») sont supprimées : sur un même client,
    elles produisaient une facture différente du barème national selon un
    simple champ de formulaire, puis un drapeau « approximatif » qui avouait
    le problème sans le corriger. Le nom du distributeur n'est plus qu'un
    LIBELLÉ ; une société dont la grille diffère la SAISIT dans ses réglages.
    """

    def test_les_trois_distributeurs_donnent_la_meme_facture(self):
        ref = kwh_from_bill(1800, utility="onee")
        for utility in ("lydec", "redal"):
            out = kwh_from_bill(1800, utility=utility)
            self.assertAlmostEqual(out["kwh_mensuel"], ref["kwh_mensuel"],
                                   places=6, msg=utility)

    def test_plus_aucune_table_n_est_approximative(self):
        for utility in ("onee", "lydec", "redal"):
            out = kwh_from_bill(210, utility=utility)
            self.assertFalse(out["approximatif"], utility)
            self.assertEqual(out["label"], "", utility)

    def test_les_grilles_estimees_ont_disparu_du_module(self):
        from apps.ventes.quote_engine import pricing
        self.assertFalse(hasattr(pricing, "LYDEC_TRANCHES"))
        self.assertFalse(hasattr(pricing, "REDAL_TRANCHES"))
        self.assertEqual(set(pricing.APPROX_UTILITIES), set())

    def test_un_bareme_colle_par_le_vendeur_reste_progressif(self):
        # 150 kWh → 100 × 2,0 + 50 × 3,0 = 350 MAD (cumulé).
        custom = [(100, 2.0), (None, 3.0)]
        self.assertAlmostEqual(
            _monthly_bill_from_kwh(150, custom), 350.0, places=9)
        self.assertAlmostEqual(
            kwh_from_bill(350, tranches_override=custom)["kwh_mensuel"], 150.0,
            places=1)


class TestSeuilExonerationTPPAN(SimpleTestCase):
    """QJR141 — le seuil d'exonération TPPAN, tranché et documenté.

    Deux sources officielles se contredisaient (≤ 50 kWh, texte de 1996 ;
    ≤ 200 kWh, page Lydec) et le module retenait 200 — la branche NON prouvée,
    et celle qui MAXIMISE l'économie vendue : la facture AVANT solaire est
    presque toujours > 200 kWh (le seuil n'y change rien), tandis que la
    facture APRÈS solaire retombe souvent entre 50 et 200, exactement la plage
    où le seuil décide. Décision QJR141 : on retient 50, la lecture PROUVÉE
    (le texte dont ce module tire déjà ses tranches et son plafond) et la plus
    prudente, et la réserve VOYAGE avec le chiffre.
    """

    def test_le_seuil_retenu_est_celui_du_texte_de_1996(self):
        from apps.ventes.quote_engine import bareme as B
        self.assertEqual(B.TPPAN_EXONERATION_KWH_MOIS, 50.0)

    def test_la_source_publie_le_seuil_retenu_et_sa_reserve(self):
        from apps.ventes.quote_engine import bareme as B
        source = B.TPPAN_SOURCE
        self.assertIn('50 kWh', source)
        self.assertIn('200 kWh', source)          # la lecture écartée est DITE
        self.assertIn('dahir 1-96-77', source)
        self.assertIn('ne départage', source)

    def test_la_marche_du_seuil_retenu_est_celle_de_la_premiere_tranche(self):
        """Dérivé de ``TPPAN_TRANCHES``, jamais recopié : 50 × 0,10 = 5,00."""
        from apps.ventes.quote_engine import bareme as B
        marche_50 = B.tppan_mad(50.0001, jours=30, exoneration_kwh=None)
        self.assertAlmostEqual(marche_50, 5.00, places=2)

    def test_la_marche_de_la_lecture_ecartee_etait_cinq_fois_plus_raide(self):
        """200 kWh → 100 × 0,10 + 100 × 0,15 = 25,00 MAD d'un seul coup."""
        from apps.ventes.quote_engine import bareme as B
        marche_200 = B.tppan_mad(200.0001, jours=30, exoneration_kwh=None)
        self.assertAlmostEqual(marche_200, 25.00, places=2)
        self.assertAlmostEqual(
            marche_200 / B.tppan_mad(50.0001, jours=30, exoneration_kwh=None),
            5.0, places=2)

    def test_l_asymetrie_est_bien_du_cote_de_la_facture_APRES(self):
        """Le seuil ne touche QUE le résidu après solaire, pas la facture avant."""
        from apps.ventes.quote_engine import bareme as B
        avant = 600.0        # facture avant solaire : au-dessus des DEUX seuils
        self.assertAlmostEqual(
            B.tppan_mad(avant, jours=30, exoneration_kwh=50.0),
            B.tppan_mad(avant, jours=30, exoneration_kwh=200.0), places=6)
        # Le résidu, lui, bascule entièrement.
        apres = 150.0
        self.assertEqual(B.tppan_mad(apres, jours=30, exoneration_kwh=200.0),
                         0.0)
        self.assertGreater(B.tppan_mad(apres, jours=30, exoneration_kwh=50.0),
                           0.0)

    def test_la_correction_annuelle_est_de_l_ordre_de_grandeur_annonce(self):
        """Ce que la lecture écartée ajoutait à l'économie vendue, par an."""
        from apps.ventes.quote_engine import bareme as B
        # Résidu de 150 kWh/mois : 100 × 0,10 + 50 × 0,15 = 17,50 MAD/mois.
        self.assertAlmostEqual(B.tppan_mad(150, jours=30) * 12, 210.00,
                               places=2)
        # Haut de la plage concernée (juste sous l'ancien seuil).
        self.assertAlmostEqual(B.tppan_mad(199, jours=30) * 12, 298.20,
                               places=2)

    def test_les_factures_du_fondateur_sont_INCHANGEES(self):
        """Toutes > 200 kWh : le seuil ne les touche ni avant ni après."""
        from apps.ventes.quote_engine import bareme as B
        self.assertAlmostEqual(B.tppan_mad(359, jours=30), 56.80, places=2)
        detail = B.facture_mad(359, jours=30)
        self.assertAlmostEqual(detail['total_mad'], 592.77, places=2)
        self.assertAlmostEqual(
            B.kwh_depuis_facture_mad(592.77, jours=30)['kwh_mensuel'],
            359.0, places=1)

    # ── La réserve voyage avec le chiffre ──────────────────────────────────

    def test_l_inversion_rend_desormais_tppan_source(self):
        from apps.ventes.quote_engine import bareme as B
        sortie = B.kwh_depuis_facture_mad(592.77, jours=30)
        self.assertIn('tppan_source', sortie)
        self.assertEqual(sortie['tppan_source'], B.TPPAN_SOURCE)

    def test_sans_tppan_la_source_est_vide(self):
        from apps.ventes.quote_engine import bareme as B
        sortie = B.kwh_depuis_facture_mad(592.77, jours=30, tppan=False)
        self.assertEqual(sortie['tppan_source'], '')

    def test_le_bloc_de_consommation_estimee_porte_la_reserve(self):
        from apps.ventes import etude_horaire as EH
        from apps.ventes.quote_engine import bareme as B
        _kwh, detail = EH.serie_kwh_depuis_mad([592.77] * 12)
        self.assertEqual(detail['tppan_source'], B.TPPAN_SOURCE)

    def test_sans_tppan_le_bloc_garde_sa_forme_d_avant(self):
        """Clé ADDITIVE : absente quand la TPPAN ne s'applique pas."""
        from apps.ventes import etude_horaire as EH
        _kwh, detail = EH.serie_kwh_depuis_mad([592.77] * 12, tppan=False)
        self.assertNotIn('tppan_source', detail)
