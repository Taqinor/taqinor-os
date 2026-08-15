"""
Tests for the premium quote engine (apps.ventes.quote_engine).

Covers the OS-quote -> data-dict mapping (power derivation, split-by-battery,
on-the-fly ROI) and a full premium PDF render with MinIO mocked.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_quote_engine -v 2
"""
import itertools
import re
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, tag
from django.contrib.auth import get_user_model

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()


# Compteur de tenants : une société NEUVE à chaque appel sans argument.
_company_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    """Une société neuve par appel — passer ``slug`` pour la nommer.

    Sans compteur, ce helper faisait un ``get_or_create`` sur un slug
    FIXE ('test-qe-co') : deux appels rendaient la MÊME ligne, et un test
    écrivant ``other = make_company()`` croyait fabriquer un second
    tenant sans en fabriquer aucun (assertion cross-tenant vide de sens).
    """
    from authentication.models import Company
    n = next(_company_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'test-qe-co-{n}',
        defaults={'nom': nom or f'Test QE Co {n}'},
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


# PV86 — DÉCLARATION d'alternative. Un document à deux options n'existe que
# lorsque le devis l'exprime : le générateur persiste TOUJOURS ce choix dans
# ``etude_params['scenario']`` (garantie QF7). Sans déclaration, un devis qui
# porte les deux onduleurs en lignes non optionnelles est un ARTEFACT de
# données (une seule réalité, total = somme de TOUTES ses lignes) — cf.
# ``test_pv86_verite_unique_devis``. Les fixtures ci-dessous qui testent
# réellement le DOCUMENT À DEUX OPTIONS déclarent donc ce que le générateur
# écrit en production ; leur rendu est inchangé au bit près.
DEUX_OPTIONS = {'scenario': 'Les deux (Sans + Avec)'}


def make_devis(company, user, client, lignes, remise_globale='0',
               reference='DEV-QE-0001', etude_params=None):
    devis = Devis.objects.create(
        company=company, reference=reference, client=client,
        statut='brouillon', taux_tva=Decimal('20.00'),
        remise_globale=Decimal(remise_globale), created_by=user,
        etude_params=etude_params,
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

    def test_real_catalogue_panel_reports_its_true_wattage(self):
        """Le devis auto utilise un VRAI panneau du catalogue : la désignation
        porte sa puissance (« Panneau Canadien Solar 710W ») et le moteur lit
        710 — jamais une valeur inventée."""
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Canadien Solar 710W', '10', '1400'),
            ('Onduleur réseau 8kW', '1', '14000'),
        ], reference='DEV-QE-REAL')
        data = build_quote_data(devis)
        self.assertEqual(data['nb_panneaux'], 10)
        self.assertEqual(data['watt_par_panneau'], 710)  # vraie puissance lue
        self.assertEqual(data['puissance_kwc'], 7.1)

    def test_unparseable_panel_defaults_to_catalogue_standard_not_stale_450(self):
        """Repli SÛR : une ligne panneau sans puissance lisible (ni désignation
        ni nom produit) ne doit PLUS inventer l'ancien 450 W obsolète — elle
        retombe sur le STANDARD du catalogue (710 W), panneau moderne réaliste.
        Garde la régression « pourquoi 450 W alors que la donnée est là ? »."""
        from apps.ventes.quote_engine import build_quote_data
        from apps.ventes.quote_engine.builder import _DEFAULT_WATT
        # désignation SANS chiffre de puissance + produit lié au même nom : aucun
        # wattage lisible → le repli s'applique.
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau photovoltaïque monocristallin', '12', '1400'),
            ('Onduleur réseau 8kW', '1', '14000'),
        ], reference='DEV-QE-NOWATT')
        data = build_quote_data(devis)
        self.assertEqual(data['nb_panneaux'], 12)
        # le repli est le standard catalogue, JAMAIS l'ancien 450 périmé
        self.assertEqual(_DEFAULT_WATT, 710)
        self.assertEqual(data['watt_par_panneau'], 710)
        self.assertNotEqual(data['watt_par_panneau'], 450)

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
        ], etude_params=DEUX_OPTIONS)
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

    def test_annexe_technique_adds_a_fourth_page(self):
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
            ('Batterie Deyness 10 kWh', '1', '25000', '20'),
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
        # PV86 — comme les 13 autres fixtures « document à deux options » : le
        # générateur DÉCLARE toujours son scénario (garantie QF7) ; sans la
        # déclaration, deux onduleurs non optionnels = artefact mono-option et
        # le split sans/avec n'existe plus.
        devis.etude_params = {**(devis.etude_params or {}), **DEUX_OPTIONS}
        devis.save(update_fields=['etude_params'])
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
        # QF9 — Smart Meter + Wifi Dongle (accessoires Huawei) restent sur
        # l'option réseau Huawei (sans) mais sont retirés de l'option hybride
        # Deye (avec).
        self.assertIn('Smart Meter', sans)
        self.assertIn('Wifi Dongle', sans)
        self.assertNotIn('Smart Meter', avec)
        self.assertNotIn('Wifi Dongle', avec)
        # Option totals match the simulator for the same inputs (±1 MAD rounding).
        # total_avec = ancien 103 040 − Smart Meter (1 800) − Wifi (1 200) Huawei.
        self.assertAlmostEqual(data['total_sans'], 65040, delta=1)
        self.assertAlmostEqual(data['total_avec'], 100040, delta=1)

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
        _item("Clé Wifi (dongle)", 1, 900, marque="Huawei"),
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
        fiche-technique page (slugs match docs/WEB_PLAN.md W141–W145); TAQINOR's
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

    def test_scan_to_sign_qr_when_qrcode_available(self):
        """The premium scan-to-sign QR renders on page 3 (qrcode is a pinned
        dep). The renderer guards the import so a missing wheel degrades to the
        text link rather than breaking the PDF — so only assert when qrcode is
        importable."""
        html, _ = self._html_and_doc()
        # The textual sign link is ALWAYS present.
        self.assertIn('Signez en ligne', html)
        try:
            import qrcode  # noqa: F401
        except Exception:
            self.skipTest('qrcode not installed in this environment')
        self.assertIn('Scannez', html)
        self.assertIn('data:image/png', html)


