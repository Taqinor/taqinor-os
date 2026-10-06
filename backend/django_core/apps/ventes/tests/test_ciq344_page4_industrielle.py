"""CIQ344 — page 4 industrielle : 4 jalons de paiement, une phrase de
décarbonation conditionnelle et exacte, et plus de « traçabilité CBAM ».

Rendu RÉEL (gabarit + WeasyPrint) de la fixture industrielle ; l'export UE
et l'activité sont les colonnes DÉCLARÉES du lead (CIQ1/CIQ405,
``_entrees_ci_lead``), les jalons ceux que sert le builder (CIQ212,
``jalons_paiement``).
"""
import re
from decimal import Decimal
from html import unescape

from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine.ci.mentions import (
    SOURCE_CBAM, TEXTES_DECARBONATION, decarbonation_ci)
from apps.ventes.quote_engine.ci.synthese import synthese_ci
from apps.ventes.quote_engine.industriel import render, renderer, sample_data

#: Les montants de ``jalons_paiement_devis`` (CIQ212) : chaque jalon non
#: final au centime, le dernier porte le reliquat — somme = total TTC.
JALONS = [
    {"jalon": "commande", "libelle": "Commande", "pct": 30,
     "montant_ttc": 525000.26},
    {"jalon": "livraison_materiel", "libelle": "Livraison du matériel",
     "pct": 40, "montant_ttc": 700000.34},
    {"jalon": "mise_en_service", "libelle": "Mise en service", "pct": 20,
     "montant_ttc": 350000.17},
    {"jalon": "reception_definitive", "libelle": "Réception définitive",
     "pct": 10, "montant_ttc": 175000.08},
]
TOTAL = Decimal("1750000.85")


def _lead(export=None, secteur=None):
    entrees, informations = [], []
    if secteur is not None:
        entrees.append({"colonne": "secteur_industriel", "valeur": secteur})
    if export is not None:
        informations.append({"colonne": "export_ue_declare",
                             "valeur": export})
    return {"entrees": entrees, "manquants": [],
            "informations": informations}


def _data(export=None, secteur=None):
    d = sample_data.build()
    d["jalons_paiement"] = [dict(j) for j in JALONS]
    d["_entrees_ci_lead"] = _lead(export, secteur)
    return d


def _html(d):
    return render.build_html(renderer._augment(d))


def _page4(d):
    return _html(d).split('class="page"')[4]


def _texte(html):
    texte = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
    texte = unescape(re.sub(r"<[^>]+>", " ", texte))
    return re.sub(r"\s+", " ", texte.replace(" ", " "))


class Ciq344Decarbonation(SimpleTestCase):

    def test_sans_declaration_export_aucun_cbam(self):
        html = _html(_data())
        self.assertNotIn("CBAM", html)
        self.assertIn(TEXTES_DECARBONATION["fr"], _texte(html))

    def test_export_ue_ciment_phrase_cbam_avec_reference(self):
        texte = _texte(_page4(_data("oui", "Cimenterie — ciment Portland")))
        self.assertIn("CBAM", texte)
        self.assertIn(SOURCE_CBAM, texte)
        self.assertIn("Règlement (UE) 2023/956", texte)

    def test_export_ue_engrais_sans_accents(self):
        self.assertTrue(decarbonation_ci(
            {"_entrees_ci_lead": _lead("oui", "Fabrication d'ENGRAIS azotés")}
        )["cbam"])

    def test_acier_exporte_pas_de_cbam(self):
        # Fer, acier, aluminium, hydrogène : émissions DIRECTES seulement.
        html = _html(_data("oui", "Laminoir — acier"))
        self.assertNotIn("CBAM", html)

    def test_ciment_sans_export_declare_pas_de_cbam(self):
        self.assertNotIn("CBAM", _html(_data("non", "ciment")))

    def test_jamais_tracabilite_ni_tonnage(self):
        for d in (_data(), _data("oui", "ciment")):
            with self.subTest():
                html = _html(d).lower()
                self.assertNotIn("traçabilité", html)
                self.assertNotIn("tco2", html)
                self.assertNotIn("tonnes de co", html)

    def test_forme_du_contrat(self):
        s = synthese_ci(_data("oui", "ciment"))
        self.assertEqual(set(s["decarbonation"]), {"cbam", "textes"})
        self.assertEqual(set(s["decarbonation"]["textes"]), {"fr", "en", "ar"})
        commercial = dict(_data(), mode_installation="commercial")
        self.assertNotIn("decarbonation", synthese_ci(commercial))

    def test_iso_50001_sans_promesse_de_conformite(self):
        texte = _texte(_page4(_data()))
        self.assertIn("ISO 50001", texte)
        self.assertIn("sans promesse de conformité", texte)


@tag("weasyprint")  # rendu PDF réel
class Ciq344Jalons(SimpleTestCase):

    def test_quatre_jalons_au_centime_somme_egale_total(self):
        html = _page4(_data())
        montants = re.findall(
            r'class="i3-ech-m"[^>]*>([^<]*)&#160;MAD TTC</div>', html)
        self.assertEqual(len(montants), 4, montants)
        somme = sum(Decimal(re.sub(r"[^\d,]", "", m).replace(",", "."))
                    for m in montants)
        self.assertEqual(somme, TOTAL)
        texte = _texte(html)
        for pct, libelle in ((30, "À la commande"), (40, "À la livraison"),
                             (20, "À la mise en service"),
                             (10, "À la réception définitive")):
            self.assertIn(f"{pct} %", texte)
            self.assertIn(libelle, texte)

    def test_quatre_pages(self):
        from weasyprint import HTML
        for d in (_data(), _data("oui", "ciment")):
            with self.subTest():
                self.assertEqual(len(HTML(string=_html(d)).render().pages), 4)
