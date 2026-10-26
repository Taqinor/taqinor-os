"""CIQ342 — page finance industrielle (1/2) : 25 ans, jalons 5/10/15/20/25,
TRI avec son horizon et payback ancré, lus dans ``synthese_ci`` — plus
aucune arithmétique privée.

Rendu RÉEL (gabarit + WeasyPrint) de la fixture industrielle, enrichie du
bloc PUBLIC ``economie_ci`` des exemples du contrat ``economie_ci.json``.
"""
import re
from html import unescape

from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine.ci.synthese import synthese_ci
from apps.ventes.quote_engine.figures import FIGURE_KEYS, extract_figures
from apps.ventes.quote_engine.industriel import (
    finance, render, renderer, sample_data)
from apps.ventes.quote_engine.montants import fmt_centimes


def _data(exemple="exemple"):
    d = sample_data.build()
    d["totaux_all"] = {"ht_brut": 1458333.33, "remise": 0,
                       "ht_net": 1458333.33, "tva": 291666.67,
                       "ttc": 1750000}
    d["economie_ci"] = sample_data.economie_ci(exemple)
    return d


def _pages(d):
    return render.build_html(renderer._augment(d)).split('class="page"')


def _texte(html):
    texte = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
    texte = unescape(re.sub(r"<[^>]+>", " ", texte))
    return re.sub(r"\s+", " ", texte.replace(" ", " "))


class Ciq342Jalons(SimpleTestCase):

    def test_cinq_jalons_tri_25_ans_au_centime(self):
        d = _data()
        argent = synthese_ci(dict(d))["argent"]
        texte = _texte(_pages(d)[3])
        self.assertIn("TRI sur 25 ans", texte)
        self.assertIn("Rentabilité sur 25 ans", texte)
        self.assertEqual(len(argent["jalons"]), 5)
        for jalon in argent["jalons"]:
            with self.subTest(annee=jalon["annee"]):
                self.assertIn(f"Année {jalon['annee']}", texte)
                self.assertIn(fmt_centimes(jalon["cumul_mad"]).replace(
                    " ", " "), texte)

    def test_cles_ancrees_egales_a_la_synthese(self):
        d = _data()
        argent = synthese_ci(dict(d))["argent"]
        figures = extract_figures(_pages(d)[3])
        valeurs = {i.split("@")[0]: float(ms[0].valeur)
                   for i, ms in figures.items()}
        self.assertAlmostEqual(valeurs["tri_pct"],
                               argent["indicateurs"]["tri_pct"], delta=0.05)
        self.assertAlmostEqual(valeurs["cumul_net_25_ans_mad"],
                               argent["jalons"][-1]["cumul_mad"], places=2)
        self.assertEqual(valeurs["payback_ans"],
                         argent["indicateurs"]["retour_ans"])
        self.assertIn("tri_pct", FIGURE_KEYS)
        self.assertIn("cumul_net_25_ans_mad", FIGURE_KEYS)

    def test_courbe_sur_tout_l_horizon(self):
        d = _data()
        page = _pages(d)[3]
        self.assertEqual(len(re.findall(r'class="i2-b[pn]"', page)),
                         len(d["economie_ci"]["flux_ht"]["flux"]))

    def test_aucun_solveur_prive(self):
        self.assertFalse(hasattr(finance, "irr_flat"))
        self.assertFalse(hasattr(finance, "irr_series"))
        self.assertFalse(hasattr(finance, "_flux_annuels"))


@tag("weasyprint")  # rendu PDF réel
class Ciq342SiteMT(SimpleTestCase):

    def test_mt_flux_present_revente_hors_cashflow(self):
        d = _data("exemple_industriel_mt")
        texte = _texte(_pages(d)[3])
        self.assertIn("Cumul net de l'investissement (HT)", texte)
        self.assertIn("hors flux annuels", texte)
        self.assertNotIn("cashflow", texte)
        # Mention 82-21 SERVIE par ``economie_ci.revente_ci`` (contrat
        # réaligné sur le service : MENTION_82_21 en tête des six).
        self.assertIn("Tarif d'excédent ANRE (décision 04/26) : 18 cDH/kWh",
                      texte)
        self.assertNotIn("n'est pas rémunéré", texte)
        # Pied de page sur la base servie (CIQ315) : HT.
        # Le titre dit « HT » : le montant ne le répète pas.
        self.assertIn("Investissement HT (clé en main) : 1 458 333,33 MAD",
                      texte)
        self.assertNotIn("1 458 333,33 MAD HT", texte)

    def test_jamais_n_est_pas_remunere(self):
        for exemple in ("exemple", "exemple_industriel_mt"):
            with self.subTest(exemple=exemple):
                html = render.build_html(renderer._augment(_data(exemple)))
                self.assertNotIn("n'est pas rémunéré", html)
                self.assertNotIn("non rémunéré", html)

    def test_sans_serie_le_motif(self):
        d = sample_data.build()
        texte = _texte(_pages(d)[3])
        self.assertIn("Rentabilité non chiffrée sur ce dossier", texte)
        self.assertNotIn("TRI sur", texte)

    def test_quatre_pages(self):
        from weasyprint import HTML
        for exemple in ("exemple", "exemple_industriel_mt"):
            with self.subTest(exemple=exemple):
                html = render.build_html(renderer._augment(_data(exemple)))
                self.assertEqual(len(HTML(string=html).render().pages), 4)