@tag('pdf')
class TestResidentialQRESRound(TestCase):
    """QRES — corrections du rendu résidentiel (audit fondateur 2026-07-17) :
    pagination JAMAIS débordée (le vrai devis DEV-202607-0021 rendait 4 pages
    physiques étiquetées « Page 3 / 3 »), lien de signature court, plus de
    scénario batterie fantôme sur un devis mono-option, garanties à source
    unique, bande légale alignée sur le pied de page, méta client dédoublonnée."""

    def _render(self, variant):
        from weasyprint import HTML
        from apps.ventes.quote_engine.residential import (
            renderer, render, sample_data)
        d = renderer._augment(sample_data.build(variant))
        html = render.build_html(d)
        return html, HTML(string=html).render()

    # QRES17/49/57 — nombre de pages ATTENDU par fixture : un devis de la
    # taille réelle du fondateur (« plus5 », ~13 lignes) tient en 3 pages AVEC
    # la grande courbe (cartes badges et ligne fiches retirées de la page 2) ;
    # seuls les très gros devis (« plus10 ») passent en 4 pages (tableau à
    # l'aise + page rentabilité dédiée).
    EXPECTED_PAGES = {"deux": 3, "sans": 3, "long": 3, "plus5": 3,
                      "plus10": 4}

    def test_page_count_per_variant_never_overflows_dirty(self):
        """La garde anti-débordement : chaque fixture rend EXACTEMENT le
        nombre de pages prévu — le bloc signature ne bascule plus jamais sur
        une page orpheline, et un devis chargé AJOUTE une page proprement."""
        from apps.ventes.quote_engine.residential import sample_data
        for variant in sample_data.keys():
            _, doc = self._render(variant)
            self.assertEqual(
                len(doc.pages), self.EXPECTED_PAGES[variant],
                f'variant {variant!r}: expected '
                f'{self.EXPECTED_PAGES[variant]} pages, got {len(doc.pages)}')

    def test_overflow_quote_paginates_cleanly(self):
        """Devis très chargé (« plus10 ») : 4 pages numérotées « / 4 »,
        TOUTES les lignes du devis présentes (aucune avalée par le
        découpage), la page rentabilité dédiée existe et porte la bande de
        financement (QRES50)."""
        import fitz
        from apps.ventes.quote_engine.residential import renderer, sample_data
        for variant in ("plus10",):
            data = sample_data.build(variant)
            pdf = renderer.render_pdf_bytes(data)
            doc = fitz.open(stream=pdf, filetype='pdf')
            self.assertEqual(len(doc), 4, variant)
            all_text = "\n".join(p.get_text() for p in doc)
            for it in data["sans_items"]:
                frag = it["designation"].split(" (")[0][:25]
                self.assertIn(frag, all_text,
                              f'{variant}: ligne perdue par le découpage : '
                              f'{frag!r}')
            self.assertIn("Page 2 / 4", all_text)
            self.assertIn("Page 4 / 4", all_text)
            self.assertIn("Rentabilité de votre investissement", all_text)
            self.assertIn("Dans votre poche", all_text)

    def test_bottom_content_never_silently_clipped(self):
        """Le cadre .page (A4 fixe, overflow:hidden) peut ROGNER sans faire de
        4ᵉ page : une page 3 trop haute perdait silencieusement la bande légale
        (SARLAU/RC/ICE). On rastérise le VRAI PDF (chemin complet, distribution
        élastique QRES62 incluse) et on exige la bande légale + la clause
        non-contractuelle physiquement sur la dernière page."""
        import fitz
        from apps.ventes.quote_engine.residential import renderer, sample_data
        for variant in sample_data.keys():
            pdf = renderer.render_pdf_bytes(sample_data.build(variant))
            doc = fitz.open(stream=pdf, filetype='pdf')
            last = doc[-1].get_text()
            self.assertIn('SARLAU', last,
                          f'variant {variant!r}: legal band clipped off page 3')
            self.assertIn('non contractuelles', last,
                          f'variant {variant!r}: disclaimer clause clipped')

    def test_no_page_ends_with_a_large_void(self):
        """QRES62 — distribution dynamique de l'espace : après le second
        passage (mesure du PDF réel → joints élastiques), plus AUCUNE page ne
        garde un vide résiduel exploitable > 12 mm — le « petit espace en bas »
        signalé par le fondateur ne peut pas revenir, quel que soit le nombre
        de pages du devis."""
        from apps.ventes.quote_engine.residential import renderer, sample_data
        for variant in sample_data.keys():
            pdf = renderer.render_pdf_bytes(sample_data.build(variant))
            residual = renderer._measure_page_slack(pdf)
            self.assertTrue(
                all(v <= 12 for v in residual.values()),
                f'variant {variant!r}: residual voids {residual}')

    def test_hypotheses_live_on_the_web_proposal_not_the_pdf(self):
        """QRES61 (fondateur) — les hypothèses de calcul quittent le papier :
        plus de bande « Nos hypothèses » dans le PDF (la proposition en ligne
        les porte, WJ32/W359) ; le papier garde UNE clause non-contractuelle
        qui y renvoie."""
        html, _ = self._render("deux")
        self.assertNotIn("p3-hyp", html)
        self.assertNotIn("Nos hypothèses", html)
        self.assertIn("Estimations non contractuelles", html)
        self.assertIn("proposition en ligne", html)

    def test_sign_link_token_never_displayed_as_text(self):
        """Le lien tokenisé vit dans le href et le QR ; le bouton n'affiche que
        « hôte/segment » (l'URL complète débordait sous le QR)."""
        html, _ = self._render("deux")
        token_tail = "rKJtbjsY-qTML35ZnjQ9Lt_v4_demo"
        self.assertEqual(html.count(token_tail), 1)          # href uniquement
        self.assertIn("Signez en ligne", html)
        self.assertIn("taqinor.ma/proposition</a>", html)

    def test_mono_option_has_no_phantom_battery_scenario(self):
        """Un devis réseau seul ne mentionne plus « Avec batterie » ni « deux
        scénarios » nulle part (cartes, sous-titre du graphe, accord)."""
        html, _ = self._render("sans")
        self.assertNotIn("deux scénarios", html)
        self.assertNotIn("Avec batterie", html)

    def test_warranties_single_source(self):
        """theme.WARRANTIES est LA source : badges en page 2, bande de
        crédibilité page 1 alignée (30 ans performance — plus aucun
        « Garantie 25 ans » contradictoire)."""
        from apps.ventes.quote_engine.residential import theme
        html, _ = self._render("deux")
        for _n, _u, label, _sub in theme.WARRANTIES:
            self.assertIn(label, html)
        self.assertIn("Performance garantie 30 ans", html)
        self.assertNotIn("Garantie 25 ans", html)
        self.assertNotIn("garantie sur 25 ans", html)

    def test_legal_band_contact_matches_footer(self):
        """La bande légale lit l'identité résolue : même email que le pied de
        page (le PDF réel imprimait .ma en pied et .com dans la bande)."""
        html, _ = self._render("deux")   # profil TAQINOR avec contact@taqinor.ma
        self.assertNotIn("contact@taqinor.com", html)
        self.assertGreaterEqual(html.count("contact@taqinor.ma"), 2)

    def test_hypotheses_deduplicated_by_builder_shape(self):
        """La fixture (miroir du builder corrigé) ne porte plus qu'UNE mention
        de la loi 82-21 dans les hypothèses — servies à la proposition EN
        LIGNE (le PDF ne les rend plus, QRES61)."""
        from apps.ventes.quote_engine.residential import sample_data
        items = sample_data.build("deux")["hypotheses"]["items"]
        self.assertEqual(sum("82-21" in i for i in items), 1)

    def test_join_meta_dedups_repeated_fragments(self):
        """« casablanca, casablanca · casablanca » → « casablanca » (l'adresse
        saisie contient souvent déjà la ville)."""
        from apps.ventes.quote_engine.residential import theme
        self.assertEqual(
            theme.join_meta("casablanca, casablanca", "casablanca",
                            "+212661850412"),
            "casablanca · +212661850412")
        self.assertEqual(
            theme.join_meta("12 rue des Orangers", "Casablanca",
                            "+212600000000"),
            "12 rue des Orangers · Casablanca · +212600000000")

    def test_builder_hypotheses_mention_8221_once(self):
        """Le builder réel dédoublonne : une seule formulation 82-21 dans le
        bloc hypothèses (il en cumulait deux, plus celle de la méthode)."""
        from apps.ventes.quote_engine.pricing import cashflow_assumptions
        notes = cashflow_assumptions()["notes"]
        self.assertTrue(any("82-21" in n for n in notes))
        self.assertTrue(any("injection" in n.lower() for n in notes))
        # plus de décimale anglaise dans les notes rendues au client
        joined = " ".join(notes)
        self.assertNotIn("0.5", joined)
        self.assertNotIn("2.0", joined)


class TestCanonicalProductible(TestCase):
    """QX38 — un seul modèle de productible (PVGIS par ville), partagé par
    l'écran, le PDF et la proposition web. CompanyProfile.productible (1600)
    devient un override, pas un modèle concurrent ; le barème ONEE est aligné.
    """

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def test_productible_lookup_per_city(self):
        from apps.ventes.quote_engine.productible import (
            productible_for_city, PRODUCTIBLE_PAR_VILLE, DEFAULT_PRODUCTIBLE)
        self.assertEqual(productible_for_city('Agadir'), 1687)
        self.assertEqual(productible_for_city('agadir'), 1687)
        self.assertEqual(productible_for_city('Casablanca'),
                         PRODUCTIBLE_PAR_VILLE['casablanca'])
        # ville inconnue → repli central (jamais un chiffre inventé)
        self.assertEqual(productible_for_city('Oujda'), DEFAULT_PRODUCTIBLE)
        # alias secondaire → ville de référence
        self.assertEqual(productible_for_city('Kenitra'),
                         PRODUCTIBLE_PAR_VILLE['rabat'])

    def test_company_override_beats_pvgis_only_when_non_default(self):
        from apps.ventes.quote_engine.productible import productible_for_city
        # override = défaut historique 1600 → on lit le PVGIS de la ville
        self.assertEqual(productible_for_city('Agadir', override=1600), 1687)
        # override société explicite (≠ 1600) → il prime
        self.assertEqual(productible_for_city('Agadir', override=1750), 1750)

    def test_builder_uses_city_productible_for_production(self):
        from apps.crm.models import Lead
        from apps.ventes.quote_engine.builder import build_quote_data
        lead = Lead.objects.create(
            company=self.company, nom='Agadiri', ville='Agadir')
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Canadien Solar 710W', '10', '1272.73'),
            ('Onduleur réseau 8kW', '1', '14000'),
        ], reference='DEV-QX38-1')
        devis.lead = lead
        devis.save(update_fields=['lead'])
        data = build_quote_data(devis)
        # QRES54 — 7,1 kWc × 1687 (Agadir PVGIS) × 0,86 (pertes système 14 %)
        from apps.ventes.quote_engine.pricing import PRODUCTION_DERATE
        self.assertEqual(data['puissance_kwc'], 7.1)
        self.assertEqual(data['prod_kwh'],
                         round(7.1 * 1687 * PRODUCTION_DERATE))

    def test_onee_tranche_ceilings_aligned(self):
        """QX38 — les plafonds ONEE représentent les vraies bandes cumulées
        (100 / 250 / 400 / ∞), plus la bande 101-250 écrasée."""
        from apps.ventes.quote_engine.pricing import ONEE_TRANCHES
        ceilings = [c for c, _ in ONEE_TRANCHES]
        self.assertEqual(ceilings, [100, 250, 400, None])


