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
        self.assertIn("Investissement HT (clé en main) : 1 458 333,33 MAD HT",
                      texte)

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
        self.assertIn("durée d'analyse : 25 ans", texte)


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
        self.assertIn("Base de production : 10° d'inclinaison, plein sud — à "
                      "confirmer au calepinage", texte)
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
        self.assertIn("Entretien (O&M) non déduite des économies", tableau)
        self.assertIn("Règle de dimensionnement", tableau)
        # Compact : jamais l'investissement (incomplet ici) dans le tableau.
        self.assertNotIn("Investissement 247 500", tableau)

    def test_taux_declare_sans_nom_de_champ_interne(self):
        texte = _texte(_pages(_data("exemple_industriel_mt"))[3])
        self.assertIn("Taux d'actualisation : 8 % — déclaré par le client",
                      texte)
        self.assertNotIn("taux_actualisation_client", texte)
        self.assertIn("Prix du kWh : ceux de votre facture d'électricité",
                      texte)
