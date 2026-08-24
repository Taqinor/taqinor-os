"""Moteur premium — gardes PAR FORMAT du document rendu.

Scindé de `test_quote_engine` le 2026-08-19 (module de 3 704 lignes,
146,9 s en CI : à lui seul le plancher du shardage backend).

Rendu WeasyPrint complet du moteur `generate_devis_premium` : nombre de
pages par format (premium / une-page / étude / annexe), chaîne des totaux
HT → remise → TVA → TTC, pompage, TVA par taux, options nettoyées. C'est
la part la plus lourde de la suite — chaque test rend un PDF.

Fixtures partagées : `apps.ventes.tests._quote_engine_common`.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_quote_engine_formats -v 2
"""

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, tag

from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)


@tag('pdf')  # rendu PDF premium complet — lourd → palier release-verify
class TestPremiumPdfRender(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    @patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket')
    @patch('apps.ventes.utils.pdf._upload_pdf')
    def test_generate_premium_pdf_produces_pdf_bytes(self, mock_upload, mock_bucket):
        from apps.ventes.quote_engine import generate_premium_devis_pdf
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '12', '1500'),
            ('Onduleur hybride', '1', '12000'),
            ('Structures acier', '12', '450'),
        ])
        key = generate_premium_devis_pdf(devis.id)

        # Stored under company-scoped key, persisted on the model.
        self.assertEqual(key, f'devis/{self.company.id}/{devis.reference}.pdf')
        devis.refresh_from_db()
        self.assertEqual(devis.fichier_pdf, key)

        # Real PDF bytes were uploaded.
        mock_upload.assert_called_once()
        pdf_bytes = mock_upload.call_args[0][0]
        self.assertTrue(pdf_bytes[:4] == b'%PDF')
        self.assertGreater(len(pdf_bytes), 5000)

    def test_premium_pdf_is_exactly_three_pages(self):
        """A full ~10-line quote must fit in exactly 3 pages (no overflow), and
        both page-2 charts must render at a visible size (no blank charts)."""
        from weasyprint import HTML
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G

        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Onduleur réseau 10kW', '1', '11700'),
            ('Onduleur hybride 5kW', '1', '24000'),
            ('Panneau mono 550W', '14', '1100'),
            ('Batterie 5 kWh', '1', '14000'),
            ('Structures acier', '14', '375'),
            ('Socles', '30', '67'),
            ('Accessoires', '1', '1667'),
            ('Tableau De Protection AC/DC', '1', '1667'),
            ('Installation', '1', '4000'),
            ('Transport', '1', '1000'),
        ], etude_params=DEUX_OPTIONS)
        data = build_quote_data(devis)

        # Capture the generated HTML without writing a file.
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_three_page_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig

        doc = HTML(string=cap['html']).render()
        self.assertEqual(
            len(doc.pages), 3,
            f'premium quote PDF must be exactly 3 pages, got {len(doc.pages)}',
        )

        # Both charts on page 2 must have a real (non-zero) rendered box.
        def _walk(box):
            yield box
            for child in (getattr(box, 'children', None) or []):
                yield from _walk(child)

        charts = [
            b for b in _walk(doc.pages[1]._page_box)
            if 'Replaced' in type(b).__name__ and b.height > 100 and b.width > 100
        ]
        self.assertGreaterEqual(
            len(charts), 2,
            'both page-2 charts must render at a visible size (not blank)',
        )