class TestHonestCashflowPayback(TestCase):
    """QX39 — payback par cashflow 25 ans (dégradation/escalade/batterie/
    onduleur), croisement du cumul à zéro, hypothèses rendues sur le PDF."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def test_cashflow_payback_zero_crossing(self):
        from apps.ventes.quote_engine.pricing import compute_cashflow_payback
        cf = compute_cashflow_payback(50000, 10000)
        # 25 années de cumul, payback interpolé au croisement de zéro
        self.assertEqual(len(cf['cumulative']), 25)
        self.assertGreater(cf['payback_years'], 0)
        self.assertLess(cf['payback_years'], 25)
        # le cumul est croissant puis positif (rentabilisé)
        self.assertLess(cf['cumulative'][0], 0)
        self.assertGreater(cf['cumulative'][-1], 0)
        self.assertGreater(cf['net_gain'], 0)

    def test_degenerate_inputs_return_zero(self):
        from apps.ventes.quote_engine.pricing import compute_cashflow_payback
        self.assertEqual(compute_cashflow_payback(0, 10000)['payback_years'], 0.0)
        self.assertEqual(compute_cashflow_payback(50000, 0)['payback_years'], 0.0)

    def test_battery_roundtrip_lengthens_payback(self):
        from apps.ventes.quote_engine.pricing import compute_cashflow_payback
        cf_no = compute_cashflow_payback(50000, 10000)
        cf_bat = compute_cashflow_payback(50000, 10000, battery=True)
        # le rendement aller-retour < 1 réduit l'économie → payback plus long
        self.assertGreaterEqual(cf_bat['payback_years'], cf_no['payback_years'])

    def test_assumptions_block_documented(self):
        from apps.ventes.quote_engine.pricing import cashflow_assumptions
        a = cashflow_assumptions()
        self.assertEqual(a['years'], 25)
        self.assertEqual(a['degradation_pct'], 0.5)
        # QRES54 (fondateur) — AUCUNE hausse tarifaire supposée : la projection
        # est à tarif constant, seule la dégradation érode les économies.
        self.assertEqual(a['escalation_pct'], 0.0)
        self.assertTrue(any('82-21' in n for n in a['notes']))
        self.assertTrue(any('injection' in n.lower() for n in a['notes']))

    def test_builder_roi_from_cashflow_and_assumptions_rendered(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Canadien Solar 710W', '14', '1272.73'),
            ('Onduleur réseau Huawei 10kW', '1', '16666.67'),
        ], reference='DEV-QX39-1')
        data = build_quote_data(devis)
        # le cumul du cashflow est porté dans les données de rendu
        self.assertIsNotNone(data.get('cashflow_sans'))
        self.assertEqual(len(data['cashflow_sans']), 25)
        # les hypothèses documentées apparaissent dans le bloc « Nos hypothèses »
        items = ' '.join(data['hypotheses']['items'])
        self.assertIn('82-21', items)
        self.assertIn('gradation', items.replace('é', 'e'))


class TestQuoteNumbersHonestyPack(TestCase):
    """QX7 — pack d'honnêteté des chiffres du PDF : couverture réelle (a),
    échéancier custom sans case morte (b), ville résolue depuis le lead (c),
    marques dérivées des vraies lignes (e). Sous-item (d) hors périmètre
    (public_views, autre lane)."""

    FULL_LINES = [
        ('Onduleur réseau 10kW', '1', '11700'),
        ('Onduleur hybride 5kW', '1', '24000'),
        ('Panneau mono 550W', '14', '1100'),
        ('Batterie 5 kWh', '1', '14000'),
        ('Structures acier', '14', '375'),
        ('Installation', '1', '4000'),
    ]

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _render_legacy(self, pdf_options=None, devis=None):
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G
        data = build_quote_data(devis or self._devis(), pdf_options)
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_qx7_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return cap['html']

    def _devis(self, ref='DEV-QX7-0'):
        # PV86 — document à deux options : le devis le DÉCLARE (générateur).
        return make_devis(self.company, self.user, self.client_obj,
                          self.FULL_LINES, reference=ref,
                          etude_params=dict(DEUX_OPTIONS))

    # ── (a) couverture ──────────────────────────────────────────────────────
    def test_coverage_uses_real_consumption_when_known(self):
        """Avec une conso réelle (étude), la couverture = prod/conso, pas un
        diviseur /1.3 fabriqué, et n'est plus étiquetée « estimation »."""
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine.residential import renderer
        devis = self._devis(ref='DEV-QX7-COV')
        devis.etude_params = {**DEUX_OPTIONS, 'conso_annuelle': 12000,
                              'distributeur': 'onee'}
        devis.save(update_fields=['etude_params'])
        data = build_quote_data(devis)
        self.assertEqual(data['conso_annuelle_kwh'], 12000)
        d = renderer._augment(data)
        self.assertFalse(d['coverage_estimated'])
        # couverture = prod/conso arrondie, jamais planchée à 40
        self.assertEqual(d['coverage_pct'],
                         min(100, max(1, round(data['prod_kwh'] / 12000 * 100))))

    def test_coverage_flagged_estimation_without_real_conso(self):
        """Sans conso réelle, la couverture est dérivée honnêtement et
        étiquetée « estimation » (drapeau vrai)."""
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine.residential import renderer
        data = build_quote_data(self._devis(ref='DEV-QX7-EST'))
        self.assertIsNone(data['conso_annuelle_kwh'])
        d = renderer._augment(data)
        self.assertTrue(d['coverage_estimated'])

    # ── (b) échéancier custom sans case morte ───────────────────────────────
    def test_custom_acompte_full_collapses_to_two_boxes(self):
        """Un acompte custom qui absorbe la tranche matériel → échéancier à
        DEUX cases (Acompte + Solde), jamais une case « Matériel » à 0 %."""
        devis = self._devis(ref='DEV-QX7-ACPT')
        # acompte custom énorme → materiel clampé à 0
        html = self._render_legacy(
            {'devis_final': True, 'payment_mode': 'custom',
             'custom_acompte': 999999}, devis=devis)
        self.assertIn('Modalit', html)                    # bloc présent
        # aucune case « Matériel » morte
        self.assertNotIn('Avant installation', html)
        self.assertIn('la livraison', html)               # solde à la livraison
        # pas de « 0% » orphelin dans une case de paiement
        self.assertNotIn('>0%</div>', html)

    def test_standard_payment_keeps_three_boxes(self):
        """Chemin standard (materiel > 0) : trois cases, rendu inchangé."""
        html = self._render_legacy(
            {'devis_final': True}, devis=self._devis(ref='DEV-QX7-STD'))
        self.assertIn('Avant installation', html)         # case Matériel présente
        self.assertIn('Acompte', html)
        self.assertIn('Solde', html)

    # ── (c) ville résolue depuis le lead ────────────────────────────────────
    def test_client_city_resolved_from_lead_ville(self):
        from apps.crm.models import Lead
        from apps.ventes.quote_engine.builder import build_quote_data
        lead = Lead.objects.create(
            company=self.company, nom='Bennani', ville='Agadir')
        devis = self._devis(ref='DEV-QX7-CITY')
        devis.lead = lead
        devis.save(update_fields=['lead'])
        data = build_quote_data(devis)
        self.assertEqual(data['client_city'], 'Agadir')

    def test_client_city_empty_without_lead(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(self._devis(ref='DEV-QX7-NOCITY'))
        self.assertEqual(data['client_city'], '')

    # ── (e) marques dérivées des vraies lignes ──────────────────────────────
    #
    # 2026-08-14 — POURQUOI CES DEUX GARDES ONT CHANGÉ D'ANCRAGE.
    # Elles épinglaient le libellé « Équipements premium certifiés [IEC] » de la
    # rangée de puces de la page 3. Cette rangée PAR DÉFAUT a été retirée du
    # moteur par QRES57 (commit b2e188a2, directive fondateur du 18/07/2026 :
    # elle répétait mot pour mot le ruban de crédibilité de la page 1) ; elle ne
    # subsiste que pour une société ayant personnalisé ``doc_texts.trust_values``.
    # Les assertions ne pouvaient donc plus passer — le PDF, lui, est correct.
    # L'EXIGENCE QX7(e) n'a pas bougé d'un pouce : une marque imprimée doit
    # VENIR D'UNE VRAIE LIGNE du devis, jamais d'une liste gravée dans le
    # moteur. Elle est ré-épinglée sur le SEUL endroit du PDF qui imprime encore
    # une marque : la pastille ``<span class="p2-mk">`` du tableau d'équipement
    # (``residential/options.py::_row``), alimentée par ``item['marque']``,
    # lui-même lu sur ``Produit.marque`` (``builder._line_to_item``).
    _MARQUE_CHIP_RE = re.compile(r'<span class="p2-mk">([^<]*)</span>')

    def _marques_imprimees(self, html):
        """Ensemble des marques réellement IMPRIMÉES sur le PDF."""
        return {m.strip() for m in self._MARQUE_CHIP_RE.findall(html)
                if m.strip()}

    def _marques_du_devis(self, data):
        """Ensemble des marques portées par les VRAIES lignes du devis."""
        lignes = (data.get('sans_items') or []) + (data.get('avec_items') or [])
        return {(it.get('marque') or '').strip() for it in lignes
                if (it.get('marque') or '').strip()}

    @tag('pdf')
    def test_brand_chips_derive_from_real_line_marques(self):
        from apps.ventes.quote_engine.residential import renderer, render
        from apps.ventes.quote_engine.builder import build_quote_data
        # produits porteurs de marques réelles distinctives
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Canadien Solar 710W', '14', '1272.73'),
            ('Onduleur réseau Huawei 10kW', '1', '16666.67'),
            ('Onduleur hybride Deye 10kW', '1', '23333.33'),
            ('Batterie Deyness 10 kWh', '1', '25000'),
            ('Installation', '1', '4000'),
        ], reference='DEV-QX7-BRAND', etude_params=DEUX_OPTIONS)
        for li in devis.lignes.all():
            if 'Canadien' in li.designation:
                li.produit.marque = 'Canadian Solar'
            elif 'Huawei' in li.designation:
                li.produit.marque = 'Huawei'
            elif 'Deye' in li.designation:
                li.produit.marque = 'Deye'
            elif 'Deyness' in li.designation:
                li.produit.marque = 'Deyness'
            li.produit.save(update_fields=['marque'])
        data = build_quote_data(devis)
        html = render.build_html(renderer._augment(data))
        imprimees = self._marques_imprimees(html)
        # Le panneau porte la marque PRODUIT « Canadian Solar » alors que sa
        # DÉSIGNATION dit « Canadien Solar » : la pastille imprimée ne peut donc
        # venir que de la vraie donnée produit, jamais d'un mot lu dans le
        # libellé de la ligne. C'est le cœur de la garde (a).
        self.assertIn('Canadian Solar', imprimees)
        self.assertNotIn('Canadien Solar', imprimees)
        # (b) et AUCUNE marque inventée : tout ce qui est imprimé est porté par
        # une ligne réelle du devis.
        self.assertTrue(
            imprimees <= self._marques_du_devis(data),
            f'marques imprimées hors des lignes du devis : '
            f'{imprimees - self._marques_du_devis(data)}')

    @tag('pdf')
    def test_brand_chip_falls_back_to_iec_without_marques(self):
        from apps.ventes.quote_engine.residential import renderer, render
        from apps.ventes.quote_engine.builder import build_quote_data
        # lignes sans AUCUNE marque → le moteur n'en invente pas une
        devis = self._devis(ref='DEV-QX7-NOBRAND')
        for li in devis.lignes.all():
            li.produit.marque = ''
            li.produit.save(update_fields=['marque'])
        data = build_quote_data(devis)
        # précondition du scénario : plus une seule marque dans les données
        self.assertEqual(self._marques_du_devis(data), set())
        html = render.build_html(renderer._augment(data))
        # … donc plus une seule pastille de marque sur le PDF client.
        self.assertEqual(self._marques_imprimees(html), set())


