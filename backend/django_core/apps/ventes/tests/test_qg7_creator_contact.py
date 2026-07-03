"""QG7 — Print the quote CREATOR's name + phone in the contact block.

The PDF/proposal contact line came only from CompanyProfile (company_identity),
so it always showed the founder. Devis stores created_by (CustomUser has
first_name/last_name/phone_number). QG7 feeds the creator's name+phone into the
seller/contact block, with a fallback to the company contact when the user has
no phone.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qg7_creator_contact -v 2
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
        slug='test-qg7-co', defaults={'nom': 'Test QG7 Co'})
    return c


def make_client(company):
    return Client.objects.create(
        company=company, nom='Berrada', prenom='Salma',
        email='s@example.com', telephone='+212600000007')


def make_devis(company, user, client, lignes, reference,
               etude_params=None):
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


LINES = [
    ('Onduleur réseau 8kW', '1', '14000'),
    ('Panneau mono 550W', '12', '1400'),
    ('Installation', '1', '4000'),
]


class TestSellerInData(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)

    def test_creator_name_and_phone_in_seller(self):
        from apps.ventes.quote_engine import build_quote_data
        user = User.objects.create_user(
            username='qg7_full', password='x', role_legacy='responsable',
            company=self.company, first_name='Yassine', last_name='Cherkaoui',
            phone_number='0612345678')
        devis = make_devis(self.company, user, self.client_obj, LINES,
                           'DEV-QG7-1', etude_params={'scenario': 'Sans batterie'})
        data = build_quote_data(devis)
        self.assertEqual(data['seller']['nom'], 'Yassine Cherkaoui')
        self.assertEqual(data['seller']['telephone'], '0612345678')

    def test_creator_without_phone_falls_back_to_company(self):
        from apps.ventes.quote_engine import build_quote_data
        user = User.objects.create_user(
            username='qg7_nophone', password='x', role_legacy='responsable',
            company=self.company, first_name='Nadia', last_name='Sefrioui')
        devis = make_devis(self.company, user, self.client_obj, LINES,
                           'DEV-QG7-2', etude_params={'scenario': 'Sans batterie'})
        data = build_quote_data(devis)
        self.assertEqual(data['seller']['nom'], 'Nadia Sefrioui')
        # Phone falls back to the company contact (may be '' if no profile),
        # never crashes, and equals the entreprise telephone.
        self.assertEqual(data['seller']['telephone'],
                         data['entreprise'].get('telephone', '') or '')

    def test_no_creator_leaves_seller_empty(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = Devis.objects.create(
            company=self.company, reference='DEV-QG7-3', client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=None,
            etude_params={'scenario': 'Sans batterie'})
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur réseau 8kW', sku='QG7-3-OND',
            prix_vente=Decimal('14000'), prix_achat=Decimal('1'),
            quantite_stock=10)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Onduleur réseau 8kW',
            quantite=Decimal('1'), prix_unitaire=Decimal('14000'),
            remise=Decimal('0'))
        data = build_quote_data(devis)
        self.assertEqual(data['seller']['nom'], '')


@tag('pdf')
class TestSellerRender(TestCase):
    def setUp(self):
        self.company = make_company()
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
            G.generate_premium_pdf(data, '/tmp/_qg7.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return cap['html'], HTML(string=cap['html']).render()

    def test_creator_contact_on_legacy_pdf(self):
        user = User.objects.create_user(
            username='qg7_pdf', password='x', role_legacy='responsable',
            company=self.company, first_name='Omar', last_name='Filali',
            phone_number='0611223344')
        devis = make_devis(self.company, user, self.client_obj, LINES,
                           'DEV-QG7-PDF', etude_params={'scenario': 'Sans batterie'})
        html, doc = self._render(devis)
        self.assertIn('Votre conseiller', html)
        self.assertIn('Omar Filali', html)
        self.assertIn('0611223344', html)
        self.assertEqual(len(doc.pages), 3)

    def test_apply_seller_is_byte_noop_when_empty(self):
        from apps.ventes.quote_engine import generate_devis_premium as G
        with G._RENDER_LOCK:
            G._apply_entreprise({})
            before = G.ENT_CONTACT_LINE
            G._apply_seller({'nom': '', 'telephone': ''})
            self.assertEqual(G.ENT_CONTACT_LINE, before)
            G._apply_seller({'nom': 'Test Seller', 'telephone': '0600000000'})
            self.assertIn('Test Seller', G.ENT_CONTACT_LINE)
            self.assertIn('0600000000', G.ENT_CONTACT_LINE)
