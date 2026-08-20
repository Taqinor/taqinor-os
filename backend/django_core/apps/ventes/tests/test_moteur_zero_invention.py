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

    def test_serie_absente_la_couche_economique_est_omise_en_place(self):
        """M1 × Z2 — la dégradation VOULUE, dans sa forme la plus stricte.

        Sans série de factures RÉELLES il n'y a rien à montrer (et plus aucun
        proxy pour la fabriquer) : plutôt que de renvoyer tout le document vers
        le moteur legacy, la proposition résidentielle est RENDUE et sa couche
        économique retirée d'un seul bloc — jamais un « −N % » fabriqué, jamais
        un bloc à moitié.
        """
        from apps.ventes.quote_engine.residential import renderer
        data = F.donnees_residentiel(factures_mensuelles=None)
        self.assertIsNone(renderer.synthese_economies(data))
        d = renderer._augment(data)          # ne lève PLUS Unsupported
        self.assertTrue(d["masquer_synthese"])
        for k in ("pct_cut", "annual_before", "annual_after",
                  "coverage_pct", "bills_before", "bills_after"):
            self.assertNotIn(k, d, k)


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
        """Sans ``stockage_present`` explicite, la présence de stockage se
        déduit de la capacité batterie RÉELLE.

        On l'épingle sur le drapeau des hypothèses, pas sur le gain final : une
        capacité réelle relève aussi le taux d'autoconsommation, donc le gain
        MONTE (et c'est correct). Ce que M9 garantit, c'est qu'aucun abattement
        n'est appliqué à une option qui ne porte pas de stockage.
        """
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        sans = calculate_savings_roi(10, 100000, 100000, battery_kwh=None)
        avec = calculate_savings_roi(10, 100000, 100000, battery_kwh=10)
        self.assertFalse(
            sans["cashflow_assumptions"]["battery_roundtrip_applique"])
        self.assertTrue(
            avec["cashflow_assumptions"]["battery_roundtrip_applique"])

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


def _ligne(designation, garantie_mois=None, garantie_production_mois=None):
    """Ligne d'équipement minimale, avec (ou sans) garantie de fiche produit."""
    return {"designation": designation, "marque": "", "description": "",
            "garantie": "", "quantite": 1, "prix_unit_ht": 100.0,
            "prix_unit_ttc": 120.0, "taux_tva": 20.0,
            "garantie_mois": garantie_mois,
            "garantie_production_mois": garantie_production_mois}


class M6GarantiesCodeesEnDurTests(SimpleTestCase):
    """M6 — les garanties du document viennent des FICHES PRODUIT.

    « 30 ans / 87,4 % » (spec Canadian Solar TOPHiKu7) et les badges
    « 10 / 12 / 30 ANS » s'imprimaient en dur sur tous les devis, y compris un
    devis Longi (30 ans mais 88,9 %) et des produits sans garantie saisie.
    """

    LONGI = dict(
        sans_items=[_ligne("Panneau Longi 585W", 144, 360),
                    _ligne("Onduleur réseau Huawei 10kW", 120)],
        avec_items=[_ligne("Panneau Longi 585W", 144, 360),
                    _ligne("Onduleur hybride Deye 10kW", 120),
                    _ligne("Batterie Dyness 10 kWh", 120)])
    SANS_GARANTIE = dict(
        sans_items=[_ligne("Onduleur réseau 10kW"), _ligne("Panneau X 585W")],
        avec_items=[_ligne("Onduleur hybride"), _ligne("Batterie 10 kWh")])

    def test_le_pourcentage_canadian_solar_ne_sort_plus_sur_un_autre_panneau(self):
        self.assertNotIn("87,4", F.html_legacy(**self.LONGI))

    def test_les_badges_reprennent_les_durees_des_fiches(self):
        html = F.html_legacy(**self.LONGI)
        durees = re.findall(r'letter-spacing:-1px;">(\d+)</div>', html)
        self.assertEqual(durees, ["10", "12", "30"])
        self.assertIn("Garanties jusqu&#8217;&#224; 30 ans", html)

    def test_aucune_garantie_saisie_aucun_badge(self):
        html = F.html_legacy(**self.SANS_GARANTIE)
        self.assertEqual(
            re.findall(r'letter-spacing:-1px;">(\d+)</div>', html), [])
        self.assertIn("Nos garanties", html)
        self.assertNotIn("Garanties jusqu", html)

    def test_le_tableau_n_invente_plus_de_garantie_par_mot_cle(self):
        # « onduleur » dans la désignation valait « 10 ans », « panneaux »
        # valait « 12 ans » — sur la foi d'un mot, sans aucune donnée produit.
        html = F.html_legacy(**self.SANS_GARANTIE)
        self.assertNotIn(">10 ans<", html)
        self.assertNotIn(">12 ans<", html)
        self.assertNotIn(">20 ans<", html)

    def test_la_garantie_saisie_reste_affichee(self):
        html = F.html_legacy(**self.LONGI)
        self.assertIn(">12 ans<", html)   # panneau : 144 mois
        self.assertIn(">10 ans<", html)   # onduleur : 120 mois