@tag('pdf')
class TestResidentialWarmPathCache(TestCase):
    """QX8 — chemin chaud : polices/logo/graphiques + octets PDF sont mis en
    cache. Un second rendu du MÊME devis inchangé réutilise le travail (aucun
    recalcul de graphiques) et produit des octets byte-identiques.
    """

    def test_font_and_logo_helpers_are_cached_pure(self):
        from apps.ventes.quote_engine.residential import theme
        # lru_cache présent → cache_info() disponible et effectif
        theme.font_face_css.cache_clear()
        theme.logo_dark_b64.cache_clear()
        theme.logo_color_b64.cache_clear()
        a = theme.font_face_css()
        b = theme.font_face_css()
        self.assertEqual(a, b)
        self.assertEqual(theme.font_face_css.cache_info().misses, 1)
        self.assertGreaterEqual(theme.font_face_css.cache_info().hits, 1)
        # le logo recoloré (boucle par pixel) n'est calculé qu'une fois
        theme.logo_dark_b64()
        theme.logo_dark_b64()
        self.assertEqual(theme.logo_dark_b64.cache_info().misses, 1)

    # 2026-08-14 — POURQUOI ON COMPTE UN ÉCART ET PLUS UN NOMBRE ABSOLU.
    # Ces deux gardes exigeaient littéralement 1 et 2 appels à ``charts.build_all``.
    # QRES62 (commit 307575f7) a introduit le rendu EN DEUX PASSES dans
    # ``renderer.render_pdf_bytes`` (passe 1 → mesure du vide résiduel réel du
    # PDF → passe 2 avec les joints élastiques dimensionnés), et chaque passe
    # rappelle ``render.build_html`` → ``build_ctx`` → ``charts.build_all``.
    # Un rendu À FROID coûte donc 2 appels au lieu de 1 : la CI observait 2 != 1
    # et 4 != 2 — soit EXACTEMENT le double, la preuve que le cache marche
    # toujours. Le nombre de passes est un détail de mise en page (il retombe
    # même à 1 si PyMuPDF est absent : ``_measure_page_slack`` renvoie {}) ;
    # l'EXIGENCE QX8, elle, est un ÉCART : un second rendu du même devis ne
    # coûte RIEN, un devis édité recoûte un vrai rendu. C'est ce qu'on mesure
    # maintenant — la garde mord donc quel que soit le nombre de passes.
    def test_second_render_reuses_bytes_and_skips_chart_work(self):
        from unittest.mock import patch
        from apps.ventes.quote_engine.residential import renderer
        from apps.ventes.quote_engine.residential import charts as charts_mod
        data = _residential_sample_data()

        # vide le cache PDF pour un décompte déterministe
        renderer._PDF_CACHE.clear()

        real_build_all = charts_mod.build_all
        with patch.object(charts_mod, 'build_all',
                          side_effect=real_build_all) as spy:
            pdf1 = renderer.render_pdf_bytes(data)
            apres_froid = spy.call_count
            pdf2 = renderer.render_pdf_bytes(data)
            apres_chaud = spy.call_count
        # le rendu à froid calcule bien les graphiques…
        self.assertGreaterEqual(apres_froid, 1)
        # … et le second rendu est servi depuis le cache : ZÉRO travail de
        # graphique en plus (si le cache régressait, apres_chaud doublerait).
        self.assertEqual(apres_chaud, apres_froid)
        # octets byte-identiques
        self.assertEqual(pdf1, pdf2)
        self.assertEqual(pdf1[:4], b'%PDF')

    def test_edited_devis_forces_a_real_rerender(self):
        from unittest.mock import patch
        from apps.ventes.quote_engine.residential import renderer
        from apps.ventes.quote_engine.residential import charts as charts_mod
        renderer._PDF_CACHE.clear()
        data = _residential_sample_data()
        data2 = _residential_sample_data()
        data2["ref"] = "DEV-202606-9999"   # une édition change l'empreinte
        real = charts_mod.build_all
        with patch.object(charts_mod, 'build_all', side_effect=real) as spy:
            renderer.render_pdf_bytes(data)
            apres_froid = spy.call_count
            renderer.render_pdf_bytes(data2)
            apres_edition = spy.call_count
        # empreintes différentes → un VRAI second rendu, du même coût que le
        # premier (jamais un PDF périmé servi depuis le cache).
        self.assertGreaterEqual(apres_froid, 1)
        self.assertEqual(apres_edition, 2 * apres_froid)


