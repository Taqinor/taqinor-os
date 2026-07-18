"""QK4 — Client-facing « Nos hypothèses » transparency block.

Surfaces on the premium PDF + proposal payload the assumptions behind the
savings: tarif MAD/kWh used, tranche source (ONEE/Lydec/Redal, flagged
approximate for private distributors), self-consumption-first (loi 82-21,
surplus injection OFF), production/degradation basis. Degrades cleanly.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qk4_hypotheses -v 2
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
        slug='test-qk4-co', defaults={'nom': 'Test QK4 Co'})
    return c


def make_user(company):
    return User.objects.create_user(
        username='qk4user', password='x', role_legacy='responsable',
        company=company)


def make_client(company):
    return Client.objects.create(
        company=company, nom='Alami', prenom='Rania',
        email='r@example.com', telephone='+212600000005')


LINES = [
    ('Onduleur réseau 8kW', '1', '14000'),
    ('Panneau mono 550W', '12', '1400'),
    ('Installation', '1', '4000'),
]


def make_devis(company, user, client, etude_params=None, reference='DEV-QK4-1'):
    devis = Devis.objects.create(
        company=company, reference=reference, client=client,
        statut='brouillon', taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'), created_by=user, etude_params=etude_params)
    for desig, qty, pu in LINES:
        produit = Produit.objects.create(
            company=company, nom=desig, sku=f'{reference[-6:]}-{desig[:10]}',
            prix_vente=Decimal(pu), prix_achat=Decimal('1'), quantite_stock=50)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=desig,
            quantite=Decimal(qty), prix_unitaire=Decimal(pu),
            remise=Decimal('0'))
    return devis


class TestHypothesesInData(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def test_hypotheses_present_and_autoconso_first(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj)
        data = build_quote_data(devis)
        h = data['hypotheses']
        self.assertTrue(h['autoconso_first'])
        joined = ' '.join(h['items'])
        self.assertIn('82-21', joined)
        self.assertIn('autoconsommation', joined.lower())
        # production basis present
        self.assertIsNotNone(h['productible_kwh_kwc'])

    def test_onee_source_labelled_public(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(
            self.company, self.user, self.client_obj,
            etude_params={'distributeur': 'onee', 'conso_annuelle': 6000},
            reference='DEV-QK4-ONEE')
        data = build_quote_data(devis)
        h = data['hypotheses']
        self.assertEqual(h['tranche_source'], 'ONEE')
        self.assertFalse(h['tranche_approximatif'])
        self.assertIn('ONEE', ' '.join(h['items']))

    def test_lydec_source_flagged_approximate(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(
            self.company, self.user, self.client_obj,
            etude_params={'distributeur': 'lydec', 'conso_annuelle': 6000},
            reference='DEV-QK4-LYD')
        data = build_quote_data(devis)
        h = data['hypotheses']
        self.assertEqual(h['tranche_source'], 'Lydec')
        self.assertTrue(h['tranche_approximatif'])
        self.assertIn('approximatif', ' '.join(h['items']).lower())

    def test_degrades_with_tarif_kwh_text(self):
        """No utility → QRES55 : le tarif interne n'est JAMAIS affiché en
        chiffres ; la ligne dit la méthode + le chemin vers l'exactitude
        (facture → recalcul par tranches). La valeur reste en métadonnée."""
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj,
                           reference='DEV-QK4-EST')
        data = build_quote_data(devis)
        h = data['hypotheses']
        self.assertIsNone(h['tranche_source'])
        self.assertIsNotNone(h['tarif_kwh_txt'])
        joined = ' '.join(h['items'])
        self.assertNotIn('1,75', joined)
        self.assertIn('par tranches', joined)


@tag('pdf')
class TestHypothesesRender(TestCase):
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
            G.generate_premium_pdf(data, '/tmp/_qk4.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return cap['html'], HTML(string=cap['html']).render()

    def test_block_on_premium_pdf_three_pages(self):
        devis = make_devis(
            self.company, self.user, self.client_obj,
            etude_params={'distributeur': 'onee', 'conso_annuelle': 6000},
            reference='DEV-QK4-PDF')
        # needs a hybrid to render the full residential 2-option layout? No —
        # a réseau-only quote renders as single-option full on the legacy engine.
        html, doc = self._render(devis)
        self.assertIn('Nos hypoth', html)
        self.assertIn('82-21', html)
        self.assertEqual(len(doc.pages), 3)

    def test_residential_renderer_shows_hypotheses(self):
        from weasyprint import HTML
        from apps.ventes.quote_engine.residential import renderer, render
        from apps.ventes.tests.test_quote_engine import _residential_sample_data
        data = _residential_sample_data()
        data['hypotheses'] = {
            'titre': 'Nos hypothèses',
            'items': ['Tarif électricité : barème ONEE par tranche (barème public)',
                      'Économies valorisées sur l\'autoconsommation (loi 82-21).'],
            'autoconso_first': True, 'tranche_source': 'ONEE',
            'tranche_approximatif': False, 'productible_kwh_kwc': 1600,
            'tarif_kwh': 1.2, 'tarif_kwh_txt': '1,20',
        }
        d = renderer._augment(data)
        html = render.build_html(d)
        doc = HTML(string=html).render()
        self.assertIn('Nos hypoth', html)
        self.assertEqual(len(doc.pages), 3)
