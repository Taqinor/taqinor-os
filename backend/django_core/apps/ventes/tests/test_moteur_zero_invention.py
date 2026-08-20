"""Le DOCUMENT RENDU n'invente aucun chiffre (audit adversarial 19/08/2026).

RÈGLE : valeur inconnue ⇒ ``None`` + omission, JAMAIS un forfait.

Chaque classe épingle un item de l'audit sur le HTML RÉELLEMENT RENDU — pas sur
la fonction qui le calcule. C'est le trou par lequel le « 87,4 % » codé en dur
est passé le 18/08 : tous les tests interrogeaient des fonctions, aucun ne
regardait le document. Les fixtures (``_moteur_fixtures``) rendent le HTML exact
qui part chez WeasyPrint, sans BD et sans WeasyPrint : ``SimpleTestCase``.
"""

import re

from django.test import SimpleTestCase

from apps.ventes.tests import _moteur_fixtures as F


class M1FactureProxyTests(SimpleTestCase):
    """M1 — la facture « avant PV » est une DONNÉE, jamais un rétro-calcul.

    Sans les 12 factures réelles du client, le document n'imprime ni barre de
    facture, ni légende ONEE, ni « facture réduite de N % ».
    """

    def test_sans_factures_le_document_n_imprime_aucune_facture_onee(self):
        html = F.html_legacy(factures_mensuelles=None)
        self.assertNotIn("Facture ONEE", html)
        self.assertIn("&#201;conomies solaires par mois", html)

    def test_avec_factures_reelles_la_carte_reste_celle_d_avant(self):
        html = F.html_legacy()
        self.assertIn("Facture ONEE vs &#233;conomies solaires par mois", html)

    def test_le_legacy_ne_plante_plus_sur_une_serie_absente(self):
        # Le renderer résidentiel refuse une série absente et dégrade vers le
        # legacy : si le legacy explose, le devis n'a PLUS aucun rendu.
        html = F.html_legacy(factures_mensuelles=None)
        self.assertGreater(len(html), 10_000)

    def test_serie_absente_le_renderer_residentiel_refuse_de_rendre(self):
        # La dégradation VOULUE : plutôt qu'une page 1 avec un « −N % »
        # fabriqué, le renderer résidentiel se déclare hors périmètre.
        from apps.ventes.quote_engine.residential import renderer
        data = F.donnees_residentiel(factures_mensuelles=None)
        with self.assertRaises(renderer.Unsupported):
            renderer._augment(data)
        self.assertIsNone(renderer.synthese_economies(data))


class M2PuissanceInventeeParLePrixTests(SimpleTestCase):
    """M2 — le kWc n'est plus déduit du prix ; inconnu ⇒ vignettes omises."""

    INCONNUE = dict(puissance_inconnue=True, puissance_kwc=None,
                    nb_panneaux=None, watt_par_panneau=None, prod_kwh=0)

    def test_puissance_inconnue_le_document_n_imprime_ni_kwc_ni_panneaux(self):
        html = F.html_legacy(**self.INCONNUE)
        self.assertNotIn("Puissance Install", html)
        self.assertNotIn("panneaux &#215;", html)

    def test_puissance_inconnue_omet_production_et_economies(self):
        html = F.html_legacy(**self.INCONNUE)
        self.assertNotIn("Production Annuelle", html)
        self.assertNotIn("&#201;conomies estim&#233;es / an", html)
        self.assertNotIn("Retour en", html)

    def test_puissance_connue_les_vignettes_restent(self):
        html = F.html_legacy()
        self.assertIn("Puissance Install", html)
        self.assertIn("Production Annuelle", html)
        self.assertIn("&#201;conomies estim&#233;es / an", html)

    def test_une_page_omet_le_resume_systeme_sans_puissance(self):
        html = F.html_onepage(**self.INCONNUE)
        self.assertNotIn("Puissance cr&#234;te", html)
        self.assertNotIn("Prix par kWc", html)

    def test_detection_panneau_elargie_aux_designations_reelles(self):
        from apps.ventes.quote_engine import builder
        for designation in ("Panneau Canadien Solar 710W", "Module PV 550W",
                            "Module photovoltaïque 550 W",
                            "Canadian Solar TOPHiKu7 710 Wc"):
            self.assertTrue(builder._is_panel(designation), designation)
        # Une marque seule, ou un équipement d'une autre famille, jamais.
        for designation in ("Canadian Solar", "Onduleur réseau Huawei 10kW",
                            "Onduleur hybride Deye 10kW", "Batterie Dyness 10 kWh",
                            "Smart Meter", "Coffret PV DC",
                            "Module de communication", "Structures acier"):
            self.assertFalse(builder._is_panel(designation), designation)


