"""
Tests for the premium quote engine (apps.ventes.quote_engine).

Covers the OS-quote -> data-dict mapping (power derivation, split-by-battery,
on-the-fly ROI) and a full premium PDF render with MinIO mocked.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_quote_engine -v 2
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, tag
from django.contrib.auth import get_user_model

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()


def make_company():
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug='test-qe-co', defaults={'nom': 'Test QE Co'},
    )
    return company


def make_user(company):
    return User.objects.create_user(
        username='test_qe_user', password='x', role_legacy='responsable',
        company=company,
    )


def make_client(company):
    return Client.objects.create(
        company=company, nom='Alaoui', prenom='Karim',
        email='k@example.com', telephone='+212600000000',
        adresse='Hay Riad, Rabat',
    )


def make_produit(company, nom, sku, prix):
    return Produit.objects.create(
        company=company, nom=nom, sku=sku,
        prix_vente=Decimal(prix), prix_achat=Decimal('1'),
        quantite_stock=100,
    )


def make_devis(company, user, client, lignes, remise_globale='0', reference='DEV-QE-0001'):
    devis = Devis.objects.create(
        company=company, reference=reference, client=client,
        statut='brouillon', taux_tva=Decimal('20.00'),
        remise_globale=Decimal(remise_globale), created_by=user,
    )
    for ligne in lignes:
        # (desig, qty, pu) historique ou (desig, qty, pu, taux_tva) réforme
        desig, qty, pu = ligne[:3]
        taux = Decimal(ligne[3]) if len(ligne) > 3 else None
        # SKU unique par devis pour éviter les collisions (company, sku)
        sku = f"{reference[-6:]}-{desig[:13]}"
        LigneDevis.objects.create(
            devis=devis, produit=make_produit(company, desig, sku, pu),
            designation=desig, quantite=Decimal(qty),
            prix_unitaire=Decimal(pu), remise=Decimal('0'),
            taux_tva=taux,
        )
    return devis


class TestBuildQuoteData(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def test_power_derived_from_panels(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '10', '1500'),
            ('Onduleur hybride', '1', '12000'),
        ])
        data = build_quote_data(devis)
        # 10 panels x 450W = 4.5 kWc
        self.assertEqual(data['nb_panneaux'], 10)
        self.assertEqual(data['watt_par_panneau'], 450)
        self.assertEqual(data['puissance_kwc'], 4.5)
        # ROI fields present and sane
        self.assertGreater(data['prod_kwh'], 0)
        self.assertGreater(data['eco_a_ann'], 0)
        self.assertIn('eco_s_monthly', data)
        self.assertEqual(len(data['eco_s_monthly']), 12)

    def test_no_hybrid_means_single_option_no_fabricated_battery(self):
        """RÈGLE DURE : sans onduleur hybride, l'option « avec batterie » ne
        se rend pas — document à option unique, jamais de batterie fabriquée
        sur une option sans onduleur."""
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 550W', '8', '2000'),
            ('Onduleur reseau', '1', '14000'),
        ])
        data = build_quote_data(devis)
        self.assertEqual(data['scenario'], 'Sans batterie')
        self.assertEqual(data['recommended'], 'Sans batterie')
        sans = [it['designation'].lower() for it in data['sans_items']]
        self.assertTrue(any('reseau' in d or 'réseau' in d for d in sans))

    def test_residential_hybrid_without_battery_synthesizes_small_module(self):
        """Échelle résidentielle (≤ 15 kWc) : hybride présent sans batterie →
        un module par défaut est ajouté (comportement historique conservé)."""
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 550W', '8', '2000'),
            ('Onduleur hybride 5kW', '1', '14000'),
        ])
        data = build_quote_data(devis)
        self.assertEqual(data['scenario'], 'Avec batterie')
        avec = [it['designation'].lower() for it in data['avec_items']]
        self.assertTrue(any('batterie' in d for d in avec))

    def test_large_plant_never_gets_token_battery(self):
        """> 15 kWc sans batterie : pas de batterie symbolique fabriquée —
        l'option avec batterie est indisponible."""
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 710W', '176', '1166.67'),
            ('Onduleur réseau 100kW', '1', '65000'),
            ('Onduleur hybride 20kW', '1', '40000'),
        ])
        data = build_quote_data(devis)
        # hybride présent mais pas de batterie et 124.96 kWc → pas de synthèse
        avec = [it['designation'].lower() for it in data['avec_items']]
        self.assertFalse(any('batterie' in d for d in avec))
        self.assertEqual(data['scenario'], 'Sans batterie')

    def test_no_inverter_at_all_fails_option_pdf(self):
        """Un devis sans aucun onduleur ne peut pas produire le PDF à options."""
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '6', '1500'),
            ('Batterie 5 kWh', '1', '16000'),
        ], reference='DEV-QE-NOINV')
        with self.assertRaises(ValueError):
            build_quote_data(devis, {'pdf_mode': 'full'})
        # …mais le format une page (liste simple, sans options) reste possible
        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
        self.assertEqual(data['pdf_mode'], 'onepage')

    def test_option_split_routes_both_inverters(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Onduleur réseau', '1', '11700'),
            ('Onduleur hybride', '1', '24000'),
            ('Panneau mono 550W', '14', '1100'),
            ('Batterie 5 kWh', '1', '14000'),
            ('Installation', '1', '4000'),
        ])
        data = build_quote_data(devis)
        sans = [it['designation'].lower() for it in data['sans_items']]
        avec = [it['designation'].lower() for it in data['avec_items']]
        # Option 1: réseau inverter, NO hybrid, NO battery.
        self.assertTrue(any('réseau' in d or 'reseau' in d for d in sans))
        self.assertFalse(any('hybride' in d for d in sans))
        self.assertFalse(any('batterie' in d for d in sans))
        # Option 2: hybrid inverter + battery, NO réseau inverter.
        self.assertTrue(any('hybride' in d for d in avec))
        self.assertTrue(any('batterie' in d for d in avec))
        self.assertFalse(any('réseau' in d or 'reseau' in d for d in avec))

    def test_existing_battery_not_duplicated(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '6', '1500'),
            ('Onduleur hybride 5kW', '1', '14000'),
            ('Batterie 5 kWh', '1', '16000'),
        ])
        data = build_quote_data(devis)
        # Battery already present: avec keeps the single one (no synthesis).
        batteries = [it for it in data['avec_items']
                     if 'batterie' in it['designation'].lower()]
        self.assertEqual(len(batteries), 1)

    def test_ttc_conversion_and_global_discount(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '10', '1000'),
        ], remise_globale='10')
        # format une page : pas d'options, la règle onduleur ne s'applique pas
        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
        # 10 x 1000 HT x1.20 TTC = 12000 before; -10% global = 10800.
        self.assertEqual(data['total_sans_before'], 12000.0)
        self.assertEqual(data['discount_pct'], 10.0)
        self.assertEqual(data['total_sans'], 10800)


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
        ])
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
        self.devis = make_devis(
            self.company, self.user, self.client_obj, self.FULL_LINES)

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
            ('Batterie Deyness 10 kWh', '1', '25000'),
            ('Panneau Canadien Solar 710W', '10', '1166.67'),
            ('Socles béton', '20', '66.67'),
        ], reference='DEV-QE-MARQUE')
        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
        marques = {it['designation']: it['marque'] for it in data['all_items']}
        self.assertEqual(marques['Onduleur hybride Deye 5kW'], 'Deye')
        self.assertEqual(marques['Batterie Deyness 10 kWh'], 'Deyness')
        self.assertEqual(marques['Panneau Canadien Solar 710W'], 'Canadien Solar')
        self.assertEqual(marques['Socles béton'], '')

    def test_ht_lines_and_visible_discount(self):
        """Per-line HT consistent with stored TTC; explicit Remise line with
        percentage and negative amount; HT → TVA → TTC chain rendered."""
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj,
                           self.FULL_LINES, remise_globale='8',
                           reference='DEV-QE-HT')
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

    def test_pompage_summary_on_onepage(self):
        """A pompage quote shows pump CV/débit/HMT in the one-page summary."""
        self.devis.mode_installation = 'agricole'
        self.devis.etude_params = {
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
                           reference='DEV-QE-LEGTVA')
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
        Le une-page ne mélange JAMAIS les deux options sur une même facture."""
        from apps.ventes.quote_engine.builder import build_quote_data, display_totals
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Canadien Solar 710W', '14', '1272.73', '10'),
            ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67', '20'),
            ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33', '20'),
            ('Batterie Deyness 10 kWh', '1', '25000', '20'),
            ('Installation', '1', '4000', '20'),
        ], remise_globale='5', reference='DEV-QE-2OPT')

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
        """Plus aucune mention « 25 ans » de performance panneau ; l'horizon
        ROI « sur 25 ans » (graphique) n'est PAS une garantie et reste."""
        self.devis.mode_installation = ''
        self.devis.save(update_fields=['mode_installation'])
        html, _ = self._render()
        self.assertIn('Garanties jusqu&#8217;à 30 ans', html)
        self.assertIn('30 ans performance (87,4&#8201;%)', html)
        self.assertIn('Performance panneau (87,4&#8201;%)', html)
        self.assertNotIn('25 ans performance', html)
        self.assertNotIn('jusqu&#8217;à 25 ans', html)

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
        self.assertIn('Industrielle / Commerciale', html)
        # taux réels présents (consommation fournie)
        self.assertIn('Taux de couverture', html)

    def test_etude_without_consumption_omits_rates_no_dashes(self):
        """Étude sans consommation : les cartes taux sont OMISES (pas de tiret,
        pas d'« autoconsommation 100 % » fabriquée)."""
        self.devis.mode_installation = 'industriel'
        self.devis.etude_params = {
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


class TestDocLiteralTemplates(TestCase):
    """D2/N60/N67/N26/N59 — textes éditables du devis (couche éditoriale).

    Garantit que (1) avec des réglages PAR DÉFAUT le HTML premium contient
    EXACTEMENT les littéraux historiques (validité, puces CGV, « Bon pour
    accord », garanties en entités HTML), donc le PDF est byte-identique ;
    (2) éditer ``DocumentTemplates`` change réellement le rendu ; (3) le tampon
    d'acceptation N26 n'apparaît QUE lorsque le devis est accepté.
    """

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
        self.devis = make_devis(
            self.company, self.user, self.client_obj, self.FULL_LINES)

    def _render(self, pdf_options=None, devis=None):
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G
        data = build_quote_data(devis or self.devis, pdf_options)
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_doclit_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return cap['html']

    def test_default_settings_keep_exact_historical_literals(self):
        """Réglages par défaut → tous les littéraux historiques présents au
        caractère et à l'entité HTML près (preuve de byte-identité du devis)."""
        html = self._render()
        # Validité (badge page 1) + format une page
        self.assertIn('Validit&#233;&#160;: 30 jours', html)
        # Conditions générales — titre + puces (entités/accents EXACTS)
        self.assertIn('Conditions générales du devis', html)
        self.assertIn('Validité de l&#8217;offre&#160;: 30 jours', html)
        self.assertIn('Acompte à la commande&#160;: 30&#37;', html)
        self.assertIn('60&#37; à la réception du matériel', html)
        self.assertIn('10&#37; après la mise en marche', html)
        self.assertIn('Délai d&#8217;installation&#160;: 7–14 jours ouvrés', html)
        self.assertIn('Tarifs de référence&#160;: barème ONEE/SRM', html)
        # Garanties — entités HTML EXACTES (cf. test garantie 30 ans)
        self.assertIn('Garanties jusqu&#8217;à 30 ans', html)
        self.assertIn('30 ans performance (87,4&#8201;%)', html)
        self.assertIn('Performance panneau (87,4&#8201;%)', html)
        # Bon pour accord — titre + mention manuscrite (espaces insécables)
        self.assertIn('Bon pour accord', html)
        self.assertIn(
            'Lu et approuvé — Signature précédée de « Bon pour accord »',
            html)

    def test_onepage_default_validity_literal_preserved(self):
        html = self._render({'pdf_mode': 'onepage'})
        self.assertIn('&#183; Validit&#233;&#160;: 30 jours', html)

    def test_editing_templates_changes_rendered_html(self):
        from apps.parametres.models_documents import DocumentTemplates
        tpl = DocumentTemplates.get(company=self.company)
        tpl.validite_badge_p1 = 'Validité : 45 jours'
        tpl.cgv_titre = 'MES CONDITIONS'
        tpl.cgv_bullets = ['Première puce', 'Acompte {acompte}&#37; à régler']
        tpl.garantie_titre = 'Garanties étendues'
        tpl.bpa_titre = 'ACCORD CLIENT'
        tpl.save()
        html = self._render()
        self.assertIn('Validité : 45 jours', html)
        self.assertIn('MES CONDITIONS', html)
        self.assertIn('Première puce', html)
        self.assertIn('Acompte 30&#37; à régler', html)
        self.assertIn('Garanties étendues', html)
        self.assertIn('ACCORD CLIENT', html)
        # Les littéraux remplacés ne subsistent pas
        self.assertNotIn('Validit&#233;&#160;: 30 jours', html)
        self.assertNotIn('Conditions générales du devis', html)

    def test_empty_template_falls_back_to_literal(self):
        """Un enregistrement existant mais VIDE = aucun changement (byte-identique)."""
        from apps.parametres.models_documents import DocumentTemplates
        DocumentTemplates.get(company=self.company)  # crée la ligne, tout vide
        html = self._render()
        self.assertIn('Conditions générales du devis', html)
        self.assertIn('Garanties jusqu&#8217;à 30 ans', html)

    def test_acceptance_stamp_only_when_accepted(self):
        # Non accepté → aucun tampon
        html = self._render()
        self.assertNotIn('Accepté le', html)
        # Accepté (nom + date) → tampon visible avec date FR
        import datetime
        self.devis.accepte_par_nom = 'Reda Kasri'
        self.devis.date_acceptation = datetime.date(2026, 6, 15)
        self.devis.save(update_fields=['accepte_par_nom', 'date_acceptation'])
        html2 = self._render()
        self.assertIn('Accepté le 15/06/2026 par Reda Kasri', html2)
        # Statuts du devis JAMAIS modifiés par le rendu (le moteur ne fait que
        # rendre) — le statut reste « brouillon ».
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'brouillon')

    def test_acceptance_stamp_absent_when_only_one_field_set(self):
        self.devis.accepte_par_nom = 'Reda Kasri'
        self.devis.save(update_fields=['accepte_par_nom'])
        html = self._render()
        self.assertNotIn('Accepté le', html)

    def test_acceptance_stamp_label_is_editable(self):
        import datetime
        from apps.parametres.models_documents import DocumentTemplates
        tpl = DocumentTemplates.get(company=self.company)
        tpl.acceptance_stamp = 'Signé le {date} — {nom}'
        tpl.save()
        self.devis.accepte_par_nom = 'Karim'
        self.devis.date_acceptation = datetime.date(2026, 1, 2)
        self.devis.save(update_fields=['accepte_par_nom', 'date_acceptation'])
        html = self._render()
        self.assertIn('Signé le 02/01/2026 — Karim', html)


