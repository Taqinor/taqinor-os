"""QK3 — Render the computed financing block on the PDF (residential + agricole).

QJ12's compute_financing_block existed and proposal exposed data['financing'],
but no PDF page rendered it. QK3 renders it on the premium PDF and corrects the
agricole programme to CAM « Saquii Solaire » (+ FDA 30 %) — pompage is NOT
eligible to ISTIDAMA. Flagged « indicatif ». Per-format page counts hold.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qk3_financing_render -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, tag

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.quote_engine.builder import compute_financing_block

User = get_user_model()


def make_company():
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(
        slug='test-qk3-co', defaults={'nom': 'Test QK3 Co'})
    return c


def make_user(company):
    return User.objects.create_user(
        username='qk3user', password='x', role_legacy='responsable',
        company=company)


def make_client(company):
    return Client.objects.create(
        company=company, nom='Naji', prenom='Omar',
        email='o@example.com', telephone='+212600000006')


def make_devis(company, user, client, lignes, reference, mode='residentiel',
               etude_params=None):
    devis = Devis.objects.create(
        company=company, reference=reference, client=client,
        statut='brouillon', taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'), created_by=user,
        mode_installation=mode, etude_params=etude_params)
    for desig, qty, pu in lignes:
        produit = Produit.objects.create(
            company=company, nom=desig, sku=f'{reference[-6:]}-{desig[:10]}',
            prix_vente=Decimal(pu), prix_achat=Decimal('1'), quantite_stock=50)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=desig,
            quantite=Decimal(qty), prix_unitaire=Decimal(pu),
            remise=Decimal('0'))
    return devis


class TestAgricoleFinancingCorrection(TestCase):
    def test_agricole_is_saquii_solaire_not_istidama(self):
        r = compute_financing_block(180_000, 12_000, 15_000, 'agricole')
        self.assertEqual(r['credit']['programme_label'], 'Saquii Solaire')
        self.assertIn('Saquii Solaire', r['credit']['programme_nom'])
        self.assertIn('Saquii Solaire', r['guidance_text'])
        self.assertIn('FDA', r['guidance_text'])
        self.assertNotIn('ISTIDAMA', r['guidance_text'])

    def test_indicatif_flag_true(self):
        r = compute_financing_block(180_000, 12_000, 15_000, 'agricole')
        self.assertTrue(r['indicatif'])


@tag('pdf')
class TestFinancingOnPdf(TestCase):
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
            G.generate_premium_pdf(data, '/tmp/_qk3.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return cap['html'], HTML(string=cap['html']).render()

    def test_residential_legacy_pdf_shows_financing_three_pages(self):
        # réseau-only residential → single-option full (legacy engine, 3 pages)
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Onduleur réseau 8kW', '1', '14000'),
            ('Panneau mono 550W', '12', '1400'),
            ('Installation', '1', '4000'),
        ], 'DEV-QK3-RES', etude_params={'scenario': 'Sans batterie'})
        html, doc = self._render(devis)
        self.assertIn('Financement possible', html)
        self.assertEqual(len(doc.pages), 3)

    def test_residential_redesigned_renderer_shows_financing(self):
        from weasyprint import HTML
        from apps.ventes.quote_engine.residential import renderer, render
        from apps.ventes.tests.test_quote_engine import _residential_sample_data
        data = _residential_sample_data()
        data['financing'] = {
            'indicatif': True,
            'credit': {'mensualite': 1110.21, 'duree_mois': 120,
                       'taux_annuel_pct': 6.0,
                       'programme_nom': 'Crédit vert résidentiel',
                       'programme_label': None},
            'onee_comparison': {'show': False, 'message': '',
                                'eco_mensuelle_sans': 1000.0,
                                'eco_mensuelle_avec': 1250.0},
        }
        d = renderer._augment(data)
        html = render.build_html(d)
        doc = HTML(string=html).render()
        self.assertIn('Financement', html)
        self.assertEqual(len(doc.pages), 3)

    def test_agricole_pdf_shows_saquii_solaire_four_pages(self):
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Pompe immergée OSP 5.5CV', '1', '9000'),
            ('Variateur VEICHI SI23 5.5kW 380V', '1', '4500'),
            ('Panneau Canadien Solar 710W', '8', '1400'),
            ('Installation', '1', '4000'),
        ], 'DEV-QK3-AGR', mode='agricole',
            etude_params={'pompe_cv': '5.5', 'pompe_kw': 4.05, 'hmt_m': '60',
                          'debit_hmt_m3h': 20, 'heures_pompage': 7,
                          'm3_jour': 140, 'champ_kwc': 5.68})
        html, doc = self._render(devis)
        self.assertEqual(len(doc.pages), 4)
        self.assertIn('Saquii Solaire', html)
        self.assertNotIn('ISTIDAMA', html)
