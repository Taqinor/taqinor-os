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

from django.test import SimpleTestCase, tag

from apps.ventes.economie_ci import economie_ci_publique
from apps.ventes.quote_engine.ci.mentions import TEXTES_PUISSANCE
from apps.ventes.quote_engine.ci.synthese import MOTIF_ARGENT_MT
from apps.ventes.quote_engine.industriel import render, renderer, sample_data

from ._moteur_fixtures import etude_ci_au_kwc_servi

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
            "Votre consommation et votre production — 2 factures, mois "
            "interpolés — estimation", p1)
        self.assertNotIn("aseline", p1)
        self.assertNotIn("12 mois", p1)
        self.assertIn("Facture électrique estimée", p1)

    def test_douze_factures(self):
        p1 = _texte(_page1(_data()))
        self.assertIn("Votre consommation et votre production — 12 factures",
                      p1)

    def test_kwh_seuls_jamais_non_communiquee(self):
        p1 = _texte(_page1(_data("exemple_industriel_mt",
                                 "exemple_industriel_mt")))
        self.assertIn("Votre consommation et votre production — d'après vos "
                      "kWh déclarés", p1)
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


@tag("weasyprint")  # rendu PDF réel
class Ciq341Synthese(SimpleTestCase):

    def test_synthese_tri_horizon_sans_van_sans_taux(self):
        p1 = _texte(_page1(_data()))
        self.assertIn("Synthèse", p1)
        self.assertIn("TRI sur 25 ans", p1)
        self.assertIn("39,8 %", p1)
        self.assertNotIn("VAN", p1)
        # CPDF — un chiffre, une fois : l'économie et le retour sont dits par
        # leurs tuiles, l'investissement par son bloc ; l'encadré ne les
        # répète plus (« Économie de l'année 1 » n'est plus en page 1).
        self.assertNotIn("Économie de l'année 1", p1)
        self.assertIn("Retour estimé", p1)
        self.assertEqual(p1.count("Retour estimé"), 1)
        self.assertEqual(p1.count("1 750 000,00"), 1)

    def test_van_sur_taux_declare_et_financement(self):
        p1 = _texte(_page1(_data("exemple_industriel_mt",
                                 "exemple_industriel_mt")))
        self.assertIn("VAN au taux déclaré de 8 %", p1)
        self.assertIn("1 670 759,73", p1.replace(" ", " "))
        self.assertIn("Financement", p1)
        self.assertIn("Devis préliminaire — les prix pourront être ajustés "
                      "après la visite technique", p1)

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


class Amot80OffreFermeEtTitresCfo(SimpleTestCase):
    """AMOT80 — plus de statut « prix ferme » (décision fondateur
    26/10/2026 : devis C&I préliminaire) ; le sous-titre de rentabilité
    seulement avec un flux."""

    def _sans_reserve(self, etude, economie):
        d = _data(etude, economie)
        d["etude"]["etude_ci"]["sous_reserve_visite"] = {"valeur": False,
                                                         "motif": None}
        return _texte(_page1(d))

    def test_offre_ferme_jamais_sur_une_grille_de_repli(self):
        # ``exemple`` : tarif d'origine grille_officielle (grille publiée).
        self.assertNotIn("prix ferme", self._sans_reserve("exemple",
                                                          "exemple"))

    def test_offre_ferme_sur_facture_declaree_sans_reserve(self):
        p1 = self._sans_reserve("exemple_industriel_mt",
                                "exemple_industriel_mt")
        # Décision fondateur 26/10/2026 — le devis C&I entier est
        # préliminaire : plus jamais « prix ferme » (ni la rangée « Statut de
        # l'étude »), même sur une facture déclarée sans réserve.
        self.assertNotIn("prix ferme", p1)
        self.assertNotIn("Statut de l'étude", p1)
        texte = _texte(_html(_data("exemple_industriel_mt",
                                   "exemple_industriel_mt")))
        self.assertNotIn("prix ferme", texte)
        # Décision fondateur 26/10/2026 — le bandeau « Devis préliminaire »
        # est imprimé sur TOUT document C&I, même sans réserve.
        self.assertIn("Devis préliminaire", p1)
        self.assertNotIn("offre ferme", _texte(_html(_data(
            "exemple_industriel_mt", "exemple_industriel_mt"))))

    def test_jamais_offre_ferme_sous_reserve(self):
        p1 = _texte(_page1(_data("exemple_industriel_mt",
                                 "exemple_industriel_mt")))
        self.assertIn("Devis préliminaire — les prix pourront être ajustés "
                      "après la visite technique", p1)
        self.assertNotIn("prix ferme", p1)

    def test_titres_cfo_seulement_avec_un_flux(self):
        avec = _texte(_html(_data()))
        self.assertIn("Analyse de rentabilité : votre consommation, vos flux "
                      "annuels et le délai de retour.", avec)
        # AMOT88 — plus aucun mot interne (CFO, baseline, cashflow, payback).
        for mot in ("CFO", "aseline", "ashflow", "payback"):
            self.assertNotIn(mot, avec)
        sans = _texte(_html(_data(economie=None)))
        self.assertNotIn("Analyse de rentabilité :", sans)
        self.assertNotIn("Rentabilité sur 25 ans", sans)


