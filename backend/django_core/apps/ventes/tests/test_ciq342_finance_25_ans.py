"""CIQ342 — page finance industrielle (1/2) : 25 ans, jalons 5/10/15/20/25,
TRI avec son horizon et payback ancré, lus dans ``synthese_ci`` — plus
aucune arithmétique privée.

Rendu RÉEL (gabarit + WeasyPrint) de la fixture industrielle, enrichie du
bloc PUBLIC ``economie_ci`` des exemples du contrat ``economie_ci.json``.
"""
import re
from html import unescape

from django.test import SimpleTestCase

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


class Ciq342SiteMT(SimpleTestCase):

    def test_mt_flux_present_revente_hors_cashflow(self):
        d = _data("exemple_industriel_mt")
        texte = _texte(_pages(d)[3])
        self.assertIn("Cumul net de l'investissement (HT)", texte)
        self.assertIn("hors cashflow", texte)
        self.assertIn("Excédent racheté 0,21 / 0,18 DH HT", texte)
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
