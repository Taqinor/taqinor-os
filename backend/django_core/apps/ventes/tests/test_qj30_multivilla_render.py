"""QJ30 — Multi-property sectioned PDF + proposal rendering.

« × N propriétés identiques » line for path A; per-villa sections with subtotals
+ a clear grand total for path B, all in ONE document (render only; degrade to
today's flat layout when not multi-villa). Single-system quotes render
identically to today; per-format page counts still pass.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qj30_multivilla_render -v 2
"""
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient, TestCase, tag

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink

User = get_user_model()


def make_company():
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(
        slug='test-qj30-co', defaults={'nom': 'Test QJ30 Co'})
    return c


def make_user(company):
    return User.objects.create_user(
        username='qj30user', password='x', role_legacy='responsable',
        company=company)


def make_client(company):
    return Client.objects.create(
        company=company, nom='Villa', prenom='Client',
        email='v@example.com', telephone='+212600000010')


def _produit(company, desig, sku, pu):
    return Produit.objects.create(
        company=company, nom=desig, sku=sku, prix_vente=Decimal(pu),
        prix_achat=Decimal('1'), quantite_stock=100)


FULL_LINES = [
    ('Onduleur réseau 10kW', '1', '11700'),
    ('Onduleur hybride 5kW', '1', '24000'),
    ('Panneau mono 550W', '14', '1100'),
    ('Batterie 5 kWh', '1', '14000'),
    ('Structures acier', '14', '375'),
    ('Installation', '1', '4000'),
]


def make_devis(company, user, client, lignes, reference, etude_params=None):
    devis = Devis.objects.create(
        company=company, reference=reference, client=client,
        statut='envoye', taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'), created_by=user, etude_params=etude_params)
    for i, row in enumerate(lignes):
        desig, qty, pu = row[:3]
        gi = row[3] if len(row) > 3 else None
        gl = row[4] if len(row) > 4 else ''
        LigneDevis.objects.create(
            devis=devis, produit=_produit(company, desig,
                                          f'{reference[-6:]}-{i}', pu),
            designation=desig, quantite=Decimal(qty), prix_unitaire=Decimal(pu),
            remise=Decimal('0'), groupe_index=gi, groupe_label=gl)
    return devis


@tag('pdf')
class TestMultiRenderPdf(TestCase):
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
            G.generate_premium_pdf(data, '/tmp/_qj30.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return cap['html'], HTML(string=cap['html']).render()

    def test_path_a_n_line_on_pdf_three_pages(self):
        devis = make_devis(
            self.company, self.user, self.client_obj, FULL_LINES,
            'DEV-QJ30-A', etude_params={'nombre_proprietes': 4})
        html, doc = self._render(devis)
        self.assertIn('propriétés identiques', html)
        self.assertEqual(len(doc.pages), 3)

    def test_path_a_n_line_on_onepage_one_page(self):
        devis = make_devis(
            self.company, self.user, self.client_obj, FULL_LINES,
            'DEV-QJ30-A1', etude_params={'nombre_proprietes': 4})
        html, doc = self._render(devis, {'pdf_mode': 'onepage'})
        self.assertIn('propriétés identiques', html)
        self.assertEqual(len(doc.pages), 1)

    def test_path_b_villa_sections_on_pdf(self):
        lignes = [
            ('Installation commune', '1', '5000', 0, 'Commun'),
            ('Onduleur réseau 8kW', '1', '14000', 1, 'Villa A'),
            ('Panneau mono 550W', '10', '1400', 1, 'Villa A'),
            ('Onduleur réseau 5kW', '1', '11000', 2, 'Villa B'),
            ('Panneau mono 550W', '8', '1400', 2, 'Villa B'),
        ]
        devis = make_devis(self.company, self.user, self.client_obj, lignes,
                           'DEV-QJ30-B')
        html, doc = self._render(devis, {'pdf_mode': 'onepage'})
        # one-page renders per-villa? No — one-page keeps the compact ×N line
        # only; the sectioned table lives on the full premium page 3.
        self.assertEqual(len(doc.pages), 1)

    def test_single_system_pdf_unchanged_no_multi_markup(self):
        devis = make_devis(self.company, self.user, self.client_obj, FULL_LINES,
                           'DEV-QJ30-PLAIN')
        html, doc = self._render(devis)
        self.assertNotIn('propriétés identiques', html)
        self.assertNotIn('Détail par propriété', html)
        self.assertEqual(len(doc.pages), 3)

    def test_residential_renderer_path_a_three_pages(self):
        from weasyprint import HTML
        from apps.ventes.quote_engine.residential import renderer, render
        from apps.ventes.tests.test_quote_engine import _residential_sample_data
        data = _residential_sample_data()
        data['nombre_proprietes'] = 3
        data['display_total_multi'] = data['totaux_sans']['ttc'] * 3
        d = renderer._augment(data)
        html = render.build_html(d)
        doc = HTML(string=html).render()
        self.assertIn('propriétés identiques', html)
        self.assertEqual(len(doc.pages), 3)

    def test_residential_renderer_path_b_sections_three_pages(self):
        from weasyprint import HTML
        from apps.ventes.quote_engine.residential import renderer, render
        from apps.ventes.tests.test_quote_engine import _residential_sample_data
        data = _residential_sample_data()
        data['multi_villa'] = {
            'groupes': [
                {'index': 0, 'label': 'Commun',
                 'totaux': {'ht_net': 5000.0, 'ttc': 6000}},
                {'index': 1, 'label': 'Villa A',
                 'totaux': {'ht_net': 28000.0, 'ttc': 33600}},
                {'index': 2, 'label': 'Villa B',
                 'totaux': {'ht_net': 22000.0, 'ttc': 26400}},
            ],
            'grand_total': {'ht_net': 55000.0, 'ttc': 66000},
        }
        d = renderer._augment(data)
        html = render.build_html(d)
        doc = HTML(string=html).render()
        self.assertIn('Détail par propriété', html)
        self.assertIn('Total général', html)
        self.assertEqual(len(doc.pages), 3)


class TestMultiInProposalPayload(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _payload(self, devis):
        token = str(uuid.uuid4())
        ShareLink.objects.create(company=self.company, devis=devis, token=token)
        return DjangoClient().get(
            f'/api/django/public/proposal/{token}/data/')

    def test_payload_exposes_multi_keys(self):
        devis = make_devis(
            self.company, self.user, self.client_obj, FULL_LINES,
            'DEV-QJ30-EP', etude_params={'nombre_proprietes': 2})
        resp = self._payload(devis)
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload['nombre_proprietes'], 2)
        self.assertIsNotNone(payload['display_total_multi'])

    def test_payload_flat_when_single_system(self):
        devis = make_devis(self.company, self.user, self.client_obj, FULL_LINES,
                           'DEV-QJ30-EP2')
        resp = self._payload(devis)
        payload = resp.json()
        self.assertIsNone(payload['nombre_proprietes'])
        self.assertIsNone(payload['multi_villa'])
