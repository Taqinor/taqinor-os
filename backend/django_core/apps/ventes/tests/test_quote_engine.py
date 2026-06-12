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

from django.test import TestCase
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


def make_devis(company, user, client, lignes, remise_globale='0'):
    devis = Devis.objects.create(
        company=company, reference='DEV-QE-0001', client=client,
        statut='brouillon', taux_tva=Decimal('20.00'),
        remise_globale=Decimal(remise_globale), created_by=user,
    )
    for desig, qty, pu in lignes:
        LigneDevis.objects.create(
            devis=devis, produit=make_produit(company, desig, desig[:20], pu),
            designation=desig, quantite=Decimal(qty),
            prix_unitaire=Decimal(pu), remise=Decimal('0'),
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

    def test_split_autoadds_battery_to_avec_only(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 550W', '8', '2000'),
            ('Onduleur reseau', '1', '14000'),
        ])
        data = build_quote_data(devis)
        sans = [it['designation'].lower() for it in data['sans_items']]
        avec = [it['designation'].lower() for it in data['avec_items']]
        # réseau inverter stays in Option 1; Option 2 drops it and gains a battery.
        self.assertTrue(any('reseau' in d or 'réseau' in d for d in sans))
        self.assertFalse(any('reseau' in d or 'réseau' in d for d in avec))
        self.assertTrue(any('batterie' in d for d in avec))
        self.assertFalse(any('batterie' in d for d in sans))

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
            ('Batterie 5 kWh', '1', '16000'),
        ])
        data = build_quote_data(devis)
        # Battery already present: sans excludes it, avec keeps the single one.
        self.assertEqual(len(data['sans_items']), 1)
        self.assertEqual(len(data['avec_items']), 2)
        batteries = [it for it in data['avec_items']
                     if 'batterie' in it['designation'].lower()]
        self.assertEqual(len(batteries), 1)

    def test_ttc_conversion_and_global_discount(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '10', '1000'),
        ], remise_globale='10')
        data = build_quote_data(devis)
        # 10 x 1000 HT x1.20 TTC = 12000 before; -10% global = 10800.
        self.assertEqual(data['total_sans_before'], 12000.0)
        self.assertEqual(data['discount_pct'], 10.0)
        self.assertEqual(data['total_sans'], 10800)


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

    def _render(self, pdf_options=None):
        from weasyprint import HTML
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G

        data = build_quote_data(self.devis, pdf_options)
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
