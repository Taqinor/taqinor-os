"""CIQ315 — chiffres phares en HT pour une entreprise qui récupère la TVA,
TTC sinon ; la chaîne HT → TVA → TTC reste au tableau (D-CIQ-3).

Rendu RÉEL des deux gabarits, la base venant de ``synthese_ci.argent.base``
(bloc ``economie_ci`` du contrat partagé) pour les trois bases.
"""
import copy
import json
from decimal import Decimal
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.economie_ci import economie_ci_publique
from apps.ventes.quote_engine.ci.couverture import NOTE_TVA_RECUPERABLE
from apps.ventes.quote_engine.commercial import render as c_render
from apps.ventes.quote_engine.commercial import renderer as c_renderer
from apps.ventes.quote_engine.commercial import sample_data as c_sample
from apps.ventes.quote_engine.figures import extract_figures
from apps.ventes.quote_engine.industriel import render as i_render
from apps.ventes.quote_engine.industriel import renderer as i_renderer
from apps.ventes.quote_engine.industriel import sample_data as i_sample

_CONTRATS = Path(__file__).resolve().parents[1] / "contract_samples"
ECONOMIE = json.loads((_CONTRATS / "economie_ci.json").read_text(
    encoding="utf-8"))["exemple"]
ETUDE_CI = json.loads((_CONTRATS / "etude_ci_preview.json").read_text(
    encoding="utf-8"))["exemple"]

GABARITS = (
    ("commercial", c_sample, c_renderer, c_render, "c1c-root", "c2-root"),
    ("industriel", i_sample, i_renderer, i_render, "i1-root", "c2-root"),
)


def _rendu(sample, renderer, render, base):
    data = copy.deepcopy(sample.build())
    if "ht_net" not in data["totaux_all"]:
        # Le builder sert TOUJOURS la chaîne entière ; la fixture industrielle
        # n'en porte que le TTC.
        data["totaux_all"] = {"ht_brut": 1458333.33, "remise": 0,
                              "ht_net": 1458333.33, "tva": 291666.67,
                              "ttc": 1750000}
    data["etude"] = dict(data.get("etude") or {},
                         etude_ci=copy.deepcopy(ETUDE_CI))
    if base is not None:
        economie = copy.deepcopy(ECONOMIE)
        economie["base"] = base
        data["economie_ci"] = economie_ci_publique(economie)
    d = renderer._augment(data)
    return d, render.build_html(d)


def _couverture(html, racine):
    """La page 1 seule (jusqu'à la racine de la page 2)."""
    debut = html.index(f'class="{racine}"')
    return html[debut:html.index('class="c2-root"')]


def _valeurs(html, cle):
    return [m.valeur for ident, ms in extract_figures(html).items()
            if ident.split("@")[0] == cle for m in ms]


class BaseHtTtc(SimpleTestCase):

    def test_base_ht(self):
        for nom, sample, renderer, render, racine, _p2 in GABARITS:
            with self.subTest(gabarit=nom):
                d, html = _rendu(sample, renderer, render, "ht")
                self.assertIn("Investissement HT (clé en main)", html)
                self.assertIn(NOTE_TVA_RECUPERABLE, html)
                self.assertNotIn("Investissement (TTC, clé en main)",
                                 _couverture(html, racine))
                ht = Decimal(str(d["totaux_all"]["ht_net"]))
                self.assertIn(ht, _valeurs(html, "total_ht"))
                self.assertIn(Decimal(str(d["_invest_ttc"])),
                              _valeurs(html, "total_affiche"))
                # Jamais un investissement HT face à des économies TTC.
                self.assertIn("Économies estimées / an (HT)", html)

    def test_base_ttc_libelle_d_hier(self):
        for nom, sample, renderer, render, racine, _p2 in GABARITS:
            with self.subTest(gabarit=nom):
                _d, html = _rendu(sample, renderer, render, "ttc")
                self.assertIn("Investissement (TTC, clé en main)", html)
                self.assertNotIn("Investissement HT", html)
                self.assertNotIn(NOTE_TVA_RECUPERABLE, html)
                self.assertIn("Économies estimées / an (TTC)", html)

    def test_base_inconnue_ht_et_ttc(self):
        for nom, sample, renderer, render, racine, _p2 in GABARITS:
            with self.subTest(gabarit=nom):
                d, html = _rendu(sample, renderer, render, "deux")
                self.assertIn("Investissement (clé en main)", html)
                self.assertIn("MAD TTC", html)
                self.assertIn("MAD HT", html)
                self.assertIn(Decimal(str(d["totaux_all"]["ht_net"])),
                              _valeurs(html, "total_ht"))

    def test_sans_argent_libelle_d_hier(self):
        for nom, sample, renderer, render, racine, _p2 in GABARITS:
            with self.subTest(gabarit=nom):
                _d, html = _rendu(sample, renderer, render, None)
                self.assertIn("Investissement (TTC, clé en main)", html)

    def test_chaine_de_totaux_page_2_inchangee(self):
        for nom, sample, renderer, render, racine, page2 in GABARITS:
            with self.subTest(gabarit=nom):
                pages = []
                for base in ("ht", "ttc", "deux"):
                    _d, html = _rendu(sample, renderer, render, base)
                    debut = html.index(f'class="{page2}"')
                    fin = html.index("Total TTC", debut)
                    pages.append(html[debut:fin + 400])
                self.assertEqual(pages[0], pages[1])
                self.assertEqual(pages[1], pages[2])
