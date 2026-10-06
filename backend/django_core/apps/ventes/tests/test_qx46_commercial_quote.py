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

from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, tag

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

    def test_include_etude_goes_to_legacy(self):
        """QJR621 — la demande « avec l'étude » n'est pas servie par le
        renderer commercial (qui n'a pas de page d'étude)."""
        self.assertFalse(renderer.is_commercial(
            _Devis("commercial"), {"pdf_mode": "full", "include_etude": 1}))
        self.assertTrue(renderer.is_commercial(
            _Devis("commercial"), {"pdf_mode": "full", "include_etude": 0}))

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
    """Chaque catégorie déclenche SON bloc conditionnel P2.

    CIQ330 — le contenu vient de la table trilingue ``ci/categories.py``
    (réponses DÉCLARÉES) : plus de « Saisonnalité hôtelière », d'« éco-OTA »,
    d'« Alignement horaires » ni de « surplus injectable » en BT."""

    def _html(self, category):
        return render.build_html(renderer._augment(sample_data.build(category)))

    def test_hotel_reponses_declarees_sans_ota(self):
        html = self._html("hotel")
        self.assertIn("Votre hôtel", html)
        self.assertIn("48 chambres, occupation 62 %, piscine chauffée", html)
        self.assertNotIn("éco-OTA", html)
        self.assertNotIn("alignement idéal", html)

    def test_restaurant_reponses_traduites(self):
        html = self._html("restaurant")
        self.assertIn("Votre restaurant", html)
        self.assertIn("service continu, cuisson au gaz", html)

    def test_froid_reponses(self):
        html = self._html("froid")
        self.assertIn("Votre entrepôt froid", html)
        self.assertIn("Consigne -18 °C", html)

    def test_boulangerie_nocturnal_baking(self):
        html = self._html("boulangerie")
        self.assertIn("cuisson nocturne", html)
        self.assertIn("pas couverte", html)
        self.assertIn("Four électrique", html)

    def test_ecole_sans_promesse_injection(self):
        html = self._html("ecole")
        self.assertIn("Votre école", html)
        self.assertNotIn("injectable", html)
        self.assertNotIn("valorisable", html)
        self.assertNotIn("prévisible", html)

    def test_bureau_sans_promesse_export(self):
        html = self._html("bureau")
        self.assertIn("Vos bureaux", html)
        self.assertNotIn("quasi-totalité", html)
        self.assertNotIn("peu d'export", html)

    def test_no_category_generic_block(self):
        base = sample_data.build("hotel")
        base["etude"] = dict(base["etude"])
        base["etude"].pop("categorie_commerciale", None)
        html = render.build_html(renderer._augment(base))
        self.assertIn("Votre établissement", html)
        self.assertIn("Autre commerce", html)
        # les blocs spécifiques n'apparaissent pas
        self.assertNotIn("Votre hôtel", html)


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


@tag('pdf')  # rendu PDF réel (WeasyPrint) — lourd → palier release-verify
class TestQjr621CommercialAvecEtude(TestCase):
    """QJR621 — un devis commercial demandé « avec l'étude » sort en 4 pages
    avec la page d'étude (moteur legacy), au lieu des 3 pages premium sans
    étude ; sans ``include_etude``, le rendu commercial premium est inchangé."""

    LIGNES = [
        ('Onduleur réseau Huawei 50kW', '1', '42000'),
        ('Panneau mono 710W', '70', '1150'),
        ('Structures acier', '70', '400'),
        ('Installation', '1', '30000'),
    ]
    ETUDE = {
        'kwc': 49.7, 'production_annuelle': 79520, 'conso_annuelle': 120000,
        'taux_autoconso': 92, 'taux_couverture': 61,
        'economies_annuelles': 98000, 'payback': 3.4, 'prix_kwc': 6100,
        'prod_mensuelle': [6627] * 12, 'conso_mensuelle': [10000] * 12,
    }

    def setUp(self):
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_devis, make_user)
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, self.LIGNES,
            reference='DEV-QJR621-COM', etude_params=dict(self.ETUDE))
        self.devis.mode_installation = 'commercial'
        self.devis.save(update_fields=['mode_installation'])

    def _pages(self, pdf_options):
        import fitz
        from apps.ventes.quote_engine import builder

        with patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket'), \
                patch('apps.ventes.utils.pdf._upload_pdf') as up:
            builder.generate_premium_devis_pdf(self.devis.id,
                                               pdf_options=pdf_options)
        up.assert_called_once()
        pdf = up.call_args[0][0]
        self.assertEqual(pdf[:4], b'%PDF')
        doc = fitz.open(stream=pdf, filetype='pdf')
        return [page.get_text() for page in doc]

    def test_avec_etude_quatre_pages_et_page_d_etude(self):
        pages = self._pages({'pdf_mode': 'full', 'include_etude': 1})
        self.assertEqual(len(pages), 4)
        self.assertTrue(any('Taux de couverture' in p for p in pages),
                        "page d'étude absente")

    def test_sans_etude_rendu_commercial_premium_inchange(self):
        self.assertTrue(renderer.is_commercial(self.devis, {'pdf_mode': 'full'}))
        pages = self._pages({'pdf_mode': 'full'})
        self.assertEqual(len(pages), 3)
        self.assertFalse(any('Taux de couverture' in p for p in pages))
