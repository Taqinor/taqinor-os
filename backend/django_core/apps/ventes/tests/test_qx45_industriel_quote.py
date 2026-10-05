"""QX45 — Renderer INDUSTRIEL (CFO) dédié.

Couvre la sélection (full/premium seulement, jamais one-page ; jamais un autre
mode), le contenu CFO (baseline, cashflow, payback, TRI, ISO 50001/CBAM,
garanties, signature), le TRI (vrai calcul actuariel), la garde rule #4
(prix_achat/marge jamais rendus) et le rendu 4 pages — couverture, équipements +
chaîne de totaux, cashflow, confiance (QJR620 / D-QJR5-12 ; WeasyPrint, CI/Docker).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qx45_industriel_quote -v 2
"""
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, tag

from apps.ventes.quote_engine.industriel import (
    render, renderer, sample_data)
from apps.ventes.quote_engine.industriel.finance import irr_flat


class _Devis:
    """Stand-in minimal pour tester la sélection sans l'ORM."""
    def __init__(self, mode):
        self.mode_installation = mode


class TestIndustrielSelection(SimpleTestCase):
    def test_full_industriel_selected(self):
        self.assertTrue(renderer.is_industrial(_Devis("industriel"), {"pdf_mode": "full"}))
        self.assertTrue(renderer.is_industrial(_Devis("industriel"), None))  # défaut full

    def test_onepage_industriel_falls_back(self):
        self.assertFalse(renderer.is_industrial(_Devis("industriel"), {"pdf_mode": "onepage"}))

    def test_other_modes_not_industriel(self):
        self.assertFalse(renderer.is_industrial(_Devis("residentiel"), {"pdf_mode": "full"}))
        self.assertFalse(renderer.is_industrial(_Devis("agricole"), {"pdf_mode": "full"}))
        self.assertFalse(renderer.is_industrial(_Devis("commercial"), {"pdf_mode": "full"}))


class TestIndustrielContent(SimpleTestCase):
    def setUp(self):
        self.data = renderer._augment(sample_data.build())
        self.html = render.build_html(self.data)

    def test_four_page_content_present(self):
        """QJR620 (D-QJR5-12) — couverture, équipements + chaîne de totaux,
        cashflow, confiance."""
        self.assertEqual(self.html.count('class="page"'), 4)
        self.assertIn("Sous-total HT", self.html)
        self.assertIn("Total TTC", self.html)

    def test_cfo_blocks_present(self):
        self.assertIn("Baseline énergétique", self.html)   # P1
        # CIQ301 — la page finance ne se remplit que d'une série SERVIE
        # (``synthese_ci.argent``, CIQ307), jamais du repli BT du builder.
        self.assertNotIn("Cashflow cumulé", self.html)
        servie = render.build_html(dict(self.data, **sample_data.serie_finance()))
        self.assertIn("Cashflow cumulé", servie)            # P2
        self.assertIn("TRI sur", servie)                    # P2
        self.assertIn("ISO 50001", self.html)               # P3
        self.assertIn("CBAM", self.html)                    # P3
        self.assertIn("Bon pour accord", self.html)         # P3 signature

    def test_autoconso_honesty_no_peak_promise(self):
        # jamais promettre la pointe sans batterie
        self.assertIn("autoconsommation", self.html.lower())
        self.assertIn("pointe", self.html.lower())

    def test_injection_omitted_without_data(self):
        # sans injection calculée (QX50), aucune ligne d'injection inventée.
        # QJR120 — la SONDE est la ligne elle-même (``i2-inj``) et son montant,
        # plus la chaîne « surplus injecté » : le bloc « Nos hypothèses » du
        # modèle de cashflow emploie légitimement ces mots pour DIRE que le
        # surplus n'est PAS rémunéré (loi 82-21).
        self.assertNotIn('class="i2-inj"', self.html)
        self.assertNotIn("MAD/an</b> — surplus injecté", self.html)

    def test_rule4_no_buy_price_or_margin(self):
        # RULE #4 / prix_achat jamais client-facing
        self.assertNotIn("prix_achat", self.html)
        self.assertNotIn("prix_achat", self.html.lower())
        self.assertNotIn("marge", self.html.lower())


