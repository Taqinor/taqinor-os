"""QF3 — « Comment nous calculons vos économies » method block + worked example.

The block (method line + compact chiffré example) appears on the premium PDF and
in the /proposal payload, degrades cleanly when there's no bill data, and the
per-format page counts stay put (full=3, +etude=4, onepage=1 unaffected).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qf3_method_block -v 2
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
        slug='test-qf3-co', defaults={'nom': 'Test QF3 Co'})
    return c


def make_user(company):
    return User.objects.create_user(
        username='qf3user', password='x', role_legacy='responsable',
        company=company)


def make_client(company):
    return Client.objects.create(
        company=company, nom='Sabri', prenom='Amine',
        email='a@example.com', telephone='+212600000002')


def make_devis(company, user, client, lignes, etude_params=None,
               reference='DEV-QF3-0001'):
    devis = Devis.objects.create(
        company=company, reference=reference, client=client,
        statut='brouillon', taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'), created_by=user,
        etude_params=etude_params)
    for desig, qty, pu in lignes:
        produit = Produit.objects.create(
            company=company, nom=desig, sku=f'{reference[-6:]}-{desig[:10]}',
            prix_vente=Decimal(pu), prix_achat=Decimal('1'), quantite_stock=50)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=desig,
            quantite=Decimal(qty), prix_unitaire=Decimal(pu),
            remise=Decimal('0'))
    return devis


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


class TestSavingsMethodInData(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def test_method_block_with_real_bill_carries_worked_example(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(
            self.company, self.user, self.client_obj, FULL_LINES,
            etude_params={'distributeur': 'onee', 'conso_annuelle': 7200},
            reference='DEV-QF3-FACT')
        data = build_quote_data(devis)
        sm = data['savings_method']
        self.assertEqual(sm['model'], 'factures')
        self.assertIsNotNone(sm['facture_actuelle'])
        self.assertIn('Facture actuelle', sm['exemple'])
        self.assertIn('économie', sm['exemple'])
        self.assertIn('MAD/an', sm['exemple'])
        # per-tranche principle stated in one line
        self.assertIn('tranche', sm['ligne_methode'])

    def test_method_block_degrades_to_estimation_without_bill(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj,
                           FULL_LINES, reference='DEV-QF3-EST')
        data = build_quote_data(devis)
        sm = data['savings_method']
        self.assertEqual(sm['model'], 'estimation')
        self.assertIsNone(sm['exemple'])       # no fabricated numbers
        self.assertTrue(sm['approximatif'])
        self.assertIn('82-21', sm['ligne_methode'])


@tag('pdf')
class TestSavingsMethodRendersAndKeepsPageCounts(TestCase):
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
            G.generate_premium_pdf(data, '/tmp/_qf3_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return cap['html'], HTML(string=cap['html']).render()

    def test_block_appears_on_premium_pdf_and_full_still_three_pages(self):
        devis = make_devis(
            self.company, self.user, self.client_obj, FULL_LINES,
            etude_params={'distributeur': 'onee', 'conso_annuelle': 7200},
            reference='DEV-QF3-PDF')
        html, doc = self._render(devis)
        self.assertIn('Comment nous calculons vos', html)
        self.assertIn('Facture actuelle', html)
        self.assertEqual(len(doc.pages), 3)

    def test_full_still_three_pages_without_bill_data(self):
        devis = make_devis(self.company, self.user, self.client_obj,
                           FULL_LINES, reference='DEV-QF3-PDF2')
        html, doc = self._render(devis)
        self.assertIn('Comment nous calculons vos', html)
        self.assertEqual(len(doc.pages), 3)

    def test_onepage_still_one_page(self):
        devis = make_devis(self.company, self.user, self.client_obj,
                           FULL_LINES, reference='DEV-QF3-1P')
        _, doc = self._render(devis, {'pdf_mode': 'onepage'})
        self.assertEqual(len(doc.pages), 1)

    def test_etude_still_four_pages(self):
        devis = make_devis(self.company, self.user, self.client_obj,
                           FULL_LINES, reference='DEV-QF3-ET')
        devis.mode_installation = 'industriel'
        devis.etude_params = {
            'kwc': 9.94, 'production_annuelle': 12486, 'conso_annuelle': 120000,
            'taux_autoconso': 100, 'taux_couverture': 10.4,
            'economies_annuelles': 21851, 'payback': 3.0, 'prix_kwc': 6543,
            'prod_mensuelle': [1040] * 12, 'conso_mensuelle': [10000] * 12,
        }
        devis.save()
        _, doc = self._render(devis, {'include_etude': True})
        self.assertEqual(len(doc.pages), 4)

    def test_residential_renderer_shows_block_and_three_pages(self):
        from weasyprint import HTML
        from apps.ventes.quote_engine.residential import renderer, render
        from apps.ventes.tests.test_quote_engine import _residential_sample_data
        data = _residential_sample_data()
        data['savings_method'] = {
            'model': 'factures', 'ligne_methode': 'Chaque kWh au prix de sa tranche.',
            'exemple': 'Facture actuelle ≈ 9 000 DH/an → avec solaire ≈ 3 000 → économie ≈ 6 000',
            'approximatif': False,
        }
        d = renderer._augment(data)
        html = render.build_html(d)
        doc = HTML(string=html).render()
        self.assertIn('Comment nous calculons vos', html)
        self.assertEqual(len(doc.pages), 3)
