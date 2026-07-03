"""QF9 — Never emit Smart Meter / Clé Wifi on a non-Huawei quote.

Smart Meter + Wifi Dongle are Huawei-inverter accessories. The premium PDF must
omit them (and their Huawei datasheet/brand labelling) when the option's inverter
is not Huawei (e.g. a Deye quote), even if a stale line slipped in — while
keeping them for a genuine Huawei quote.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qf9_huawei_accessories -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, tag

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()


def make_company():
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(
        slug='test-qf9-co', defaults={'nom': 'Test QF9 Co'})
    return c


def make_user(company):
    return User.objects.create_user(
        username='qf9user', password='x', role_legacy='responsable',
        company=company)


def make_client(company):
    return Client.objects.create(
        company=company, nom='Tahiri', prenom='Salim',
        email='s@example.com', telephone='+212600000004')


def make_devis(company, user, client, lignes, reference, etude_params=None):
    devis = Devis.objects.create(
        company=company, reference=reference, client=client,
        statut='brouillon', taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'), created_by=user, etude_params=etude_params)
    for desig, qty, pu in lignes:
        produit = Produit.objects.create(
            company=company, nom=desig, sku=f'{reference[-6:]}-{desig[:10]}',
            prix_vente=Decimal(pu), prix_achat=Decimal('1'), quantite_stock=50)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=desig,
            quantite=Decimal(qty), prix_unitaire=Decimal(pu),
            remise=Decimal('0'))
    return devis


class TestQF9BuilderFilter(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def test_deye_hybrid_option_drops_accessories(self):
        """An « Avec batterie » Deye hybrid option must not carry Smart Meter /
        Wifi Dongle even if the lines include them."""
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Onduleur hybride Deye 5kW', '1', '24000'),
            ('Panneau mono 550W', '10', '1100'),
            ('Batterie Deyness 10 kWh', '1', '14000'),
            ('Smart Meter', '1', '1800'),
            ('Wifi Dongle', '1', '1200'),
        ], 'DEV-QF9-DEYE', etude_params={'scenario': 'Avec batterie'})
        data = build_quote_data(devis)
        avec = [it['designation'].lower() for it in data['avec_items']]
        self.assertFalse(any('smart meter' in d for d in avec))
        self.assertFalse(any('wifi' in d or 'dongle' in d for d in avec))

    def test_huawei_reseau_option_keeps_accessories(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Onduleur réseau Huawei 10kW', '1', '11700'),
            ('Panneau mono 550W', '10', '1100'),
            ('Smart Meter Huawei', '1', '1800'),
            ('Wifi Dongle Huawei', '1', '1200'),
        ], 'DEV-QF9-HUA', etude_params={'scenario': 'Sans batterie'})
        data = build_quote_data(devis)
        sans = [it['designation'].lower() for it in data['sans_items']]
        self.assertTrue(any('smart meter' in d for d in sans))
        self.assertTrue(any('wifi' in d or 'dongle' in d for d in sans))


@tag('pdf')
class TestQF9PdfRender(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _render(self, devis, pdf_options=None):
        from weasyprint import HTML
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G
        data = build_quote_data(devis, pdf_options)
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_qf9.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return cap['html'], HTML(string=cap['html']).render()

    def test_deye_pdf_omits_smart_meter_and_wifi(self):
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Onduleur hybride Deye 5kW', '1', '24000'),
            ('Panneau mono 550W', '10', '1100'),
            ('Batterie Deyness 10 kWh', '1', '14000'),
            ('Smart Meter', '1', '1800'),
            ('Wifi Dongle', '1', '1200'),
            ('Installation', '1', '4000'),
        ], 'DEV-QF9-DEYE-PDF', etude_params={'scenario': 'Avec batterie'})
        html, _ = self._render(devis)
        self.assertNotIn('Smart Meter', html)
        self.assertNotIn('Wifi Dongle', html)
        self.assertNotIn('smart-meter-huawei', html)
        self.assertNotIn('wifi-dongle-huawei', html)

    def test_huawei_pdf_keeps_smart_meter_and_wifi(self):
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Onduleur réseau Huawei 10kW', '1', '11700'),
            ('Panneau mono 550W', '10', '1100'),
            ('Smart Meter Huawei', '1', '1800'),
            ('Wifi Dongle Huawei', '1', '1200'),
            ('Installation', '1', '4000'),
        ], 'DEV-QF9-HUA-PDF', etude_params={'scenario': 'Sans batterie'})
        html, _ = self._render(devis)
        self.assertIn('Smart Meter', html)
        self.assertIn('Wifi Dongle', html)

    def test_guard_drops_stale_line_defense_in_depth(self):
        """Even if a stale Smart Meter line reaches the engine's data dict on a
        Deye option, the engine-level guard removes it."""
        from apps.ventes.quote_engine import generate_devis_premium as G
        items = [
            {'designation': 'Onduleur hybride Deye 5kW', 'marque': 'Deye',
             'quantite': 1, 'prix_unit_ht': 20000, 'prix_unit_ttc': 24000,
             'taux_tva': 20.0},
            {'designation': 'Smart Meter', 'marque': '', 'quantite': 1,
             'prix_unit_ht': 1500, 'prix_unit_ttc': 1800, 'taux_tva': 20.0},
        ]
        guarded = G._guard_huawei_accessories(items)
        desigs = [it['designation'] for it in guarded]
        self.assertNotIn('Smart Meter', desigs)
        self.assertIn('Onduleur hybride Deye 5kW', desigs)


class TestQF9FicheSlugGuard(TestCase):
    def test_non_huawei_meter_dongle_have_no_datasheet(self):
        from apps.ventes.quote_engine.residential import theme
        self.assertEqual(theme.fiche_slug('Smart Meter'), '')
        self.assertEqual(theme.fiche_slug('Wifi Dongle'), '')
        # Huawei-branded still map to their datasheet.
        self.assertEqual(theme.fiche_slug('Smart Meter Huawei'),
                         'smart-meter-huawei')
        self.assertEqual(theme.fiche_slug('Wifi Dongle Huawei'),
                         'wifi-dongle-huawei')