class M3WattNonLuTests(SimpleTestCase):
    """M3 — « × 710 W » n'est plus imprimé sans lecture, et la désignation
    facturée n'est jamais réécrite."""

    def test_watt_non_lu_le_document_ecrit_n_panneaux_sans_puissance(self):
        html = F.html_legacy(watt_par_panneau=None)
        self.assertNotIn("panneaux &#215;", html)
        self.assertIn("8 panneaux</div>", html)

    def test_watt_lu_la_puissance_unitaire_reste_imprimee(self):
        html = F.html_legacy()
        self.assertIn("8 panneaux &#215; 710&nbsp;W", html)

    def test_la_designation_facturee_n_est_jamais_suffixee(self):
        # Le libellé contractuel de la ligne s'affiche tel quel : le moteur
        # ajoutait « 710 Wc » derrière, donc engageait une caractéristique
        # que le devis ne porte pas.
        html = F.html_legacy()
        self.assertIn("Panneau Canadien Solar 710W", html)
        self.assertNotIn("Panneau Canadien Solar 710W 710&#160;Wc", html)
        self.assertNotIn("710W 710", html)

    def test_le_moteur_lit_le_watt_sans_repli_catalogue(self):
        from apps.ventes.quote_engine import builder

        class _L:
            def __init__(self, designation, quantite):
                self.designation = designation
                self.quantite = quantite
                self.produit = None

        # Aucune puissance lisible nulle part → None, jamais 710.
        nb, watt = builder.panneaux_et_watt_lu([_L("Panneaux solaires", 16)])
        self.assertEqual(nb, 16)
        self.assertIsNone(watt)
        # Le contrat HISTORIQUE (KPI interne) garde, lui, son repli documenté.
        self.assertEqual(
            builder.puissance_panneaux_lignes([_L("Panneaux solaires", 16)]),
            (16, builder._DEFAULT_WATT))
        # Puissance écrite dans la désignation → elle est LUE.
        self.assertEqual(
            builder.panneaux_et_watt_lu([_L("Panneau Jinko 585W", 10)]),
            (10, 585))


class M4UnePageMemeBrancheTests(SimpleTestCase):
    """M4 — l'économie du format UNE PAGE vient de la branche facturée.

    Le document chiffre l'option SANS batterie et le dit ; il affichait
    pourtant ``max(éco sans, éco avec)``, donc l'économie de l'option AVEC.
    """

    @staticmethod
    def _eco(html):
        """Montant d'économie RENDU dans le résumé système, sans séparateurs."""
        i = html.find("conomie annuelle")
        if i < 0:
            return None
        m = re.search(r">([\d   ]+) MAD/an<", html[i:i + 300])
        if not m:
            return None
        return re.sub(r"[^\d]", "", m.group(1))

    def test_branche_sans_affiche_l_economie_sans_batterie(self):
        d = F.donnees_legacy()
        html = F.html_onepage(onepage_branche="sans")
        self.assertEqual(self._eco(html), str(d["eco_s_ann"]))

    def test_branche_avec_affiche_l_economie_avec_batterie(self):
        d = F.donnees_legacy()
        html = F.html_onepage(onepage_branche="avec")
        self.assertEqual(self._eco(html), str(d["eco_a_ann"]))

    def test_branche_inconnue_omet_la_vignette(self):
        self.assertIsNone(self._eco(F.html_onepage()))

    def test_jamais_le_maximum_des_deux_branches(self):
        d = F.donnees_legacy()
        self.assertNotEqual(d["eco_s_ann"], d["eco_a_ann"],
                            "fixture invalide : les deux branches doivent "
                            "différer pour que le test prouve quelque chose")
        maxi = str(max(d["eco_s_ann"], d["eco_a_ann"]))
        self.assertNotEqual(self._eco(F.html_onepage(onepage_branche="sans")),
                            maxi)