#: AMOT80 — codes et chemins INTERNES jamais lus par un client.
CHAINES_INTERNES = ("D-CIQ", "economie_ci.", "etude_ci.", "Groupe CIQ",
                    "décision Q1", ".json")


class Amot80PageFinance(SimpleTestCase):
    """AMOT80 (D-ACI-8=a) — page 3 : motif vrai quand l'investissement n'est
    pas chiffré, LCOE « non actualisé » étiqueté, aucun code interne."""

    def test_investissement_non_chiffre_le_motif_remplace_la_phrase(self):
        from apps.ventes import economie_ci as eco
        from apps.ventes.tests.test_ciq210_branchement import _apercu
        d = sample_data.build()
        d["economie_ci"] = eco.economie_ci_publique(eco.assembler_economie_ci(
            _apercu("mt"), investissement={"ht": 0.0, "ttc": 0.0},
            mode_installation="industriel"))
        texte = _texte(_pages(d)[3])
        self.assertIn("Investissement non encore chiffré (3 articles sans "
                      "prix)", texte)
        self.assertNotIn("n'ont pas encore été calculées", texte)
        self.assertNotIn("12 dernières factures", texte)
        self.assertNotIn("Rentabilité sur 25 ans", texte)
        self.assertNotIn("TRI sur", texte)

    def test_lcoe_non_actualise_etiquete(self):
        texte = _texte(_pages(_data())[3])
        self.assertIn("Coût moyen non actualisé du kWh produit (HT)", texte)
        self.assertNotIn("Coût du kWh solaire", texte)

    def test_aucun_code_interne(self):
        for exemple in ("exemple", "exemple_industriel_mt"):
            texte = _texte(_pages(_data(exemple))[3])
            for interne in CHAINES_INTERNES:
                with self.subTest(exemple=exemple, interne=interne):
                    self.assertNotIn(interne, texte)
        # Les sources restent dites, en mots du client.
        texte = _texte(_pages(_data())[3])
        self.assertIn("valorisation heure par heure au tarif de chaque poste",
                      texte)
        # « Horizon : 25 ans », une seule mention (la source le répétait).
        self.assertIn("Horizon : 25 ans", texte)
        self.assertNotIn("durée d'analyse", texte)


def _data_energie(exemple="exemple"):
    """La fixture industrielle + la sortie du moteur C&I (bilan horaire,
    contrat ``etude_ci_preview.json``) alignée sur le kWc servi."""
    import copy
    import json
    from pathlib import Path

    from ._moteur_fixtures import etude_ci_au_kwc_servi
    contrat = Path(__file__).resolve().parents[1] / "contract_samples"
    etude_ci = json.loads((contrat / "etude_ci_preview.json").read_text(
        encoding="utf-8"))["exemple"]
    d = _data(exemple) if exemple else sample_data.build()
    d["etude"] = dict(d.get("etude") or {}, etude_ci=copy.deepcopy(etude_ci))
    return etude_ci_au_kwc_servi(d)


