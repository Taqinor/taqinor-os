"""CIQ331 — PDF commercial : 3 pages complétées du retour sur investissement,
de la production annuelle, de l'échéancier et de la validité (D-CIQ-9).

Rendu RÉEL (gabarit + WeasyPrint) sur la fixture commerciale, enrichie de la
sortie du moteur C&I (contrat ``etude_ci_preview.json``), du bloc PUBLIC
``economie_ci`` (contrat ``economie_ci.json``) et des N jalons de paiement
servis par le builder (CIQ212, ``jalons_paiement``).
"""
import copy
import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.economie_ci import economie_ci_publique
from apps.ventes.quote_engine.ci.categories import CATEGORIES
from apps.ventes.quote_engine.ci.synthese import (
    MOTIF_ARGENT_MT, chiffres_cles, synthese_ci)
from apps.ventes.quote_engine.commercial import render, renderer, sample_data
from apps.ventes.quote_engine.figures import extract_figures

_CONTRATS = Path(__file__).resolve().parents[1] / "contract_samples"


def _contrat(nom):
    return json.loads((_CONTRATS / nom).read_text(encoding="utf-8"))


ETUDE_CI = _contrat("etude_ci_preview.json")
ECONOMIE_CI = _contrat("economie_ci.json")

JALONS = [
    {"jalon": "commande", "libelle": "Commande", "pct": 40,
     "montant_ttc": 256000.0},
    {"jalon": "livraison_materiel", "libelle": "Livraison du matériel",
     "pct": 50, "montant_ttc": 320000.0},
    {"jalon": "mise_en_service", "libelle": "Mise en service", "pct": 10,
     "montant_ttc": 64000.0},
]


def _data(categorie="hotel", *, argent=True, lignes=None, tension=None,
          etude_ci=True):
    data = copy.deepcopy(sample_data.build(categorie))
    etude = dict(data["etude"])
    if etude_ci:
        etude["etude_ci"] = copy.deepcopy(ETUDE_CI["exemple"])
    if tension:
        etude["tension_raccordement"] = tension
    data["etude"] = etude
    if argent:
        data["economie_ci"] = economie_ci_publique(
            copy.deepcopy(ECONOMIE_CI["exemple"]))
    data["jalons_paiement"] = copy.deepcopy(JALONS)
    data["valid_until"] = "05/11/2026"
    if lignes:
        modele = data["all_items"][0]
        data["all_items"] = [dict(modele, designation=f"Article {i}")
                             for i in range(lignes)]
    return data


def _html(data):
    return render.build_html(renderer._augment(data))


def _pages(data):
    import fitz
    pdf = renderer.render_pdf_bytes(data)
    return [p.get_text() for p in fitz.open(stream=pdf, filetype="pdf")]


def _cles(html):
    return {i.split("@")[0] for i in extract_figures(html)}


class Ciq331DocumentChiffre(SimpleTestCase):

    def test_payback_production_et_jalons(self):
        data = _data()
        pages = _pages(data)
        self.assertEqual(len(pages), 3)
        chiffres = chiffres_cles(synthese_ci(data))
        p1 = pages[0]
        self.assertIn("Production annuelle", p1)
        self.assertIn("95 425", p1.replace(" ", " ").replace(
            "\xa0", " "))
        self.assertIn("Retour estimé", p1)
        self.assertIn("Valable jusqu", p1)
        self.assertEqual(chiffres["payback_ans"], 3)
        p3 = pages[2].replace(" ", " ").replace("\xa0", " ")
        self.assertIn("Échéancier de paiement", p3)
        for montant in ("256 000,00", "320 000,00", "64 000,00"):
            self.assertIn(montant, p3)
        for libelle in ("À la commande", "À la livraison",
                        "À la mise en service"):
            self.assertIn(libelle, p3)

    def test_ancres_payback_et_production(self):
        html = _html(_data())
        cles = _cles(html)
        self.assertIn("payback_ans", cles)
        self.assertIn("production_annuelle_kwh", cles)

    def test_financement_servi_puis_conditions(self):
        data = _data()
        eco = copy.deepcopy(ECONOMIE_CI["exemple"])
        eco["financement"] = copy.deepcopy(
            ECONOMIE_CI["exemple_industriel_mt"]["financement"])
        data["economie_ci"] = economie_ci_publique(eco)
        html = _html(data)
        p3 = html.split('class="page"')[3]
        self.assertIn("Offre de financement", p3)
        self.assertLess(p3.index("Échéancier de paiement"),
                        p3.index("Offre de financement"))
        self.assertLess(p3.index("Offre de financement"),
                        p3.index("Bon pour accord"))


class Ciq331SansArgent(SimpleTestCase):

    def test_motif_et_aucun_zero(self):
        html = _html(_data(argent=False))
        p1 = html.split('class="page"')[1]
        self.assertIn("vos 12 dernières factures", p1)
        self.assertNotIn("0&nbsp;MAD", p1)
        self.assertNotIn(">0<", p1)
        cles = _cles(html)
        self.assertNotIn("economie_annuelle", cles)
        self.assertNotIn("payback_ans", cles)

    def test_mt_sans_factures(self):
        html = _html(_data(argent=False, tension="mt", etude_ci=False))
        self.assertNotIn("répartition horaire", html)
        self.assertIn(MOTIF_ARGENT_MT, html)
        self.assertEqual(len(_pages(_data(argent=False, tension="mt",
                                          etude_ci=False))), 3)


class Ciq331TroisPages(SimpleTestCase):

    def test_dix_categories(self):
        from weasyprint import HTML
        self.assertEqual(len(CATEGORIES), 10)
        for categorie in CATEGORIES:
            with self.subTest(categorie=categorie):
                doc = HTML(string=_html(_data(categorie))).render()
                self.assertEqual(len(doc.pages), 3)

    def test_quarante_lignes(self):
        self.assertEqual(len(_pages(_data(lignes=40))), 3)


class Ciq331EcheancierN(SimpleTestCase):

    def test_quatre_jalons_servis_tels_quels(self):
        data = _data()
        data["jalons_paiement"] = [
            {"jalon": "commande", "libelle": "Commande", "pct": 30,
             "montant_ttc": 192000.0},
            {"jalon": "livraison_materiel", "libelle": "x", "pct": 40,
             "montant_ttc": 256000.0},
            {"jalon": "mise_en_service", "libelle": "x", "pct": 20,
             "montant_ttc": 128000.0},
            {"jalon": "reception_definitive", "libelle": "x", "pct": 10,
             "montant_ttc": 64000.0},
        ]
        ech = synthese_ci(data)["echeancier"]
        self.assertEqual([j["jalon"] for j in ech],
                         ["commande", "livraison", "mise_en_service",
                          "reception_definitive"])
        self.assertEqual([j["pct"] for j in ech], [30, 40, 20, 10])
        self.assertEqual(sum(j["montant_ttc"] for j in ech), 640000)
        self.assertEqual(set(ech[0]), {"libelle", "pct", "montant_ttc",
                                       "jalon"})

    def test_sans_jalons_repli_sur_les_trois_creneaux(self):
        data = _data()
        data.pop("jalons_paiement")
        ech = synthese_ci(data)["echeancier"]
        self.assertEqual([j["jalon"] for j in ech],
                         ["commande", "livraison", "mise_en_service"])
