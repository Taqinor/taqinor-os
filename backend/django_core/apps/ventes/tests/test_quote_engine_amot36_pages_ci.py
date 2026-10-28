"""AMOT36 (C-AMOT-046, volet C&I) — le PDF C&I tient son contrat de pages
(commerce 3, usine 4) : ``pdf_adaptatif`` mesure TOUTES les pages, la liste
variable des conditions est tronquée avec renvoi déclaré (« Suite des
conditions : proposition en ligne ») avant tout refus, et aucun repli legacy
n'est servi à un devis C&I dont le contrat de pages est intenable.

WeasyPrint + PyMuPDF RÉELS (sautés sans eux). Test-du-test : remettre
``deborde(doc.pages[index_page])`` dans ``pdf_adaptatif`` ⇒
``test_contrat_de_pages`` échoue (puces sous le pied, ou page de trop).
"""
import copy

from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine.ci import blocs
from apps.ventes.quote_engine.commercial import equip
from apps.ventes.quote_engine.commercial import renderer as c_renderer
from apps.ventes.quote_engine.commercial import sample_data as c_sample
from apps.ventes.quote_engine.industriel import renderer as i_renderer
from apps.ventes.quote_engine.industriel import sample_data as i_sample

GABARITS = (("commercial", c_sample, c_renderer, 3),
            ("industriel", i_sample, i_renderer, 4))
_SUITE = "Suite des conditions : proposition en ligne"


def _puces(n):
    return [(f"Condition contractuelle n° {i:02d} — " + "texte " * 40)[:220]
            for i in range(1, n + 1)]


def _avec_option_batterie(data):
    """Le panier « avec » d'un C&I à deux options (forme ``build_quote_data``)
    et l'option chiffrée par le moteur (``etude_ci.option_avec``)."""
    data["option_servie"] = "sans"
    data["option_batterie"] = {
        "lignes": [dict(it) for it in data["all_items"] if "Onduleur" not in it["designation"]] + [
            {"designation": "Onduleur hybride Deye SUN-20K-SG05LP3", "quantite": 2,
             "prix_unit_ht": 40000.0, "taux_tva": 20},
            {"designation": "Batterie Dyness 10 kWh", "quantite": 10,
             "prix_unit_ht": 25000.0, "taux_tva": 20}],
        "totaux": {"ht_net": 803333, "tva": 160667, "ttc": 964000},
        "valeur_chiffree": None, "motif": "valeur non chiffrée"}
    etude = data.setdefault("etude", {})
    etude["etude_ci"] = dict(etude.get("etude_ci") or {}, option_avec={
        "economie_annuelle_mad": 120000.0, "retour_simple_ans": 8.4,
        "bilan": {"batterie": {"capacite_utile_kwh": 92.2, "restitue_kwh_an": 31000}}})
    return data


class OptionAvecValeurTests(SimpleTestCase):
    def test_valeur_chiffree_par_le_moteur(self):
        from apps.ventes.quote_engine.ci.mentions import valeur_option_avec
        from apps.ventes.quote_engine.commercial import sample_data
        valeur = valeur_option_avec(_avec_option_batterie(sample_data.build()))
        # CPDF2 — le retour SERVI par l'étude (flux 25 ans), jamais le
        # quotient HT ÷ économie (6,7 ans ici) recalculé par le PDF.
        self.assertEqual(valeur["retour_simple_ans"], 8.4)
        self.assertIn("92,2 kWh utiles", valeur["textes"]["fr"])
        self.assertIn("92.2 kWh usable", valeur["textes"]["en"])

    def test_sans_option_avec_rien(self):
        from apps.ventes.quote_engine.ci.mentions import valeur_option_avec
        from apps.ventes.quote_engine.commercial import sample_data
        self.assertIsNone(valeur_option_avec(sample_data.build()))
        self.assertEqual(blocs.bloc_option_avec(sample_data.build(), None, str, ("",) * 4), "")


class TroncatureDeclareeTests(SimpleTestCase):
    def test_puces_tronquees_avec_renvoi(self):
        d = {"cgv_ci": _puces(10), "_cgv_max": 3}
        puces = blocs.puces_conditions(d)
        self.assertEqual(len(puces), 4)
        self.assertEqual(puces[-1], _SUITE)

    def test_sans_troncature_inchange(self):
        self.assertEqual(blocs.puces_conditions({"cgv_ci": _puces(5)}),
                         _puces(5))


@tag("pdf")
class PagesCiTests(SimpleTestCase):
    def setUp(self):
        try:
            __import__('fitz')
            __import__('weasyprint')
        except Exception:  # pragma: no cover — libs natives absentes
            self.skipTest("weasyprint / PyMuPDF indisponible")

    def _rendre(self, sample, renderer, n):
        import fitz
        data = copy.deepcopy(sample.build())
        data["cgv_ci"] = _puces(n)
        pdf = renderer.render_pdf_bytes(data)
        return fitz.open(stream=pdf, filetype="pdf")

    def test_contrat_de_pages(self):
        for nom, sample, renderer, pages in GABARITS:
            for n in (15, 18, 19, 40):
                with self.subTest(gabarit=nom, puces=n):
                    doc = self._rendre(sample, renderer, n)
                    self.assertEqual(len(doc), pages)
                    for page in doc:
                        pied = page.rect.height * (1 - equip.PIED_MM / 297.0)
                        for bloc in page.get_text("blocks"):
                            x0, y0, x1, y1 = bloc[:4]
                            # Aucun bloc de texte ne CHEVAUCHE le haut du pied.
                            self.assertFalse(y0 < pied - 1 and y1 > pied + 1,
                                             (nom, n, bloc[4][:60]))

    def test_option_avec_batterie_tient_le_contrat_de_pages(self):
        """Fondateur 26/10/2026 — un C&I à deux options imprime l'option
        « avec batterie » (équipements propres, totaux, économie et retour du
        moteur) sans page de plus."""
        import fitz
        for nom, sample, renderer, pages in GABARITS:
            with self.subTest(gabarit=nom):
                data = _avec_option_batterie(copy.deepcopy(sample.build()))
                data["cgv_ci"] = _puces(15)
                doc = fitz.open(stream=renderer.render_pdf_bytes(data), filetype="pdf")
                self.assertEqual(len(doc), pages)
                texte = " ".join(page.get_text() for page in doc)
                self.assertIn("PROPRES À CETTE OPTION", texte)
                self.assertIn("964 000,00 MAD", texte)
                self.assertIn("Batterie Dyness 10 kWh", texte)
                self.assertIn("Retour sur investissement", texte)

    def test_quarante_puces_renvoi_imprime(self):
        for nom, sample, renderer, _pages in GABARITS:
            with self.subTest(gabarit=nom):
                doc = self._rendre(sample, renderer, 40)
                texte = " ".join(page.get_text() for page in doc)
                self.assertIn("Suite des conditions", texte)