class Q1ProvisionOnduleurTests(SimpleTestCase):
    """Q1 (décision fondateur du 20/08) — la provision de remplacement de
    l'onduleur vaut le PRIX RÉEL de la ligne onduleur, jamais un % du CAPEX.
    Aucun onduleur chiffré ⇒ aucune provision, et le document le DIT."""

    def test_le_creux_de_l_annee_12_vaut_le_prix_reel_de_l_onduleur(self):
        from apps.ventes.quote_engine.pricing import compute_cashflow_payback
        sans = compute_cashflow_payback(100000, 20000)
        avec = compute_cashflow_payback(100000, 20000,
                                        inverter_replace_cost=16000)
        self.assertEqual(sans["cumulative"][11] - avec["cumulative"][11], 16000)

    def test_aucun_onduleur_aucune_provision(self):
        from apps.ventes.quote_engine.pricing import compute_cashflow_payback
        a = compute_cashflow_payback(100000, 20000, inverter_replace_cost=None)
        b = compute_cashflow_payback(100000, 20000, inverter_replace_cost=0)
        self.assertEqual(a["cashflow"], b["cashflow"])
        # aucun palier : l'année 12 vaut ce que vaut l'année 11 à la
        # dégradation près, jamais un décrochement.
        self.assertGreater(a["cashflow"][11], a["cashflow"][11] * 0.9)

    def test_le_montant_reel_est_imprime_dans_les_hypotheses(self):
        from apps.ventes.quote_engine.pricing import cashflow_assumptions
        notes = cashflow_assumptions(inverter_replace_cost=16000)["notes"]
        html = F.html_legacy(hypotheses={"titre": "Nos hypothèses",
                                         "items": notes})
        self.assertIn("Provision de remplacement", html)
        # espace fine insécable : le format monétaire des documents
        self.assertIn("16 000 MAD", html)
        self.assertIn("année 12", html)

    def test_sans_onduleur_le_document_dit_hors_provision(self):
        from apps.ventes.quote_engine.pricing import cashflow_assumptions
        notes = cashflow_assumptions()["notes"]
        html = F.html_legacy(hypotheses={"titre": "Nos hypothèses",
                                         "items": notes})
        self.assertIn("hors provision de remplacement onduleur", html)

    def test_la_legende_de_la_courbe_affiche_le_montant_provisionne(self):
        html = F.html_residentiel(cashflow_assumptions={
            "inverter_replace_cost": 23000, "inverter_replace_year": 12})
        self.assertIn("remplacement onduleur provisionn", html)
        self.assertIn("23", html)

    def test_sans_provision_la_legende_ne_mentionne_rien(self):
        html = F.html_residentiel()
        self.assertNotIn("remplacement onduleur provisionn", html)

    def test_le_builder_lit_le_prix_ttc_reel_des_lignes_onduleur(self):
        from apps.ventes.quote_engine import builder
        rows = [{"designation": "Onduleur hybride Deye 10kW",
                 "quantite": 2, "prix_unit_ttc": 12000},
                {"designation": "Batterie Dyness 10 kWh",
                 "quantite": 1, "prix_unit_ttc": 25000}]
        self.assertEqual(builder._cout_onduleur(rows), 24000)
        self.assertIsNone(builder._cout_onduleur(rows[1:]))
        self.assertIsNone(builder._cout_onduleur([]))


class M9AbattementBatterieTests(SimpleTestCase):
    """M9 — l'abattement de rendement batterie ne s'applique qu'au stockage
    RÉELLEMENT présent, et les deux hypothèses cachées sont divulguées."""

    def test_sans_stockage_aucun_abattement(self):
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        sans = calculate_savings_roi(10, 100000, 100000,
                                     stockage_present=False)
        avec = calculate_savings_roi(10, 100000, 100000,
                                     stockage_present=True)
        # Même devis, même prix : seule la présence de stockage change le
        # cashflow de l'option 2 — l'abattement s'appliquait aux deux.
        self.assertGreater(sans["cashflow_avec"][-1], avec["cashflow_avec"][-1])

    def test_le_stockage_se_deduit_de_la_capacite_batterie_reelle(self):
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        sans = calculate_savings_roi(10, 100000, 100000, battery_kwh=None)
        avec = calculate_savings_roi(10, 100000, 100000, battery_kwh=10)
        self.assertGreater(sans["cashflow_avec"][-1], avec["cashflow_avec"][-1])

    def test_les_deux_hypotheses_cachees_sont_imprimees(self):
        from apps.ventes.quote_engine.pricing import cashflow_assumptions
        notes = cashflow_assumptions(inverter_replace_cost=16000,
                                     stockage=True)["notes"]
        html = F.html_legacy(hypotheses={"titre": "Nos hypothèses",
                                         "items": notes})
        self.assertIn("rendement aller-retour batterie 90", html)
        self.assertIn("Provision de remplacement", html)

    def test_sans_stockage_l_hypothese_batterie_ne_s_affiche_pas(self):
        from apps.ventes.quote_engine.pricing import cashflow_assumptions
        notes = cashflow_assumptions(stockage=False)["notes"]
        self.assertFalse(any("aller-retour" in n for n in notes))


