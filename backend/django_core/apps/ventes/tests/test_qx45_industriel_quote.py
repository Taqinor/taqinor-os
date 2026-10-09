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
    finance, render, renderer, sample_data)


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

    def test_include_etude_reste_premium(self):
        """CIQ340 — « Inclure l'étude » ne bascule plus vers le legacy : le
        document industriel est toujours le premium 4 pages."""
        self.assertTrue(renderer.is_industrial(
            _Devis("industriel"), {"pdf_mode": "full", "include_etude": 1}))
        self.assertFalse(renderer.is_industrial(
            _Devis("industriel"), {"pdf_mode": "onepage", "include_etude": 1}))

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
        # CIQ342 — la page finance lit ``synthese_ci['argent']`` (moteur C&I).
        base = sample_data.build()
        base["economie_ci"] = sample_data.economie_ci()
        servie = render.build_html(renderer._augment(base))
        self.assertIn("Cumul net de l'investissement", servie)   # P3
        self.assertIn("TRI sur 25 ans", servie)                  # P3
        self.assertIn("ISO 50001", self.html)               # P4
        # CIQ344 — CBAM seulement pour un exportateur UE déclaré de ciment
        # ou d'engrais : la fixture n'en déclare pas.
        self.assertNotIn("CBAM", self.html)                 # P4
        self.assertIn("Bilan carbone de votre électricité", self.html)
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
        # CIQ129 — l'injection est la revente CALCULÉE du moteur C&I
        # (``economie_ci.revente``), plus une clé d'étude écran v1.
        base = sample_data.build()
        base["economie_ci"] = sample_data.economie_ci()
        # AMOT40 — le PDF imprime les mentions SERVIES par ``revente_ci`` : la
        # revente porte la liste que le moteur sert réellement
        # (``economie_ci.revente_ci``, MENTION_82_21 en tête), pas les
        # libellés abrégés de l'exemple du contrat.
        from apps.ventes import economie_ci as eco
        from apps.ventes.quote_engine import constants_82_21 as c8221
        base["economie_ci"]["revente"]["mentions"] = [
            c8221.MENTION_82_21, eco.MENTION_NON_GARANTI,
            eco.MENTION_SECOND_COMPTEUR, eco.MENTION_TSS,
            eco.MENTION_TARIF_ARRETE, c8221.MENTION_ART13]
        html = render.build_html(renderer._augment(base))
        self.assertIn("surplus injecté", html)
        self.assertIn("82-21", html)
        # CIQ305 — la mention est ``MENTION_82_21`` (D-CIQ-4), lue, jamais
        # recopiée : plus de « net des frais réseau » ni « plafond en révision ».
        self.assertIn("plafond légal 20 %", html)
        self.assertIn("décision 04/26", html)
        self.assertNotIn("net des frais réseau", html)
        self.assertNotIn("plafond en révision", html)


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


class TestTriServi(SimpleTestCase):
    """CIQ342 — plus de solveur privé (``irr_flat``/``irr_series``
    supprimés) : le TRI imprimé est celui que sert le moteur C&I
    (``synthese_ci.argent.indicateurs``), sur son horizon."""

    def test_positive_irr(self):
        base = sample_data.build()
        base["economie_ci"] = sample_data.economie_ci()
        html = render.build_html(renderer._augment(base))
        tri = base["economie_ci"]["indicateurs"]["tri_pct"]
        self.assertIn(f"{tri:.1f}".replace(".", ","), html)
        self.assertIn("TRI sur 25 ans", html)
        self.assertFalse(hasattr(finance, "irr_flat"))
        self.assertFalse(hasattr(finance, "irr_series"))

    def test_degenerate_returns_none(self):
        """Sans argent servi : aucun TRI imprimé, le motif à sa place."""
        html = render.build_html(renderer._augment(sample_data.build()))
        self.assertNotIn("TRI sur", html)
        self.assertIn("Rentabilité non chiffrée sur ce dossier", html)


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


@tag("pdf")
class TestCiq340IndustrielToujoursPremium(TestCase):
    """CIQ340 — par le dispatch RÉEL : un devis industriel demandé « avec
    l'étude » sort en 4 pages PREMIUM (le legacy n'est pas appelé) ; le
    une-page reste servi par le legacy, en 1 page."""

    LIGNES = TestIndustrielDispatchEquipements.LIGNES
    ETUDE = {
        'kwc': 99.4, 'production_annuelle': 160000, 'conso_annuelle': 300000,
        'taux_autoconso': 92, 'taux_couverture': 53,
        'prod_mensuelle': [13333] * 12, 'conso_mensuelle': [25000] * 12,
    }

    def _rendu(self, pdf_options):
        import fitz
        from apps.ventes.quote_engine import builder
        from apps.ventes.quote_engine import generate_devis_premium as moteur
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_devis, make_user)
        company = make_company()
        devis = make_devis(company, make_user(company), make_client(company),
                           self.LIGNES, reference='DEV-CIQ340-IND',
                           etude_params=dict(self.ETUDE))
        devis.mode_installation = 'industriel'
        devis.save(update_fields=['mode_installation'])
        with patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket'), \
                patch('apps.ventes.utils.pdf._upload_pdf') as up, \
                patch.object(moteur, 'generate_premium_pdf',
                             wraps=moteur.generate_premium_pdf) as legacy:
            builder.generate_premium_devis_pdf(devis.id,
                                               pdf_options=pdf_options)
        doc = fitz.open(stream=up.call_args[0][0], filetype='pdf')
        return len(doc), legacy.called

    def test_avec_etude_quatre_pages_premium(self):
        pages, legacy = self._rendu({'pdf_mode': 'full', 'include_etude': 1})
        self.assertFalse(legacy)
        self.assertEqual(pages, 4)

    def test_une_page_reste_legacy(self):
        pages, legacy = self._rendu({'pdf_mode': 'onepage'})
        self.assertTrue(legacy)
        self.assertEqual(pages, 1)