class TestQuoteSignLinkAndPageNumbers(TestCase):
    """QX6 — le CTA de signature pointe vers la VRAIE proposition tokenisée
    (ShareLink), plus l'ancien /signer/<ref> 404 ; le pied de page n'a plus de
    « / 3 » codé en dur (il lit le nombre réel de pages rendues)."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _resid_devis(self):
        return make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Canadien Solar 710W', '14', '1272.73'),
            ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67'),
            ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33'),
            ('Batterie Deyness 10 kWh', '1', '25000'),
            ('Installation', '1', '4000'),
        ], reference='DEV-QX6-1', etude_params=DEUX_OPTIONS)

    def test_builder_mints_tokenized_signer_link(self):
        from apps.ventes.models import ShareLink
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._resid_devis()
        data = build_quote_data(devis)
        signer = (data.get("links") or {}).get("signer", "")
        self.assertIn('/proposition/', signer)
        # le lien porte le token d'un vrai ShareLink de ce devis
        link = ShareLink.for_devis(devis)
        self.assertIn(link.token, signer)
        # plus jamais l'ancien chemin inventé /signer/<ref>
        self.assertNotIn('/signer/', signer)

    def test_signer_link_reused_not_duplicated(self):
        from apps.ventes.models import ShareLink
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._resid_devis()
        build_quote_data(devis)
        build_quote_data(devis)
        # un seul ShareLink valide par devis (réutilisé, pas dupliqué)
        self.assertEqual(
            ShareLink.objects.filter(devis=devis).count(), 1)

    @tag('pdf')
    def test_rendered_pdf_qr_points_at_live_proposal(self):
        from apps.ventes.quote_engine.residential import renderer, render
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.models import ShareLink
        devis = self._resid_devis()
        data = build_quote_data(devis)
        html = render.build_html(renderer._augment(data))
        link = ShareLink.for_devis(devis)
        # le lien texte « Signez en ligne » pointe vers la proposition tokenisée
        # PV84 — chemin partagé : slug du client ('Alaoui Karim', make_client)
        # devant le token.
        self.assertIn(f'/proposition/alaoui-karim/{link.token}', html)
        self.assertNotIn('taqinor.ma/signer/', html)

    @tag('pdf')
    def test_footer_page_total_matches_real_pages(self):
        from apps.ventes.quote_engine.residential import renderer, render
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._resid_devis()
        html = render.build_html(renderer._augment(build_quote_data(devis)))
        # le pied affiche « Page N / 3 » = nombre RÉEL de pages (résidentiel = 3)
        self.assertIn('Page 1 / 3', html)
        self.assertIn('Page 3 / 3', html)


@tag('pdf')
class TestResidentialSingleOptionGate(TestCase):
    """QX5 — jamais d'option fantôme : un devis résidentiel mono-option rend
    UNE seule carte partout (page 1 pleine largeur, page 2 sans découpage
    delta, en-tête « commun aux deux options » renommé). Un devis à deux
    options reste inchangé (les tests de nombre de pages ci-dessus le prouvent).
    """

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _resid_html(self, devis):
        from apps.ventes.quote_engine.residential import renderer, render
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(devis)
        # mode résidentiel par défaut → renderer résidentiel
        d = renderer._augment(data)
        return render.build_html(d)

    def _avec_only_devis(self):
        # hybride + batterie + panneaux, AUCUN onduleur réseau → une seule
        # option réelle (« Avec batterie »).
        return make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Canadien Solar 710W', '12', '1272.73'),
            ('Onduleur hybride Deye 5kW', '1', '24000'),
            ('Batterie Deyness 10 kWh', '1', '25000'),
            ('Structures acier', '12', '417'),
            ('Installation', '1', '5000'),
        ], reference='DEV-QX5-AVEC')

    def test_battery_only_quote_shows_single_option_everywhere(self):
        from weasyprint import HTML
        devis = self._avec_only_devis()
        html = self._resid_html(devis)
        doc = HTML(string=html).render()
        # toujours 3 pages (le format n'a pas changé)
        self.assertEqual(len(doc.pages), 3)
        # page 1 : PAS de carte « Option 1 » / « Option 2 » fabriquée
        self.assertNotIn('Option 1', html)
        self.assertNotIn('Option 2', html)
        # page 2 : l'en-tête « commun aux deux options » est renommé
        self.assertNotIn('Équipement commun aux deux options', html)
        self.assertIn('Votre équipement', html)
        # page 2 : aucun bloc delta (cf. note d'ancrage sur le test à deux
        # options ci-dessous — cette assertion était devenue VIDE DE SENS,
        # elle interdisait un marqueur que le moteur ne rend plus depuis
        # QRES27 ; elle mord de nouveau sur le bloc réellement rendu).
        self.assertNotIn('<div class="p2-deltas">', html)
        self.assertNotIn('Spécifique à l&rsquo;option 1', html)
        # aucune option « Sans batterie » fantôme (dépourvue d'onduleur)
        self.assertNotIn('Sans batterie', html)
        # l'option réelle est bien présente
        self.assertIn('Avec batterie', html)

    def test_two_option_quote_keeps_both_cards(self):
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Canadien Solar 710W', '14', '1272.73'),
            ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67'),
            ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33'),
            ('Batterie Deyness 10 kWh', '1', '25000'),
            ('Installation', '1', '4000'),
        ], reference='DEV-QX5-DEUX', etude_params=DEUX_OPTIONS)
        html = self._resid_html(devis)
        # deux options → les deux cartes + le découpage delta subsistent
        self.assertIn('Option 1', html)
        self.assertIn('Option 2', html)
        self.assertIn('Équipement commun aux deux options', html)
        # 2026-08-14 — l'ancien marqueur ``<small>ajoute</small>`` a disparu du
        # moteur avec QRES27 (commit db7ff60f) : les en-têtes des deux cartes
        # delta ont été recomposés en « Spécifique à l'option N — … » (le mot
        # « ajoute » pendait sous la barre or et le contraste blanc-sur-#F5A623
        # était mauvais). La garde QX5 épinglait ce marqueur mort ; elle est
        # ré-ancrée sur le bloc réellement rendu — ``<div class="p2-deltas">``
        # n'existe dans le corps QUE quand ``deux_options`` est vrai (le sélecteur
        # CSS ``.p2-deltas {`` de la feuille de style ne matche pas cette chaîne).
        self.assertIn('<div class="p2-deltas">', html)
        self.assertIn('Spécifique à l&rsquo;option 1 — Sans batterie', html)
        self.assertIn('Spécifique à l&rsquo;option 2 — Avec batterie', html)


# ─── SCA27 — pied de page + liens du PDF résidentiel pilotés par CompanyProfile ─


class TestResidentialFooterBranding(SimpleTestCase):
    """SCA27 — le pied de page résidentiel et les liens fiches ne gravent plus
    « TAQINOR · contact@taqinor.com · +212 6 61 85 04 10 » ni taqinor.ma pour
    tout tenant : ils sont pilotés par ``data["entreprise"]`` (CompanyProfile).
    Fonctions pures : aucune DB, aucun rendu PDF."""

    # La chaîne EXACTE gravée aujourd'hui (référence byte-à-byte fondateur).
    FOUNDER_FOOTER = ('<b>TAQINOR</b> &nbsp;·&nbsp; contact@taqinor.com '
                      '&nbsp;·&nbsp; +212 6 61 85 04 10')

    def test_footer_default_is_exact_founder_string(self):
        """Sans ``entreprise`` (forme des données d'échantillon), le pied de page
        reproduit EXACTEMENT la chaîne fondateur historique."""
        from apps.ventes.quote_engine.residential import theme
        foot = theme.page_footer({'ref': 'DEV-1'})
        self.assertIn(self.FOUNDER_FOOTER, foot)

    def test_footer_founder_profile_is_char_for_char_identical(self):
        """Quand le profil porte les valeurs fondateur, la ligne est identique."""
        from apps.ventes.quote_engine.residential import theme
        data = {'ref': 'DEV-1', 'entreprise': {
            'nom': 'TAQINOR', 'email': 'contact@taqinor.com',
            'telephone': '+212 6 61 85 04 10'}}
        self.assertIn(self.FOUNDER_FOOTER, theme.page_footer(data))

    def test_footer_tenant_carries_its_own_coordinates(self):
        """Un tenant #2 : SES coordonnées, jamais celles du fondateur."""
        from apps.ventes.quote_engine.residential import theme
        data = {'ref': 'DEV-2', 'entreprise': {
            'nom': 'Helios SARL', 'email': 'hello@helios.ma',
            'telephone': '+212 5 22 00 00 00'}}
        foot = theme.page_footer(data)
        self.assertIn('<b>Helios SARL</b>', foot)
        self.assertIn('hello@helios.ma', foot)
        self.assertIn('+212 5 22 00 00 00', foot)
        self.assertNotIn('TAQINOR', foot)
        self.assertNotIn('contact@taqinor.com', foot)

    def test_footer_nom_only_keeps_founder_contact_line(self):
        """Nom fourni sans contact → contact fondateur préservé (comme DC1)."""
        from apps.ventes.quote_engine.residential import theme
        foot = theme.page_footer(
            {'ref': 'DEV-3', 'entreprise': {'nom': 'Helios SARL'}})
        self.assertIn('<b>Helios SARL</b>', foot)
        self.assertIn('contact@taqinor.com &nbsp;·&nbsp; +212 6 61 85 04 10',
                      foot)

    def test_footer_html_escapes_tenant_name(self):
        from apps.ventes.quote_engine.residential import theme
        foot = theme.page_footer(
            {'ref': 'DEV-4', 'entreprise': {'nom': 'A & B <Co>'}})
        self.assertIn('A &amp; B &lt;Co&gt;', foot)
        self.assertNotIn('<Co>', foot)

    def test_fiche_href_kept_for_taqinor_base(self):
        """Base taqinor.ma (fondateur) → lien fiche conservé (byte-identique)."""
        from apps.ventes.quote_engine.residential import theme
        self.assertEqual(
            theme.fiche_href('Panneau Jinko 710W', 'Jinko'),
            'https://taqinor.ma/produits/jinko-710')

    def test_fiche_href_omitted_for_non_taqinor_base(self):
        """Base d'un autre site → aucun lien fiche (omis) : le PDF d'un tenant
        ne pointe pas vers les fiches produits du fondateur."""
        from apps.ventes.quote_engine.residential import theme
        self.assertEqual(
            theme.fiche_href('Panneau Jinko 710W', 'Jinko',
                             produits_base='helios.ma/produits'),
            '')


@tag('pdf')
class TestResidentialFooterBrandingRendered(TestCase):
    """SCA27 (harnais rendu) — un devis résidentiel d'un tenant #2 porte SES
    coordonnées dans le pied de page des 3 pages, jamais celles du fondateur."""

    def test_tenant_footer_and_no_founder_datasheet_links(self):
        from weasyprint import HTML
        from apps.ventes.quote_engine.residential import renderer, render
        data = _residential_sample_data()
        # Identité d'un tenant #2 + base produits de SON site.
        data['entreprise'] = {
            'nom': 'Helios SARL', 'email': 'hello@helios.ma',
            'telephone': '+212 5 22 00 00 00'}
        data['links'] = {'produits': 'helios.ma/produits',
                         'realisations': 'helios.ma/realisations',
                         'avis': 'helios.ma/realisations',
                         'garanties': 'helios.ma/garanties',
                         'signer': 'helios.ma/signer'}
        data['site_url'] = 'helios.ma'
        d = renderer._augment(data)
        html = render.build_html(d)
        # Pied de page : coordonnées du tenant, aucune trace fondateur.
        self.assertIn('Helios SARL', html)
        self.assertIn('hello@helios.ma', html)
        self.assertNotIn('contact@taqinor.com', html)
        self.assertNotIn('<b>TAQINOR</b>', html)
        # Liens fiches produits du fondateur omis (base non-taqinor.ma).
        self.assertNotIn('taqinor.ma/produits/', html)
        # Le PDF se rend (octets valides).
        doc = HTML(string=html).render()
        self.assertEqual(len(doc.pages), 3)

    def test_founder_render_unchanged_when_no_entreprise(self):
        """Sans ``entreprise`` (rendu fondateur historique), le pied de page
        garde la chaîne exacte et les liens fiches taqinor.ma."""
        from apps.ventes.quote_engine.residential import renderer, render
        d = renderer._augment(_residential_sample_data())
        html = render.build_html(d)
        self.assertIn('<b>TAQINOR</b> &nbsp;·&nbsp; contact@taqinor.com '
                      '&nbsp;·&nbsp; +212 6 61 85 04 10', html)
        self.assertIn('taqinor.ma/produits/', html)


# ─── SCA27 — pied de page ÉTUDE (page 4) piloté par CompanyProfile ─────────────


@tag('pdf')
class TestEtudeFooterBranding(TestCase):
    """SCA27 (page étude) — le pied de page de la page d'étude
    d'autoconsommation (premium full + include_etude, industriel) ne grave plus
    ``contact@taqinor.com`` / ``www.taqinor.ma`` (le contact fondateur) pour un
    tenant qui n'a qu'un téléphone (email et site vides) : la ligne est
    reconstruite dès qu'un contact quelconque est fourni. Le rendu fondateur
    (email + tél + site) reste byte-identique."""

    FULL_LINES = [
        ('Onduleur réseau 10kW', '1', '11700'),
        ('Panneau mono 550W', '14', '1100'),
        ('Structures acier', '14', '375'),
        ('Installation', '1', '4000'),
    ]

    ETUDE_PARAMS = {
        'kwc': 9.94, 'production_annuelle': 12486, 'conso_annuelle': 120000,
        'taux_autoconso': 100, 'taux_couverture': 10.4,
        'economies_annuelles': 21851, 'payback': 3.0, 'prix_kwc': 6543,
        'prod_mensuelle': [1040] * 12, 'conso_mensuelle': [10000] * 12,
    }

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, self.FULL_LINES,
            reference='DEV-QE-ETUDE')
        self.devis.mode_installation = 'industriel'
        self.devis.etude_params = self.ETUDE_PARAMS
        self.devis.save()

    def _etude_page_html(self, entreprise):
        """Rend le PDF premium+étude en injectant ``entreprise`` et renvoie le
        fragment HTML de la page d'étude (à partir du titre « Étude
        d'autoconsommation ») — la seule page portant ``ENT_ETUDE_CONTACT``."""
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G

        data = build_quote_data(self.devis, {'include_etude': True})
        data['entreprise'] = entreprise
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_etude_footer_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        html = cap['html']
        marker = "Étude d'autoconsommation"
        idx = html.rfind(marker)
        self.assertNotEqual(idx, -1, "la page d'étude doit être rendue")
        return html[idx:]

    def test_tel_only_tenant_no_founder_contact_on_etude_page(self):
        """Tenant nom + téléphone, email et site VIDES → la page d'étude ne
        montre NI l'email NI le site du fondateur (elle porte SON téléphone)."""
        etude = self._etude_page_html({
            'nom': 'Helios SARL', 'email': '', 'site_web': '',
            'telephone': '+212 5 22 00 00 00'})
        self.assertNotIn('contact@taqinor.com', etude)
        self.assertNotIn('www.taqinor.ma', etude)
        # Repli gracieux : à défaut d'email/site, SON téléphone est affiché.
        self.assertIn('+212 5 22 00 00 00', etude)

    def test_founder_full_profile_etude_footer_byte_identical(self):
        """Profil fondateur (email + tél + site) → le pied de page d'étude
        reste EXACTEMENT la chaîne historique (byte-identique)."""
        etude = self._etude_page_html({
            'nom': 'TAQINOR', 'email': 'contact@taqinor.com',
            'telephone': '+212 6 61 85 04 10', 'site_web': 'www.taqinor.ma'})
        self.assertIn('contact@taqinor.com &nbsp;·&nbsp; www.taqinor.ma', etude)


# ─── SCA27 (complément) — site_url/produits_base du tenant câblés au moteur ────


class TestNormalizeSiteHost(SimpleTestCase):
    """SCA27 — forme d'affichage d'un site tenant (fonction pure, aucune DB)."""

    def test_strips_scheme_www_path_and_trailing_slash(self):
        from apps.ventes.quote_engine.builder import _normalize_site_host
        self.assertEqual(_normalize_site_host('https://www.helios.ma/'),
                         'helios.ma')
        self.assertEqual(_normalize_site_host('http://helios.ma'), 'helios.ma')
        self.assertEqual(_normalize_site_host('helios.ma/produits'), 'helios.ma')
        self.assertEqual(_normalize_site_host('  helios.ma  '), 'helios.ma')

    def test_empty_or_none_yields_empty(self):
        from apps.ventes.quote_engine.builder import _normalize_site_host
        self.assertEqual(_normalize_site_host(''), '')
        self.assertEqual(_normalize_site_host(None), '')
        self.assertEqual(_normalize_site_host('   '), '')


