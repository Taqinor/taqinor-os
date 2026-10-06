"""CIQ341 — couverture industrielle : une synthèse de direction à
transmettre, une baseline étiquetée par sa vraie source, et la mention que
la puissance souscrite ne change pas.

Rendu RÉEL (gabarit + WeasyPrint) de la fixture industrielle, enrichie de la
sortie du moteur C&I (contrat ``etude_ci_preview.json``) et du bloc PUBLIC
``economie_ci`` (contrat ``economie_ci.json``).
"""
import copy
import json
import re
from html import unescape
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.economie_ci import economie_ci_publique
from apps.ventes.quote_engine.ci.mentions import TEXTES_PUISSANCE
from apps.ventes.quote_engine.ci.synthese import MOTIF_ARGENT_MT
from apps.ventes.quote_engine.industriel import render, renderer, sample_data

_CONTRATS = Path(__file__).resolve().parents[1] / "contract_samples"


def _contrat(nom):
    return json.loads((_CONTRATS / nom).read_text(encoding="utf-8"))


ETUDE_CI = _contrat("etude_ci_preview.json")
ECONOMIE_CI = _contrat("economie_ci.json")


def _data(etude="exemple", economie="exemple", *, interpoles=None,
          factures=True, tension=None):
    d = copy.deepcopy(sample_data.build())
    etude_d = dict(d["etude"])
    if etude:
        etude_ci = copy.deepcopy(ETUDE_CI[etude])
        if interpoles is not None:
            entrees = dict(etude_ci["entrees_resolues"])
            entrees["kwh_mensuels"] = {
                "valeur": [20000] * 12,
                "mois_interpoles": list(range(interpoles)),
                "provenance": {"origine": "lead", "detail": "facture",
                               "date": "2026-09-10"}}
            etude_ci["entrees_resolues"] = entrees
        etude_d["etude_ci"] = etude_ci
    if tension:
        etude_d["tension_raccordement"] = tension
    d["etude"] = etude_d
    if not factures:
        d["factures_mensuelles"] = None
    if economie:
        d["economie_ci"] = economie_ci_publique(
            copy.deepcopy(ECONOMIE_CI[economie]))
    return d


def _html(d):
    return render.build_html(renderer._augment(d))


def _page1(d):
    return _html(d).split('class="page"')[1]


def _texte(html):
    texte = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
    texte = unescape(re.sub(r"<[^>]+>", " ", texte))
    return re.sub(r"\s+", " ", texte.replace(" ", " "))


class Ciq341Baseline(SimpleTestCase):

    def test_deux_factures_interpolees_estimation(self):
        p1 = _texte(_page1(_data(interpoles=10)))
        self.assertIn(
            "Baseline énergétique — 2 factures, mois interpolés — estimation",
            p1)
        self.assertNotIn("12 mois", p1)
        self.assertIn("Facture électrique estimée", p1)

    def test_douze_factures(self):
        p1 = _texte(_page1(_data()))
        self.assertIn("Baseline énergétique — 12 factures", p1)

    def test_kwh_seuls_jamais_non_communiquee(self):
        p1 = _texte(_page1(_data("exemple_industriel_mt",
                                 "exemple_industriel_mt")))
        self.assertIn("Baseline énergétique — kWh déclarés", p1)
        self.assertNotIn("non communiquée", p1)
        self.assertNotIn("MAD/an", p1.split("kWh déclarés")[1][:200])

    def test_sans_source_pas_de_douze_mois(self):
        p1 = _texte(_page1(_data(etude=None, economie=None)))
        self.assertNotIn("12 mois —", p1)
        self.assertNotIn("— 12 mois", p1)


class Ciq341SiteMT(SimpleTestCase):

    def test_puissance_souscrite_et_aucune_repartition_horaire(self):
        html = _html(_data("exemple_industriel_mt", "exemple_industriel_mt"))
        self.assertIn(TEXTES_PUISSANCE["fr"], _texte(html))
        self.assertNotIn("répartition horaire", html)

    def test_mt_sans_argent_demande_les_factures_mt(self):
        html = _html(_data("exemple_industriel_mt", None))
        self.assertNotIn("répartition horaire", html)
        self.assertIn(MOTIF_ARGENT_MT, html)
        self.assertNotIn("écrêt", html)
        self.assertNotIn("cos φ", html)


class Ciq341Synthese(SimpleTestCase):

    def test_synthese_tri_horizon_sans_van_sans_taux(self):
        p1 = _texte(_page1(_data()))
        self.assertIn("Synthèse", p1)
        self.assertIn("TRI sur 25 ans", p1)
        self.assertIn("39,8 %", p1)
        self.assertNotIn("VAN", p1)
        self.assertIn("Économie de l'année 1", p1)
        self.assertIn("Retour estimé", p1)

    def test_van_sur_taux_declare_et_financement(self):
        p1 = _texte(_page1(_data("exemple_industriel_mt",
                                 "exemple_industriel_mt")))
        self.assertIn("VAN au taux déclaré de 8 %", p1)
        self.assertIn("1 670 759,73", p1.replace(" ", " "))
        self.assertIn("Financement", p1)
        self.assertIn("Estimation sous réserve de la visite technique", p1)

    def test_sans_argent_motif(self):
        p1 = _texte(_page1(_data(economie=None)))
        self.assertIn("Synthèse", p1)
        self.assertNotIn("TRI sur", p1)
        self.assertIn("vos 12 dernières factures", p1)

    def test_quatre_pages(self):
        from weasyprint import HTML
        for etude, eco in (("exemple", "exemple"),
                           ("exemple_industriel_mt", "exemple_industriel_mt"),
                           ("exemple_industriel_mt", None), (None, None)):
            with self.subTest(etude=etude, eco=eco):
                doc = HTML(string=_html(_data(etude, eco))).render()
                self.assertEqual(len(doc.pages), 4)