class TestGeneratorQuoteFlow(TestCase):
    """End-to-end flow of the solar generator screen (/ventes/devis/nouveau):
    the screen creates a plain Devis via the REST API, then posts its lines via
    devis-lignes — exactly as exercised here. The created quote must get an
    auto-generated reference and must render the premium PDF in exactly 3 pages.
    """

    def setUp(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.api = APIClient()
        token = str(AccessToken.for_user(self.user))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def _create_via_api(self, lignes):
        resp = self.api.post('/api/django/ventes/devis/', {
            'client': self.client_obj.id,
            'statut': 'brouillon',
            'taux_tva': '20.00',
            'remise_globale': '0',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        devis_id = resp.data['id']
        for desig, qty, pu in lignes:
            produit = make_produit(self.company, desig, desig[:20], pu)
            line_resp = self.api.post('/api/django/ventes/devis-lignes/', {
                'devis': devis_id,
                'produit': produit.id,
                'designation': desig,
                'quantite': qty,
                'prix_unitaire': pu,
                'remise': '0',
            }, format='json')
            self.assertEqual(line_resp.status_code, 201, line_resp.data)
        return resp.data

    def test_api_created_devis_gets_auto_reference(self):
        from apps.ventes.models import Devis
        first = self._create_via_api([('Panneau mono 550W', '4', '1100')])
        ref1 = Devis.objects.get(pk=first['id']).reference
        self.assertRegex(ref1, r'^DEV-\d{6}-0001$')
        # Second create must not collide (regression: reference used to be '').
        resp = self.api.post('/api/django/ventes/devis/', {
            'client': self.client_obj.id,
            'statut': 'brouillon',
            'taux_tva': '20.00',
            'remise_globale': '0',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ref2 = Devis.objects.get(pk=resp.data['id']).reference
        self.assertRegex(ref2, r'^DEV-\d{6}-0002$')
        self.assertNotEqual(ref1, ref2)

    def test_generator_created_quote_renders_three_page_premium_pdf(self):
        """A quote shaped exactly like the generator's catalogue auto-fill
        (14 panels, both inverters, battery, structures, socles, power-priced
        accessories) must produce the premium PDF in exactly 3 pages."""
        from weasyprint import HTML
        from apps.ventes.models import Devis
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G

        created = self._create_via_api([
            ('Panneau mono 550W', '14', '1100'),
            ('Onduleur réseau 10kW', '1', '11700'),
            ('Onduleur hybride 5kW', '1', '24000'),
            ('Batterie 5 kWh', '2', '14000'),
            ('Structures acier', '14', '375'),
            ('Socles', '28', '67'),
            ('Accessoires', '1', '1666.67'),
            ('Tableau De Protection AC/DC', '1', '2500'),
            ('Installation', '1', '6000'),
            ('Transport', '1', '1000'),
        ])

        devis = Devis.objects.get(pk=created['id'])
        data = build_quote_data(devis)

        # Power must come from the panel line the generator wrote.
        self.assertEqual(data['nb_panneaux'], 14)
        self.assertEqual(data['watt_par_panneau'], 550)

        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_generator_flow_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig

        doc = HTML(string=cap['html']).render()
        self.assertEqual(
            len(doc.pages), 3,
            f'generator-created quote must render exactly 3 pages, got {len(doc.pages)}',
        )

    def test_catalogue_quote_renders_three_page_premium_pdf(self):
        """A quote composed from the seeded simulator catalogue (exactly what
        the generator's auto-fill produces for 14 panels x 710 W) must render
        the premium PDF in exactly 3 pages. Prices are the screen's TTC
        converted back to HT, as the save path does."""
        from django.core.management import call_command
        from weasyprint import HTML
        from apps.stock.models import Produit
        from apps.ventes.models import Devis
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G

        call_command('seed_catalogue', company_slug=self.company.slug)

        # Auto-fill output for 14 x 710 W (9.94 kWc), as saved by the screen:
        # (sku, qty, prix HT = TTC simulateur / 1.2)
        lines = [
            ('OND-R-HUA-10T', '1', None),       # 20 000 TTC
            ('OND-H-DEY-10T', '1', None),       # 28 000 TTC
            ('SMART-MET', '1', None),           # 1 800 TTC
            ('WIFI-DON', '1', None),            # 1 200 TTC
            ('PAN-CS-710', '14', None),         # 1 400 TTC
            ('BAT-DEY-10', '1', None),          # 30 000 TTC
            ('STR-ACIER', '14', None),          # 500 TTC
            ('SOC-BET', '28', None),            # 80 TTC
            ('ACC-CAT', '1', '1666.67'),        # formule : 2 blocs x 1000 TTC
            ('TAB-PROT', '1', '2500.00'),       # formule : 2 blocs x 1500 TTC
            ('INST-CAT', '1', '6000.00'),       # formule : 3 x 2400 TTC
            ('TRANS-CAT', '1', None),           # 1 000 TTC
        ]

        resp = self.api.post('/api/django/ventes/devis/', {
            'client': self.client_obj.id,
            'statut': 'brouillon',
            'taux_tva': '20.00',
            'remise_globale': '0',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        devis_id = resp.data['id']

        for sku, qty, prix_ht in lines:
            produit = Produit.objects.get(company=self.company, sku=sku)
            line_resp = self.api.post('/api/django/ventes/devis-lignes/', {
                'devis': devis_id,
                'produit': produit.id,
                'designation': produit.nom,
                'quantite': qty,
                'prix_unitaire': prix_ht or str(produit.prix_vente),
                'remise': '0',
            }, format='json')
            self.assertEqual(line_resp.status_code, 201, line_resp.data)

        devis = Devis.objects.get(pk=devis_id)
        data = build_quote_data(devis)

        # Power from the catalogue panel line; both options split correctly.
        self.assertEqual(data['nb_panneaux'], 14)
        self.assertEqual(data['watt_par_panneau'], 710)
        sans = [it['designation'] for it in data['sans_items']]
        avec = [it['designation'] for it in data['avec_items']]
        self.assertIn('Onduleur réseau Huawei 10kW Triphasé', sans)
        self.assertNotIn('Onduleur réseau Huawei 10kW Triphasé', avec)
        self.assertIn('Onduleur hybride Deye 10kW Triphasé', avec)
        self.assertIn('Batterie Deyness 10 kWh', avec)
        self.assertNotIn('Batterie Deyness 10 kWh', sans)
        # Option totals match the simulator for the same inputs (±1 MAD rounding)
        self.assertAlmostEqual(data['total_sans'], 65040, delta=1)
        self.assertAlmostEqual(data['total_avec'], 103040, delta=1)

        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_catalogue_quote_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig

        doc = HTML(string=cap['html']).render()
        self.assertEqual(
            len(doc.pages), 3,
            f'catalogue quote must render exactly 3 pages, got {len(doc.pages)}',
        )


def _residential_sample_data():
    """A minimal residential two-option quote dict for the residential renderer
    (built without the DB so the layout can be tested in isolation). Mirrors the
    shape `builder.build_quote_data` produces for a residentiel quote."""
    def _item(desig, q, ht, taux=20.0, marque=""):
        return {"designation": desig, "marque": marque, "description": "",
                "garantie": "", "quantite": float(q), "prix_unit_ht": float(ht),
                "prix_unit_ttc": round(float(ht) * (1 + taux / 100), 2),
                "taux_tva": float(taux)}

    def _totaux(rows):
        ht = round(sum(r["quantite"] * r["prix_unit_ht"] for r in rows), 2)
        buckets = {}
        for r in rows:
            buckets[r["taux_tva"]] = (
                buckets.get(r["taux_tva"], 0.0) + r["quantite"] * r["prix_unit_ht"])
        tpt = [{"taux": t, "montant": round(b * t / 100, 2), "ht_net": round(b, 2)}
               for t, b in sorted(buckets.items())]
        tva = round(sum(x["montant"] for x in tpt), 2)
        return {"ht_brut": ht, "remise": 0.0, "ht_net": ht, "tva": tva,
                "tva_par_taux": tpt, "ttc": round(ht + tva)}

    shared = [
        _item("Installation", 1, 6000), _item("Transport", 1, 1000),
        _item("Smart Meter", 1, 1500, marque="Huawei"),
        _item("Structures acier", 16, 417),
        _item("Panneau Canadien Solar 710W", 16, 1272.73, 10, marque="Canadian Solar"),
    ]
    sans = shared + [_item("Onduleur réseau Huawei 10kW Triphasé", 1, 16667, marque="Huawei")]
    avec = shared + [_item("Onduleur hybride Deye 10kW Triphasé", 1, 23333, marque="Deye"),
                     _item("Batterie Deyness 10 kWh", 1, 25000, marque="Deyness")]
    eco = 20953
    sf = [0.053, 0.062, 0.083, 0.098, 0.114, 0.116, 0.116, 0.101, 0.087, 0.070, 0.052, 0.048]
    eco_m = [round(eco * f) for f in sf]
    return {
        "ref": "DEV-202606-0071", "date": "21/06/2026",
        # deliberately lower-case + empty address to prove the display fixes
        "client_name": "meryem hida", "client_full": "meryem hida",
        "client_addr": "", "client_city": "Casablanca",
        "client_phone": "+212600000000", "inst_type": "Résidentielle",
        "puissance_kwc": 11.36, "nb_panneaux": 16, "watt_par_panneau": 710,
        "prod_kwh": 14086,
        "total_sans": _totaux(sans)["ttc"], "total_avec": _totaux(avec)["ttc"],
        "totaux_sans": _totaux(sans), "totaux_avec": _totaux(avec),
        "roi_s": 4.7, "roi_a": 5.1,
        "eco_s_ann": eco, "eco_a_ann": eco, "eco_a_cumul": eco,
        "eco_s_monthly": eco_m, "eco_a_monthly": eco_m,
        "factures_mensuelles": [round(v / 0.85) for v in eco_m],
        "sans_items": sans, "avec_items": avec,
        "sans_bullets": ["16 panneaux 710 W", "Onduleur réseau Huawei 10kW Triphasé",
                         "Smart Meter + monitoring"],
        "avec_bullets": ["16 panneaux 710 W", "Onduleur hybride Deye 10kW Triphasé",
                         "Batterie Deyness 10 kWh"],
        "scenario": "Les deux (Sans + Avec)", "recommended": "Avec batterie",
        "tva_note": "TVA : 10% panneaux photovoltaïques · 20% autres équipements et prestations",
        "payment_terms": {"acompte": 30, "materiel": 60, "solde": 10},
        "discount_pct": 0.0, "taux_tva": 20.0,
    }


@tag('pdf')
class TestResidentialRenderer(TestCase):
    """The redesigned residential 3-page proposal (the engine that renders a
    real residentiel quote). The legacy-engine page-count tests above don't
    exercise this renderer, so guard its layout + display polish here."""

    def _html_and_doc(self):
        from weasyprint import HTML
        from apps.ventes.quote_engine.residential import renderer, render
        d = renderer._augment(_residential_sample_data())
        html = render.build_html(d)
        return html, HTML(string=html).render()

    def test_residential_proposal_is_exactly_three_pages(self):
        _, doc = self._html_and_doc()
        self.assertEqual(
            len(doc.pages), 3,
            f'residential proposal must render exactly 3 pages, got {len(doc.pages)}')

    def test_render_pdf_bytes_smoke(self):
        from apps.ventes.quote_engine.residential import renderer
        pdf = renderer.render_pdf_bytes(_residential_sample_data())
        self.assertEqual(pdf[:4], b'%PDF')
        self.assertGreater(len(pdf), 5000)

    def test_client_name_is_display_cased_everywhere(self):
        """'meryem hida' is shown 'Meryem Hida' on the cover greeting and the
        signature block — never the raw lower-case input."""
        html, _ = self._html_and_doc()
        self.assertIn('Bonjour Meryem,', html)
        self.assertIn('Meryem Hida', html)
        self.assertNotIn('Bonjour meryem', html)

    def test_no_dangling_comma_when_address_empty(self):
        """An empty address must not leave a stray ', Casablanca' on the cover."""
        html, _ = self._html_and_doc()
        self.assertNotIn(', Casablanca', html)
        self.assertIn('Casablanca', html)

    def test_tangible_monthly_and_impact_framing_present(self):
        """Cover carries the per-month framing and the derived CO₂ impact line."""
        html, _ = self._html_and_doc()
        self.assertIn('MAD/mois', html)
        self.assertIn('CO', html)        # CO₂ impact strip
        self.assertIn('arbres', html)

    def test_equipment_lines_deep_link_to_fiche_pages(self):
        """Panels/inverters/battery/meter/dongle link to their /produits/<slug>
        fiche-technique page (slugs match docs/WEB_PLAN.md W119–W123); TAQINOR's
        own lines (structures, socles, installation…) stay plain text."""
        html, _ = self._html_and_doc()
        for slug in ('canadian-solar-710', 'onduleur-huawei-reseau',
                     'onduleur-deye-hybride', 'batterie-dyness',
                     'smart-meter-huawei', 'wifi-dongle-huawei'):
            self.assertIn(f'/produits/{slug}', html)
        # an own-component line is not turned into a datasheet link
        self.assertNotIn('produits/structures', html)

    def test_fiche_slug_mapping(self):
        from apps.ventes.quote_engine.residential import theme
        self.assertEqual(theme.fiche_slug('Panneau Canadien Solar 710W'),
                         'canadian-solar-710')
        self.assertEqual(theme.fiche_slug('Panneau Jinko 710W'), 'jinko-710')
        self.assertEqual(theme.fiche_slug('Onduleur hybride Deye 10kW'),
                         'onduleur-deye-hybride')
        self.assertEqual(theme.fiche_slug('Onduleur réseau Huawei 10kW'),
                         'onduleur-huawei-reseau')
        self.assertEqual(theme.fiche_slug('Batterie Deyness 10 kWh'),
                         'batterie-dyness')
        self.assertEqual(theme.fiche_slug('Structures acier'), '')
        self.assertEqual(theme.fiche_slug('Installation'), '')

    def test_scan_to_sign_qr_when_segno_available(self):
        """The scan-to-sign QR renders on page 3 (segno is a pinned dep). The
        renderer guards the import so a missing wheel degrades to the text link
        rather than breaking the PDF — so only assert when segno is importable."""
        html, _ = self._html_and_doc()
        # The textual sign link is ALWAYS present.
        self.assertIn('Signez en ligne', html)
        try:
            import segno  # noqa: F401
        except Exception:
            self.skipTest('segno not installed in this environment')
        self.assertIn('Scannez', html)
        self.assertIn('data:image/svg+xml', html)