class Amot90PageEnergie(SimpleTestCase):
    """AMOT90 — la page 3 industrielle non chiffrable n'est plus une page
    blanche : l'énergie mois par mois (kWh du bilan servi) et le surplus,
    sous la petite ligne de motif ; chiffrable, le graphique suit le bloc
    financier (retiré par le rendu adaptatif s'il ne tient pas)."""

    def test_non_chiffrable_page_energie(self):
        d = _data_energie(None)
        p3 = _pages(d)[3]
        texte = _texte(p3)
        self.assertIn('data-graphique="energie_mensuelle"', p3)
        graphique = p3[p3.index('data-graphique="energie_mensuelle"'):]
        self.assertEqual(graphique[:graphique.index("</svg>")].count("<rect"),
                         36)
        self.assertIn("Ce que la centrale produit pour votre site", texte)
        self.assertIn("Votre énergie mois par mois", texte)
        self.assertIn("Surplus non valorisé : ≈ 25 959 kWh/an", texte)
        # La petite ligne de motif reste ; plus l'encadré blanc.
        self.assertIn("Économies et retour sur investissement non chiffrés",
                      texte)
        self.assertNotIn("Rentabilité non chiffrée sur ce dossier", texte)
        self.assertEqual(len(_pages(d)) - 1, 4)

    def test_sans_bilan_encadre_d_hier(self):
        texte = _texte(_pages(sample_data.build())[3])
        self.assertIn("Rentabilité non chiffrée sur ce dossier", texte)
        self.assertNotIn("Votre énergie mois par mois", texte)

    def test_chiffrable_graphique_apres_le_bloc_financier(self):
        p3 = _pages(_data_energie())[3]
        self.assertIn("Rentabilité sur 25 ans", _texte(p3))
        self.assertLess(p3.index("Hypothèses de l"),
                        p3.index('data-graphique="energie_mensuelle"'))
        sans = _pages(dict(_data_energie(), _sans_graphiques=True))[3]
        self.assertNotIn("data-graphique", sans)


class Amot91Hypotheses(SimpleTestCase):
    """AMOT91 — les deux rangées nouvelles (base de production, règle de
    dimensionnement) dans la liste de la page finance ; le tableau compact
    sur la page énergie (non chiffrable)."""

    def test_page_finance_deux_rangees_nouvelles(self):
        texte = _texte(_pages(_data_energie())[3])
        self.assertIn("Base de production : 10° d'inclinaison, plein sud",
                      texte)
        # Décision fondateur 26/10/2026 — aucune réserve interne imprimée.
        self.assertNotIn("à confirmer au calepinage", texte)
        self.assertIn("Règle de dimensionnement : chaque palier de 5 kWc "
                      "retenu se rembourse en moins de 10 ans", texte)
        self.assertIn("Prix du kWh : Tarif ONEE BT publié", texte)
        self.assertNotIn("repli", texte)

    def test_page_energie_tableau_compact(self):
        d = _data_energie(None)
        d["economie_ci"] = sample_data.economie_ci("exemple")
        d["economie_ci"]["omissions"] = [{
            "cle": "investissement_mad", "motif": "investissement à "
            "compléter après la visite technique (3 postes hors total)"}]
        d["economie_ci"]["flux_ht"] = dict(d["economie_ci"]["flux_ht"],
                                           flux=[])
        texte = _texte(_pages(d)[3])
        self.assertIn("Ce que la centrale produit pour votre site", texte)
        tableau = texte[texte.index("Hypothèses de l'estimation"):]
        self.assertIn("Entretien (O&M) non déduit des économies", tableau)
        self.assertIn("Règle de dimensionnement", tableau)
        # Compact : jamais l'investissement (incomplet ici) dans le tableau.
        self.assertNotIn("Investissement 247 500", tableau)

    def test_methode_8760_dite(self):
        """AMOT99 (D-ACI-18=a) — la méthode retenue par le moteur est dite :
        série 8 760 h de l'année type (``production.methode_autoconso``)."""
        texte = _texte(_pages(_data_energie())[3])
        self.assertIn("Méthode de calcul : autoconsommation calculée heure "
                      "par heure sur l'année type (8 760 h)", texte)
        self.assertNotIn("journées moyennes", texte)

    def test_methode_repli_journees_moyennes_dite(self):
        d = _data_energie()
        d["etude"]["etude_ci"]["production"]["methode_autoconso"] = \
            "journees_moyennes"
        texte = _texte(_pages(d)[3])
        self.assertIn("autoconsommation : estimation sur journées moyennes",
                      texte)
        self.assertNotIn("8 760 h", texte)
        # Décision fondateur 26/10/2026 — sans « (série horaire
        # indisponible) ».
        self.assertNotIn("série horaire indisponible", texte)

    def test_methode_absente_rien_d_imprime(self):
        """Une étude stockée avant AMOT99 (sans méthode) : aucune ligne."""
        d = _data_energie()
        d["etude"]["etude_ci"]["production"].pop("methode_autoconso", None)
        self.assertNotIn("Méthode de calcul", _texte(_pages(d)[3]))

    def test_methode_tableau_commun_commercial_et_anglais(self):
        """La SEULE source (``rangees_hypotheses``) des deux documents ; en
        anglais, le libellé du catalogue."""
        from apps.ventes.quote_engine import i18n_labels
        for methode, cle in (("horaire_8760", "ci_h_methode_8760"),
                             ("journees_moyennes", "ci_h_methode_journees")):
            synthese = {"estimation": {"methode_autoconso": methode}}
            for langue in ("fr", "en"):
                def L(c, fr, langue=langue, **kw):
                    return i18n_labels.libelle(c, langue)
                rangees = finance.rangees_hypotheses(
                    {"langue_sortie": langue}, synthese, str, str, L)
                with self.subTest(methode=methode, langue=langue):
                    self.assertIn(
                        (i18n_labels.libelle("ci_h_methode_autoconso",
                                             langue),
                         i18n_labels.libelle(cle, langue)), rangees)

    def test_degradation_de_la_fiche_dite(self):
        """AMOT99 — la dégradation de la fiche module et sa 1re année."""
        from apps.ventes.moteur_ci import degradation
        d = _data_energie()
        hyps = d["economie_ci"]["flux_ht"]["hypotheses"]
        for h in hyps:
            if h["cle"] == "degradation_pct":
                h.update(valeur=0.4, source=degradation.SOURCE_FICHE,
                         source_code="degradation_fiche_module")
        hyps.append({"cle": "degradation_annee1_pct", "valeur": 1.0,
                     "source": degradation.SOURCE_FICHE,
                     "source_code": "degradation_fiche_module"})
        texte = _texte(_pages(d)[3])
        self.assertIn("Dégradation de la 1re année : 1 % — fiche module : "
                      "courbe de garantie de performance du fabricant", texte)

    def test_taux_declare_sans_nom_de_champ_interne(self):
        texte = _texte(_pages(_data("exemple_industriel_mt"))[3])
        self.assertIn("Taux d'actualisation : 8 % — déclaré par le client",
                      texte)
        self.assertNotIn("taux_actualisation_client", texte)
        self.assertIn("Prix du kWh : ceux de votre facture d'électricité",
                      texte)