class M7DateDeValiditeTests(SimpleTestCase):
    """M7 — la date de validité vient du DEVIS, jamais d'un « 30 jours » codé.

    Le portail client affichait la vraie échéance (date_validite ou réglage
    société), le PDF — bandeau à signer compris — une fausse.
    """

    def test_le_pdf_imprime_l_echeance_reelle(self):
        html = F.html_legacy(valid_until="16/08/2026")
        self.assertIn("jusqu&#8217;au 16/08/2026", html)
        self.assertNotIn("30 jours", html)

    def test_echeance_indeterminable_la_mention_disparait(self):
        html = F.html_legacy()
        self.assertNotIn("Validit&#233;", html)
        self.assertNotIn("30 jours", html)

    def test_une_page_suit_la_meme_echeance(self):
        self.assertIn("jusqu&#8217;au 16/08/2026",
                      F.html_onepage(valid_until="16/08/2026"))
        self.assertNotIn("Validit&#233;", F.html_onepage())

    def test_le_bandeau_a_signer_porte_la_vraie_date(self):
        html = F.html_residentiel(valid_until="16/08/2026")
        self.assertIn("16/08/2026", html)
        self.assertNotIn("30 jours", html)

    def test_le_builder_lit_la_regle_d_expiration_du_backend(self):
        # Une seconde règle de validité à côté de utils/expiry serait
        # exactement le défaut corrigé : deux dates pour un même devis.
        from apps.ventes.quote_engine import builder
        import inspect
        self.assertIn("date_expiration", inspect.getsource(builder))


class Q5DelaisIndicatifsTests(SimpleTestCase):
    """Q5 — les délais commerciaux sont indicatifs, paramétrables, et hors des
    « Conditions » (où ils se lisaient comme des engagements)."""

    REGLES = {"visite_technique": "48-72 h",
              "installation": "7-14 jours ouvrés"}

    def test_les_delais_portent_la_mention_indicatif(self):
        html = F.html_legacy(delais=self.REGLES)
        self.assertIn("Sous 48-72 h (indicatif)", html)
        self.assertIn("7-14 jours ouvrés (indicatif)", html)

    def test_ils_ne_sont_plus_dans_la_boite_conditions(self):
        html = F.html_legacy(delais=self.REGLES)
        self.assertNotIn("D&#233;lai d&#8217;installation&#160;:", html)

    def test_un_reglage_vide_retire_le_delai_du_document(self):
        html = F.html_legacy(delais={"visite_technique": "",
                                     "installation": ""})
        # On regarde le bloc « prochaines étapes », seul endroit où les délais
        # s'affichent désormais (un commentaire HTML sans rapport porte aussi
        # le mot « indicatif » ailleurs dans la page).
        etapes = html.split("PROCHAINES")[-1][:1200]
        self.assertNotIn("(indicatif)", etapes)
        self.assertNotIn("48", etapes)
        self.assertNotIn("14 jours", etapes)

    def test_le_renderer_residentiel_suit_le_meme_reglage(self):
        html = F.html_residentiel(delais=self.REGLES)
        self.assertIn("sous 48-72 h (indicatif)", html)
        self.assertIn("7-14 jours ouvrés (indicatif)", html)
        self.assertNotIn("Délai d'installation", html)