class TestPdfFormats(TestCase):
    """Per-format page-count guardrails (replaces the old single '3 pages'
    rule): the premium format renders exactly 3 pages, the one-page format
    exactly 1, and the modifiers (monthly chart off, devis final) keep the
    premium at 3 pages."""

    FULL_LINES = [
        ('Onduleur réseau 10kW', '1', '11700'),
        ('Onduleur hybride 5kW', '1', '24000'),
        ('Panneau mono 550W', '14', '1100'),
        ('Batterie 5 kWh', '1', '14000'),
        ('Structures acier', '14', '375'),
        ('Socles', '30', '67'),
        ('Accessoires', '1', '1667'),
        ('Tableau De Protection AC/DC', '1', '1667'),
        ('Installation', '1', '4000'),
        ('Transport', '1', '1000'),
    ]

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        # PV86 — document à DEUX options : le devis le déclare (ce que le
        # générateur persiste toujours). Rendu identique à l'historique.
        self.devis = make_devis(
            self.company, self.user, self.client_obj, self.FULL_LINES,
            etude_params=DEUX_OPTIONS)

    def _render(self, pdf_options=None, devis=None):
        from weasyprint import HTML
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G

        data = build_quote_data(devis or self.devis, pdf_options)
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_format_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return cap['html'], HTML(string=cap['html']).render()

    @staticmethod
    def _charts_on_page(page):
        def _walk(box):
            yield box
            for child in (getattr(box, 'children', None) or []):
                yield from _walk(child)
        return [
            b for b in _walk(page._page_box)
            if 'Replaced' in type(b).__name__ and b.height > 100 and b.width > 100
        ]

    def test_premium_default_renders_three_pages(self):
        html, doc = self._render()
        self.assertEqual(len(doc.pages), 3)
        # default = no payment/RIB block
        self.assertNotIn('SGMBMAMCXXX', html)

    def test_onepage_format_renders_exactly_one_page(self):
        html, doc = self._render({'pdf_mode': 'onepage'})
        self.assertEqual(
            len(doc.pages), 1,
            f'one-page quote must render exactly 1 page, got {len(doc.pages)}',
        )
        # the product list is there (designations from the quote lines)
        self.assertIn('Panneau mono 550W', html)

    def test_devis_final_keeps_three_pages_with_rib_and_payment(self):
        html, doc = self._render({
            'devis_final': True,
            'payment_mode': 'custom',
            'custom_acompte': 12000,
        })
        self.assertEqual(len(doc.pages), 3)
        self.assertIn('SGMBMAMCXXX', html)  # RIB / BIC block present

    def test_monthly_chart_toggle_keeps_three_pages(self):
        _, doc_with = self._render({'show_monthly': True})
        _, doc_without = self._render({'show_monthly': False})
        self.assertEqual(len(doc_with.pages), 3)
        self.assertEqual(len(doc_without.pages), 3)
        # page 2 loses exactly one chart when the monthly chart is off
        charts_with = len(self._charts_on_page(doc_with.pages[1]))
        charts_without = len(self._charts_on_page(doc_without.pages[1]))
        self.assertEqual(charts_with - charts_without, 1)

    def test_onepage_brand_column_filled_from_product_names(self):
        """The one-page Marque column shows the product brand (extracted from
        the designation), and stays empty for unbranded items — like the
        simulator's badge column."""
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Onduleur hybride Deye 5kW', '1', '14166.67'),
            ('Batterie Dyness 10 kWh', '1', '25000'),
            ('Panneau Canadien Solar 710W', '10', '1166.67'),
            ('Socles béton', '20', '66.67'),
        ], reference='DEV-QE-MARQUE')
        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
        marques = {it['designation']: it['marque'] for it in data['all_items']}
        self.assertEqual(marques['Onduleur hybride Deye 5kW'], 'Deye')
        self.assertEqual(marques['Batterie Dyness 10 kWh'], 'Dyness')
        self.assertEqual(marques['Panneau Canadien Solar 710W'], 'Canadien Solar')
        self.assertEqual(marques['Socles béton'], '')

    def test_ht_lines_and_visible_discount(self):
        """Per-line HT consistent with stored TTC; explicit Remise line with
        percentage and negative amount; HT → TVA → TTC chain rendered."""
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj,
                           self.FULL_LINES, remise_globale='8',
                           reference='DEV-QE-HT', etude_params=DEUX_OPTIONS)
        data = build_quote_data(devis)
        for it in data['sans_items'] + data['avec_items']:
            self.assertAlmostEqual(
                it['prix_unit_ht'] * 1.2, it['prix_unit_ttc'], places=1)
        html, doc = self._render(devis=devis)
        self.assertEqual(len(doc.pages), 3)
        self.assertIn('Sous-total HT', html)
        self.assertIn('Remise (8', html)      # ligne remise explicite
        self.assertIn('TVA (20', html)
        self.assertIn('P.U. HT', html)
        # one-page : même chaîne de totaux
        html1, doc1 = self._render({'pdf_mode': 'onepage'}, devis=devis)
        self.assertEqual(len(doc1.pages), 1)
        self.assertIn('Sous-total HT', html1)
        self.assertIn('Remise (8', html1)

    def test_etude_page_renders_four_pages_with_data_three_without(self):
        """include_etude adds the étude page (4 pages) only when the quote
        carries étude data; degrades gracefully to 3 pages otherwise."""
        self.devis.mode_installation = 'industriel'
        self.devis.etude_params = {
            **DEUX_OPTIONS,   # PV86 — l'alternative reste DÉCLARÉE
            'kwc': 9.94, 'production_annuelle': 12486, 'conso_annuelle': 120000,
            'taux_autoconso': 100, 'taux_couverture': 10.4,
            'economies_annuelles': 21851, 'payback': 3.0, 'prix_kwc': 6543,
            'prod_mensuelle': [1040] * 12, 'conso_mensuelle': [10000] * 12,
        }
        self.devis.save()
        html, doc = self._render({'include_etude': True})
        self.assertEqual(len(doc.pages), 4)
        self.assertIn('autoconsommation', html)
        self.assertIn('Taux de couverture', html)
        # Sans données d'étude → 3 pages, pas d'erreur
        self.devis.etude_params = None
        self.devis.save(update_fields=['etude_params'])
        _, doc2 = self._render({'include_etude': True})
        self.assertEqual(len(doc2.pages), 3)

    # ── PV46 — page « Annexe technique » (défaut OFF) ────────────────────────
    _ELECTRICAL_DESIGN = {
        'chaines': [
            {'pan': 1, 'mppt': 1, 'nb_modules': 7, 'vmp_froid_v': 268.0,
             'voc_froid_v': 327.2, 'vmp_chaud_v': 212.8, 'conforme': True},
            {'pan': 1, 'mppt': 2, 'nb_modules': 7, 'vmp_froid_v': 268.0,
             'voc_froid_v': 327.2, 'vmp_chaud_v': 212.8, 'conforme': True},
        ],
        'conformite': {'conforme': True, 'bloquants': [], 'alertes': []},
        'ratio_dc_ac': 1.18, 'ratio_ac_dc': 0.847,
        'protections': [
            {'repere': 'QAC1', 'designation': 'Disjoncteur AC général',
             'calibre': '32 A', 'quantite': 1},
        ],
        'cables': [
            {'liaison': 'Liaison DC', 'longueur_m': 40.0,
             'section_mm2': 6.0, 'chute_pct': 0.62},
        ],
        'bom': [
            {'designation': 'Câble solaire H1Z2Z2-K 6,0 mm²', 'quantite': 80.0,
             'spec': 'chute de tension 0,62 %'},
            {'designation': 'QAC1 — Disjoncteur AC général', 'quantite': 1,
             'spec': '32 A ; NF C 15-100 §433'},
        ],
        'note': ["Fenêtre de tension entre -5 °C et 70 °C"],
        'parametres': {'dc_m': 40.0, 'ac_m': 15.0, 'phases': 3,
                       'regime': 'TT'},
    }

    def test_sans_etude_electrique_le_pdf_est_celui_d_hier(self):
        """Aucune conception ⇒ aucune clé nouvelle, aucune page nouvelle."""
        from apps.ventes.quote_engine.builder import build_quote_data

        self.devis.electrical_design = None
        self.devis.save(update_fields=['electrical_design'])
        data = build_quote_data(self.devis)
        for clef in ('include_annexe_technique', 'electrical_design',
                     'sld_svg'):
            self.assertNotIn(clef, data)
        _, doc = self._render()
        self.assertEqual(len(doc.pages), 3)

    def test_l_annexe_est_automatique_des_qu_une_etude_existe(self):
        """PVSLD — l'annexe était INATTEIGNABLE pour un client.

        `/proposal`, le document public et le PDF signé appellent tous
        ``clean_pdf_options({})`` : avec un défaut ``False``, la seule page qui
        porte le schéma unifilaire ne pouvait sortir que si un agent cochait la
        case. Le défaut est donc AUTO — présente dès que l'étude existe.
        """
        from apps.ventes.quote_engine.builder import (
            DEFAULT_PDF_OPTIONS, build_quote_data, clean_pdf_options)

        # Tri-état : ``None`` = auto (ni un « oui » ni un « non » figés).
        self.assertIsNone(DEFAULT_PDF_OPTIONS['include_annexe_technique'])
        self.assertIsNone(clean_pdf_options({})['include_annexe_technique'])

        self.devis.electrical_design = self._ELECTRICAL_DESIGN
        self.devis.save(update_fields=['electrical_design'])
        data = build_quote_data(self.devis)
        self.assertTrue(data['include_annexe_technique'])
        self.assertEqual(data['electrical_design'], self._ELECTRICAL_DESIGN)
        html, doc = self._render()
        self.assertEqual(len(doc.pages), 4)
        self.assertIn('Annexe technique', html)

    def test_un_refus_explicite_reste_souverain(self):
        """L'opt-out marche toujours : ``False`` explicite ⇒ 3 pages."""
        from apps.ventes.quote_engine.builder import build_quote_data

        self.devis.electrical_design = self._ELECTRICAL_DESIGN
        self.devis.save(update_fields=['electrical_design'])
        data = build_quote_data(self.devis,
                                {'include_annexe_technique': False})
        self.assertNotIn('include_annexe_technique', data)
        _, doc = self._render({'include_annexe_technique': False})
        self.assertEqual(len(doc.pages), 3)

    def _equiper_fiches_annexe(self):
        """PVFCH-ANNEXE — le schéma de l'annexe est celui du MOTEUR, jamais
        plus l'esquisse historique : il exige des fiches techniques COMPLÈTES
        (7 variables module + 7 onduleur). Ce helper les pose sur le panneau
        et l'onduleur du devis de la classe (valeurs de fixture plausibles,
        fenêtres larges — le sujet du test est la PAGE, pas le dimensionnement)."""
        from apps.stock.models import FicheTechnique
        panneau = onduleur = None
        for ligne in self.devis.lignes.all():
            nom = (ligne.designation or '').lower()
            if panneau is None and 'panneau' in nom:
                panneau = ligne.produit
            elif onduleur is None and 'onduleur' in nom:
                onduleur = ligne.produit
        FicheTechnique.objects.create(
            company=self.company, produit=panneau, type_fiche='module',
            pmax_wc=Decimal('550'), voc_v=Decimal('49.9'),
            vmp_v=Decimal('41.9'), isc_a=Decimal('14.0'),
            imp_a=Decimal('13.2'),
            temp_coeff_voc_pct_c=Decimal('-0.25'),
            temp_coeff_pmax_pct_c=Decimal('-0.29'))
        FicheTechnique.objects.create(
            company=self.company, produit=onduleur, type_fiche='onduleur',
            ond_ac_kw=Decimal('10'), ond_phases=3, ond_n_mppt=2,
            ond_mppt_v_min=Decimal('200.0'), ond_mppt_v_max=Decimal('950.0'),
            ond_v_max_abs=Decimal('1100.0'), ond_i_max_mppt_a=Decimal('26.0'))

    def test_annexe_technique_adds_a_fourth_page(self):
        self._equiper_fiches_annexe()
        self.devis.electrical_design = self._ELECTRICAL_DESIGN
        self.devis.save(update_fields=['electrical_design'])
        html, doc = self._render({'include_annexe_technique': True})
        self.assertEqual(len(doc.pages), 4)
        self.assertIn('Annexe technique', html)
        self.assertIn('Nomenclature électrique', html)
        self.assertIn('Disjoncteur AC général', html)
        self.assertIn('Schéma unifilaire', html)
        self.assertIn('<svg', html)
        self.assertIn('Page 4', html)   # la signature reste la DERNIÈRE page

    def test_annexe_sans_fiche_complete_n_imprime_plus_l_esquisse(self):
        """PVFCH-ANNEXE (21/08/2026) — étude rangée mais fiches INCOMPLÈTES
        (le cas des études d'avant le verrou PVFCH) : l'annexe sort avec sa
        nomenclature, mais SANS schéma — plus jamais l'esquisse à cinq blocs,
        qui ignorait l'étude et contredisait la page client."""
        self.devis.electrical_design = self._ELECTRICAL_DESIGN
        self.devis.save(update_fields=['electrical_design'])
        html, _doc = self._render({'include_annexe_technique': True})
        self.assertIn('Annexe technique', html)
        self.assertIn('Nomenclature électrique', html)
        # La SECTION schéma n'apparaît pas (les <svg> des graphiques du corps
        # du devis, eux, existent toujours — on épingle la section, pas la
        # simple présence d'un svg).
        self.assertNotIn('Schéma unifilaire', html)

    def test_annexe_technique_degrades_without_design(self):
        """Drapeau activé mais aucune conception électrique → 3 pages, sans
        erreur (même dégradation gracieuse qu'``include_etude``)."""
        self.devis.electrical_design = None
        self.devis.save(update_fields=['electrical_design'])
        html, doc = self._render({'include_annexe_technique': True})
        self.assertEqual(len(doc.pages), 3)
        self.assertNotIn('Annexe technique', html)

    def test_annexe_and_etude_together_make_five_pages(self):
        self.devis.mode_installation = 'industriel'
        self.devis.etude_params = {
            **DEUX_OPTIONS,   # PV86 — l'alternative reste DÉCLARÉE
            'kwc': 9.94, 'production_annuelle': 12486, 'conso_annuelle': 120000,
            'taux_autoconso': 100, 'taux_couverture': 10.4,
            'economies_annuelles': 21851, 'payback': 3.0, 'prix_kwc': 6543,
            'prod_mensuelle': [1040] * 12, 'conso_mensuelle': [10000] * 12,
        }
        self.devis.electrical_design = self._ELECTRICAL_DESIGN
        self.devis.save()
        _, doc = self._render({'include_etude': True,
                               'include_annexe_technique': True})
        self.assertEqual(len(doc.pages), 5)

    def test_annexe_technique_ignored_in_onepage_mode(self):
        self.devis.electrical_design = self._ELECTRICAL_DESIGN
        self.devis.save(update_fields=['electrical_design'])
        html, doc = self._render({'pdf_mode': 'onepage',
                                  'include_annexe_technique': True})
        self.assertEqual(len(doc.pages), 1)
        self.assertNotIn('Nomenclature électrique', html)

    def test_annexe_technique_totals_unchanged(self):
        """L'annexe n'ajoute AUCUN montant : les totaux du devis sont
        identiques avec et sans elle."""
        from apps.ventes.quote_engine.builder import build_quote_data

        self.devis.electrical_design = self._ELECTRICAL_DESIGN
        self.devis.save(update_fields=['electrical_design'])
        sans = build_quote_data(self.devis,
                                {'include_annexe_technique': False})
        avec = build_quote_data(self.devis,
                                {'include_annexe_technique': True})
        for clef in ('totaux_sans', 'totaux_avec', 'totaux_all',
                     'display_total', 'total_sans', 'total_avec'):
            self.assertEqual(sans.get(clef), avec.get(clef), clef)

    def test_annexe_technique_carries_no_price(self):
        self.devis.electrical_design = self._ELECTRICAL_DESIGN
        self.devis.save(update_fields=['electrical_design'])
        from apps.ventes.quote_engine import generate_devis_premium as G
        annexe = self._annexe_html()
        # Ni les prix d'achat/marge, ni AUCUN prix de ligne du devis.
        for interdit in ('prix_achat', 'marge', 'Total TTC', 'Sous-total'):
            self.assertNotIn(interdit, annexe)
        # PVSLD — le schéma v2 du moteur a rendu le scan de SOUS-CHAÎNE nue
        # intenable : « 67 » surgissait d'une coordonnée SVG (x1="67"), puis
        # « 1000 » de « 1000 V DC » — des grandeurs électriques LÉGITIMES.
        # Le vrai vecteur de fuite d'un prix est son RENDU MONÉTAIRE : tout
        # montant que le moteur imprime passe par ``fmt`` (« 11 700 MAD »,
        # séparateurs insécables), et un contournement naïf écrirait
        # « 11700 MAD ». On scanne donc l'annexe BRUTE ENTIÈRE pour ces deux
        # formes — aucune collision possible avec tensions/calibres, et une
        # fuite réelle reste attrapée à coup sûr.
        for _designation, _qte, _prix in self.FULL_LINES:
            self.assertNotIn(G.fmt(float(_prix)), annexe)
            self.assertNotIn(f'{_prix} MAD', annexe)
            self.assertNotIn(f'{_prix} MAD', annexe)
        self.assertIn('Nomenclature électrique', annexe)
        # La page de signature reste la DERNIÈRE page numérotée.
        self.assertEqual(G.PAGE3_NUM, G.PAGES_TOTAL)

    @staticmethod
    def _sans_donnees_binaires(html):
        """Retire les charges utiles ``data:...;base64,...`` du HTML.

        L'en-tête de l'annexe embarque le logo en PNG base64 : ~870 000
        caractères d'alphabet base64, où PRESQUE TOUTE suite de deux ou trois
        chiffres finit par apparaître (ici « 67 » et « 375 », deux prix de
        lignes du montage). Chercher un prix dans ces octets ne dit rien de ce
        que le client LIT — c'est un faux positif de la garde, pas une fuite.
        On garde donc la garde entière sur le contenu lisible : un prix
        RENDU y apparaîtrait toujours, puisqu'il serait du texte.
        """
        import re
        return re.sub(r'data:[^;"\']+;base64,[A-Za-z0-9+/=]+', 'data:…', html)

    def _annexe_html(self):
        """Rend la SEULE page d'annexe (globals posés par un rendu complet)."""
        from apps.ventes.quote_engine import generate_devis_premium as G

        self._render({'include_annexe_technique': True})
        return G.page_annexe_technique()

    # ── PV77 — étude bancable sur la page Étude (additif, sans page en plus) ──
    _SIMULATION = {
        'version': 1,
        'computed_at': '2026-08-14T10:00:00Z',
        'source': 'pvgis',
        'zones': [{'label': 'Pan Sud', 'lat': 33.57, 'lon': -7.59,
                   'tilt': 30, 'azimuth': 0, 'kwc': 42.3,
                   'base_production_kwh': 71800,
                   'shading_annual_loss_pct': 4.2}],
        'pr': {
            'performance_ratio': 0.812, 'total_loss_pct': 18.8,
            'loss_breakdown': {'temperature': 8.0, 'soiling': 3.0,
                               'shading': 4.2, 'wiring': 2.0,
                               'inverter': 2.5, 'mismatch': 2.0,
                               'availability': 1.0},
            'p50_kwh': 71800, 'p90_kwh': 58300, 'p75_kwh': 66400,
            'annual_variability': 0.06, 'specific_yield_kwh_kwc': 1697,
        },
        'self_consumption': {'hours': 8760, 'self_consumption_rate': 0.41,
                             'coverage_rate': 0.63,
                             'self_consumed_kwh': 29400,
                             'surplus_kwh': 42400, 'grid_import_kwh': 17300},
        'net_metering': {'annual_savings_mad': 33800,
                         'annual_compensated_kwh': 24100,
                         'annual_spill_value_mad': 0},
        'subscribed_power': {'peak_reduction_pct': 22.0,
                             'recommended_subscribed': 68,
                             'annual_saving': 5200},
        'degradation': {'factor_year1': 0.9784, 'factor_last_year': 0.874,
                        'any_warranty_breach': False},
        'projection_25y': {'npv': 412300, 'irr': 0.187, 'payback_year': 6,
                           'discounted_payback_year': 7},
        'warnings': [],
    }

    _ETUDE_INDUSTRIELLE = {
        'kwc': 9.94, 'production_annuelle': 12486, 'conso_annuelle': 120000,
        'taux_autoconso': 100, 'taux_couverture': 10.4,
        'economies_annuelles': 21851, 'payback': 3.0, 'prix_kwc': 6543,
        'prod_mensuelle': [1040] * 12, 'conso_mensuelle': [10000] * 12,
    }

    def _devis_avec_etude(self, simulation=None):
        self.devis.mode_installation = 'industriel'
        etude = {**DEUX_OPTIONS, **self._ETUDE_INDUSTRIELLE}
        if simulation is not None:
            etude['simulation'] = simulation
        self.devis.etude_params = etude
        self.devis.save()
        return self.devis

    @staticmethod
    def _cles_profondes(obj):
        """Toutes les clés de dict présentes à N'IMPORTE QUELLE profondeur."""
        vues = set()
        if isinstance(obj, dict):
            for clef, valeur in obj.items():
                vues.add(clef)
                vues |= TestPdfFormats._cles_profondes(valeur)
        elif isinstance(obj, (list, tuple)):
            for valeur in obj:
                vues |= TestPdfFormats._cles_profondes(valeur)
        return vues

    def test_pv77_sans_simulation_la_charge_utile_est_byte_identique(self):
        """Aucune simulation → AUCUNE clé nouvelle, nulle part, jamais."""
        from apps.ventes.quote_engine.builder import build_quote_data

        self._devis_avec_etude()
        data = build_quote_data(self.devis, {'include_etude': True})
        # Deux constructions du même devis rendent le MÊME dict (déterminisme :
        # sans lui, « byte-identique » ne voudrait rien dire).
        self.assertEqual(data, build_quote_data(self.devis,
                                                {'include_etude': True}))
        self.assertNotIn('bankable', self._cles_profondes(data))
        self.assertNotIn('simulation', data['etude'])

    def test_pv77_avec_simulation_seule_la_cle_bankable_apparait(self):
        """Avec simulation → la charge utile ne gagne QUE ``etude.bankable``."""
        from apps.ventes.quote_engine.builder import build_quote_data

        self._devis_avec_etude()
        sans = build_quote_data(self.devis, {'include_etude': True})
        self._devis_avec_etude(self._SIMULATION)
        avec = build_quote_data(self.devis, {'include_etude': True})

        self.assertEqual(set(avec) - set(sans), set())
        etude_avec = dict(avec['etude'])
        self.assertEqual(etude_avec.pop('bankable'), self._SIMULATION)
        # ``simulation`` est la clé BRUTE déjà portée par etude_params : elle
        # reste telle quelle, le bloc bancable s'AJOUTE à côté sans la toucher.
        self.assertEqual(etude_avec.pop('simulation'), self._SIMULATION)
        self.assertEqual(etude_avec, sans['etude'])
        # Le reste du dict (totaux, ROI, options…) est identique clé par clé.
        for clef in set(sans) - {'etude'}:
            self.assertEqual(sans[clef], avec[clef], clef)

    def test_pv77_le_bloc_bancable_est_une_copie_defensive(self):
        """Le rendu ne peut jamais muter l'étude STOCKÉE sur le devis."""
        from apps.ventes.quote_engine.builder import build_quote_data

        self._devis_avec_etude(self._SIMULATION)
        data = build_quote_data(self.devis, {'include_etude': True})
        data['etude']['bankable']['pr']['p50_kwh'] = 1
        # En mémoire (une copie de surface aurait partagé le sous-dict 'pr')…
        self.assertEqual(
            self.devis.etude_params['simulation']['pr']['p50_kwh'], 71800)
        # … et en base.
        self.devis.refresh_from_db()
        self.assertEqual(
            self.devis.etude_params['simulation']['pr']['p50_kwh'], 71800)

    def test_pv77_la_page_etude_montre_p50_p90_et_la_cascade(self):
        self._devis_avec_etude(self._SIMULATION)
        html, doc = self._render({'include_etude': True})
        self.assertEqual(len(doc.pages), 4)
        self.assertIn('Étude bancable', html)
        self.assertIn('Production P50', html)
        self.assertIn('P90', html)
        self.assertIn('71 800', html)      # P50 formaté à la française
        self.assertIn('58 300', html)      # P90
        self.assertIn('Cascade de pertes', html)
        for libelle in ('Température', 'Salissures', 'Ombrage', 'Câblage',
                        'Onduleur', 'Disponibilité'):
            self.assertIn(libelle, html)
        self.assertIn('Ratio de performance', html)

    def test_pv77_le_nombre_de_pages_ne_bouge_jamais(self):
        """Le bloc vit DANS la page Étude : 4 pages avec, 4 pages sans."""
        self._devis_avec_etude()
        _, sans = self._render({'include_etude': True})
        self._devis_avec_etude(self._SIMULATION)
        html, avec = self._render({'include_etude': True})
        self.assertEqual(len(sans.pages), len(avec.pages))
        self.assertEqual(len(avec.pages), 4)
        # Et avec l'annexe technique par-dessus : toujours 5, jamais 6.
        self.devis.electrical_design = self._ELECTRICAL_DESIGN
        self.devis.save(update_fields=['electrical_design'])
        _, cinq = self._render({'include_etude': True,
                                'include_annexe_technique': True})
        self.assertEqual(len(cinq.pages), 5)
        self.assertIn('Étude bancable', html)

    def test_pv77_sans_simulation_la_page_etude_est_celle_d_hier(self):
        self._devis_avec_etude()
        html, doc = self._render({'include_etude': True})
        self.assertEqual(len(doc.pages), 4)
        self.assertNotIn('Étude bancable', html)
        self.assertNotIn('Cascade de pertes', html)

    def test_pv77_le_bloc_bancable_ne_porte_aucun_montant(self):
        """Règle #4 — que des grandeurs énergétiques : ni VAN, ni TRI, ni prix."""
        from apps.ventes.quote_engine import generate_devis_premium as G

        bloc = G._bankable_block_html(self._SIMULATION)
        self.assertTrue(bloc)
        for interdit in ('MAD', 'VAN', 'TRI', 'npv', 'irr', '412', '33 800',
                         'prix_achat', 'marge'):
            self.assertNotIn(interdit, bloc)

    def test_pv77_une_simulation_illisible_ne_rend_rien(self):
        from apps.ventes.quote_engine import generate_devis_premium as G

        for entree in (None, {}, [], 'oui', {'pr': {}},
                       {'pr': {'loss_breakdown': {}}}):
            self.assertEqual(G._bankable_block_html(entree), '')

    # ── CJ2b-bis (L-PDF, lot 4) — falaise tarifaire / remplissage batterie /
    # part des glitchs, additifs sur la page Étude. ``dimensionnement`` suit
    # le contrat ``apps.ventes.dimensionnement.recommander_taille`` (le même
    # que ``POST /ventes/etude-horaire/preview/`` — voir
    # ``apps/ventes/contract_samples/etude_horaire.json``) : AUCUN devis réel
    # ne le porte encore ([HANDOFF backend], voir generate_devis_premium.
    # _falaise_context), donc ces tests le posent directement pour prouver le
    # rendu une fois le producteur câblé. ``etude_horaire`` en revanche EST
    # déjà posé sur de vrais devis par ``services.rafraichir_etude_horaire_
    # devis`` — le sous-ensemble ``annuel.part_glitch_*`` testé ici est réel.
    _DIMENSIONNEMENT_SAMPLE = {
        'falaise': {
            'cible_kwh_mois': 500.0,
            'tranche_actuelle': {'rang': 6, 'libelle': 'Tranche 6 (> 500 kWh)'},
            'tranche_visee': {'rang': 5, 'libelle': 'Tranche 5 (401-500 kWh)'},
        },
        'meilleure_falaise': {
            'panneaux': 14, 'kwc': 7.7, 'batterie_kwh': 10.0,
            'residuel_kwh_mois': 420.0,
            'tranche_apres': {'rang': 5, 'libelle': 'Tranche 5 (401-500 kWh)'},
            'remplissage': {
                'moyen': 0.62,
                'pire_mois': {'mois': 1, 'ratio': 0.62,
                              'charge_jour_kwh': 8.0, 'surplus_jour_kwh': 5.0},
            },
            'cible_kwh_mois': 500.0,
        },
    }

    _ETUDE_HORAIRE_GLITCH_SAMPLE = {
        'annuel': {
            'part_glitch_sans_kwh': 180.0,
            'part_glitch_avec_kwh': 60.0,
            'part_glitch_batterie_kwh': 120.0,
            'part_glitch_sans_mad': 216.0,
            'part_glitch_avec_mad': 72.0,
        },
    }

    def _devis_avec_falaise(self, dimensionnement=None, etude_horaire=None):
        etude = {**DEUX_OPTIONS, **self._ETUDE_INDUSTRIELLE}
        if dimensionnement is not None:
            etude['dimensionnement'] = dimensionnement
        if etude_horaire is not None:
            etude['etude_horaire'] = etude_horaire
        self.devis.mode_installation = 'industriel'
        self.devis.etude_params = etude
        self.devis.save()
        return self.devis

    def test_cj2b_bis_falaise_et_remplissage_rendus_quand_le_contrat_existe(self):
        self._devis_avec_falaise(dimensionnement=self._DIMENSIONNEMENT_SAMPLE)
        html, doc = self._render({'include_etude': True})
        self.assertEqual(len(doc.pages), 4)
        self.assertIn('Résiduel sous la marche', html)
        self.assertIn('420', html)
        self.assertIn('Tranche 5', html)
        self.assertIn('Tranche 6', html)
        self.assertIn('Remplissage batterie', html)
        self.assertIn('62 %', html)

    def test_cj2b_bis_part_glitch_rendue_quand_le_bloc_horaire_existe(self):
        self._devis_avec_falaise(etude_horaire=self._ETUDE_HORAIRE_GLITCH_SAMPLE)
        html, doc = self._render({'include_etude': True})
        self.assertEqual(len(doc.pages), 4)
        self.assertIn('Part des pointes rattrapée par la batterie', html)
        self.assertIn('67 %', html)  # 120 / 180 = 66,7 % → arrondi 67

    def test_cj2b_bis_absent_ne_change_rien(self):
        """Sans ``dimensionnement`` ni glitch : page Étude byte-identique à
        avant ce lot — aucune des trois nouvelles cartes n'apparaît."""
        self._devis_avec_falaise()
        html, doc = self._render({'include_etude': True})
        self.assertEqual(len(doc.pages), 4)
        for texte in ('Résiduel sous la marche', 'Remplissage batterie',
                      'Part des pointes rattrapée par la batterie'):
            self.assertNotIn(texte, html)

    def test_cj2b_bis_dimensionnement_malforme_est_ignore(self):
        """Contrat cassé (types inattendus) : omission propre, jamais une
        exception ni un tiret fabriqué."""
        self._devis_avec_falaise(
            dimensionnement={'falaise': 'invalide', 'meilleure_falaise': None})
        html, doc = self._render({'include_etude': True})
        self.assertEqual(len(doc.pages), 4)
        self.assertNotIn('Résiduel sous la marche', html)

    def test_cj2b_bis_onepage_mentionne_le_residuel_quand_present(self):
        self._devis_avec_falaise(dimensionnement=self._DIMENSIONNEMENT_SAMPLE)
        html, doc = self._render({'pdf_mode': 'onepage'})
        self.assertEqual(len(doc.pages), 1)
        self.assertIn('R&#233;siduel vis&#233;', html)
        self.assertIn('420', html)

    def test_cj2b_bis_onepage_sans_contrat_est_celui_d_hier(self):
        self._devis_avec_falaise()
        html, doc = self._render({'pdf_mode': 'onepage'})
        self.assertEqual(len(doc.pages), 1)
        self.assertNotIn('R&#233;siduel vis&#233;', html)

    def test_pompage_summary_on_onepage(self):
        """A pompage quote shows pump CV/débit/HMT in the one-page summary."""
        self.devis.mode_installation = 'agricole'
        self.devis.etude_params = {
            **DEUX_OPTIONS,
            'pompe_cv': '5.5', 'pompe_kw': 4.05, 'type_pompe': 'immergee',
            'alim': 'tri', 'hmt_m': '80', 'debit_m3j': '45', 'champ_kwc': 5.68,
        }
        self.devis.save()
        html, doc = self._render({'pdf_mode': 'onepage'})
        self.assertEqual(len(doc.pages), 1)
        self.assertIn('Puissance pompe', html)
        self.assertIn('HMT', html)

    def test_pompage_curve_figures_water_per_day_one_page(self):
        """Curve-sized pump: the one-page summary states pump CV+kW, débit at
        the HMT, and the m³/day with the hours assumption — exactly 1 page."""
        self.devis.mode_installation = 'agricole'
        self.devis.etude_params = {
            **DEUX_OPTIONS,
            'pompe_cv': '10', 'pompe_kw': 7.5,
            'pompe_nom': 'Pompe immergée OSP 30/8 — 10 CV / 7.5 kW (3", 380V)',
            'type_pompe': 'immergee', 'alim': 'tri',
            'hmt_m': '60', 'debit_souhaite_m3h': '30',
            'debit_hmt_m3h': 30, 'heures_pompage': 7, 'm3_jour': 210,
            'champ_kwc': 10.65,
        }
        self.devis.save()
        html, doc = self._render({'pdf_mode': 'onepage'})
        self.assertEqual(len(doc.pages), 1)
        self.assertIn('10 CV (7.5 kW)', html)
        self.assertIn('D&#233;bit &#224; 60 m', html)
        self.assertIn('30 m&#179;/h', html)
        self.assertIn('Eau / jour (sur 7 h de pompage)', html)
        self.assertIn('210 m&#179;', html)

    def test_pompage_without_curve_never_shows_water_per_day(self):
        """No curve → no débit-at-HMT, no m³/day card, no dashes — the card
        is omitted entirely rather than faked."""
        self.devis.mode_installation = 'agricole'
        self.devis.etude_params = {
            **DEUX_OPTIONS,
            'pompe_cv': '5.5', 'pompe_kw': 4.05, 'type_pompe': 'immergee',
            'alim': 'tri', 'hmt_m': '80', 'champ_kwc': 5.68,
            'debit_hmt_m3h': None, 'heures_pompage': None, 'm3_jour': None,
        }
        self.devis.save()
        html, doc = self._render({'pdf_mode': 'onepage'})
        self.assertEqual(len(doc.pages), 1)
        self.assertNotIn('Eau / jour', html)
        self.assertNotIn('m&#179;/jour', html)
        # pas de tiret placeholder dans le bloc résumé
        self.assertNotIn('>&#8212;<', html)

    def test_panel_ht_derivation_at_10_percent(self):
        """1 400 TTC @ 10 % → 1 272,73 HT par ligne (TTC ancre, jamais 1 166,67)."""
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Canadien Solar 710W', '14', '1272.73', '10'),
            ('Onduleur réseau Huawei 10kW', '1', '16666.67', '20'),
        ], reference='DEV-QE-TVA10')
        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
        panel = next(it for it in data['all_items'] if 'Panneau' in it['designation'])
        self.assertEqual(panel['taux_tva'], 10.0)
        self.assertEqual(panel['prix_unit_ht'], 1272.73)
        self.assertEqual(panel['prix_unit_ttc'], 1400.0)
        ond = next(it for it in data['all_items'] if 'Onduleur' in it['designation'])
        self.assertEqual(ond['taux_tva'], 20.0)
        self.assertEqual(ond['prix_unit_ttc'], 20000.0)

    def _mixed_devis(self, remise='0', reference='DEV-QE-MIX'):
        return make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Canadien Solar 710W', '14', '1272.73', '10'),
            ('Onduleur réseau Huawei 10kW', '1', '16666.67', '20'),
            ('Structures acier', '14', '416.67', '20'),
            ('Installation', '1', '4000', '20'),
        ], remise_globale=remise, reference=reference)

    def test_mixed_rates_buckets_reconcile_to_the_centime(self):
        """TVA 10 % + TVA 20 % éclatées ; HT net + somme des TVA = TTC exact,
        avec et sans remise globale."""
        from apps.ventes.quote_engine.builder import build_quote_data
        for remise, ref in (('0', 'DEV-QE-MIX0'), ('8', 'DEV-QE-MIX8')):
            devis = self._mixed_devis(remise=remise, reference=ref)
            data = build_quote_data(devis, {'pdf_mode': 'onepage'})
            t = data['totaux_all']
            buckets = {b['taux']: b for b in t['tva_par_taux']}
            self.assertEqual(set(buckets), {10.0, 20.0})
            # réconciliation au centime
            self.assertAlmostEqual(
                t['ht_net'], sum(b['ht_net'] for b in t['tva_par_taux']), places=2)
            self.assertAlmostEqual(
                t['ttc_exact'],
                round(t['ht_net'] + sum(b['montant'] for b in t['tva_par_taux']), 2),
                places=2)
            # la remise réduit chaque panier proportionnellement
            if remise == '8':
                self.assertGreater(t['remise'], 0)
            # montants TVA cohérents avec leurs paniers nets
            for b in t['tva_par_taux']:
                self.assertAlmostEqual(
                    b['montant'], round(b['ht_net'] * b['taux'] / 100, 2), places=2)
            # le HTML one-page montre les deux lignes TVA et le TTC canonique
            html, doc = self._render({'pdf_mode': 'onepage'}, devis=devis)
            self.assertEqual(len(doc.pages), 1)
            self.assertIn('TVA (10', html)
            self.assertIn('TVA (20', html)

    def test_mixed_rates_tva_note_describes_reform(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._mixed_devis(reference='DEV-QE-MIXN')
        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
        self.assertIn('10% panneaux photovolta', data['tva_note'])
        self.assertIn('20% autres', data['tva_note'])

    def test_legacy_single_rate_quote_renders_unchanged(self):
        """Devis historique (lignes sans taux) : note d'origine, ligne TVA
        unique au taux du devis, totaux identiques à l'ancien calcul."""
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj,
                           self.FULL_LINES, remise_globale='8',
                           reference='DEV-QE-LEGTVA',
                           etude_params=DEUX_OPTIONS)
        data = build_quote_data(devis)
        self.assertFalse(data['per_line_tva'])
        self.assertIn('appliquée sur l\'ensemble', data['tva_note'])
        t = data['totaux_sans']
        # ancien calcul exact : TVA unique sur le HT net
        self.assertAlmostEqual(t['tva'], round(t['ht_net'] * 0.20, 2), places=2)
        self.assertEqual(len(t['tva_par_taux']), 1)
        html, _ = self._render(devis=devis)
        self.assertIn('TVA (20', html)
        self.assertNotIn('TVA (10', html)

    def test_mixed_rates_onepage_15_lines_still_one_page(self):
        """Le format une page absorbe la colonne TVA même en table dense."""
        lignes = [(f'Divers {i} article générique', '2', '500', '20') for i in range(13)]
        lignes += [('Panneau mono 710W', '14', '1272.73', '10'),
                   ('Onduleur réseau 10kW', '1', '16666.67', '20')]
        devis = make_devis(self.company, self.user, self.client_obj,
                           lignes, reference='DEV-QE-MIX15')
        html, doc = self._render({'pdf_mode': 'onepage'}, devis=devis)
        self.assertEqual(len(doc.pages), 1)

    def test_two_option_quote_one_canonical_total_everywhere(self):
        """INTÉGRITÉ : pour un devis à DEUX options (remise incluse), le total
        de liste = total option 1 du premium = total du une-page, au dirham.
        Le une-page ne mélange JAMAIS les deux options sur une même facture.

        PV86 — le devis DÉCLARE son alternative (``etude_params['scenario']``,
        ce que le générateur persiste toujours). Sans cette déclaration, deux
        onduleurs en lignes non optionnelles ne sont plus un document à deux
        options mais un artefact de données rendu en UNE présentation au total
        du devis (cf. ``test_pv86_verite_unique_devis``).
        """
        from apps.ventes.quote_engine.builder import build_quote_data, display_totals
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Canadien Solar 710W', '14', '1272.73', '10'),
            ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67', '20'),
            ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33', '20'),
            ('Batterie Dyness 10 kWh', '1', '25000', '20'),
            ('Installation', '1', '4000', '20'),
        ], remise_globale='5', reference='DEV-QE-2OPT',
            etude_params=DEUX_OPTIONS)

        dt = display_totals(devis)
        full = build_quote_data(devis)
        one = build_quote_data(devis, {'pdf_mode': 'onepage'})
        self.assertEqual(dt['nb_options'], 2)
        self.assertEqual(dt['total'], full['totaux_sans']['ttc'])
        self.assertEqual(dt['total'], one['totaux_all']['ttc'])
        # le total de liste n'est JAMAIS la somme mensongère des deux options
        self.assertLess(dt['total'], float(devis.total_ttc))

        # une page : OPTION 1 SEULE — un une-page avec deux onduleurs DOIT
        # échouer ce test (règle de sécurité demandée)
        designations = [it['designation'].lower() for it in one['all_items']]
        self.assertTrue(any('réseau' in d for d in designations))
        self.assertFalse(any('hybride' in d for d in designations),
                         'une facture une-page ne contient JAMAIS deux onduleurs')
        self.assertFalse(any('batterie' in d for d in designations))
        html, doc = self._render({'pdf_mode': 'onepage'}, devis=devis)
        self.assertEqual(len(doc.pages), 1)
        self.assertIn('option sans batterie', html)
        self.assertIn('option avec batterie est disponible', html)

    def test_mono_option_quote_display_total_is_full_bill(self):
        """Devis sans options (liste libre/pompage) : total de liste = total
        complet, pas de badge deux-options — comportement inchangé."""
        from apps.ventes.quote_engine.builder import display_totals
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Pompe immergée 5.5 CV', '1', '9166.67', '20'),
            ('Installation', '1', '4000', '20'),
        ], reference='DEV-QE-MONO')
        dt = display_totals(devis)
        self.assertEqual(dt['nb_options'], 1)
        self.assertEqual(dt['total'], round((9166.67 + 4000) * 1.2))

    def test_payment_terms_by_mode_on_all_formats(self):
        """Conditions de paiement = mapping UNIQUE par mode : résidentiel et
        agricole 30/60/10, industriel 50/40/10 — cohérent sur tous formats."""
        # Résidentiel (défaut) — premium
        html, _ = self._render()
        self.assertIn('Acompte à la commande&#160;: 30&#37;', html)
        self.assertIn('60&#37; à la réception du matériel', html)
        self.assertIn('10&#37; après la mise en marche', html)
        self.assertIn('+ acompte 30&#37;', html)
        # Résidentiel — one-page
        html1, _ = self._render({'pdf_mode': 'onepage'})
        self.assertIn('Acompte&#160;: 30&#37;', html1)
        self.assertIn('60&#37; &#224; la r&#233;ception du mat&#233;riel', html1)
        self.assertIn('10&#37; apr&#232;s mise en marche', html1)
        # Industriel — 50/40/10 partout
        self.devis.mode_installation = 'industriel'
        self.devis.save(update_fields=['mode_installation'])
        html2, _ = self._render()
        self.assertIn('Acompte à la commande&#160;: 50&#37;', html2)
        self.assertIn('40&#37; à la réception du matériel', html2)
        self.assertIn('+ acompte 50&#37;', html2)
        self.assertNotIn('Acompte à la commande&#160;: 30&#37;', html2)
        html3, _ = self._render({'pdf_mode': 'onepage'})
        self.assertIn('Acompte&#160;: 50&#37;', html3)
        self.assertIn('40&#37; &#224; la r&#233;ception du mat&#233;riel', html3)
        # Bloc « Modalités de paiement » (devis final) suit aussi le mode
        html4, _ = self._render({'devis_final': True})
        self.assertIn('Modalit', html4)
        self.assertIn('>50%</div>', html4)   # acompte industriel
        # Agricole — défaut résidentiel 30/60/10 (one-page)
        self.devis.mode_installation = 'agricole'
        self.devis.save(update_fields=['mode_installation'])
        html5, _ = self._render({'pdf_mode': 'onepage'})
        self.assertIn('Acompte&#160;: 30&#37;', html5)

    def test_panel_performance_warranty_is_30_years(self):
        """Performance panneau : 30 ans, jamais 25 — mais LUE sur la fiche.

        M6 (audit adversarial du 19/08/2026) — ces durées étaient des
        littéraux : « Garanties jusqu'à 30 ans », « 30 ans performance
        (87,4 %) » sortaient sur TOUS les devis, y compris un Longi (30 ans
        mais 88,9 %) et des produits sans aucune garantie saisie. Le document
        les dérive maintenant des FICHES PRODUIT — la fixture en porte donc,
        comme le catalogue réel. Le « 87,4 % » ne s'écrit plus : c'est une
        spec Canadian Solar, elle n'appartient pas au libellé générique.

        L'horizon ROI « sur 25 ans » (graphique) n'est PAS une garantie et
        reste : c'est ce que ce test protège depuis toujours.
        """
        self.devis.mode_installation = ''
        self.devis.save(update_fields=['mode_installation'])
        for ligne in self.devis.lignes.all():
            nom = ligne.designation.lower()
            if 'panneau' in nom:
                ligne.produit.garantie_mois = 144            # 12 ans produit
                ligne.produit.garantie_production_mois = 360  # 30 ans perf.
                ligne.produit.save(update_fields=[
                    'garantie_mois', 'garantie_production_mois'])
            elif 'onduleur' in nom:
                ligne.produit.garantie_mois = 120             # 10 ans
                ligne.produit.save(update_fields=['garantie_mois'])
        html, _ = self._render()
        self.assertIn('Garanties jusqu&#8217;&#224; 30 ans', html)
        self.assertIn('Performance panneau', html)
        self.assertNotIn('25 ans performance', html)
        self.assertNotIn('jusqu&#8217;&#224; 25 ans', html)
        # Le pourcentage d'une marque ne s'imprime plus sous un libellé générique.
        self.assertNotIn('87,4', html)

    def test_ice_rendered_when_present_absent_when_empty(self):
        self.client_obj.ice = '003799642000099'
        self.client_obj.save(update_fields=['ice'])
        html, _ = self._render()
        self.assertIn('003799642000099', html)
        self.assertIn('ICE', html)
        html1, _ = self._render({'pdf_mode': 'onepage'})
        self.assertIn('003799642000099', html1)
        # Vide → la ligne disparaît entièrement (pas de tiret)
        self.client_obj.ice = ''
        self.client_obj.save(update_fields=['ice'])
        html2, _ = self._render()
        self.assertNotIn('ICE&#160;:', html2)
        html3, _ = self._render({'pdf_mode': 'onepage'})
        self.assertNotIn('ICE&#160;:', html3)

    def test_buy_prices_never_in_pdf_html(self):
        """Le prix d'achat (revendeur) n'apparaît dans AUCUN rendu client —
        sweep sur les deux formats avec un prix d'achat très reconnaissable."""
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('VARIATEUR VEICHI SI23 7.5KW 380V', '1', '3333.33'),
            ('Pompe immergée OSP 30/8', '1', '12500'),
            ('Panneau Canadien Solar 710W', '15', '1166.67'),
        ], reference='DEV-QE-SWEEP')
        # prix d'achat distinctifs sur les produits liés
        for ligne in devis.lignes.all():
            ligne.produit.prix_achat = Decimal('9876.54')
            ligne.produit.save(update_fields=['prix_achat'])
        devis.mode_installation = 'agricole'
        devis.etude_params = {'pompe_cv': '10', 'pompe_kw': 7.5, 'hmt_m': '60'}
        devis.save()
        for opts in ({'pdf_mode': 'onepage'}, None):
            html, _ = self._render(opts, devis=devis)
            for marker in ('9876', '9 876', '9\u202f876', '9&#8239;876', 'achat'):
                self.assertNotIn(marker, html.lower())

    def test_onepage_15_rich_lines_stays_one_page_with_totals_visible(self):
        """Adaptive density: a 15-line quote with long product descriptions
        must compact (descriptions suppressed > 12 lines) so the table AND
        the totals block fit on exactly one page."""
        from apps.stock.models import Produit
        from weasyprint import HTML
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G

        lignes = [(f'P{i:02d} produit audit', '2', '1000') for i in range(15)]
        devis = make_devis(self.company, self.user, self.client_obj,
                           lignes, reference='DEV-QE-15L')
        # Toutes les fiches portent une longue description + garantie
        Produit.objects.filter(
            lignes_devis__devis=devis).update(
            description='Ligne 1 de description\nLigne 2\nLigne 3\nLigne 4',
            garantie='Garantie constructeur 10 ans')

        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_15l.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        html = cap['html']
        doc = HTML(string=html).render()
        self.assertEqual(len(doc.pages), 1)
        # > 12 lignes → mode compact : pas de lignes de description ni de
        # garanties (le tableau + totaux tiennent alors largement sur la page,
        # vérifié visuellement sur un rendu réel)
        self.assertNotIn('Ligne 1 de description', html)
        self.assertNotIn('Garantie constructeur 10 ans', html)
        self.assertIn('Sous-total HT', html)

        # Cas confortable : 6 lignes → descriptions présentes
        devis2 = make_devis(self.company, self.user, self.client_obj,
                            [(f'C{i} produit confort', '1', '500') for i in range(6)],
                            reference='DEV-QE-6L')
        Produit.objects.filter(lignes_devis__devis=devis2).update(
            description='Desc visible A\nDesc visible B')
        data2 = build_quote_data(devis2, {'pdf_mode': 'onepage'})
        cap2 = {}
        G._render_pdf_weasyprint = lambda html, out: cap2.update(html=html)
        try:
            G.generate_premium_pdf(data2, '/tmp/_6l.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        self.assertIn('Desc visible A', cap2['html'])
        self.assertEqual(len(HTML(string=cap2['html']).render().pages), 1)

    def test_figures_identical_on_every_page(self):
        """ONE source of truth: the page-1 headline totals equal the page-2
        totals block exactly (no rounding drift), and the étude repeats the
        page-1 production/savings/payback verbatim."""
        from apps.ventes.quote_engine.builder import build_quote_data
        self.devis.mode_installation = 'industriel'
        self.devis.etude_params = {
            **DEUX_OPTIONS,
            'kwc': 9.94, 'production_annuelle': 156978, 'conso_annuelle': 120000,
            'taux_autoconso': 71.4, 'taux_couverture': 93.3,
            'economies_annuelles': 274711, 'payback': 2.1, 'prix_kwc': 4557,
            'prod_mensuelle': [13081] * 12, 'conso_mensuelle': [10000] * 12,
        }
        self.devis.save()
        data = build_quote_data(self.devis)
        # totaux canoniques : la valeur page 1 EST la valeur du bloc page 2
        self.assertEqual(data['total_sans'], data['totaux_sans']['ttc'])
        self.assertEqual(data['total_avec'], data['totaux_avec']['ttc'])
        # production/économies de l'étude = celles de la page 1 (canoniques)
        self.assertEqual(data['prod_kwh'], data['etude']['production_annuelle'])
        self.assertEqual(data['eco_s_ann'], data['etude']['economies_annuelles'])
        self.assertEqual(data['roi_s'], data['etude']['payback'])
        # prix/kWc recalculé depuis le total canonique (jamais l'ancien stocké)
        ref_total = data['total_sans']
        self.assertEqual(data['etude']['prix_kwc'],
                         round(ref_total / data['puissance_kwc']))
        # rendu : le Total TTC canonique apparaît plusieurs fois — même nombre
        # partout (les pages diffèrent seulement par le type d'espace fine)
        import re
        html, doc = self._render()
        digits = str(data['totaux_sans']['ttc'])
        pattern = r'[\s   ]?'.join(
            [digits[max(0, len(digits) - 3 * (i + 1)):len(digits) - 3 * i]
             for i in range((len(digits) + 2) // 3 - 1, -1, -1)])
        self.assertGreaterEqual(len(re.findall(pattern, html)), 2)

    def test_tva_note_matches_applied_math(self):
        """Le texte TVA décrit exactement le taux appliqué — l'ancienne
        mention contradictoire 10 %/20 % a disparu de tout le document."""
        html, _ = self._render()
        self.assertIn('TVA 20 % appliquée sur l’ensemble'.replace('’', "'"),
                      html.replace('&#8217;', "'").replace('’', "'"))
        self.assertNotIn('10&#37; sur les modules', html)
        self.assertNotIn('10&#37; modules', html)

    def test_industrial_document_single_option_with_etude(self):
        """Document industriel : option unique sans batterie (jamais d'option
        avec batterie fabriquée), étude incluse d'office → 4 pages, mode
        affiché Industrielle, confirmation unique en signature."""
        from apps.ventes.models import Devis
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Canadien Solar 710W', '176', '1166.67'),
            ('Onduleur réseau Huawei 100kW Triphasé', '1', '65000'),
            ('Structures acier', '176', '416.67'),
            ('Installation', '1', '52000'),
        ], reference='DEV-QE-IND')
        Devis.objects.filter(pk=devis.pk).update(
            mode_installation='industriel',
            etude_params={
                'kwc': 124.96, 'production_annuelle': 156978,
                'conso_annuelle': 240000, 'taux_autoconso': 92.1,
                'taux_couverture': 60.2, 'economies_annuelles': 252000,
                'payback': 2.2, 'prix_kwc': 4500,
                'prod_mensuelle': [13081] * 12, 'conso_mensuelle': [20000] * 12,
            })
        devis.refresh_from_db()
        html, doc = self._render(devis=devis)
        self.assertEqual(len(doc.pages), 4)  # 1 proposition, 2 équipements, 3 étude, 4 signature
        # option unique : pas de boilerplate « Onduleur hybride Deye »,
        # pas de batterie inventée, cases à deux options absentes
        self.assertNotIn('Onduleur hybride Deye', html)
        self.assertNotIn('Batterie de stockage incluse', html)
        self.assertIn('Confirmation de la commande', html)
        # QX43 — industriel et commercial séparés : le libellé industriel est
        # désormais « Industrielle » (plus « Industrielle / Commerciale »).
        self.assertIn('Industrielle', html)
        self.assertNotIn('Industrielle / Commerciale', html)
        # taux réels présents (consommation fournie)
        self.assertIn('Taux de couverture', html)

    def test_etude_without_consumption_omits_rates_no_dashes(self):
        """Étude sans consommation : les cartes taux sont OMISES (pas de tiret,
        pas d'« autoconsommation 100 % » fabriquée)."""
        self.devis.mode_installation = 'industriel'
        self.devis.etude_params = {
            **DEUX_OPTIONS,
            'kwc': 9.94, 'production_annuelle': 12486,
            'conso_annuelle': None, 'taux_autoconso': 100,
            'taux_couverture': None, 'economies_annuelles': 21851,
            'payback': 3.0, 'prix_kwc': 6543,
            'prod_mensuelle': [1040] * 12, 'conso_mensuelle': None,
        }
        self.devis.save()
        html, doc = self._render()
        self.assertNotIn("Taux d'autoconsommation", html)
        self.assertNotIn('Taux de couverture', html)
        self.assertNotIn('Consommation annuelle', html)

    def test_unknown_options_are_whitelisted_away(self):
        from apps.ventes.quote_engine import clean_pdf_options
        opts = clean_pdf_options({
            'pdf_mode': 'evil', 'show_monthly': 1, 'devis_final': 'yes',
            'payment_mode': 'weird', 'custom_acompte': 'abc', 'junk': True,
        })
        self.assertEqual(opts['pdf_mode'], 'full')
        self.assertTrue(opts['show_monthly'])
        self.assertTrue(opts['devis_final'])
        self.assertEqual(opts['payment_mode'], 'standard')
        self.assertIsNone(opts['custom_acompte'])
        self.assertNotIn('junk', opts)