class Amot84SourcesServiesParCode(SimpleTestCase):
    """AMOT84 — les textes français SERVIS par ``economie_ci`` (indexation
    constante, dégradation NREL, méthode horaire) portent un code stable :
    un document anglais en imprime le libellé anglais ; le français reste le
    texte servi, octet pour octet."""

    def _texte(self, langue):
        from apps.ventes import economie_ci as eco
        d = _data()
        d["langue_sortie"] = langue
        for h in d["economie_ci"]["flux_ht"]["hypotheses"]:
            if h["cle"] == "indexation_pct":
                h.update(source=eco.MENTION_INDEXATION_CONSTANTE,
                         source_code=eco.CODE_INDEXATION_CONSTANTE)
            elif h["cle"] == "degradation_pct":
                h.update(source=eco.DEGRADATION_CI_SOURCE,
                         source_code=eco.CODE_DEGRADATION_NREL)
        return _texte(_pages(d)[3])

    def test_anglais_libelles_du_code(self):
        texte = self._texte("en")
        hyp = texte[texte.index("Estimate assumptions"):]
        hyp = hyp[:hyp.index("kWh price")]
        for en in ("median from Jordan & Kurtz, NREL/JA-5200-51664, 2012",
                   "tariff of the time-of-use period covered, hour by hour"):
            self.assertIn(en, hyp)
        # Décision fondateur 26/10/2026 — l'indexation constante est une
        # réserve interne : la valeur seule, jamais « (assumption) ».
        self.assertNotIn("assumption", hyp)
        for fr in ("hypothèse", "médiane", "heure par heure"):
            self.assertNotIn(fr, hyp)

    def test_francais_texte_servi(self):
        from apps.ventes import economie_ci as eco
        texte = self._texte("fr")
        for fr in (eco.DEGRADATION_CI_SOURCE,
                   eco.HYPOTHESE_VALORISATION["valeur"]):
            self.assertIn(fr, texte)
        # Décision fondateur 26/10/2026 — « 0 % / an », sans « tarif de
        # vente constant (hypothèse) ».
        self.assertIn("Indexation du tarif : 0 % / an", texte)
        self.assertNotIn(eco.MENTION_INDEXATION_CONSTANTE, texte)

    def test_aucune_reserve_interne_imprimee(self):
        """Décision fondateur 26/10/2026 — le document C&I ne justifie
        jamais une incertitude interne : dégradation par défaut (fiche
        muette), indexation constante, entretien non chiffré, base PVGIS,
        méthode de repli, tarif de grille — la VALEUR reste, la réserve
        part. FR et EN."""
        from apps.ventes import economie_ci as eco
        from apps.ventes.moteur_ci import degradation
        for langue in ("fr", "en"):
            d = _data_energie()
            d["langue_sortie"] = langue
            production = d["etude"]["etude_ci"]["production"]
            production["methode_autoconso"] = "journees_moyennes"
            for h in d["economie_ci"]["flux_ht"]["hypotheses"]:
                if h["cle"] == "indexation_pct":
                    h.update(source=eco.MENTION_INDEXATION_CONSTANTE,
                             source_code=eco.CODE_INDEXATION_CONSTANTE)
                elif h["cle"] == "degradation_pct":
                    h.update(valeur=0.5, source=degradation.SOURCE_DEFAUT,
                             source_code="degradation_defaut_fiche_muette")
            texte = "".join(_texte(p) for p in _pages(d))
            with self.subTest(langue=langue):
                for reserve in (
                        "fiche muette", "datasheet silent", "(hypothèse)",
                        "(assumption)", "entretien non chiffré",
                        "maintenance not quantified",
                        "à confirmer au calepinage",
                        "to be confirmed by the panel layout",
                        "to be confirmed on your bill", "À confirmer :",
                        "To be confirmed:", "série horaire indisponible",
                        "hourly series unavailable", "non sourcée",
                        "à confirmer sur votre facture"):
                    self.assertNotIn(reserve, texte)
            if langue == "fr":
                for valeur in ("Dégradation des panneaux : 0,5 % / an",
                               "Indexation du tarif : 0 % / an",
                               "non déduit des économies"):
                    self.assertIn(valeur, texte)

    def test_le_moteur_sert_les_codes(self):
        from apps.ventes import economie_ci as eco
        bloc = eco.flux_ci(
            eco.base_economique(
                "oui", investissement={"ht": 400000.0, "ttc": 480000.0},
                economie_annee1={"total_mad": 80000.0,
                                 "total_mad_ttc": 96000.0}),
            production_annee1_kwh=100000)["flux_ht"]
        hyp = {h["cle"]: h for h in bloc["hypotheses"]}
        self.assertEqual(hyp["indexation_pct"]["source_code"],
                         "indexation_constante")
        self.assertEqual(hyp["degradation_pct"]["source_code"],
                         "degradation_nrel_2012")
        # Le texte français reste servi (lecteurs d'hier).
        self.assertEqual(hyp["indexation_pct"]["source"],
                         eco.MENTION_INDEXATION_CONSTANTE)
        self.assertEqual(eco.HYPOTHESE_VALORISATION["valeur_code"],
                         "methode_horaire_poste")