class TestBuilderWiresTenantSite(TestCase):
    """SCA27 (complément) — ``build_quote_data`` passe le site du tenant au
    renderer (ligne site + base des fiches), fermant la fuite ``taqinor.ma``.

    Trois cas : tenant AVEC site → SES clés ; tenant SANS site → aucune clé
    (défauts renderer = littéraux fondateur, byte-identique DC1) ; profil
    fondateur (site = taqinor.ma) → base taqinor conservée (fiches gardées)."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _residential_devis(self, reference):
        # Forme résidentielle « deux options » (panneaux + les deux onduleurs +
        # batterie) → le renderer résidentiel s'applique.
        return make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 550W', '14', '1100'),
            ('Onduleur réseau 10kW', '1', '11700'),
            ('Onduleur hybride 5kW', '1', '24000'),
            ('Batterie 5 kWh', '1', '14000'),
        ], reference=reference, etude_params=DEUX_OPTIONS)

    def _set_site(self, site):
        from apps.parametres.models import CompanyProfile
        p = CompanyProfile.get(company=self.company)
        p.site_web = site
        p.save()

    def test_tenant_with_site_gets_own_site_url_and_produits_base(self):
        from apps.ventes.quote_engine import build_quote_data
        self._set_site('https://www.helios.ma/')
        devis = self._residential_devis('DEV-SCA27-WITH')
        data = build_quote_data(devis)
        # Ligne site du pied de page = SON site (forme d'affichage normalisée).
        self.assertEqual(data['site_url'], 'helios.ma')
        # Base des liens fiches = SON site → theme.fiche_href omet taqinor.ma.
        self.assertEqual(data['links']['produits'], 'helios.ma/produits')
        self.assertEqual(data['links']['realisations'], 'helios.ma/realisations')
        # QX6 (fusion) — le lien de signature est tokenisé VERS LA VRAIE
        # proposition (ShareLink), sur la base DU TENANT : plus jamais l'ancien
        # « /signer/<ref> » 404, et aucun domaine fondateur ne fuit.
        self.assertIn('/proposition/', data['links']['signer'])
        self.assertTrue(data['links']['signer'].startswith('https://helios.ma/'))
        self.assertNotIn('/signer/', data['links']['signer'])
        # Aucune valeur ne fuit vers le site du fondateur.
        for v in [data['site_url']] + list(data['links'].values()):
            self.assertNotIn('taqinor', v.lower())

    def test_siteless_tenant_omits_keys_founder_defaults_preserved(self):
        """Tenant SANS site → aucune BASE tenant n'est posée : ``site_url`` est
        vide et ``links`` ne porte AUCUNE fiche tenant (produits/réalisations/
        garanties), donc le renderer garde ses littéraux historiques (taqinor.ma)
        — repli fondateur DC1.

        QX6 (fusion) : ``data`` porte quand même ``links`` avec l'UNIQUE lien de
        signature tokenisé (sur la base fondateur ``SITE_URL`` puisqu'il n'y a pas
        de site tenant) — c'est un vrai lien de proposition, jamais un 404, et il
        ne fait fuiter aucun AUTRE tenant."""
        from apps.ventes.quote_engine import build_quote_data
        self._set_site('')  # profil rempli MAIS sans site
        devis = self._residential_devis('DEV-SCA27-NOSITE')
        data = build_quote_data(devis)
        # Aucune base tenant : site_url vide → renderer applique taqinor.ma.
        self.assertEqual(data.get('site_url', ''), '')
        # links ne contient AUCUNE fiche tenant (seul le signer QX6 peut y être).
        _links = data.get('links') or {}
        for k in ('produits', 'realisations', 'garanties'):
            self.assertNotIn(k, _links)

    def test_founder_site_keeps_taqinor_base(self):
        """Profil fondateur (site = taqinor.ma) → base taqinor conservée : les
        fiches produits taqinor.ma restent liées (byte-identique fondateur)."""
        from apps.ventes.quote_engine import build_quote_data
        self._set_site('taqinor.ma')
        devis = self._residential_devis('DEV-SCA27-FOUNDER')
        data = build_quote_data(devis)
        self.assertEqual(data['site_url'], 'taqinor.ma')
        self.assertEqual(data['links']['produits'], 'taqinor.ma/produits')


@tag('pdf')
class TestBuilderTenantSiteRendered(TestCase):
    """SCA27 (complément, rendu réel) — un devis résidentiel d'un tenant #2 avec
    site rempli produit un PDF SANS aucune trace de ``taqinor.ma`` (ligne site du
    pied de page + liens fiches). Rendu WeasyPrint lourd → ``@tag('pdf')``."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def test_no_taqinor_anywhere_when_tenant_fills_site(self):
        from apps.ventes.quote_engine import build_quote_data
        from apps.ventes.quote_engine.residential import renderer, render
        from apps.parametres.models import CompanyProfile
        p = CompanyProfile.get(company=self.company)
        p.nom = 'Helios SARL'
        p.email = 'hello@helios.ma'
        p.telephone = '+212 5 22 00 00 00'
        p.site_web = 'helios.ma'
        p.save()
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 550W', '14', '1100'),
            ('Onduleur réseau 10kW', '1', '11700'),
            ('Onduleur hybride 5kW', '1', '24000'),
            ('Batterie 5 kWh', '1', '14000'),
        ], reference='DEV-SCA27-REND', etude_params=DEUX_OPTIONS)
        data = build_quote_data(devis)
        d = renderer._augment(data)
        html = render.build_html(d)
        # SON site partout, ZÉRO taqinor.ma.
        self.assertIn('helios.ma', html)
        self.assertNotIn('taqinor.ma', html)
        # Le pied de page porte SES coordonnées (identité DC1 déjà câblée).
        self.assertIn('hello@helios.ma', html)
        self.assertNotIn('contact@taqinor.com', html)


# ─── QJ13 — Loi 82-21 self-consumption-first savings + utility tranche tables ──


