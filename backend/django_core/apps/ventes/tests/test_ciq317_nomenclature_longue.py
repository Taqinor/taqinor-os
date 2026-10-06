"""CIQ317 — page équipements C&I : une longue nomenclature n'est jamais
coupée en silence.

WeasyPrint RÉEL (``@tag('pdf')``) : densité adaptative par paliers mesurée
sur le rendu ; au-delà du dernier palier, ``Unsupported('nomenclature trop
longue')`` (le dispatch prend alors le repli NOMMÉ) — jamais une ligne, le
Total TTC ou une option perdue.
"""
import copy

from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine.commercial import equip
from apps.ventes.quote_engine.commercial import render as c_render
from apps.ventes.quote_engine.commercial import renderer as c_renderer
from apps.ventes.quote_engine.commercial import sample_data as c_sample
from apps.ventes.quote_engine.industriel import renderer as i_renderer
from apps.ventes.quote_engine.industriel import sample_data as i_sample

GABARITS = (
    ("commercial", c_sample, c_renderer, 3),
    ("industriel", i_sample, i_renderer, 4),
)


def _lignes(n):
    return [{"designation": f"Article de nomenclature n° {i:03d}",
             "marque": "Marque", "quantite": 2, "prix_unit_ht": 1000.0,
             "prix_unit_ttc": 1200.0, "taux_tva": 20}
            for i in range(1, n + 1)]


def _data(sample, n_lignes, n_options=0, note=""):
    data = copy.deepcopy(sample.build())
    lignes = _lignes(n_lignes)
    data["all_items"] = lignes
    ht = sum(li["quantite"] * li["prix_unit_ht"] for li in lignes)
    data["totaux_all"] = {"ht_brut": ht, "remise": 0, "ht_net": ht,
                          "tva": round(ht * 0.2, 2),
                          "ttc": round(ht * 1.2, 2)}
    data["display_total"] = round(ht * 1.2, 2)
    data["options_proposees"] = [
        {"id": i, "designation": f"Option proposée n° {i}", "marque": "",
         "quantite": 1, "taux_tva": 20, "prix_unit_ht": 500.0,
         "prix_unit_ttc": 600.0, "total_ht": 500.0, "total_ttc": 600.0}
        for i in range(1, n_options + 1)]
    if note:
        data["note_client"] = note
    return data


class DensiteCss(SimpleTestCase):

    def test_palier_zero_octet_identique(self):
        self.assertEqual(equip.css_densite(0), "")
        self.assertEqual(equip.css_densite(None), "")
        data = c_renderer._augment(c_sample.build())
        self.assertEqual(c_render.build_html(data),
                         c_render.build_html(dict(data, _palier_equip=0)))

    def test_paliers_reduisent_la_police(self):
        polices = [p[0] for p in equip.PALIERS_DENSITE[1:]]
        self.assertEqual(polices, sorted(polices, reverse=True))


@tag("pdf")
class NomenclatureLongue(SimpleTestCase):

    def setUp(self):
        try:
            import fitz  # noqa: F401
            import weasyprint  # noqa: F401
        except Exception:  # pragma: no cover - libs natives absentes
            self.skipTest("weasyprint / PyMuPDF indisponible")

    def test_quarante_lignes_six_options_une_note(self):
        import fitz
        for nom, sample, renderer, pages in GABARITS:
            with self.subTest(gabarit=nom):
                data = _data(sample, 40, 6,
                             note="Accès au toit par l'escalier de service.")
                pdf = renderer.render_pdf_bytes(data)
                doc = fitz.open(stream=pdf, filetype="pdf")
                self.assertEqual(len(doc), pages)
                page = doc[1]
                texte = page.get_text()
                pied = page.rect.height * (1 - 13.0 / 297.0)
                attendus = (["Article de nomenclature n° 040", "Total TTC"]
                            + [f"Option proposée n° {i}" for i in range(1, 7)])
                for attendu in attendus:
                    self.assertIn(attendu, texte, attendu)
                    zones = page.search_for(attendu)
                    self.assertTrue(zones, attendu)
                    self.assertLess(zones[0].y1, pied, attendu)

    def test_cent_vingt_lignes_repli_nomme(self):
        for nom, sample, renderer, _pages in GABARITS:
            with self.subTest(gabarit=nom):
                with self.assertRaisesMessage(renderer.Unsupported,
                                              "nomenclature trop longue"):
                    renderer.render_pdf_bytes(_data(sample, 120))