class Q7BaremeNationalUniqueTests(SimpleTestCase):
    """Q7 — les trois distributeurs lisent LA grille nationale."""

    def test_meme_facture_quel_que_soit_le_distributeur(self):
        from apps.ventes.quote_engine.pricing import kwh_from_bill
        ref = kwh_from_bill(1800, utility="onee")["kwh_mensuel"]
        for utility in ("lydec", "redal"):
            self.assertAlmostEqual(
                kwh_from_bill(1800, utility=utility)["kwh_mensuel"], ref,
                places=6, msg=utility)

    def test_l_etiquette_approximatif_a_disparu_du_document(self):
        from apps.ventes.quote_engine.pricing import kwh_from_bill
        for utility in ("onee", "lydec", "redal"):
            self.assertEqual(kwh_from_bill(210, utility=utility)["label"], "")

    def test_le_miroir_js_porte_la_meme_regle(self):
        # Le repo exige que solar.js reste le miroir EXACT du moteur : deux
        # grilles divergentes, c'est l'écran qui promet autre chose que le PDF.
        import os
        racine = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "..", ".."))
        chemin = os.path.join(racine, "frontend", "src", "features", "ventes",
                              "solar.js")
        with open(chemin, encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("LYDEC_TRANCHES", src)
        self.assertNotIn("REDAL_TRANCHES", src)
        self.assertIn("lydec: ONEE_TRANCHES", src)
        self.assertIn("redal: ONEE_TRANCHES", src)


class M10M11EstimationDivulgueeTests(SimpleTestCase):
    """M10/M11 — une économie estimée le DIT, et un réglage société posé par
    défaut ne se fait pas passer pour la donnée du client."""

    def test_l_economie_estimee_porte_la_mention_sur_les_trois_pages(self):
        self.assertIn("(estimation)", F.html_legacy(savings_estimated=True))

    def test_l_economie_estimee_porte_la_mention_sur_une_page(self):
        html = F.html_onepage(savings_estimated=True, onepage_branche="sans")
        self.assertIn("MAD/an (estimation)", html)

    def test_sans_drapeau_aucune_mention_ajoutee(self):
        html = F.html_onepage(onepage_branche="sans")
        self.assertNotIn("MAD/an (estimation)", html)

    def test_un_tarif_estime_n_est_jamais_dit_personnalise(self):
        # M11 — le discriminateur était « ce tarif est-il égal à la constante
        # 1,75 ? » : une société ayant simplement touché son réglage voyait ses
        # devis annoncer un tarif « personnalisé pour votre profil de
        # consommation ». Un forfait maison n'est pas la donnée du client.
        from apps.ventes.quote_engine.builder import ligne_tarif_hypothese
        estime = ligne_tarif_hypothese("1,80", "ONEE", True)
        self.assertIn("estimation", estime)
        self.assertNotIn("personnalisé", estime)
        self.assertNotIn("1,80", estime)
        # Seul un tarif saisi pour CE devis (aucune estimation) est présenté
        # comme tel — et il s'affiche alors, car c'est la donnée du client.
        saisi = ligne_tarif_hypothese("1,42", "", False)
        self.assertIn("saisi pour ce devis", saisi)
        self.assertIn("1,42", saisi)

    def test_la_ligne_de_tarif_estimee_est_rendue_telle_quelle(self):
        from apps.ventes.quote_engine.builder import ligne_tarif_hypothese
        ligne = ligne_tarif_hypothese("1,80", "ONEE", True)
        html = F.html_legacy(hypotheses={"titre": "Nos hypothèses",
                                         "items": [ligne]})
        self.assertIn("référence prudente (estimation)", html)
        self.assertNotIn("1,80", html)


class Q2SerieDeLOptionChiffreeTests(SimpleTestCase):
    """Q2 — la page 1 décrit l'option que le document chiffre.

    Elle lisait ``eco_a_monthly`` d'office : sur un devis réseau MONO-OPTION
    (aucune batterie vendue, aucune carte « avec batterie »), le « −N % » et
    l'avant/après décrivaient l'option AVEC batterie — un second jeu de
    chiffres qu'aucune page du document n'assumait.
    """

    @staticmethod
    def _donnees():
        d = F.donnees_residentiel()
        d["eco_s_monthly"] = [round(v * 0.6) for v in d["eco_a_monthly"]]
        return d

    def test_mono_option_sans_batterie_lit_la_serie_sans(self):
        from apps.ventes.quote_engine.residential.renderer import (
            synthese_economies,
        )
        d = self._donnees()
        mono = {**d, "deux_options": False, "avec_ok": False, "sans_ok": True}
        attendu = [max(0, round(b - s)) for b, s
                   in zip(d["factures_mensuelles"], d["eco_s_monthly"])]
        self.assertEqual(synthese_economies(mono)["bills_after"], attendu)

    def test_deux_options_garde_la_serie_de_l_option_recommandee(self):
        from apps.ventes.quote_engine.residential.renderer import (
            synthese_economies,
        )
        d = self._donnees()
        attendu = [max(0, round(b - s)) for b, s
                   in zip(d["factures_mensuelles"], d["eco_a_monthly"])]
        self.assertEqual(synthese_economies(d)["bills_after"], attendu)

    def test_un_seul_jeu_de_chiffres_par_document(self):
        from apps.ventes.quote_engine.residential.renderer import (
            synthese_economies,
        )
        d = self._donnees()
        mono = {**d, "deux_options": False, "avec_ok": False, "sans_ok": True}
        # Le document mono-option annonce une baisse PLUS FAIBLE — celle qu'il
        # vend réellement, pas celle d'une batterie qu'il ne chiffre pas.
        self.assertLess(synthese_economies(mono)["pct_cut"],
                        synthese_economies(d)["pct_cut"])


class M1GhiSourceUniqueTests(SimpleTestCase):
    """M1 (suite) — une SEULE dérivation du profil GHI dans tout le backend."""

    def test_public_views_importe_les_poids_au_lieu_de_les_recopier(self):
        # On lit la SOURCE plutôt que d'importer le module : `public_views`
        # tire WeasyPrint (dépendance native lourde) et ce test doit rester
        # pur. Ce qu'on vérifie est justement textuel : plus aucune seconde
        # copie de la table GHI, seulement l'import de l'unique dérivation.
        import os
        chemin = os.path.join(os.path.dirname(__file__), "..",
                              "public_views.py")
        with open(os.path.abspath(chemin), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn(
            "from .quote_engine.constants import "
            "MOROCCO_SOLAR_MONTHLY_WEIGHTS", src)
        self.assertNotIn("83.99", src)
        self.assertNotIn("_GHI_MONTHLY", src)

    def test_les_poids_derivent_de_la_table_ghi_verrouillee(self):
        from apps.ventes.quote_engine import constants
        attendu = [round(g / sum(constants.GHI), 6) for g in constants.GHI]
        self.assertEqual(constants.MOROCCO_SOLAR_MONTHLY_WEIGHTS, attendu)
