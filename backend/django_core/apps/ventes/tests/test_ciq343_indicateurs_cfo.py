"""CIQ343 — page finance industrielle (2/2) : coût du kWh solaire face au
tarif du client, VAN sur le seul taux déclaré, sensibilités saisies par
Reda, production P90 et offre de financement.

Rendu RÉEL (gabarit + WeasyPrint) de la fixture industrielle, enrichie du
bloc PUBLIC ``economie_ci`` des exemples du contrat ``economie_ci.json``.
"""
import json
import re
from html import unescape

from django.test import SimpleTestCase, tag

from apps.ventes.public.payload_economie import _sans_internes_bancables
from apps.ventes.quote_engine.ci.synthese import synthese_ci
from apps.ventes.quote_engine.figures import FIGURE_KEYS, extract_figures
from apps.ventes.quote_engine.industriel import render, renderer, sample_data

SENSIBILITES = [
    {"cle": "indexation_tarif", "variation_pct": 2.0,
     "source": "Paramètres › Tarification & ROI", "economie_annee1_mad": 1,
     "retour_ans": 4, "tri_pct": 29.1, "ecart_retour_ans": 0,
     "ecart_tri_pct": 2.1},
    {"cle": "production", "variation_pct": -10.0,
     "source": "Paramètres › Tarification & ROI", "economie_annee1_mad": 1,
     "retour_ans": 5, "tri_pct": 24.2, "ecart_retour_ans": 1,
     "ecart_tri_pct": -2.8},
]
BANCABLE = {"pr": {"p50_kwh": 340000, "p90_kwh": 312500,
                   "performance_ratio": 0.81}}


def _data(exemple="exemple", *, sensibilites=None, bancable=False):
    d = sample_data.build()
    bloc = sample_data.economie_ci(exemple)
    if sensibilites is not None:
        bloc["sensibilites"] = sensibilites
    d["economie_ci"] = bloc
    if bancable:
        d["etude"] = dict(d["etude"], bankable=dict(BANCABLE))
    return d


def _page(d):
    return render.build_html(renderer._augment(d)).split('class="page"')[3]


def _texte(html):
    texte = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
    texte = unescape(re.sub(r"<[^>]+>", " ", texte))
    return re.sub(r"\s+", " ", texte.replace(" ", " "))


class Ciq343Van(SimpleTestCase):

    def test_sans_taux_declare_aucune_van_motif(self):
        texte = _texte(_page(_data()))
        self.assertNotIn("VAN au taux", texte)
        self.assertIn("VAN non calculée : aucun taux d'actualisation déclaré "
                      "par le client", texte)

    def test_avec_taux_declare_van_egale_synthese(self):
        d = _data("exemple_industriel_mt")
        van = synthese_ci(dict(d))["argent"]["indicateurs"]["van_mad"]
        texte = _texte(_page(d))
        self.assertIn("VAN au taux déclaré de 8 % : 1 670 759,73 MAD", texte)
        self.assertEqual(van, 1670759.73)


class Ciq343Lcoe(SimpleTestCase):

    def test_lcoe_face_au_prix_du_client_ancre(self):
        d = _data("exemple_industriel_mt")
        page = _page(d)
        texte = _texte(page)
        indicateurs = d["economie_ci"]["indicateurs"]
        self.assertIn("Coût du kWh solaire (LCOE, HT) : 0,1221 MAD/kWh",
                      texte)
        self.assertIn("prix moyen de votre kWh évité : 0,8407 MAD/kWh", texte)
        figures = extract_figures(page)
        lcoe = [m.valeur for i, ms in figures.items()
                if i.startswith("lcoe_mad_kwh") for m in ms]
        self.assertEqual([float(v) for v in lcoe],
                         [indicateurs["lcoe_mad_kwh"]])
        self.assertIn("lcoe_mad_kwh", FIGURE_KEYS)


class Ciq343Sensibilites(SimpleTestCase):

    def test_sans_sensibilite_aucun_scenario(self):
        texte = _texte(_page(_data()))
        self.assertNotIn("Sensibilités saisies", texte)
        self.assertNotIn("Indexation du tarif +", texte)

    def test_sensibilites_saisies_imprimees(self):
        texte = _texte(_page(_data(sensibilites=SENSIBILITES)))
        self.assertIn("Indexation du tarif +2 % : retour 4 ans, TRI 29,1 %",
                      texte)
        self.assertIn("Production -10 % : retour 5 ans, TRI 24,2 %", texte)
        self.assertIn("base : 0 % d'indexation", texte)


class Ciq343P90(SimpleTestCase):

    def test_bloc_bancable_ligne_p90(self):
        texte = _texte(_page(_data(bancable=True)))
        self.assertIn(
            "Production à 90 % de probabilité (P90) : 312 500 kWh/an", texte)

    def test_sans_bloc_bancable_aucune_p90(self):
        self.assertNotIn("P90", _texte(_page(_data())))

    def test_aucune_cle_p90_dans_la_charge_publique(self):
        d = _data(bancable=True)
        self.assertNotIn("p90", json.dumps(synthese_ci(dict(d))).lower())
        public = _sans_internes_bancables(d)
        self.assertNotIn("bankable", public["etude"])


@tag("weasyprint")  # rendu PDF réel
class Ciq343Financement(SimpleTestCase):

    def test_offre_de_financement_servie(self):
        texte = _texte(_page(_data("exemple_industriel_mt")))
        self.assertIn("Offre de financement", texte)
        self.assertIn("Échéance mensuelle : 12 000,00 MAD HT sur 84 mois",
                      texte)

    def test_quatre_pages_avec_tout(self):
        from weasyprint import HTML
        d = _data("exemple_industriel_mt", sensibilites=SENSIBILITES,
                  bancable=True)
        html = render.build_html(renderer._augment(d))
        doc = HTML(string=html).render()
        self.assertEqual(len(doc.pages), 4)
        # Densité MESURÉE : aucun texte de la page finance ne descend dans la
        # bande de pied (la page fixe le couperait en silence).
        from apps.ventes.quote_engine.commercial.equip import deborde
        self.assertFalse(deborde(doc.pages[2]))
