"""QJR119 — les PDF industriel et commercial cessent de fabriquer des zéros.

Trois zéros d'apparence factuelle vivaient sur ces deux documents clients :

* ``industriel/cover.py`` rembourrait les factures manquantes de ``0.0`` et
  imprimait « 0 MAD/an — Facture électrique actuelle » + douze barres vides,
  alors que ``builder`` pose ``factures_mensuelles = None`` sur tout dossier
  chiffré depuis une consommation annuelle ;
* ``industriel/renderer.py`` et ``commercial/renderer.py`` faisaient
  ``round(eco) if eco else 0``, écrasant ``None`` en ``0`` — d'où une promesse
  de « 0 MAD d'économies par an », la seule garde d'omission ne couvrant que
  le cas moyenne tension ;
* ``industriel/finance.py`` imprimait « Payback ≈ 0,0 ans » (sentinelle
  ``pricing``) sur la page même qui annonce « Point mort > 15 ans ».

Le résidentiel fait l'inverse et OMET. Les deux paquets pro font pareil.

Run (sans base de données) :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr119_zero_fabrique -v 2
"""
import re

from django.test import SimpleTestCase

from apps.ventes.quote_engine.commercial import (
    render as c_render, renderer as c_renderer, sample_data as c_sample)
from apps.ventes.quote_engine.industriel import (
    render as i_render, renderer as i_renderer, sample_data as i_sample)


def _visible(html):
    """Texte visible d'un rendu (CSS + balises retirés, espaces normalisés)."""
    txt = re.sub(r"<style>.*?</style>", " ", html, flags=re.S)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = txt.replace("&nbsp;", " ").replace(" ", " ")
    txt = txt.replace("&amp;", "&").replace("&#8217;", "'")
    return re.sub(r"[\s  ]+", " ", txt)


def _sans_donnees(sample_mod, renderer_mod):
    """Devis réel mais SANS factures ni économies chiffrables."""
    data = sample_mod.build()
    data["factures_mensuelles"] = None
    data["eco_s_ann"] = None
    data["roi_s"] = None
    data.pop("etude", None)
    # Sans économie année 1, ``pricing.compute_cashflow_payback`` rend une
    # série VIDE : la fixture reproduit ce que le builder servirait vraiment.
    for cle in ("cashflow_sans", "cashflow_avec", "cashflow_assumptions"):
        data.pop(cle, None)
    return renderer_mod._augment(data)


class TestIndustrielSansDonnees(SimpleTestCase):
    def setUp(self):
        self.d = _sans_donnees(i_sample, i_renderer)
        self.html = i_render.build_html(self.d)
        self.txt = _visible(self.html)

    def test_augment_propage_none(self):
        self.assertIsNone(self.d["ind_economies"])
        self.assertIsNone(self.d["ind_payback"])

    def test_aucun_zero_monetaire_imprime(self):
        self.assertIsNone(
            re.search(r"(?<![\d  ])0(?:[.,]0)? ?MAD", self.txt),
            "un « 0 MAD » d'apparence mesurée subsiste : %r"
            % self.txt[:400])

    def test_carte_facture_et_barres_omises(self):
        self.assertNotIn("Facture électrique actuelle · ", self.txt)
        self.assertIn("non communiquée", self.txt)
        self.assertNotIn('class="i1-bar"', self.html)

    def test_carte_economies_omise(self):
        self.assertNotIn("Économies / an", self.txt)

    def test_page_financiere_omet_cashflow_et_payback(self):
        self.assertNotIn("Cashflow cumulé", self.txt)
        self.assertNotIn("Payback", self.txt)
        self.assertNotIn("Point mort", self.txt)
        # …et dit POURQUOI, sans invoquer la moyenne tension (dossier BT).
        self.assertIn("Rentabilité non chiffrée sur ce dossier", self.txt)
        self.assertNotIn("MOYENNE TENSION", self.txt)

    def test_le_document_reste_a_trois_pages(self):
        self.assertEqual(self.html.count('class="page"'), 3)


class TestCommercialSansDonnees(SimpleTestCase):
    def setUp(self):
        self.d = _sans_donnees(c_sample, c_renderer)
        self.html = c_render.build_html(self.d)
        self.txt = _visible(self.html)

    def test_augment_propage_none(self):
        self.assertIsNone(self.d["com_economies"])
        self.assertIsNone(self.d["com_payback"])

    def test_aucun_zero_monetaire_imprime(self):
        self.assertIsNone(
            re.search(r"(?<![\d  ])0(?:[.,]0)? ?MAD", self.txt),
            "un « 0 MAD » d'apparence mesurée subsiste : %r"
            % self.txt[:400])

    def test_carte_economies_omise(self):
        self.assertNotIn("Économies / an", self.txt)

    def test_le_document_reste_a_trois_pages(self):
        self.assertEqual(self.html.count('class="page"'), 3)


class TestSentinellePayback(SimpleTestCase):
    """``pricing`` pose ``roi_* = 0.0`` pour dire « pas de payback »."""

    def test_zero_virgule_zero_an_jamais_imprime(self):
        data = i_sample.build()
        data.pop("etude", None)     # la sentinelle vient du repli builder…
        data["roi_s"] = 0.0         # …c.-à-d. de ``pricing.roi_opt1 = 0.0``
        d = i_renderer._augment(data)
        self.assertIsNone(d["ind_payback"])
        txt = _visible(i_render.build_html(d))
        self.assertNotIn("0,0 ans", txt)


class TestNonRegressionDossierChiffre(SimpleTestCase):
    """Un dossier COMPLET reste rendu exactement comme avant."""

    def setUp(self):
        self.ind = i_renderer._augment(i_sample.build())
        self.com = c_renderer._augment(c_sample.build())

    def test_industriel_garde_sa_baseline_et_ses_kpis(self):
        txt = _visible(i_render.build_html(self.ind))
        self.assertIn("Baseline énergétique — 12 mois", txt)
        self.assertIn("Facture électrique actuelle", txt)
        self.assertIn("Économies / an", txt)
        self.assertIn("Cashflow cumulé", txt)
        self.assertIn("Payback", txt)

    def test_commercial_garde_sa_carte_economies(self):
        txt = _visible(c_render.build_html(self.com))
        self.assertIn("Économies / an", txt)