class Amot89DefinitionsEtSurplus(SimpleTestCase):
    """AMOT89 — couverture industrielle : définition servie sous la tuile
    d'autoconsommation et surplus en kWh du bilan (règle 82-21)."""

    def test_definition_et_surplus(self):
        # L'étude décrit le kWc servi (garde AMOT62) : taux et bilan servis.
        p1 = _texte(_page1(etude_ci_au_kwc_servi(_data())))
        self.assertIn("Autoconsommation part de la production consommée sur "
                      "place", p1)
        # CPDF5 — un chiffre du bilan, sans « ≈ ».
        self.assertIn("Surplus non valorisé : 25 959 kWh/an (27 % de la "
                      "production) — revente non ouverte en basse tension",
                      p1)

    def test_site_mt_sans_revente(self):
        p1 = _texte(_page1(etude_ci_au_kwc_servi(_data(
            "exemple_industriel_mt", "exemple_industriel_mt"))))
        self.assertIn("— revente du surplus non retenue.", p1)
        self.assertNotIn("basse tension à ce jour", p1)


def _deux_options(d):
    """``d`` en devis « les deux » (offre réseau servie, option batterie
    servie à côté avec la valeur chiffrée du moteur)."""
    d["option_servie"] = "sans"
    d["puissance_kwc_avec"] = 260.0
    d["option_batterie"] = {
        "totaux": {"ht_net": 1666666.67, "ttc": 2000000.0},
        "valeur_chiffree": {"economie_annuelle_mad": 150000.0,
                            "retour_simple_ans": 11.1,
                            "textes": {"fr": "x", "en": "x", "ar": "x"}},
        "motif": None}
    return d


class Cpdf3IndustrielDeuxOptions(SimpleTestCase):

    def test_deux_cartes_et_un_seul_investissement(self):
        p1 = _texte(_page1(_deux_options(_data())))
        sans, avec = p1.split("Sans batterie")[1].split("Avec batterie")
        for carte in (sans, avec):
            for libelle in ("Puissance", "Investissement TTC",
                            "Économie annuelle", "Retour sur investissement"):
                self.assertIn(libelle, carte)
        self.assertIn("2 000 000,00 MAD", avec)
        self.assertIn("11,1 ans", avec)
        self.assertNotIn("Investissement (TTC, clé en main)", p1)
        self.assertNotIn("Économies estimées", p1)
        self.assertEqual(p1.count("1 750 000,00"), 1)

    def test_mono_option_sans_carte(self):
        p1 = _texte(_page1(_data()))
        self.assertNotIn("Sans batterie", p1)
        self.assertIn("Investissement (TTC, clé en main)", p1)


@tag("weasyprint")  # rendu PDF réel
class Cpdf3IndustrielQuatrePages(SimpleTestCase):

    def test_deux_options_quatre_pages(self):
        from weasyprint import HTML
        doc = HTML(string=_html(_deux_options(_data()))).render()
        self.assertEqual(len(doc.pages), 4)


class Cpdf5CouvertureSansReserve(SimpleTestCase):

    def test_conso_et_production_sans_approximation(self):
        p1 = _texte(_page1(etude_ci_au_kwc_servi(_data())))
        self.assertIn("Consommation : ", p1)
        self.assertIn("Production : 95 425 kWh/an", p1)
        self.assertNotIn("Production estimée", p1)
        self.assertNotIn("Consommation ≈", p1)
        self.assertNotIn("· ≈", p1)

    def test_mention_mt_sans_parenthese_de_releve(self):
        from apps.ventes.quote_engine.constants_82_21 import MENTION_MT
        d = _data()
        d["tarif_mt_mention"] = MENTION_MT
        p1 = _texte(_page1(d))
        self.assertIn("Tarif Général (MT)", p1)
        self.assertNotIn("TVA 18 %", p1)
        self.assertNotIn("relevé le", p1)

    def test_motif_option_avec_jamais_imprime(self):
        from apps.ventes.quote_engine.ci.couverture import ligne_non_chiffre
        d = {"ind_motif_argent": ("économies de l'option avec batterie non "
                                  "chiffrées à ce stade"),
             "ind_synthese": {}}
        self.assertEqual(ligne_non_chiffre(d, "ind", "i1"), "")