class M5CourbeVingtCinqAnsTests(SimpleTestCase):
    """M5 — la courbe 25 ans trace le VRAI cumul, pas une droite."""

    def _cumuls(self, **surcharges):
        from apps.ventes.quote_engine import generate_devis_premium as legacy
        legacy.apply_quote_data(F.donnees_legacy(**surcharges))
        return list(legacy.CUMUL_S), list(legacy.CUMUL_A)

    def test_le_cumul_vient_du_cashflow_reel_pas_de_eco_fois_annee(self):
        d = F.donnees_legacy()
        cs, ca = self._cumuls()
        # La droite surestimait le gain final : elle ignorait la dégradation
        # panneau, le rendement batterie et la provision onduleur.
        self.assertLess(cs[25], -d["total_sans"] + d["eco_s_ann"] * 25)
        self.assertLess(ca[25], -d["total_avec"] + d["eco_a_cumul"] * 25)
        self.assertEqual(cs[25], d["cashflow_sans"][24])

    def test_les_deux_series_gardent_26_points(self):
        cs, ca = self._cumuls()
        self.assertEqual((len(cs), len(ca)), (26, 26))
        self.assertEqual(cs[0], -F.donnees_legacy()["total_sans"])

    def test_repli_sur_la_droite_quand_le_cumul_manque(self):
        d = F.donnees_legacy()
        sans_cf = {k: v for k, v in d.items()
                   if k not in ("cashflow_sans", "cashflow_avec")}
        from apps.ventes.quote_engine import generate_devis_premium as legacy
        legacy.apply_quote_data(sans_cf)
        self.assertEqual(legacy.CUMUL_S[25],
                         -d["total_sans"] + d["eco_s_ann"] * 25)

    def test_la_garde_moyenne_tension_couvre_la_page_2(self):
        # Un dossier MT n'a aucun chiffre d'économies légitime : la page 1 les
        # omettait déjà, la courbe « Gain cumulé sur 25 ans » les traçait.
        html = F.html_legacy(masquer_economies=True)
        self.assertNotIn("Gain cumul", html)
        normal = F.html_legacy()
        self.assertIn("Gain cumul", normal)


class Q6ProductibleLocalTests(SimpleTestCase):
    """Q6 — la donnée PVGIS locale remplace « 3 000 h/an d'ensoleillement »."""

    PVGIS = {"titre": "Nos hypothèses", "items": [],
             "productible_net_kwh_kwc": 1651,
             "productible_ville": "casablanca"}

    def test_le_slogan_national_a_disparu(self):
        self.assertNotIn("h/an d&#8217;ensoleillement", F.html_legacy())

    def test_la_donnee_locale_est_imprimee_avec_sa_source(self):
        html = F.html_legacy(hypotheses=self.PVGIS)
        self.assertIn("kWh par kWc et par an &#224; Casablanca", html)
        self.assertIn("(donn&#233;e PVGIS)", html)

    def test_ville_inconnue_la_phrase_s_omet(self):
        self.assertNotIn("(donn&#233;e PVGIS)", F.html_legacy())

    def test_le_builder_omet_hors_table_pvgis(self):
        from apps.ventes.quote_engine.productible import ville_reconnue
        self.assertTrue(ville_reconnue("Casablanca"))
        self.assertTrue(ville_reconnue("settat"))   # alias → casablanca
        self.assertFalse(ville_reconnue("Ouarzazate"))
        self.assertFalse(ville_reconnue(""))
        self.assertFalse(ville_reconnue(None))

    def test_le_cent_pour_cent_propre_n_est_plus_chiffre(self):
        html = F.html_legacy()
        self.assertNotIn("100&#37; propre", html)
        self.assertIn("&#201;nergie propre", html)


class Q8DeviseTests(SimpleTestCase):
    """Q8 — les documents impriment MAD, jamais une étiquette non convertie."""

    def test_les_montants_sont_etiquetes_mad(self):
        from apps.ventes.quote_engine import generate_devis_premium as legacy
        legacy.apply_quote_data(F.donnees_legacy(devise="EUR"))
        self.assertTrue(legacy.fmt(52650).endswith("MAD"))
        self.assertNotIn("EUR", legacy.fmt(52650))

    def test_le_document_rendu_ne_porte_aucune_autre_devise(self):
        # On cherche l'ÉTIQUETTE monétaire (espace insécable + code), pas la
        # sous-chaîne nue : les data-URI base64 des polices en contiennent.
        html = F.html_legacy(devise="EUR")
        self.assertNotIn(" EUR", html)
        self.assertIn(" MAD", html)


class M1GhiSourceUniqueTests(SimpleTestCase):
    """M1 (suite) — une SEULE dérivation du profil GHI dans tout le backend."""

    def test_public_views_importe_les_poids_au_lieu_de_les_recopier(self):
        from apps.ventes import public_views
        from apps.ventes.quote_engine import constants
        self.assertIs(public_views.MOROCCO_SOLAR_MONTHLY_WEIGHTS,
                      constants.MOROCCO_SOLAR_MONTHLY_WEIGHTS)

    def test_les_poids_derivent_de_la_table_ghi_verrouillee(self):
        from apps.ventes.quote_engine import constants
        attendu = [round(g / sum(constants.GHI), 6) for g in constants.GHI]
        self.assertEqual(constants.MOROCCO_SOLAR_MONTHLY_WEIGHTS, attendu)
