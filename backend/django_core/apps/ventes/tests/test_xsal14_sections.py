"""XSAL14 — Lignes de section et de note dans le devis.

``LigneDevis.type_ligne`` (produit [défaut] / section / note) + ``ordre``
(additifs). Les lignes section/note ne portent NI produit NI prix NI quantité :
rendues comme intertitres/notes (écran + PDF premium, ordonnées par ``ordre``),
JAMAIS comptées dans les totaux. Défaut 'produit' ⇒ un devis sans section est
octet-identique.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xsal14_sections -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, tag

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()


def make_company(slug='test-xsal14-co'):
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': 'Test XSAL14 Co'})
    return c


def make_client_obj(company):
    return Client.objects.create(
        company=company, nom='Sect', prenom='Client',
        email='sect@example.com', telephone='+212600000014')


def _produit(company, desig, sku, pu):
    return Produit.objects.create(
        company=company, nom=desig, sku=sku, prix_vente=Decimal(pu),
        prix_achat=Decimal('9'), quantite_stock=100)


class TestSectionNoteExcludedFromTotals(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='xsal14user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = make_client_obj(self.company)

    def _devis(self, reference='D-XSAL14-1'):
        return Devis.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user)

    def _produit_line(self, devis, desig, sku, pu, ordre=0):
        return LigneDevis.objects.create(
            devis=devis, produit=_produit(self.company, desig, sku, pu),
            designation=desig, quantite=Decimal('1'),
            prix_unitaire=Decimal(pu), remise=Decimal('0'),
            taux_tva=Decimal('20.00'), ordre=ordre)

    def _struct(self, devis, type_ligne, texte, ordre):
        return LigneDevis.objects.create(
            devis=devis, produit=None, designation=texte,
            quantite=None, prix_unitaire=None, remise=Decimal('0'),
            taux_tva=None, type_ligne=type_ligne, ordre=ordre)

    def test_section_and_note_excluded_from_totals(self):
        devis = self._devis()
        self._struct(devis, 'section', 'Champ PV', 0)
        self._produit_line(devis, 'Panneau 550W', 'X14-PAN', '1000', ordre=1)
        self._struct(devis, 'note', 'Pose sous 15 jours', 2)
        # Seule la ligne produit compte.
        self.assertEqual(Decimal(devis.total_ht), Decimal('1000'))
        self.assertEqual(Decimal(devis.total_ttc), Decimal('1200'))

    def test_section_line_total_ht_is_zero_no_crash(self):
        devis = self._devis('D-XSAL14-2')
        s = self._struct(devis, 'section', 'Onduleur & protection', 0)
        self.assertEqual(s.total_ht, Decimal('0'))
        self.assertFalse(s.compte_dans_totaux)
        self.assertFalse(s.est_ligne_produit)

    def test_product_only_devis_byte_identical(self):
        devis = self._devis('D-XSAL14-3')
        self._produit_line(devis, 'Onduleur 5kW', 'X14-OND', '2000')
        self.assertEqual(Decimal(devis.total_ht), Decimal('2000'))
        self.assertEqual(Decimal(devis.total_ttc), Decimal('2400'))
        self.assertTrue(all(li.est_ligne_produit for li in devis.lignes.all()))

    def test_ordering_by_ordre(self):
        devis = self._devis('D-XSAL14-4')
        self._produit_line(devis, 'B produit', 'X14-B', '100', ordre=2)
        self._struct(devis, 'section', 'A section', 1)
        self._struct(devis, 'note', 'C note', 3)
        ordered = [li.designation for li in devis.lignes.all()]
        self.assertEqual(ordered, ['A section', 'B produit', 'C note'])

    def test_selector_canonical_totaux_excludes_structure(self):
        from apps.ventes.selectors import _canonical_totaux
        devis = self._devis('D-XSAL14-5')
        self._struct(devis, 'section', 'Titre', 0)
        self._produit_line(devis, 'Produit', 'X14-P', '500', ordre=1)
        tot = _canonical_totaux(
            list(devis.lignes.all()), remise_globale_pct=Decimal('0'),
            fallback_taux=Decimal('20'))
        self.assertEqual(tot['ht_net'], Decimal('500.00'))
        self.assertEqual(tot['ttc'], Decimal('600.00'))

    def test_option_lines_excludes_structure(self):
        from apps.ventes.utils.options import option_lines
        devis = self._devis('D-XSAL14-6')
        self._struct(devis, 'section', 'Titre', 0)
        self._produit_line(devis, 'Produit', 'X14-OL', '500', ordre=1)
        lines = option_lines(devis)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].designation, 'Produit')


class TestBuilderStructureBlock(TestCase):
    def setUp(self):
        self.company = make_company('test-xsal14-b-co')
        self.user = User.objects.create_user(
            username='xsal14buser', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = make_client_obj(self.company)

    def _devis(self, reference='D-XSAL14-B1'):
        devis = Devis.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user)
        LigneDevis.objects.create(
            devis=devis, produit=_produit(
                self.company, 'Onduleur réseau 5kW', f'{reference}-O', '1000'),
            designation='Onduleur réseau 5kW', quantite=Decimal('1'),
            prix_unitaire=Decimal('1000'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'), ordre=1)
        return devis

    def test_structure_block_present_and_ordered(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis()
        LigneDevis.objects.create(
            devis=devis, produit=None, designation='Champ PV',
            quantite=None, prix_unitaire=None, remise=Decimal('0'),
            taux_tva=None, type_ligne='section', ordre=0)
        LigneDevis.objects.create(
            devis=devis, produit=None, designation='Note finale',
            quantite=None, prix_unitaire=None, remise=Decimal('0'),
            taux_tva=None, type_ligne='note', ordre=2)
        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
        self.assertIn('lignes_structure', data)
        struct = data['lignes_structure']
        self.assertEqual([s['texte'] for s in struct],
                         ['Champ PV', 'Note finale'])
        self.assertEqual(struct[0]['type'], 'section')
        # Les totaux ignorent la structure.
        self.assertEqual(data['totaux_all']['ht_brut'], 1000.0)

    def test_structure_block_absent_without(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis('D-XSAL14-B2')
        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
        self.assertNotIn('lignes_structure', data)


class TestSerializerValidation(SimpleTestCase):
    def test_section_neutralizes_produit_and_price(self):
        from apps.ventes.serializers import LigneDevisSerializer
        s = LigneDevisSerializer()
        attrs = s.validate({
            'type_ligne': 'section', 'designation': 'Champ PV',
            'quantite': Decimal('3'), 'prix_unitaire': Decimal('99'),
            'taux_tva': Decimal('20')})
        self.assertIsNone(attrs['produit'])
        self.assertIsNone(attrs['quantite'])
        self.assertIsNone(attrs['prix_unitaire'])

    def test_section_requires_designation(self):
        from rest_framework.exceptions import ValidationError
        from apps.ventes.serializers import LigneDevisSerializer
        s = LigneDevisSerializer()
        with self.assertRaises(ValidationError):
            s.validate({'type_ligne': 'note', 'designation': ''})

    def test_product_requires_produit(self):
        from rest_framework.exceptions import ValidationError
        from apps.ventes.serializers import LigneDevisSerializer
        s = LigneDevisSerializer()
        with self.assertRaises(ValidationError):
            s.validate({'type_ligne': 'produit', 'designation': 'X',
                        'produit': None})


@tag('pdf')  # rendu PDF premium (weasyprint) — palier release-verify
class TestOnepagePdfWithStructure(TestCase):
    """Un devis avec section + note rend TOUJOURS exactement 1 page en
    format une-page, et l'intitulé de section apparaît dans le HTML."""

    def setUp(self):
        self.company = make_company('test-xsal14-pdf-co')
        self.user = User.objects.create_user(
            username='xsal14pdf', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = make_client_obj(self.company)

    def _render(self, devis, pdf_options):
        from weasyprint import HTML
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G
        data = build_quote_data(devis, pdf_options)
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_xsal14_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return cap['html'], HTML(string=cap['html']).render()

    def test_onepage_with_section_note_still_one_page(self):
        devis = Devis.objects.create(
            company=self.company, reference='D-XSAL14-PDF1',
            client=self.client_obj, statut='brouillon',
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
            created_by=self.user)
        LigneDevis.objects.create(
            devis=devis, produit=None, designation='Champ PV',
            quantite=None, prix_unitaire=None, remise=Decimal('0'),
            taux_tva=None, type_ligne='section', ordre=0)
        LigneDevis.objects.create(
            devis=devis, produit=_produit(
                self.company, 'Onduleur réseau 5kW', 'X14PDF-O', '11700'),
            designation='Onduleur réseau 5kW', quantite=Decimal('1'),
            prix_unitaire=Decimal('11700'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'), ordre=1)
        LigneDevis.objects.create(
            devis=devis, produit=None, designation='Pose sous 15 jours',
            quantite=None, prix_unitaire=None, remise=Decimal('0'),
            taux_tva=None, type_ligne='note', ordre=2)
        html, doc = self._render(devis, {'pdf_mode': 'onepage'})
        self.assertEqual(
            len(doc.pages), 1,
            f'one-page devis with section/note must stay 1 page, got {len(doc.pages)}')
        self.assertIn('Champ PV', html)
        self.assertIn('Pose sous 15 jours', html)