class TestSavingsMath(TestCase):
    """QJ13 — Pure-Python tests for the self-consumption-first savings model.

    These tests are DB-free (no Devis needed): they exercise pricing.py directly.
    """

    def test_self_consumption_first_no_surplus_valued(self):
        """Only self-consumed kWh are valued — surplus injection yields nothing."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        roi = calculate_savings_roi(
            5.0, 50000, 80000,
            tarif_kwh_override=1.75,
            autoconso_sans=0.60,
            autoconso_avec=0.85,
        )
        prod = roi["prod_kwh"]   # 5 kWc × 1240 × 0,86 (QRES54, pertes 14 %)
        # Option 1 savings = production × autoconso_sans × tarif
        self.assertEqual(roi["eco_s_ann"], round(prod * 0.60 * 1.75))
        # Option 2 savings = production × autoconso_avec × tarif
        self.assertEqual(roi["eco_a_ann"], round(prod * 0.85 * 1.75))
        # Savings < production × tarif (surplus not valued)
        self.assertLess(roi["eco_s_ann"], round(prod * 1.75))
        self.assertLess(roi["eco_a_ann"], round(prod * 1.75))

    def test_onee_tranche_weighted_price_increases_with_consumption(self):
        """Higher consumption → higher average ONEE tariff (progressive tranches)."""
        from apps.ventes.quote_engine.pricing import _weighted_kwh_price, ONEE_TRANCHES
        price_low = _weighted_kwh_price(80, ONEE_TRANCHES)    # within first tranche
        price_mid = _weighted_kwh_price(250, ONEE_TRANCHES)   # crosses first two
        price_high = _weighted_kwh_price(600, ONEE_TRANCHES)  # crosses all
        self.assertLessEqual(price_low, price_mid)
        self.assertLessEqual(price_mid, price_high)
        # First-tranche cap
        self.assertAlmostEqual(price_low, 0.9010, places=3)

    def test_utility_name_resolves_to_table(self):
        """Passing utility='onee' uses the ONEE tranche table, not the fallback."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi, _FALLBACK_KWH_PRICE
        roi_onee = calculate_savings_roi(
            5.0, 50000, 80000,
            utility="onee",
            conso_annuelle_kwh=3600,   # 300 kWh/mois
        )
        # Result is NOT the fallback flat price
        self.assertFalse(roi_onee["savings_estimated"])
        self.assertNotAlmostEqual(roi_onee["tarif_kwh"], _FALLBACK_KWH_PRICE, places=2)

    def test_utility_case_insensitive(self):
        """utility='ONEE' and utility='onee' produce identical results."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        r1 = calculate_savings_roi(5.0, 50000, 80000, utility="ONEE",
                                   conso_annuelle_kwh=3600)
        r2 = calculate_savings_roi(5.0, 50000, 80000, utility="onee",
                                   conso_annuelle_kwh=3600)
        self.assertEqual(r1["eco_s_ann"], r2["eco_s_ann"])

    def test_lydec_and_redal_tables_present(self):
        """Lydec and Redal tables are registered and return non-estimated results."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        for util in ("lydec", "redal"):
            roi = calculate_savings_roi(5.0, 50000, 80000, utility=util,
                                        conso_annuelle_kwh=3000)
            self.assertFalse(roi["savings_estimated"],
                             f"{util} should not trigger the fallback")

    def test_tranches_override_beats_utility_name(self):
        """Caller-supplied tranches_override takes precedence over utility name."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        custom = [[100, 2.00], [None, 3.00]]
        roi_custom = calculate_savings_roi(
            5.0, 50000, 80000,
            utility="onee",
            tranches_override=custom,
            conso_annuelle_kwh=1200,
        )
        roi_onee = calculate_savings_roi(
            5.0, 50000, 80000,
            utility="onee",
            conso_annuelle_kwh=1200,
        )
        # Custom has higher prices → custom savings > ONEE savings
        self.assertGreater(roi_custom["eco_s_ann"], roi_onee["eco_s_ann"])
        self.assertFalse(roi_custom["savings_estimated"])

    def test_explicit_tarif_kwh_override_beats_all(self):
        """tarif_kwh_override wins over utility name and tranches."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        roi = calculate_savings_roi(
            5.0, 50000, 80000,
            tarif_kwh_override=2.50,
            utility="onee",
            conso_annuelle_kwh=3600,
        )
        self.assertAlmostEqual(roi["tarif_kwh"], 2.50, places=4)
        self.assertFalse(roi["savings_estimated"])
        prod = roi["prod_kwh"]
        self.assertEqual(roi["eco_s_ann"], round(prod * 0.60 * 2.50))

    def test_roi_computed_from_totals(self):
        """QX39 — le payback n'est plus un ratio année-1 (total / éco annuelle)
        mais le croisement à zéro du cumul de cashflow 25 ans (dégradation
        panneau, escalade tarifaire, batterie/onduleur). On vérifie donc que
        ``roi_s``/``roi_a`` DÉLÈGUENT bien à ``compute_cashflow_payback`` avec
        le total de l'option et son économie annuelle — le vrai contrat."""
        from apps.ventes.quote_engine.pricing import (
            calculate_savings_roi, compute_cashflow_payback)
        roi = calculate_savings_roi(
            5.0, 50000, 80000,
            tarif_kwh_override=1.75,
        )
        expected_roi_s = compute_cashflow_payback(
            50000, roi["eco_s_ann"])["payback_years"]
        expected_roi_a = compute_cashflow_payback(
            80000, roi["eco_a_ann"], battery=True)["payback_years"]
        self.assertAlmostEqual(roi["roi_s"], expected_roi_s, places=1)
        self.assertAlmostEqual(roi["roi_a"], expected_roi_a, places=1)

    def test_monthly_seasonal_factors_sum_to_production(self):
        """The 12 monthly savings values sum to approximately the annual savings."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        roi = calculate_savings_roi(10.0, 100000, 150000, tarif_kwh_override=1.40)
        # Sum of monthly ≈ annual (within ±12 MAD due to rounding per month)
        self.assertAlmostEqual(sum(roi["eco_s_monthly"]), roi["eco_s_ann"], delta=12)
        self.assertAlmostEqual(sum(roi["eco_a_monthly"]), roi["eco_a_ann"], delta=12)
        self.assertEqual(len(roi["eco_s_monthly"]), 12)
        self.assertEqual(len(roi["eco_a_monthly"]), 12)

    def test_tranche_table_zero_consumption_returns_first_tranche_price(self):
        """With zero consumption, return the first-tranche price (conservative floor)."""
        from apps.ventes.quote_engine.pricing import _weighted_kwh_price, ONEE_TRANCHES
        price = _weighted_kwh_price(0, ONEE_TRANCHES)
        self.assertAlmostEqual(price, ONEE_TRANCHES[0][1], places=4)

    def test_tranche_table_large_consumption_approaches_last_tranche(self):
        """Very large consumption is dominated by the last (most expensive) band."""
        from apps.ventes.quote_engine.pricing import _weighted_kwh_price, ONEE_TRANCHES
        # 10 000 kWh/mois — the last tranche dominates the weighted average, so
        # the result must be close to (but not exceed) the last tranche price.
        price_huge = _weighted_kwh_price(10000, ONEE_TRANCHES)
        last_tranche_price = ONEE_TRANCHES[-1][1]
        self.assertGreater(price_huge, 1.35)
        self.assertLessEqual(price_huge, last_tranche_price)


class TestNoInventedNumberGuard(TestCase):
    """QJ13 — No-invented-number guard: when tariff/consumption data is absent,
    savings degrade honestly (flagged as estimate) rather than fabricating a
    precise number.
    """

    def test_no_tariff_data_flags_savings_as_estimated(self):
        """Without any tariff override or utility name, savings_estimated is True."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        roi = calculate_savings_roi(5.0, 50000, 80000)
        self.assertTrue(roi["savings_estimated"],
                        "savings must be flagged as an estimate when no tariff data")

    def test_no_tariff_data_uses_fallback_price_not_zero(self):
        """Fallback still produces a non-zero savings figure (honest estimate, not
        a blank/zero that would confuse the user)."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        roi = calculate_savings_roi(5.0, 50000, 80000)
        self.assertGreater(roi["eco_s_ann"], 0)
        self.assertGreater(roi["eco_a_ann"], 0)

    def test_tarif_kwh_override_zero_keeps_estimated_flag_false(self):
        """tarif_kwh_override=0 is treated as absent → fallback fires."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        roi_zero = calculate_savings_roi(5.0, 50000, 80000, tarif_kwh_override=0)
        self.assertTrue(roi_zero["savings_estimated"])

    def test_with_tariff_data_flag_is_false(self):
        """Providing a real tariff override disables the estimated flag."""
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        roi = calculate_savings_roi(5.0, 50000, 80000, tarif_kwh_override=1.40)
        self.assertFalse(roi["savings_estimated"])

    def test_builder_exposes_savings_estimated_key(self):
        """build_quote_data forwards savings_estimated into the data dict."""
        company = make_company()
        user = make_user(company)
        client_obj = make_client(company)
        devis = make_devis(company, user, client_obj, [
            ('Panneau mono 450W', '10', '1500'),
            ('Onduleur hybride', '1', '12000'),
        ], reference='DEV-QJ13-EST')
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(devis)
        # No etude_params → no tariff data → must be estimated
        self.assertIn("savings_estimated", data)
        self.assertTrue(data["savings_estimated"])
        self.assertIn("tarif_kwh", data)

    def test_builder_with_etude_params_tarif_kwh_not_estimated(self):
        """When etude_params carries tarif_kwh, savings are not estimated."""
        company = make_company()
        user = make_user(company)
        client_obj = make_client(company)
        devis = make_devis(company, user, client_obj, [
            ('Panneau mono 450W', '10', '1500'),
            ('Onduleur hybride', '1', '12000'),
        ], reference='DEV-QJ13-KWH')
        devis.etude_params = {"tarif_kwh": 1.50}
        devis.save(update_fields=["etude_params"])
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(devis)
        self.assertFalse(data["savings_estimated"])
        self.assertAlmostEqual(data["tarif_kwh"], 1.50, places=2)

    def test_builder_with_distributeur_onee_not_estimated(self):
        """etude_params distributeur='onee' → ONEE tranche table, not estimated."""
        company = make_company()
        user = make_user(company)
        client_obj = make_client(company)
        devis = make_devis(company, user, client_obj, [
            ('Panneau mono 450W', '10', '1500'),
            ('Onduleur réseau 8kW', '1', '14000'),
        ], reference='DEV-QJ13-ONEE')
        devis.etude_params = {"distributeur": "onee", "conso_annuelle": 18000}
        devis.save(update_fields=["etude_params"])
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(devis)
        self.assertFalse(data["savings_estimated"])

    def test_surplus_injection_not_in_savings(self):
        """Savings must NEVER exceed production × autoconso × price.

        The self-consumption ratio caps savings; there is no surplus-injection bonus.
        """
        from apps.ventes.quote_engine.pricing import (
            calculate_savings_roi, AUTOCONSO_AVEC)
        kwc = 10.0
        roi = calculate_savings_roi(kwc, 100000, 150000, tarif_kwh_override=1.75)
        prod = roi["prod_kwh"]
        # Savings must not exceed 100% autoconsumption (no injection bonus)
        max_possible = round(prod * 1.0 * 1.75)
        self.assertLessEqual(roi["eco_s_ann"], max_possible)
        self.assertLessEqual(roi["eco_a_ann"], max_possible)
        # And they should reflect only the self-consumed share
        self.assertEqual(roi["eco_a_ann"], round(prod * AUTOCONSO_AVEC * 1.75))