class Amot94RemplacementSurLaBaseServie(SimpleTestCase):
    """AMOT94 — la rangée « Remplacement onduleur » des hypothèses dit le
    montant sur la BASE servie : HT quand la TVA est récupérable
    (``argent.base == 'ht'``), TTC sinon (base « deux » inchangée)."""

    def _ligne(self, exemple):
        d = _data(exemple)
        argent = synthese_ci(dict(d))["argent"]
        texte = _texte(_pages(d)[3])
        debut = texte.index("Remplacement onduleur en année")
        return argent, texte[debut:debut + 80]

    def test_base_ht_montant_ht(self):
        argent, ligne = self._ligne("exemple_industriel_mt")
        self.assertEqual(argent["base"], "ht")
        ht = argent["remplacements"][0]["montant_ht_mad"]
        ttc = argent["remplacements"][0]["montant_ttc_mad"]
        self.assertIn(fmt_centimes(ht).replace(" ", " ") + " MAD HT", ligne)
        self.assertNotIn(fmt_centimes(ttc).replace(" ", " "), ligne)
        self.assertNotIn("TTC", ligne)

    def test_base_deux_montant_ttc_inchange(self):
        argent, ligne = self._ligne("exemple")
        self.assertEqual(argent["base"], "deux")
        ttc = argent["remplacements"][0]["montant_ttc_mad"]
        self.assertIn(fmt_centimes(ttc).replace(" ", " ") + " MAD TTC",
                      ligne)


