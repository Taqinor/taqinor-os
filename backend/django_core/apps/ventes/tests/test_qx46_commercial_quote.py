"""QX46 — Renderer COMMERCIAL (catégorie-aware) dédié.

Couvre la sélection (full/premium seulement ; jamais un autre mode), les blocs
CONDITIONNELS par catégorie (hôtel saisonnalité + éco-OTA, restaurant/froid
chaîne du froid, boulangerie cuisson nocturne, école fermeture estivale/injection,
bureau alignement horaires ; sans catégorie → générique), la garde rule #4
(prix_achat/marge jamais rendus) et le rendu 3 pages (WeasyPrint, CI/Docker).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qx46_commercial_quote -v 2
"""
import re
from decimal import Decimal

from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine.commercial import render, renderer, sample_data


class _Devis:
    def __init__(self, mode):
        self.mode_installation = mode


class TestCommercialSelection(SimpleTestCase):
    def test_full_commercial_selected(self):
        self.assertTrue(renderer.is_commercial(_Devis("commercial"), {"pdf_mode": "full"}))
        self.assertTrue(renderer.is_commercial(_Devis("commercial"), None))  # défaut full

    def test_onepage_commercial_falls_back(self):
        self.assertFalse(renderer.is_commercial(_Devis("commercial"), {"pdf_mode": "onepage"}))

    def test_other_modes_not_commercial(self):
        self.assertFalse(renderer.is_commercial(_Devis("residentiel"), {"pdf_mode": "full"}))
        self.assertFalse(renderer.is_commercial(_Devis("industriel"), {"pdf_mode": "full"}))
        self.assertFalse(renderer.is_commercial(_Devis("agricole"), {"pdf_mode": "full"}))


class TestCommercialContent(SimpleTestCase):
    def _html(self, category="hotel"):
        return render.build_html(renderer._augment(sample_data.build(category)))

    def test_three_pages(self):
        self.assertEqual(self._html().count('class="page"'), 3)

    def test_cover_category_aware(self):
        html = self._html("hotel")
        self.assertIn("Hôtel", html)         # label catégorie
        self.assertIn("Équipements", html)   # P2
        self.assertIn("Total TTC", html)     # totaux

    def test_rule4_no_buy_price_or_margin(self):
        html = self._html("hotel")
        self.assertNotIn("prix_achat", html.lower())
        self.assertNotIn("marge", html.lower())

    def test_no_peak_promise_without_battery(self):
        html = self._html("hotel")
        self.assertIn("stockage", html.lower())
        self.assertIn("pointe", html.lower())


class TestCommercialCategoryBlocks(SimpleTestCase):
    """Chaque catégorie déclenche SON bloc conditionnel P2."""

    def _html(self, category):
        return render.build_html(renderer._augment(sample_data.build(category)))

    def test_hotel_seasonality_and_ota(self):
        html = self._html("hotel")
        self.assertIn("Saisonnalité hôtelière", html)
        self.assertIn("éco-OTA", html)

    def test_restaurant_cold_chain(self):
        self.assertIn("chaîne du froid", self._html("restaurant"))

    def test_froid_cold_chain(self):
        self.assertIn("chaîne du froid", self._html("froid"))

    def test_boulangerie_nocturnal_baking(self):
        html = self._html("boulangerie")
        self.assertIn("cuisson nocturne", html)
        self.assertIn("pas couverte", html)

    def test_ecole_summer_closure_injection(self):
        html = self._html("ecole")
        self.assertIn("Calendrier scolaire", html)
        self.assertIn("injection", html.lower())

    def test_bureau_hours_alignment(self):
        self.assertIn("Alignement horaires", self._html("bureau"))

    def test_no_category_generic_block(self):
        base = sample_data.build("hotel")
        base["etude"] = dict(base["etude"])
        base["etude"].pop("categorie_commerciale", None)
        html = render.build_html(renderer._augment(base))
        self.assertIn("profil de consommation", html)
        # les blocs spécifiques n'apparaissent pas
        self.assertNotIn("Saisonnalité hôtelière", html)


class TestCommercialUnsupported(SimpleTestCase):
    def test_no_priced_lines_unsupported(self):
        base = sample_data.build("hotel")
        base["all_items"] = [{"designation": "x", "quantite": 0}]
        with self.assertRaises(renderer.Unsupported):
            renderer._augment(base)


@tag("weasyprint")
class TestCommercialPageCount(SimpleTestCase):
    """Rendu PDF réel — exactement 3 pages A4 (WeasyPrint, CI/Docker)."""
    def test_three_pages(self):
        try:
            import weasyprint  # noqa: F401
        except Exception:  # pragma: no cover - skip where native libs absent
            self.skipTest("weasyprint native libs unavailable")
        from weasyprint import HTML
        for cat in sample_data.keys():
            data = renderer._augment(sample_data.build(cat))
            pdf = renderer.render_pdf_bytes(data)
            self.assertTrue(pdf[:4] == b"%PDF")
            doc = HTML(string=render.build_html(data)).render()
            self.assertEqual(len(doc.pages), 3, f"{cat} not 3 pages")


class TestQjr615LignesEnHT(SimpleTestCase):
    """QJR615 — la page équipements imprime P.U. HT / Total HT par ligne, et la
    somme des Total HT imprimés est le Sous-total HT imprimé, au centime."""

    def _page2(self):
        data = sample_data.build("hotel")
        data["all_items"] = [
            {"designation": "Panneau Jinko 710W", "marque": "Jinko",
             "quantite": 3, "prix_unit_ht": 1150.37, "prix_unit_ttc": 1265.41,
             "taux_tva": 10},
            {"designation": "Onduleur Huawei 100kW", "marque": "Huawei",
             "quantite": 1, "prix_unit_ht": 60000.20, "prix_unit_ttc": 72000.24,
             "taux_tva": 20},
        ]
        ht = Decimal("3451.11") + Decimal("60000.20")
        tva = Decimal("345.11") + Decimal("12000.04")
        data["totaux_all"] = {"ht_brut": float(ht), "remise": 0,
                              "ht_net": float(ht), "tva": float(tva),
                              "ttc": float(ht + tva)}
        data["display_total"] = float(ht + tva)
        html = render.build_html(renderer._augment(data))
        return html.split('class="page"')[2]

    @staticmethod
    def _dec(txt):
        return Decimal(re.sub(r"[^0-9,]", "", txt).replace(",", "."))

    def test_en_tetes_ht(self):
        p2 = self._page2()
        self.assertIn("P.U. HT", p2)
        self.assertIn("Total HT", p2)
        self.assertNotIn("P.U. TTC", p2)

    def test_somme_des_lignes_egale_sous_total_ht(self):
        p2 = self._page2()
        totaux = re.findall(r'<td class="c2-t">([^<]*)</td>', p2)
        self.assertEqual(len(totaux), 2, totaux)
        m = re.search(r'Sous-total HT<span[^>]*></span></td><td[^>]*>'
                      r'([^<]*) MAD</td>', p2)
        self.assertIsNotNone(m)
        self.assertEqual(sum(self._dec(t) for t in totaux), self._dec(m.group(1)))
        self.assertEqual(self._dec(m.group(1)), Decimal("63451.31"))

    def test_taux_de_tva_par_ligne(self):
        p2 = self._page2()
        taux = re.findall(r'<td class="c2-v">([^<]*)</td>', p2)
        self.assertEqual([re.sub(r"\D", "", t) for t in taux], ["10", "20"])