class TestIndustrielInjectionWhenPresent(SimpleTestCase):
    def test_injection_line_rendered_with_mention(self):
        base = sample_data.build()
        base["etude"] = dict(base["etude"])
        base["etude"]["injection_dh_an"] = 30000
        base["etude"]["injection_kwh_an"] = 45000
        html = render.build_html(renderer._augment(base))
        self.assertIn("surplus injecté", html)
        self.assertIn("82-21", html)
        self.assertIn("plafond 20 %", html)
        self.assertIn("ANRE 03/2026", html)


class TestIndustrielUnsupported(SimpleTestCase):
    def test_no_priced_lines_unsupported(self):
        base = sample_data.build()
        base["all_items"] = [{"designation": "x", "quantite": 0}]
        with self.assertRaises(renderer.Unsupported):
            renderer._augment(base)

    def test_no_investment_unsupported(self):
        base = sample_data.build()
        base["display_total"] = 0
        base["totaux_all"] = {"ttc": 0}
        with self.assertRaises(renderer.Unsupported):
            renderer._augment(base)


class TestIrrFlat(SimpleTestCase):
    def test_positive_irr(self):
        # 1,75 M investis, 420 k/an sur 15 ans → TRI ~22-24 %
        tri = irr_flat(1_750_000, 420_000, 15)
        self.assertIsNotNone(tri)
        self.assertGreater(tri, 15)
        self.assertLess(tri, 30)

    def test_degenerate_returns_none(self):
        self.assertIsNone(irr_flat(0, 420_000))
        self.assertIsNone(irr_flat(1_750_000, 0))
        self.assertIsNone(irr_flat(1_750_000, 420_000, 0))


@tag("weasyprint")
class TestIndustrielPageCount(SimpleTestCase):
    """Rendu PDF réel — exactement 4 pages A4 (QJR620 ; WeasyPrint, CI/Docker)."""
    def test_four_pages(self):
        try:
            import weasyprint  # noqa: F401
        except Exception:  # pragma: no cover - skip where native libs absent
            self.skipTest("weasyprint native libs unavailable")
        data = renderer._augment(sample_data.build())
        pdf = renderer.render_pdf_bytes(data)
        self.assertTrue(pdf[:4] == b"%PDF")
        from weasyprint import HTML
        doc = HTML(string=render.build_html(data)).render()
        self.assertEqual(len(doc.pages), 4)


@tag("pdf")
class TestIndustrielDispatchEquipements(TestCase):
    """QJR620 — par le dispatch RÉEL ``generate_premium_devis_pdf`` (upload
    mocké) : chaque désignation, 'Sous-total HT' et 'Total TTC' sont dans le
    document industriel premium, qui fait 4 pages."""

    LIGNES = [
        ('Onduleur réseau Huawei 100kW', '1', '90000'),
        ('Panneau mono 710W', '140', '1150'),
        ('Structures acier', '140', '400'),
    ]

    def test_trois_lignes_quatre_pages_chaine_de_totaux(self):
        import fitz
        from apps.ventes.quote_engine import builder
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_devis, make_user)
        company = make_company()
        devis = make_devis(company, make_user(company), make_client(company),
                           self.LIGNES, reference='DEV-QJR620-IND')
        devis.mode_installation = 'industriel'
        devis.save(update_fields=['mode_installation'])
        self.assertTrue(renderer.is_industrial(devis, {'pdf_mode': 'full'}))
        captures = []
        _vrai_build_html = render.build_html

        def _capture(data):
            html = _vrai_build_html(data)
            captures.append(html)
            return html

        with patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket'), \
                patch('apps.ventes.utils.pdf._upload_pdf') as up, \
                patch.object(render, 'build_html', side_effect=_capture):
            builder.generate_premium_devis_pdf(
                devis.id, pdf_options={'pdf_mode': 'full'})
        self.assertEqual(len(captures), 1, "renderer industriel non servi")
        html = captures[0]
        for desig, _q, _pu in self.LIGNES:
            self.assertIn(desig, html)
        self.assertIn('Sous-total HT', html)
        self.assertIn('Total TTC', html)
        doc = fitz.open(stream=up.call_args[0][0], filetype='pdf')
        self.assertEqual(len(doc), 4)