class Amot97Sensibilites(SimpleTestCase):
    """AMOT97 (D-ACI-15=a) — les scénarios du réglage société (seedés,
    modifiables) calculés sur la MÊME série que le central, imprimés en
    tableau sur l'industriel : retour, TRI, cumul 25 ans et source, chaque
    chiffre servi par ``economie_ci``."""

    SCENARIOS = [
        {"cle": "production", "variation_pct": -7.7, "source": "P90 seedé"},
        {"cle": "indexation_tarif", "variation_pct": 2.0,
         "source": "historique saisi"},
        {"cle": "degradation", "variation_pct": 0.75, "source": "D-ACI-15"},
        {"cle": "tarif_kwh", "variation_pct": -5.0,
         "source": "contribution art. 13 saisie"},
    ]

    def _bloc(self, scenarios, investissement=None):
        import copy
        import json
        from pathlib import Path

        from apps.ventes import economie_ci as eco
        contrats = Path(__file__).resolve().parents[1] / "contract_samples"
        apercu = copy.deepcopy(json.loads(
            (contrats / "etude_ci_preview.json").read_text(
                encoding="utf-8"))["exemple"])
        return eco.assembler_economie_ci(
            apercu, tarif_declare={"contrat": "bt_patente"},
            investissement=investissement or {"ht": 900000.0,
                                              "ttc": 1080000.0},
            mode_installation="industriel",
            reglages={"sensibilites_ci": scenarios})

    def test_seedes_sources_et_valides(self):
        from apps.parametres import tariff
        defaut = tariff.sensibilites_ci_par_defaut()
        self.assertEqual(tariff.erreurs_sensibilites_ci(defaut), {})
        self.assertTrue(all(s["source"].strip() for s in defaut))
        bloc = self._bloc(defaut)
        self.assertEqual([s["cle"] for s in bloc["sensibilites"]],
                         [s["cle"] for s in defaut])

    def test_quatre_scenarios_servis_meme_serie_et_cumul(self):
        bloc = self._bloc(self.SCENARIOS)
        self.assertEqual(len(bloc["sensibilites"]), 4)
        for s in bloc["sensibilites"]:
            with self.subTest(cle=s["cle"]):
                self.assertIsNotNone(s["retour_ans"])
                self.assertIsNotNone(s["cumul_25_ans_mad"])
        # Même série que le central, une seule grandeur change : dégradation
        # 0,75 %/an > 0,5 % ⇒ cumul plus bas ; indexation +2 %/an ⇒ plus haut.
        par_cle = {s["cle"]: s for s in bloc["sensibilites"]}
        central = bloc["flux_ht"]["flux"][-1]["cumul_mad"]
        self.assertLess(par_cle["degradation"]["cumul_25_ans_mad"], central)
        self.assertGreater(par_cle["indexation_tarif"]["cumul_25_ans_mad"],
                           central)

    def test_scenario_retire_n_apparait_pas(self):
        bloc = self._bloc(self.SCENARIOS[:3])
        self.assertNotIn("tarif_kwh", [s["cle"] for s in bloc["sensibilites"]])

    def test_prix_incomplet_aucun_scenario_chiffre(self):
        from apps.ventes import economie_ci as eco
        lignes = [{"designation": "Panneau", "ht": 0, "ttc": 0,
                   "optionnelle": False, "onduleur": False, "panneau": True,
                   "role_ci": None}]
        import copy
        import json
        from pathlib import Path
        contrats = Path(__file__).resolve().parents[1] / "contract_samples"
        apercu = copy.deepcopy(json.loads(
            (contrats / "etude_ci_preview.json").read_text(
                encoding="utf-8"))["exemple"])
        bloc = eco.assembler_economie_ci(
            apercu, tarif_declare={"contrat": "bt_patente"},
            investissement={"ht": None, "ttc": None}, lignes=lignes,
            mode_installation="industriel",
            reglages={"sensibilites_ci": self.SCENARIOS})
        self.assertEqual(bloc["sensibilites"], [])
        self.assertIn("sensibilites", [o["cle"] for o in bloc["omissions"]])

    def test_tableau_imprime_chaque_chiffre_servi(self):
        d = _data()
        sensibilites = [
            {"cle": "production", "variation_pct": -7.7, "source": "P90 seedé",
             "retour_ans": 4, "tri_pct": 31.2, "cumul_25_ans_mad": 1111111.11},
            {"cle": "indexation_tarif", "variation_pct": 2.0,
             "source": "historique saisi", "retour_ans": 3, "tri_pct": 44.4,
             "cumul_25_ans_mad": 2222222.22},
            {"cle": "degradation", "variation_pct": 0.75, "source": "D-ACI-15",
             "retour_ans": 3, "tri_pct": 38.8, "cumul_25_ans_mad": 1999999.99},
            {"cle": "tarif_kwh", "variation_pct": -5.0,
             "source": "contribution art. 13 saisie", "retour_ans": 4,
             "tri_pct": 35.5, "cumul_25_ans_mad": 1555555.55}]
        d["economie_ci"]["sensibilites"] = sensibilites
        argent = synthese_ci(dict(d))["argent"]
        p3 = _pages(d)[3]
        debut = p3.index("Scénario central")
        texte = _texte(p3[debut:p3.index("</table>", debut)])
        self.assertIn(f"Scénario central {argent['indicateurs']['retour_ans']}"
                      f" ans", texte)
        self.assertIn(fmt_centimes(argent["flux_ht"]["flux"][-1][
            "cumul_mad"]).replace(" ", " "), texte)
        for s in sensibilites:
            with self.subTest(cle=s["cle"]):
                self.assertIn(fmt_centimes(s["cumul_25_ans_mad"]).replace(
                    " ", " "), texte)
                self.assertIn(f"{s['tri_pct']:.1f}".replace(".", ","), texte)
                self.assertIn(s["source"], texte)
        self.assertIn("Production -7,7 %", texte)
        # Rendu adaptatif : le tableau cède avec les hypothèses.
        sans = _pages(dict(d, _sans_graphiques=frozenset({"hypotheses"})))[3]
        self.assertNotIn("Scénario central", sans)

    def test_sans_scenario_aucun_tableau(self):
        d = _data()
        d["economie_ci"]["sensibilites"] = []
        self.assertNotIn("Scénario central", _pages(d)[3])