# ── PV11 : la fiche technique prime sur la regex pour le wattage panneau ──────
class TestPanelWattFromFicheTechnique(TestCase):
    """PV11 — ordre de résolution : fiche technique (Pmax réel) > regex
    désignation/nom > repli catalogue.

    RÈGLE #4 : le moteur ne fait que RENDRE. Les tests ci-dessous vérifient donc
    aussi que rien d'autre ne bouge — nombre de pages et totaux identiques avec
    et sans fiche.
    """

    LINES = [
        ('Panneau Canadien Solar 710W', '10', '1400'),
        ('Onduleur réseau 8kW', '1', '14000'),
    ]

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, reference):
        return make_devis(self.company, self.user, self.client_obj,
                          self.LINES, reference=reference)

    def _panneau(self, devis):
        return devis.lignes.get(
            designation='Panneau Canadien Solar 710W').produit

    def _fiche(self, produit, **kwargs):
        from apps.stock.models import FicheTechnique
        return FicheTechnique.objects.create(
            company=self.company, produit=produit, **kwargs)

    # ── Fiche présente : sa puissance EXACTE est utilisée ──
    def test_fiche_pmax_wins_over_designation_regex(self):
        from apps.ventes.quote_engine import build_quote_data
        from apps.stock.models import FicheTechnique
        devis = self._devis('DEV-PV11-FICHE')
        # La désignation dit 710 W, la fiche constructeur dit 705 Wc : c'est la
        # FICHE qui fait foi.
        self._fiche(self._panneau(devis),
                    type_fiche=FicheTechnique.TypeFiche.MODULE,
                    pmax_wc=Decimal('705.00'))
        data = build_quote_data(devis)
        self.assertEqual(data['watt_par_panneau'], 705)
        self.assertEqual(data['nb_panneaux'], 10)
        self.assertEqual(data['puissance_kwc'], 7.05)

    def test_fiche_pmax_used_when_designation_has_no_wattage(self):
        """Désignation illisible + fiche → la vraie puissance, pas le repli."""
        from apps.ventes.quote_engine import build_quote_data
        from apps.ventes.quote_engine.builder import _DEFAULT_WATT
        from apps.stock.models import FicheTechnique
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau photovoltaïque monocristallin', '12', '1400'),
            ('Onduleur réseau 8kW', '1', '14000'),
        ], reference='DEV-PV11-NOWATT')
        produit = devis.lignes.get(
            designation='Panneau photovoltaïque monocristallin').produit
        self._fiche(produit, type_fiche=FicheTechnique.TypeFiche.MODULE,
                    pmax_wc=Decimal('580.00'))
        data = build_quote_data(devis)
        self.assertEqual(data['watt_par_panneau'], 580)
        self.assertNotEqual(data['watt_par_panneau'], _DEFAULT_WATT)

    def test_legacy_fiche_without_type_still_counts(self):
        """Une fiche ANTÉRIEURE à PV5 (``type_fiche`` vide) porte déjà un Pmax
        de panneau : elle reste exploitée."""
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis('DEV-PV11-LEGACY')
        self._fiche(self._panneau(devis), pmax_wc=Decimal('665.00'))
        data = build_quote_data(devis)
        self.assertEqual(data['watt_par_panneau'], 665)

    # ── Fiche absente / inexploitable : chemin regex STRICTEMENT inchangé ──
    def test_without_fiche_regex_path_is_unchanged(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis('DEV-PV11-SANS')
        data = build_quote_data(devis)
        self.assertEqual(data['watt_par_panneau'], 710)  # lu dans « 710W »
        self.assertEqual(data['puissance_kwc'], 7.1)

    def test_fiche_without_pmax_falls_back_to_regex(self):
        from apps.ventes.quote_engine import build_quote_data
        from apps.stock.models import FicheTechnique
        devis = self._devis('DEV-PV11-NOPMAX')
        self._fiche(self._panneau(devis),
                    type_fiche=FicheTechnique.TypeFiche.MODULE,
                    voc_v=Decimal('48.00'))  # aucun pmax_wc
        data = build_quote_data(devis)
        self.assertEqual(data['watt_par_panneau'], 710)

    def test_non_module_fiche_is_ignored(self):
        """Un Pmax saisi par erreur sur une fiche onduleur/batterie ne dicte
        JAMAIS la puissance d'un panneau."""
        from apps.ventes.quote_engine import build_quote_data
        from apps.stock.models import FicheTechnique
        devis = self._devis('DEV-PV11-ONDFICHE')
        self._fiche(self._panneau(devis),
                    type_fiche=FicheTechnique.TypeFiche.ONDULEUR,
                    pmax_wc=Decimal('12000.00'))
        data = build_quote_data(devis)
        self.assertEqual(data['watt_par_panneau'], 710)

    def test_zero_pmax_falls_back_to_regex(self):
        from apps.ventes.quote_engine import build_quote_data
        from apps.stock.models import FicheTechnique
        devis = self._devis('DEV-PV11-ZERO')
        self._fiche(self._panneau(devis),
                    type_fiche=FicheTechnique.TypeFiche.MODULE,
                    pmax_wc=Decimal('0.00'))
        data = build_quote_data(devis)
        self.assertEqual(data['watt_par_panneau'], 710)

    # ── RÈGLE #4 : ni les totaux ni le nombre de pages ne bougent ──
    def test_totals_identical_with_and_without_fiche(self):
        from apps.ventes.quote_engine import build_quote_data
        from apps.stock.models import FicheTechnique
        sans = build_quote_data(self._devis('DEV-PV11-T1'))
        devis = self._devis('DEV-PV11-T2')
        self._fiche(self._panneau(devis),
                    type_fiche=FicheTechnique.TypeFiche.MODULE,
                    pmax_wc=Decimal('705.00'))
        avec = build_quote_data(devis)
        for key in ('totaux_sans', 'totaux_avec', 'totaux_all'):
            self.assertEqual(avec[key], sans[key], key)
        # Seule la puissance change — c'est bien le seul effet de PV11.
        self.assertNotEqual(avec['watt_par_panneau'],
                            sans['watt_par_panneau'])

    def test_page_counts_unchanged_with_fiche(self):
        from weasyprint import HTML
        from apps.stock.models import FicheTechnique
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G

        # MÊME fixture golden que les garde-fous de pagination existants.
        devis = make_devis(self.company, self.user, self.client_obj,
                           TestPdfFormats.FULL_LINES, reference='DEV-PV11-PDF')
        produit = devis.lignes.get(designation='Panneau mono 550W').produit
        FicheTechnique.objects.create(
            company=self.company, produit=produit,
            type_fiche=FicheTechnique.TypeFiche.MODULE,
            pmax_wc=Decimal('545.00'))

        def _render(pdf_options=None):
            data = build_quote_data(devis, pdf_options)
            cap = {}
            orig = G._render_pdf_weasyprint
            G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
            try:
                G.generate_premium_pdf(data, '/tmp/_pv11_test.pdf')
            finally:
                G._render_pdf_weasyprint = orig
            return data, HTML(string=cap['html']).render()

        data, doc = _render()
        self.assertEqual(len(doc.pages), 3)
        self.assertEqual(data['watt_par_panneau'], 545)
        _, doc_one = _render({'pdf_mode': 'onepage'})
        self.assertEqual(len(doc_one.pages), 1)


class TestLayoutV2NeBougePasLeDocument(TestCase):
    """PV24 — le layout v2 allume un chemin du builder : on le VERROUILLE.

    ``build_quote_data`` écrase ``puissance_kwc`` avec ``roof_layout['result']
    ['kwc']`` (builder.py, bloc « Q5 — Toiture 3D »). Ce chemin est resté
    THÉORIQUE tant que l'outil 3D sérialisait en v1 : le blob v1 ne porte
    AUCUN bloc ``result``, donc la condition n'était jamais vraie. Depuis PV13
    la sérialisation est en v2 et le bloc ``result`` est TOUJOURS là — ce
    chemin s'allume donc en production, sur tous les devis venus de la 3D.

    Règle #4 : la puissance affichée peut suivre le calepinage réel (c'est le
    but), mais le DOCUMENT lui-même ne bouge pas — mêmes pages, mêmes totaux.
    Les totaux naissent des LIGNES et d'elles seules ; aucun champ de layout
    n'a le droit de s'inviter dans la chaîne
    Sous-total HT → Remise → Total HT → TVA → Total TTC.
    """

    #: Clés de TOTAUX de ``build_quote_data`` — la chaîne monétaire complète.
    CLES_TOTAUX = ('total_sans', 'total_avec', 'total_sans_before',
                   'total_avec_before', 'totaux_sans', 'totaux_avec',
                   'totaux_all', 'discount_pct', 'per_line_tva')

    @staticmethod
    def _layout_v1():
        """Le blob HISTORIQUE : géométrie de zones, AUCUN bloc ``result``."""
        return {
            'version': 1,
            'pin': {'lat': 33.57, 'lng': -7.58},
            'outline': [[33.57, -7.58], [33.58, -7.58], [33.58, -7.57]],
            'billKwh': 900,
            'activeAreaId': 'z1',
            'zones': [{
                'id': 'z1', 'label': 'Pan Sud',
                'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
                'obstacles': [], 'roofType': 'pitched', 'pitchDeg': 30,
                'facingAzimuthDeg': 0, 'neededPanels': 14,
            }],
        }

    @classmethod
    def _layout_v2(cls):
        """Le MÊME toit, sérialisé en v2 (PV13) : + result/scenario/panelWatt."""
        layout = cls._layout_v1()
        layout.update({
            'version': 2,
            'result': {'panels': 14, 'kwc': 8.4, 'annualKwh': 13000,
                       'savings': 11000},
            'scenario': 'reseau',
            'panelWatt': 600,
            'battery': None,
            'source': 'devis',
            'devisId': 4242,
        })
        layout['zones'][0]['geometry'] = {
            'azimuthDeg': 0, 'tiltDeg': 30, 'family': 'portrait',
            'flush': True, 'kwc': 8.4, 'count': 14, 'origin': [0, 0],
            'panels': [],
        }
        return layout

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        # MÊME fixture golden que les garde-fous de pagination existants
        # (``TestPdfFormats``) : le nombre de pages testé ici est donc bien
        # celui du document de référence, pas celui d'un devis inventé.
        self.devis = make_devis(
            self.company, self.user, self.client_obj,
            TestPdfFormats.FULL_LINES, reference='DEV-PV24-001')

    def _data(self, layout, pdf_options=None, devis=None):
        from apps.ventes.quote_engine.builder import build_quote_data

        devis = devis or self.devis
        Devis.objects.filter(pk=devis.pk).update(roof_layout=layout)
        devis.refresh_from_db()
        return build_quote_data(devis, pdf_options)

    def _pages(self, layout, pdf_options=None):
        from weasyprint import HTML
        from apps.ventes.quote_engine import generate_devis_premium as G

        data = self._data(layout, pdf_options)
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_pv24_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return len(HTML(string=cap['html']).render().pages)

    def test_le_chemin_v2_s_allume_vraiment(self):
        """Sans cette divergence, tout le reste du module serait vide de sens."""
        v1 = self._data(self._layout_v1())
        v2 = self._data(self._layout_v2())
        self.assertEqual(v2['puissance_kwc'], 8.4)
        self.assertNotEqual(v1['puissance_kwc'], v2['puissance_kwc'])

    def test_les_totaux_sont_identiques_au_centime(self):
        v1 = self._data(self._layout_v1())
        v2 = self._data(self._layout_v2())
        for cle in self.CLES_TOTAUX:
            self.assertEqual(v1[cle], v2[cle],
                             'le layout v2 a bougé le total « %s »' % cle)

    def test_les_totaux_remises_sont_identiques(self):
        """La remise globale est le maillon fragile de la chaîne : verrouillé.

        Un devis REMISÉ fait vivre les trois maillons intermédiaires
        (``ht_brut`` → ``remise`` → ``ht_net``) que le devis golden, sans
        remise, laisse au repos.
        """
        remise = make_devis(
            self.company, self.user, self.client_obj,
            TestPdfFormats.FULL_LINES, remise_globale='12',
            reference='DEV-PV24-002')
        v1 = self._data(self._layout_v1(), devis=remise)
        v2 = self._data(self._layout_v2(), devis=remise)
        self.assertGreater(v1['totaux_all']['remise'], 0)
        for cle in self.CLES_TOTAUX:
            self.assertEqual(v1[cle], v2[cle],
                             'le layout v2 a bougé le total « %s »' % cle)

    def test_les_totaux_ignorent_aussi_un_layout_absent(self):
        """Aucun layout, v1, v2 : la chaîne monétaire est la MÊME partout."""
        sans = self._data(None)
        for layout in (self._layout_v1(), self._layout_v2()):
            avec = self._data(layout)
            for cle in self.CLES_TOTAUX:
                self.assertEqual(sans[cle], avec[cle],
                                 'le layout a bougé le total « %s »' % cle)

    def test_le_premium_reste_a_trois_pages(self):
        self.assertEqual(self._pages(self._layout_v1()), 3)
        self.assertEqual(self._pages(self._layout_v2()), 3)

    def test_la_une_page_reste_a_une_page(self):
        options = {'pdf_mode': 'onepage'}
        self.assertEqual(self._pages(self._layout_v1(), options), 1)
        self.assertEqual(self._pages(self._layout_v2(), options), 1)

    def test_le_layout_v2_n_ecrit_aucun_statut(self):
        """Règle #4 — le builder REND, il ne change jamais un statut."""
        self._data(self._layout_v2())
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'brouillon')