class Amot94TableauVingtCinqAns(SimpleTestCase):
    """AMOT94 — le flux servi année par année (0 → 25) à la place des cinq
    jalons : production, économie, O&M (si déduite), remplacement, flux net
    et cumul de CHAQUE ligne servie ; le cumul de l'année 25 reste ancré."""

    def _tableau(self, d):
        p3 = _pages(d)[3]
        debut = p3.index('class="i2-tbl i2-fx"')
        return p3, p3[debut:p3.index("</table>", debut)]

    def test_chaque_ligne_servie(self):
        d = _data()
        argent = synthese_ci(dict(d))["argent"]
        _p3, tableau = self._tableau(d)
        texte = _texte(tableau)
        flux = argent["flux_ht"]["flux"]
        self.assertEqual(len(flux), 26)
        self.assertEqual(tableau.count("<tr>"), 27)  # en-tête + 26 années
        for f in flux:
            with self.subTest(annee=f["annee"]):
                self.assertIn(f"Année {f['annee']}", texte)
                self.assertIn(fmt_centimes(f["cumul_mad"]).replace(
                    " ", " "), texte)
                self.assertIn(fmt_centimes(f["flux_mad"]).replace(
                    " ", " "), texte)
        for entete in ("Production (kWh)", "Économie", "Remplacement",
                       "Flux net", "Cumul net (HT)"):
            self.assertIn(entete, texte)
        # Remplacement de l'onduleur au montant HT servi, l'année servie.
        remplacement = argent["remplacements"][0]
        ligne = texte[texte.index(f"Année {remplacement['annee']} "):]
        self.assertTrue(ligne.split("Année")[1].count(fmt_centimes(
            -remplacement["montant_ht_mad"]).replace(" ", " ")))
        # O&M non souscrite : non déduite, aucune colonne.
        self.assertNotIn("O&M", texte)
        self.assertIn('data-figure="cumul_net_25_ans_mad"', tableau)

    def test_production_lue_sur_la_ligne_servie(self):
        d = _data()
        flux = d["economie_ci"]["flux_ht"]["flux"]
        for f in flux:
            if f["annee"]:
                f["production_kwh"] = 90000 + f["annee"]
        texte = _texte(self._tableau(d)[1])
        self.assertIn("Année 7 90 007", texte)

    def test_om_souscrite_colonne_deduite(self):
        d = _data()
        d["economie_ci"]["om"] = {"statut": "souscrit",
                                  "montant_mad_an": 12000.0,
                                  "source": "ligne O&M souscrite"}
        texte = _texte(self._tableau(d)[1])
        self.assertIn("O&M", texte)
        self.assertEqual(texte.count("-12 000,00"), 25)

    def test_entretien_minimum_colonne_et_hypotheses(self):
        """AMOT96 (D-ACI-14=a) — l'entretien minimum DÉDUIT par le moteur
        (``argent.entretien``) : colonne « Entretien » du tableau des 25 ans
        (le montant servi chaque année), la ligne sous les KPI et la rangée
        des hypothèses étiquetées « réglage société »."""
        d = _data()
        d["economie_ci"]["entretien"] = {
            "statut": "deduit", "montant_mad_an": 6000.0, "mad_kwc_an": 30.0,
            "kwc": 200.0, "source": "entretien minimum à votre charge "
                                    "(réglage société)"}
        p3, tableau = self._tableau(d)
        texte = _texte(tableau)
        self.assertIn("Entretien", texte)
        self.assertNotIn("O&M", texte)
        self.assertEqual(texte.count("-6 000,00"), 25)
        page = _texte(p3)
        self.assertIn("entretien minimum à votre charge (réglage société) : "
                      "6 000,00 MAD/an, déduit des économies", page)
        self.assertIn("Entretien (O&M) : entretien minimum à votre charge",
                      page)

    def test_entretien_non_chiffre_dit_sans_colonne(self):
        d = _data()
        self.assertEqual(d["economie_ci"]["entretien"]["statut"],
                         "non_chiffre")
        p3, tableau = self._tableau(d)
        self.assertNotIn("Entretien", _texte(tableau))
        # Décision fondateur 26/10/2026 — « non déduit des économies »,
        # sans la réserve « entretien non chiffré ».
        self.assertIn("non déduit des économies", _texte(p3))
        self.assertNotIn("entretien non chiffré", _texte(p3))

    def test_courbe_cedable_tableau_garde(self):
        p3 = _pages(dict(_data(), _sans_graphiques=frozenset(
            {"courbe_cumul"})))[3]
        self.assertNotIn('class="i2-courbe"', p3)
        self.assertIn('class="i2-tbl i2-fx"', p3)

    def test_rendu_adaptatif_cede_les_blocs_de_la_seule_page_qui_deborde(self):
        from unittest import mock

        from apps.ventes.quote_engine.commercial import equip
        html = ('<div class="page"><div data-graphique="etapes"></div></div>'
                '<div class="page"><div data-graphique="energie_mensuelle">'
                '</div><div data-graphique="courbe_cumul"></div></div>')

        class _Doc:
            pages = ["p1", "p2"]

        with mock.patch.object(equip, "deborde", lambda page: page == "p2"):
            self.assertEqual(
                equip._cedables_des_pages_debordantes(html, _Doc()),
                frozenset({"energie_mensuelle", "courbe_cumul"}))
        # Page de trop : on ne sait plus laquelle a poussé — toutes.
        _Doc.pages = ["p1", "p2", "p3"]
        self.assertEqual(equip._cedables_des_pages_debordantes(html, _Doc()),
                         frozenset({"etapes", "energie_mensuelle",
                                    "courbe_cumul"}))

    def test_ordre_des_blocs_cedes_chaque_retrait_re_mesure(self):
        """AMOT94 — page finance qui déborde : l'énergie mensuelle cède
        d'abord, puis la courbe du cumul, puis les hypothèses, chaque retrait
        RE-MESURÉ ; le bloc d'une page qui ne déborde pas reste."""
        from unittest import mock

        from apps.ventes.quote_engine.ci.graphiques import cede
        from apps.ventes.quote_engine.commercial import equip
        essais = []

        def _build(donnees):
            essais.append(donnees.get("_sans_graphiques"))
            blocs = "".join(
                f'<div data-graphique="{nom}"></div>'
                for nom in ("courbe_cumul", "hypotheses", "energie_mensuelle")
                if not cede(donnees, nom))
            return ('<div class="page"><div data-graphique="etapes"></div>'
                    '</div><div class="page">' + blocs + '</div>')

        class _Doc:
            pages = ["p1", "p2"]

        def _tient(html, _doc):
            return 'data-graphique="hypotheses"' not in html

        with mock.patch.object(equip, "deborde", lambda page: page == "p2"), \
                mock.patch.object(equip, "_tient", _tient):
            doc = equip.document_adaptatif({}, _build, lambda _html: _Doc())
        self.assertIsNotNone(doc)
        self.assertEqual(essais, [
            None, frozenset({"energie_mensuelle"}),
            frozenset({"energie_mensuelle", "courbe_cumul"}),
            frozenset({"energie_mensuelle", "courbe_cumul", "hypotheses"})])
